"""
ChronoTrace — Live MFT Reader
On-demand reader of $MFT records from a live NTFS volume.
When the USN monitor flags a suspicious file (by MFT entry number),
this module reads the live $SI and $FN attributes to compare timestamps.

Uses FSCTL_GET_NTFS_FILE_RECORD via DeviceIoControl.
Requires Administrator / SeBackupPrivilege.
"""

import ctypes
import ctypes.wintypes as wt
import struct
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger("chronotrace.live_mft")

# ── Win32 constants ──────────────────────────────────────────────────
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FSCTL_GET_NTFS_FILE_RECORD = 0x00090068

# MFT attribute type codes
ATTR_STANDARD_INFORMATION = 0x10
ATTR_FILE_NAME = 0x30


def _filetime_to_iso(ft_bytes: bytes) -> str:
    """Convert an 8-byte FILETIME to ISO string."""
    ft = struct.unpack("<Q", ft_bytes)[0]
    if ft <= 0:
        return "N/A"
    EPOCH_DIFF = 116444736000000000
    try:
        ts = (ft - EPOCH_DIFF) / 10_000_000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except (OSError, ValueError, OverflowError):
        return "N/A"


def _filetime_to_datetime(ft_bytes: bytes) -> Optional[datetime]:
    """Convert an 8-byte FILETIME to datetime object."""
    ft = struct.unpack("<Q", ft_bytes)[0]
    if ft <= 0:
        return None
    EPOCH_DIFF = 116444736000000000
    try:
        ts = (ft - EPOCH_DIFF) / 10_000_000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OSError, ValueError, OverflowError):
        return None


class LiveMFTReader:
    """
    Reads individual MFT records from a live NTFS volume.
    Extracts $STANDARD_INFORMATION and $FILE_NAME timestamps.
    """

    def __init__(self, drive_letter: str = "C"):
        self.drive = drive_letter.upper().rstrip(":\\")
        self._handle = None

    def open(self):
        """Open a handle to the volume."""
        path = f"\\\\.\\{self.drive}:"
        self._handle = ctypes.windll.kernel32.CreateFileW(
            path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if self._handle in (-1, 0xFFFFFFFF):
            err = ctypes.get_last_error() or ctypes.windll.kernel32.GetLastError()
            raise PermissionError(
                f"Cannot open volume {self.drive}: — error {err}. Run as Administrator."
            )

    def close(self):
        if self._handle and self._handle not in (-1, 0xFFFFFFFF):
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()

    def read_mft_record(self, entry_number: int) -> Optional[Dict[str, Any]]:
        """
        Read a single MFT record by entry number and parse $SI + $FN attributes.
        Returns a dict compatible with the existing correlator/detector pipeline.
        """
        if not self._handle:
            raise RuntimeError("Volume not opened. Call open() first.")

        try:
            raw = self._fetch_raw_record(entry_number)
        except OSError as e:
            logger.warning("Failed to read MFT entry %d: %s", entry_number, e)
            return None

        if raw is None:
            return None

        return self._parse_record(raw, entry_number)

    def _fetch_raw_record(self, entry_number: int) -> Optional[bytes]:
        """Use FSCTL_GET_NTFS_FILE_RECORD to retrieve the raw MFT record bytes."""
        # NTFS_FILE_RECORD_INPUT_BUFFER: 8 bytes (LONGLONG FileReferenceNumber)
        in_buf = struct.pack("<q", entry_number)

        # Output: NTFS_FILE_RECORD_OUTPUT_BUFFER
        # First 8 bytes: FileReferenceNumber, then the raw record data
        out_size = 4096 + 8  # typical MFT record is 1024 bytes, allow extra
        out_buf = ctypes.create_string_buffer(out_size)
        bytes_returned = wt.DWORD(0)

        ok = ctypes.windll.kernel32.DeviceIoControl(
            self._handle,
            FSCTL_GET_NTFS_FILE_RECORD,
            in_buf, len(in_buf),
            out_buf, out_size,
            ctypes.byref(bytes_returned),
            None,
        )
        if not ok:
            err = ctypes.get_last_error() or ctypes.windll.kernel32.GetLastError()
            raise OSError(f"FSCTL_GET_NTFS_FILE_RECORD failed for entry {entry_number} — error {err}")

        data = out_buf.raw[: bytes_returned.value]
        if len(data) < 16:
            return None

        # Skip the 8-byte FileReferenceNumber prefix to get the raw MFT record
        # Actually the output is: LONGLONG FileReferenceNumber + ULONG FileRecordLength + UCHAR FileRecordBuffer[]
        _ref_num = struct.unpack_from("<q", data, 0)[0]
        rec_len = struct.unpack_from("<I", data, 8)[0]
        raw_record = data[12: 12 + rec_len]

        # Validate MFT record signature "FILE"
        if len(raw_record) < 4 or raw_record[:4] != b"FILE":
            return None

        return raw_record

    def _parse_record(self, raw: bytes, entry_number: int) -> Optional[Dict[str, Any]]:
        """Parse the raw MFT record bytes to extract $SI and $FN timestamps."""
        if len(raw) < 56:
            return None

        # MFT record header
        # Offset 20: first attribute offset (2 bytes)
        # Offset 22: flags (2 bytes) — 0x01 = in use, 0x02 = directory
        first_attr_offset = struct.unpack_from("<H", raw, 20)[0]
        flags = struct.unpack_from("<H", raw, 22)[0]
        sequence_number = struct.unpack_from("<H", raw, 16)[0]
        lsn = struct.unpack_from("<Q", raw, 8)[0]

        if not (flags & 0x01):
            # Record not in use
            return None

        si_data = None
        fn_data = None
        fn_filename = ""

        # Walk attribute list
        offset = first_attr_offset
        while offset + 16 <= len(raw):
            attr_type = struct.unpack_from("<I", raw, offset)[0]
            if attr_type == 0xFFFFFFFF:
                break  # end marker
            attr_len = struct.unpack_from("<I", raw, offset + 4)[0]
            if attr_len == 0 or attr_len > len(raw) - offset:
                break

            non_resident = raw[offset + 8] if offset + 9 <= len(raw) else 0

            if attr_type == ATTR_STANDARD_INFORMATION and non_resident == 0:
                si_data = self._parse_si(raw, offset)

            elif attr_type == ATTR_FILE_NAME and non_resident == 0:
                parsed = self._parse_fn(raw, offset)
                if parsed:
                    # Prefer the Win32 name (namespace 1 or 3) over DOS name (namespace 2)
                    ns = parsed.get("namespace", 0)
                    if ns != 2 or fn_data is None:  # not DOS-only, or first FN we found
                        fn_data = parsed
                        fn_filename = parsed.get("filename", "")

            offset += attr_len

        if si_data is None:
            return None

        result = {
            "entry_number": entry_number,
            "sequence_number": sequence_number,
            "lsn": lsn,
            "flags": flags,
            "is_directory": bool(flags & 0x02),
            "filename": fn_filename,
            "timestamps": {
                "si_created":  si_data.get("created", "N/A"),
                "si_modified": si_data.get("modified", "N/A"),
                "si_accessed": si_data.get("accessed", "N/A"),
                "si_mft_modified": si_data.get("mft_modified", "N/A"),
                "fn_created":  fn_data.get("created", "N/A") if fn_data else "N/A",
                "fn_modified": fn_data.get("modified", "N/A") if fn_data else "N/A",
                "fn_accessed": fn_data.get("accessed", "N/A") if fn_data else "N/A",
                "fn_mft_modified": fn_data.get("mft_modified", "N/A") if fn_data else "N/A",
            },
            "timestamps_dt": {
                "si_created":  si_data.get("created_dt"),
                "si_modified": si_data.get("modified_dt"),
                "fn_created":  fn_data.get("created_dt") if fn_data else None,
                "fn_modified": fn_data.get("modified_dt") if fn_data else None,
            },
            "file_size": fn_data.get("real_size", 0) if fn_data else 0,
            "parent_entry": fn_data.get("parent_entry", 0) if fn_data else 0,
        }
        return result

    def _parse_si(self, raw: bytes, attr_offset: int) -> Dict[str, Any]:
        """Parse $STANDARD_INFORMATION attribute (0x10)."""
        # Resident attribute header: type(4) + len(4) + non_resident(1) + name_len(1) + name_off(2) + flags(2) + id(2) + content_size(4) + content_off(2) + ...
        content_offset = struct.unpack_from("<H", raw, attr_offset + 20)[0]
        si_start = attr_offset + content_offset

        # $SI layout: Created(8) Modified(8) MFTModified(8) Accessed(8) ...
        if si_start + 32 > len(raw):
            return {}

        return {
            "created":      _filetime_to_iso(raw[si_start:si_start + 8]),
            "modified":     _filetime_to_iso(raw[si_start + 8:si_start + 16]),
            "mft_modified": _filetime_to_iso(raw[si_start + 16:si_start + 24]),
            "accessed":     _filetime_to_iso(raw[si_start + 24:si_start + 32]),
            "created_dt":      _filetime_to_datetime(raw[si_start:si_start + 8]),
            "modified_dt":     _filetime_to_datetime(raw[si_start + 8:si_start + 16]),
        }

    def _parse_fn(self, raw: bytes, attr_offset: int) -> Optional[Dict[str, Any]]:
        """Parse $FILE_NAME attribute (0x30)."""
        content_offset = struct.unpack_from("<H", raw, attr_offset + 20)[0]
        fn_start = attr_offset + content_offset

        # $FN layout: ParentRef(8) Created(8) Modified(8) MFTModified(8) Accessed(8)
        #             AllocSize(8) RealSize(8) Flags(4) Reparse(4) NameLen(1) Namespace(1) Name(variable)
        if fn_start + 66 > len(raw):
            return None

        parent_ref = struct.unpack_from("<Q", raw, fn_start)[0]
        parent_entry = parent_ref & 0x0000FFFFFFFFFFFF

        name_len = raw[fn_start + 64]
        namespace = raw[fn_start + 65]

        name_bytes_start = fn_start + 66
        name_bytes_end = name_bytes_start + name_len * 2
        try:
            filename = raw[name_bytes_start:name_bytes_end].decode("utf-16-le")
        except (UnicodeDecodeError, IndexError):
            filename = "<unknown>"

        real_size = struct.unpack_from("<Q", raw, fn_start + 48)[0]

        return {
            "parent_entry": parent_entry,
            "created":      _filetime_to_iso(raw[fn_start + 8:fn_start + 16]),
            "modified":     _filetime_to_iso(raw[fn_start + 16:fn_start + 24]),
            "mft_modified": _filetime_to_iso(raw[fn_start + 24:fn_start + 32]),
            "accessed":     _filetime_to_iso(raw[fn_start + 32:fn_start + 40]),
            "created_dt":      _filetime_to_datetime(raw[fn_start + 8:fn_start + 16]),
            "modified_dt":     _filetime_to_datetime(raw[fn_start + 16:fn_start + 24]),
            "real_size": real_size,
            "filename": filename,
            "namespace": namespace,
        }
