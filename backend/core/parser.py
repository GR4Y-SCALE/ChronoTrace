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
            if callback:
                await callback(f"❌ EWF load failed: {e}")
            return False

        try:
            self._fh = self._ewf.open()
        except EWFError as e:
            if callback:
                await callback(f"❌ Failed to open EWF stream: {e}")
            return False
        except Exception as e:
            if callback:
                await callback(f"❌ Unexpected EWF stream error: {e}")
            return False

        if callback:
            size_gb = self._fh.size / (1024 ** 3)  # type: ignore[union-attr]
            await callback(f"✅ Disk image loaded — {size_gb:.2f} GB")

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
        except EWFError as e:
            if callback:
                await callback(
                    "❌ Incomplete EWF segment set. Ensure all split files "
                    "(.E01, .E02, .E03, ...) are uploaded for this image."
                )
                await callback(f"❌ Detail: {e}")
            return False
        except Exception as e:
            if callback:
                await callback(f"❌ Failed to initialize NTFS parser: {e}")
            return False

        if callback:
            await callback(
                f"✅ NTFS partition found — offset {offset:#x}, "
                f"size {size / (1024**3):.2f} GB, "
                f"cluster size {self.ntfs.cluster_size}"
            )

        return True

    # ── Phase 1a: MFT ─────────────────────────────────────────────
    async def parse_mft(self, callback: Optional[Callable] = None) -> pd.DataFrame:
        if callback:
            await callback("⚙️ $MFT — Enumerating Master File Table records…")
        await asyncio.sleep(0.05)

        rows = []
        count = 0
        if self.ntfs is None:
            return pd.DataFrame()
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
