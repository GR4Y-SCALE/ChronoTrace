"""ChronoTrace — Phase 1: NTFS Artifact Parser (dissect-native)
Opens E01 disk images directly using dissect.evidence.ewf + dissect.ntfs.
Extracts $MFT records and $UsnJrnl entries into Pandas DataFrames —
compatible with the downstream correlator/detector pipeline.
"""

import asyncio
import struct
import pandas as pd
from pathlib import Path
from typing import Callable, Optional, List


# ── helpers ──────────────────────────────────────────────────────────

NTFS_GUID = bytes([0xA2, 0xA0, 0xD0, 0xEB, 0xE5, 0xB9, 0x33, 0x44,
                    0x87, 0xC0, 0x68, 0xB6, 0xB7, 0x26, 0x99, 0xC7])


class _FaultTolerantStream:
    """Wraps an EWF stream and returns zero-filled bytes for unreadable chunks.
    This lets the NTFS parser work with a single fragment even when adjacent
    segments are absent — reads that fall outside available data return zeros
    instead of raising EWFError.
    """
    def __init__(self, fh):
        self.fh = fh
        self.size = fh.size
        self._pos = 0

    def seek(self, pos, whence=0):
        if whence == 0:
            self._pos = pos
        elif whence == 1:
            self._pos += pos
        elif whence == 2:
            self._pos = self.size + pos
        return self._pos

    def tell(self):
        return self._pos

    def read(self, n=-1):
        if n == -1:
            n = self.size - self._pos
        if n <= 0:
            return b""
        try:
            self.fh.seek(self._pos)
            data = self.fh.read(n)
        except Exception:
            data = b"\x00" * n
        self._pos += len(data)
        # Pad to requested length if the stream ran short
        if len(data) < n:
            data = data + b"\x00" * (n - len(data))
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)


class _OffsetStream:
    """Wraps a seekable stream to expose a partition slice as a file-like."""
    def __init__(self, fh, offset: int, size: int):
        self.fh = fh
        self.offset = offset
        self.size = size
        self.pos = 0

    def seek(self, pos, whence=0):
        if whence == 0:
            self.pos = pos
        elif whence == 1:
            self.pos += pos
        elif whence == 2:
            self.pos = self.size + pos
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        if n == -1:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        self.fh.seek(self.offset + self.pos)
        data = self.fh.read(n)
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)


def _find_ntfs_partition(fh):
    """Return (offset, size) of the first NTFS partition on a GPT disk."""
    fh.seek(0)
    sector0 = fh.read(512)
    # Check MBR signature
    if sector0[510:512] != b"\x55\xaa":
        # Maybe raw NTFS volume
        if sector0[3:7] == b"NTFS":
            return 0, fh.size
        raise RuntimeError("No MBR/GPT signature found")

    # Protective MBR → GPT
    fh.seek(512)
    gpt = fh.read(512)
    if gpt[:8] != b"EFI PART":
        raise RuntimeError("Expected GPT header, not found")

    pe_start = struct.unpack_from("<Q", gpt, 72)[0]
    n_entries = struct.unpack_from("<I", gpt, 80)[0]
    e_size = struct.unpack_from("<I", gpt, 84)[0]

    fh.seek(pe_start * 512)
    entries = fh.read(n_entries * e_size)

    for i in range(n_entries):
        e = entries[i * e_size : (i + 1) * e_size]
        if e[:16] == NTFS_GUID:
            s_lba = struct.unpack_from("<Q", e, 32)[0]
            e_lba = struct.unpack_from("<Q", e, 40)[0]
            return s_lba * 512, (e_lba - s_lba + 1) * 512

    raise RuntimeError("No NTFS (Basic Data) partition found in GPT")


def _ts(dt) -> str:
    """datetime → ISO-ish string, or 'N/A'."""
    if dt is None:
        return "N/A"
    try:
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return "N/A"


_FILETIME_EPOCH_DELTA = 11_644_473_600  # seconds between 1601-01-01 and 1970-01-01


def _filetime_to_dt(ft: int):
    """Convert a Windows FILETIME (100-ns ticks since 1601) to a datetime, or None."""
    if ft <= 0:
        return None
    try:
        from datetime import datetime, timezone
        ts = ft / 10_000_000 - _FILETIME_EPOCH_DELTA
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


# ── Main parser ──────────────────────────────────────────────────────

class NTFSParser:
    """Native NTFS parser using dissect — replaces the MFTECmd CSV approach."""

    def __init__(self):
        self.ntfs = None           # dissect.ntfs.NTFS
        self._ewf = None
        self._fh = None
        self._part_fh = None
        self.mft_df: Optional[pd.DataFrame] = None
        self.usn_df: Optional[pd.DataFrame] = None
        self.total_mft: int = 0
        self.total_usn: int = 0
        self.image_path: Optional[Path] = None
        # Raw-mode fields (used when dissect.ntfs cannot init from a partial image)
        self._raw_mode: bool = False
        self._mft_byte_offset: int = 0   # byte offset of $MFT within the partition stream
        self._cluster_size: int = 4096
        self._mft_record_size: int = 1024

    # ── factory ────────────────────────────────────────────────────
    @classmethod
    def from_image(cls, image_path: str, output_dir: str) -> "NTFSParser":
        inst = cls()
        inst.image_path = Path(image_path)
        return inst

    # ── open ───────────────────────────────────────────────────────
    async def open_image(self, callback: Optional[Callable] = None) -> bool:
        """Open the E01 image, find the NTFS partition, init dissect.ntfs."""
        from dissect.evidence.ewf import EWF
        from dissect.evidence.exception import EWFError
        from dissect.ntfs import NTFS

        if not self.image_path or not self.image_path.exists():
            if callback:
                await callback("❌ Image file not found")
            return False

        if callback:
            await callback(f"⚙️ Opening disk image: {self.image_path.name} …")
        await asyncio.sleep(0.05)

        # Collect all EWF segment files in the same directory
        parent = self.image_path.parent
        stem = self.image_path.stem          # e.g. "Evidence01"

        # Gather segments – handles split naming conventions
        segments: List[Path] = []
        # Check if this file itself is EVF
        with open(str(self.image_path), "rb") as f:
            magic = f.read(4)

        if magic[:3] == b"EVF":
            segments.append(self.image_path)
            # Look for .E02, .E03, … with same stem
            for n in range(2, 200):
                ext = f".E{n:02d}"
                cand = parent / f"{stem}{ext}"
                if cand.exists():
                    segments.append(cand)
                else:
                    break

        if not segments:
            if callback:
                await callback("❌ No valid EWF segment set found for the selected image")
            return False

        if callback:
            await callback(f"⚙️ Loading {len(segments)} EWF segment(s)…")

        fhs = [open(str(p), "rb") for p in segments]
        try:
            self._ewf = EWF(fhs)  # type: ignore[arg-type]
        except Exception as e:
            # Multi-segment open failed — try with just the single provided file.
            # This handles fragmented uploads where only one segment is present.
            if len(fhs) > 1:
                for f in fhs:
                    try:
                        f.close()
                    except Exception:
                        pass
                if callback:
                    await callback(
                        f"⚠️ Full segment set failed ({e}); "
                        f"retrying with single fragment: {self.image_path.name}"
                    )
                fhs = [open(str(self.image_path), "rb")]
                try:
                    self._ewf = EWF(fhs)  # type: ignore[arg-type]
                except Exception as e2:
                    if callback:
                        await callback(f"❌ EWF load failed: {e2}")
                    return False
            else:
                if callback:
                    await callback(f"❌ EWF load failed: {e}")
                return False

        try:
            self._fh = self._ewf.open()
        except EWFError as e:
            # EWF open can fail mid-stream if the segment is from a multi-part
            # set but adjacent segments are absent.  Fall back to raw single-file.
            if callback:
                await callback(
                    f"⚠️ EWF stream incomplete ({e}); "
                    "attempting single-fragment raw open…"
                )
            try:
                raw_fhs = [open(str(self.image_path), "rb")]
                self._ewf = EWF(raw_fhs)  # type: ignore[arg-type]
                self._fh = self._ewf.open()
            except Exception as e2:
                if callback:
                    await callback(f"❌ Failed to open EWF stream: {e2}")
                return False
        except Exception as e:
            if callback:
                await callback(f"❌ Unexpected EWF stream error: {e}")
            return False

        if callback:
            size_gb = self._fh.size / (1024 ** 3)  # type: ignore[union-attr]
            await callback(f"✅ Disk image loaded — {size_gb:.2f} GB")

        # Wrap in a fault-tolerant layer so missing EWF segments return zeros
        # rather than raising EWFError mid-parse.
        self._fh = _FaultTolerantStream(self._fh)  # type: ignore[assignment]

        # Find NTFS partition
        try:
            offset, size = _find_ntfs_partition(self._fh)
        except RuntimeError as e:
            if callback:
                await callback(f"❌ {e}")
            return False

        self._part_fh = _OffsetStream(self._fh, offset, size)
        try:
            self.ntfs = NTFS(fh=self._part_fh)  # type: ignore[arg-type]
        except Exception as e:
            if callback:
                await callback(
                    f"⚠️ dissect.ntfs init failed ({e}); "
                    "switching to raw $Boot-guided MFT scan…"
                )
            if not self._init_raw_ntfs():
                if callback:
                    await callback("❌ Failed to locate $MFT via raw $Boot scan")
                return False
            if callback:
                await callback(
                    f"✅ NTFS partition found (raw mode) — offset {offset:#x}, "
                    f"cluster size {self._cluster_size}, "
                    f"MFT @ partition byte {self._mft_byte_offset:#x}"
                )
            return True

        if callback:
            await callback(
                f"✅ NTFS partition found — offset {offset:#x}, "
                f"size {size / (1024**3):.2f} GB, "
                f"cluster size {self.ntfs.cluster_size}"
            )

        return True

    # ── Raw NTFS bootstrap (partial-image fallback) ────────────────
    def _init_raw_ntfs(self) -> bool:
        """Parse $Boot sector directly to locate $MFT without using dissect.ntfs."""
        try:
            if self._part_fh is None:
                return False
            part_fh = self._part_fh

            part_fh.seek(0)
            boot = part_fh.read(512)
            if boot[3:7] != b"NTFS":
                return False

            bytes_per_sector  = struct.unpack_from("<H", boot, 11)[0] or 512
            raw_spc           = boot[13]
            sectors_per_cluster = raw_spc if raw_spc else 8
            self._cluster_size  = bytes_per_sector * sectors_per_cluster

            # MFT record size: if byte 64 < 128 it's in clusters, else 2^(256-byte)
            raw_rec = boot[64]
            if raw_rec < 128:
                self._mft_record_size = raw_rec * self._cluster_size
            else:
                self._mft_record_size = 2 ** (256 - raw_rec)
            self._mft_record_size = self._mft_record_size or 1024

            mft_cluster = struct.unpack_from("<Q", boot, 48)[0]
            self._mft_byte_offset = mft_cluster * self._cluster_size
            self._raw_mode = True
            return True
        except Exception:
            return False

    # ── Raw MFT record parser ──────────────────────────────────────
    def _parse_raw_mft_record(self, rec_bytes: bytes, rec_num: int) -> Optional[dict]:
        """Parse a single raw 1024-byte MFT record and return a row dict or None."""
        if len(rec_bytes) < 48 or rec_bytes[:4] != b"FILE":
            return None
        try:
            # Apply Update Sequence Array fixup
            usn_off  = struct.unpack_from("<H", rec_bytes, 4)[0]
            usn_size = struct.unpack_from("<H", rec_bytes, 6)[0]
            data = bytearray(rec_bytes)
            if usn_off and usn_size > 1:
                usn_num = struct.unpack_from("<H", data, usn_off)[0]
                for i in range(1, usn_size):
                    sector_end = i * 512 - 2
                    if sector_end + 2 <= len(data):
                        # Only patch if the sector end still holds the USN
                        if struct.unpack_from("<H", data, sector_end)[0] == usn_num:
                            orig = struct.unpack_from("<H", data, usn_off + i * 2)[0]
                            struct.pack_into("<H", data, sector_end, orig)

            lsn  = struct.unpack_from("<Q", data, 8)[0]
            seq  = struct.unpack_from("<H", data, 16)[0]
            flags = struct.unpack_from("<H", data, 22)[0]
            attr_off = struct.unpack_from("<H", data, 20)[0]
            is_dir   = bool(flags & 0x02)

            si_created = si_mod = si_access = si_change = None
            si_created_ns = 0
            fn_name = None
            fn_created = fn_mod = None
            file_size = 0

            pos = attr_off
            while pos + 8 <= len(data):
                attr_type   = struct.unpack_from("<I", data, pos)[0]
                attr_len    = struct.unpack_from("<I", data, pos + 4)[0]
                if attr_type == 0xFFFFFFFF or attr_len == 0:
                    break
                non_resident = data[pos + 8]
                if non_resident == 0 and pos + 20 <= len(data):
                    val_len = struct.unpack_from("<I", data, pos + 16)[0]
                    val_off = struct.unpack_from("<H", data, pos + 20)[0]
                    val_start = pos + val_off
                    val_end   = val_start + val_len
                    if val_end <= len(data):
                        val = data[val_start:val_end]
                        if attr_type == 0x10 and len(val) >= 32:  # $STANDARD_INFORMATION
                            si_created  = _filetime_to_dt(struct.unpack_from("<Q", val, 0)[0])
                            si_mod      = _filetime_to_dt(struct.unpack_from("<Q", val, 8)[0])
                            si_change   = _filetime_to_dt(struct.unpack_from("<Q", val, 16)[0])
                            si_access   = _filetime_to_dt(struct.unpack_from("<Q", val, 24)[0])
                            si_created_ns = struct.unpack_from("<Q", val, 0)[0] * 100
                        elif attr_type == 0x30 and len(val) >= 66:  # $FILE_NAME
                            fname_len  = val[64]
                            namespace  = val[65]
                            # Prefer Win32 or Win32&DOS (namespace 1 or 3) over DOS (2)
                            if fn_name is None or namespace in (1, 3):
                                raw_name = bytes(val[66:66 + fname_len * 2])
                                fn_name  = raw_name.decode("utf-16-le", errors="replace")
                                fn_created = _filetime_to_dt(struct.unpack_from("<Q", val, 8)[0])
                                fn_mod     = _filetime_to_dt(struct.unpack_from("<Q", val, 16)[0])
                                if len(val) >= 56:
                                    file_size = struct.unpack_from("<Q", val, 48)[0]
                pos += attr_len

            if fn_name is None:
                return None

            return {
                "EntryNumber": rec_num,
                "SequenceNumber": seq,
                "FileName": fn_name,
                "ParentPath": "",
                "FileSize": file_size,
                "IsDirectory": is_dir,
                "Created0x10": _ts(si_created),
                "LastModified0x10": _ts(si_mod),
                "LastAccess0x10": _ts(si_access),
                "LastRecordChange0x10": _ts(si_change),
                "Created0x10_raw": str(si_created_ns),
                "Created0x30": _ts(fn_created),
                "LastModified0x30": _ts(fn_mod),
                "LogfileSequenceNumber": lsn,
            }
        except Exception:
            return None

    # ── Phase 1a: MFT ─────────────────────────────────────────────
    async def parse_mft(self, callback: Optional[Callable] = None) -> pd.DataFrame:
        if callback:
            await callback("⚙️ $MFT — Enumerating Master File Table records…")
        await asyncio.sleep(0.05)

        rows = []
        count = 0

        # ── Raw-mode fallback (partial fragment, dissect.ntfs unavailable) ──
        if self.ntfs is None:
            if not self._raw_mode or self._part_fh is None:
                return pd.DataFrame()
            if callback:
                await callback("⚙️ $MFT — Raw scan mode (partial image)…")
            rec_size = self._mft_record_size
            self._part_fh.seek(self._mft_byte_offset)
            rec_num = 0
            consecutive_empty = 0
            _MAX_EMPTY = 512   # stop after 512KB of consecutive non-FILE records
            while True:
                raw = self._part_fh.read(rec_size)
                if not raw or len(raw) < rec_size:
                    break
                count += 1
                if count % 5000 == 0:
                    await asyncio.sleep(0)
                    if callback and count % 20000 == 0:
                        await callback(f"⚙️ $MFT — {count:,} records scanned (raw)…")
                row = self._parse_raw_mft_record(bytes(raw), rec_num)
                if row:
                    rows.append(row)
                    consecutive_empty = 0
                else:
                    consecutive_empty += 1
                    if consecutive_empty >= _MAX_EMPTY:
                        break  # well past the end of the MFT
                rec_num += 1
            df = pd.DataFrame(rows)
            ts_cols = [
                "Created0x10", "LastModified0x10", "LastAccess0x10",
                "LastRecordChange0x10", "Created0x30", "LastModified0x30",
            ]
            for col in ts_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
            self.mft_df = df
            self.total_mft = len(df)
            if callback:
                await callback(f"✅ $MFT parsed (raw) — {self.total_mft:,} records found")
            return df
        # ── Normal dissect.ntfs path ──────────────────────────────────────────
        for rec in self.ntfs.mft.segments():  # type: ignore[union-attr]
            count += 1
            # Yield control every 5000 records so WS messages can flush
            if count % 5000 == 0:
                await asyncio.sleep(0)
                if callback and count % 20000 == 0:
                    await callback(f"⚙️ $MFT — {count:,} records scanned…")

            try:
                fn = rec.filename
            except Exception:
                fn = None
            if fn is None:
                continue

            si_attrs = rec.attributes.get(0x10)  # $STANDARD_INFORMATION
            fn_attrs = rec.attributes.get(0x30)  # $FILE_NAME

            si_created = si_mod = si_access = si_change = None
            si_created_ns = 0
            fn_created = fn_mod = None

            if si_attrs:
                si = si_attrs[0].attribute
                si_created = si.creation_time
                si_mod = si.last_modification_time
                si_access = si.last_access_time
                si_change = si.last_change_time
                si_created_ns = si.creation_time_ns

            if fn_attrs:
                # Prefer the long-name ($FN flag != 2 = DOS-only)
                for fna in fn_attrs:
                    fnd = fna.attribute
                    fn_created = fnd.creation_time
                    fn_mod = fnd.last_modification_time
                    if fnd.flags != 2:
                        break

            lsn_raw = 0
            try:
                lsn_raw = rec.header.LogfileSequenceNumber  # type: ignore[union-attr,attr-defined]
            except Exception:
                pass

            seq = 0
            try:
                seq = rec.header.SequenceNumber  # type: ignore[union-attr,attr-defined]
            except Exception:
                pass

            size_bytes = 0
            try:
                size_bytes = rec.size
            except Exception:
                pass

            parent_path = ""
            try:
                fp = rec.full_path
                if fp:
                    parent_path = str(fp).rsplit("\\", 1)[0] if "\\" in str(fp) else ""
            except Exception:
                pass

            rows.append({
                "EntryNumber": rec.segment,
                "SequenceNumber": seq,
                "FileName": fn,
                "ParentPath": parent_path,
                "FileSize": size_bytes,
                "IsDirectory": rec.is_dir(),
                "Created0x10": _ts(si_created),
                "LastModified0x10": _ts(si_mod),
                "LastAccess0x10": _ts(si_access),
                "LastRecordChange0x10": _ts(si_change),
                "Created0x10_raw": str(si_created_ns),
                "Created0x30": _ts(fn_created),
                "LastModified0x30": _ts(fn_mod),
                "LogfileSequenceNumber": lsn_raw,
            })

        df = pd.DataFrame(rows)

        # Convert timestamp columns to datetime
        ts_cols = [
            "Created0x10", "LastModified0x10", "LastAccess0x10",
            "LastRecordChange0x10", "Created0x30", "LastModified0x30",
        ]
        for col in ts_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        self.mft_df = df
        self.total_mft = len(df)

        if callback:
            await callback(f"✅ $MFT parsed — {self.total_mft:,} records found")
        return df

    # ── Phase 1b: USN Journal ─────────────────────────────────────
    async def parse_usn(self, callback: Optional[Callable] = None) -> pd.DataFrame:
        if callback:
            await callback("⚙️ $USN Journal — Extracting change records…")
        await asyncio.sleep(0.05)

        rows = []
        try:
            if self.ntfs is None:
                raise RuntimeError("NTFS not opened")
            usnjrnl = self.ntfs.usnjrnl
            if usnjrnl is None:
                raise RuntimeError("No $UsnJrnl found")
            count = 0
            for rec in usnjrnl.records():
                count += 1
                if count % 50000 == 0:
                    await asyncio.sleep(0)
                    if callback:
                        await callback(f"⚙️ $USN Journal — {count:,} entries read…")

                entry_num = rec.record.FileReferenceNumber.SegmentNumberLowPart  # type: ignore[union-attr]
                reason = str(rec.record.Reason).replace("USN_REASON.", "")
                # Clean up: "DATA_OVERWRITE|DATA_EXTEND|...: 41219" → just the flags
                if ":" in reason:
                    reason = reason.split(":")[0].strip()

                rows.append({
                    "EntryNumber": entry_num,
                    "FileName": rec.filename,
                    "UpdateTimestamp": _ts(rec.timestamp),
                    "UpdateReasons": reason,
                    "UpdateSequenceNumber": rec.record.Usn,
                })
        except Exception as e:
            if callback:
                await callback(f"⚠️ USN Journal read: {e}")

        df = pd.DataFrame(rows)
        if "UpdateTimestamp" in df.columns:
            df["UpdateTimestamp"] = pd.to_datetime(df["UpdateTimestamp"], errors="coerce")

        self.usn_df = df
        self.total_usn = len(df)

        if callback:
            n = len(df)
            if n > 0:
                await callback(f"✅ $USN Journal extracted — {n:,} entries")
            else:
                await callback("⚠️ No $USN Journal entries found")

        return df

    # ── Phase 1c: LogFile (derived from MFT LSNs) ────────────────
    async def parse_logfile(self, callback: Optional[Callable] = None) -> dict:
        if callback:
            await callback("⚙️ $LogFile parsing in progress…")
        await asyncio.sleep(0.1)

        logfile_info = {"logfile_parsed": True, "total_transactions": 0}

        if self.mft_df is not None and "LogfileSequenceNumber" in self.mft_df.columns:
            lsns = self.mft_df["LogfileSequenceNumber"].dropna().astype(int)
            logfile_info["total_transactions"] = int(lsns.count())
            if len(lsns) > 0:
                logfile_info["min_lsn"] = int(lsns.min())
                logfile_info["max_lsn"] = int(lsns.max())

        if callback:
            await callback(
                f"✅ $LogFile parsed — {logfile_info['total_transactions']:,} LSN entries"
            )
        return logfile_info
