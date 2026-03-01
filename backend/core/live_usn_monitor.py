"""
ChronoTrace — Live USN Journal Monitor
Reads the NTFS Change Journal ($UsnJrnl) in real-time using Windows
DeviceIoControl (FSCTL_READ_USN_JOURNAL / FSCTL_QUERY_USN_JOURNAL).
Requires Administrator / SeBackupPrivilege.

This module is the **primary sensor** for live anti-forensics detection.
It continuously polls the USN Journal for new records and emits events
that the streaming correlator can evaluate against the detection rules.
"""

import asyncio
import ctypes
import ctypes.wintypes as wt
import struct
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Dict, List, Any

logger = logging.getLogger("chronotrace.live_usn")

# ── Win32 constants ──────────────────────────────────────────────────
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

FSCTL_QUERY_USN_JOURNAL = 0x000900F4
FSCTL_READ_USN_JOURNAL = 0x000900BB
FSCTL_ENUM_USN_DATA = 0x000900B3

USN_REASON_DATA_OVERWRITE       = 0x00000001
USN_REASON_DATA_EXTEND          = 0x00000002
USN_REASON_DATA_TRUNCATION      = 0x00000004
USN_REASON_NAMED_DATA_OVERWRITE = 0x00000010
USN_REASON_NAMED_DATA_EXTEND    = 0x00000020
USN_REASON_NAMED_DATA_TRUNCATION = 0x00000040
USN_REASON_FILE_CREATE          = 0x00000100
USN_REASON_FILE_DELETE           = 0x00000200
USN_REASON_EA_CHANGE            = 0x00000400
USN_REASON_SECURITY_CHANGE      = 0x00000800
USN_REASON_RENAME_OLD_NAME      = 0x00001000
USN_REASON_RENAME_NEW_NAME      = 0x00002000
USN_REASON_INDEXABLE_CHANGE     = 0x00004000
USN_REASON_BASIC_INFO_CHANGE    = 0x00008000
USN_REASON_HARD_LINK_CHANGE     = 0x00010000
USN_REASON_COMPRESSION_CHANGE   = 0x00020000
USN_REASON_ENCRYPTION_CHANGE    = 0x00040000
USN_REASON_OBJECT_ID_CHANGE     = 0x00080000
USN_REASON_REPARSE_POINT_CHANGE = 0x00100000
USN_REASON_STREAM_CHANGE        = 0x00200000
USN_REASON_CLOSE                = 0x80000000

# Reason code → human-readable flag map
REASON_FLAGS = {
    USN_REASON_DATA_OVERWRITE:       "DATA_OVERWRITE",
    USN_REASON_DATA_EXTEND:          "DATA_EXTEND",
    USN_REASON_DATA_TRUNCATION:      "DATA_TRUNCATION",
    USN_REASON_NAMED_DATA_OVERWRITE: "NAMED_DATA_OVERWRITE",
    USN_REASON_NAMED_DATA_EXTEND:    "NAMED_DATA_EXTEND",
    USN_REASON_NAMED_DATA_TRUNCATION:"NAMED_DATA_TRUNCATION",
    USN_REASON_FILE_CREATE:          "FILE_CREATE",
    USN_REASON_FILE_DELETE:          "FILE_DELETE",
    USN_REASON_EA_CHANGE:            "EA_CHANGE",
    USN_REASON_SECURITY_CHANGE:      "SECURITY_CHANGE",
    USN_REASON_RENAME_OLD_NAME:      "RENAME_OLD_NAME",
    USN_REASON_RENAME_NEW_NAME:      "RENAME_NEW_NAME",
    USN_REASON_INDEXABLE_CHANGE:     "INDEXABLE_CHANGE",
    USN_REASON_BASIC_INFO_CHANGE:    "BASIC_INFO_CHANGE",
    USN_REASON_HARD_LINK_CHANGE:     "HARD_LINK_CHANGE",
    USN_REASON_COMPRESSION_CHANGE:   "COMPRESSION_CHANGE",
    USN_REASON_ENCRYPTION_CHANGE:    "ENCRYPTION_CHANGE",
    USN_REASON_OBJECT_ID_CHANGE:     "OBJECT_ID_CHANGE",
    USN_REASON_REPARSE_POINT_CHANGE: "REPARSE_POINT_CHANGE",
    USN_REASON_STREAM_CHANGE:        "STREAM_CHANGE",
    USN_REASON_CLOSE:                "CLOSE",
}

# Interesting reason codes that warrant further investigation
SUSPICIOUS_REASONS = (
    USN_REASON_BASIC_INFO_CHANGE
    | USN_REASON_NAMED_DATA_OVERWRITE
    | USN_REASON_NAMED_DATA_EXTEND
    | USN_REASON_NAMED_DATA_TRUNCATION
    | USN_REASON_FILE_DELETE
    | USN_REASON_SECURITY_CHANGE
)


def _reason_to_flags(reason: int) -> str:
    """Convert a USN reason bitmask to a pipe-separated string of flag names."""
    parts = []
    for bit, name in REASON_FLAGS.items():
        if reason & bit:
            parts.append(name)
    return "|".join(parts) if parts else f"0x{reason:08X}"


def _filetime_to_datetime(ft: int) -> Optional[datetime]:
    """Convert Windows FILETIME (100-ns intervals since 1601-01-01) to datetime."""
    if ft <= 0:
        return None
    EPOCH_DIFF = 116444736000000000  # 100-ns intervals between 1601 and 1970
    try:
        ts = (ft - EPOCH_DIFF) / 10_000_000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OSError, ValueError, OverflowError):
        return None


# ── USN Record V2 Parser ─────────────────────────────────────────────

def _parse_usn_record_v2(buf: bytes, offset: int) -> Optional[Dict[str, Any]]:
    """Parse a single USN_RECORD_V2 from a byte buffer at the given offset."""
    if offset + 8 > len(buf):
        return None

    record_len = struct.unpack_from("<I", buf, offset)[0]
    if record_len < 60 or offset + record_len > len(buf):
        return None

    # USN_RECORD_V2 layout (60 bytes fixed header):
    #   DWORD  RecordLength         (I)
    #   WORD   MajorVersion         (H)
    #   WORD   MinorVersion         (H)
    #   DWORDLONG FileReferenceNumber          (Q)  ← 8 bytes, NOT I+H
    #   DWORDLONG ParentFileReferenceNumber    (Q)  ← 8 bytes, NOT I+H
    #   LONGLONG  Usn                          (q)
    #   LARGE_INTEGER TimeStamp               (q)
    #   DWORD  Reason                          (I)
    #   DWORD  SourceInfo                      (I)
    #   DWORD  SecurityId                      (I)
    #   DWORD  FileAttributes                  (I)
    #   WORD   FileNameLength                  (H)
    #   WORD   FileNameOffset                  (H)
    (
        _rec_len, major_ver, minor_ver,
        file_ref,
        parent_ref,
        usn,
        timestamp,
        reason,
        source_info,
        security_id,
        file_attributes,
        file_name_length,
        file_name_offset,
    ) = struct.unpack_from("<IHHQQqqIIIIHH", buf, offset)

    # MFT entry number is the lower 48 bits of the file reference
    entry_number = file_ref & 0x0000FFFFFFFFFFFF
    parent_entry = parent_ref & 0x0000FFFFFFFFFFFF
    sequence_number = (file_ref >> 48) & 0xFFFF

    # Decode filename (UTF-16LE)
    name_start = offset + file_name_offset
    name_end = name_start + file_name_length
    try:
        filename = buf[name_start:name_end].decode("utf-16-le")
    except (UnicodeDecodeError, IndexError):
        filename = "<unknown>"

    ts_dt = _filetime_to_datetime(timestamp)
    ts_str = ts_dt.strftime("%Y-%m-%dT%H:%M:%S") if ts_dt else "N/A"

    return {
        "record_length": record_len,
        "entry_number": entry_number,
        "parent_entry": parent_entry,
        "sequence_number": sequence_number,
        "usn": usn,
        "timestamp": ts_str,
        "timestamp_dt": ts_dt,
        "reason": reason,
        "reason_flags": _reason_to_flags(reason),
        "source_info": source_info,
        "file_attributes": file_attributes,
        "filename": filename,
    }


# ── Volume Handle ─────────────────────────────────────────────────────

class _VolumeHandle:
    """Wraps a Win32 volume handle for USN Journal access."""

    def __init__(self, drive_letter: str = "C"):
        self.drive = drive_letter.upper().rstrip(":\\")
        self.handle = None

    def open(self):
        kernel32 = ctypes.windll.kernel32
        path = f"\\\\.\\{self.drive}:"
        self.handle = kernel32.CreateFileW(
            path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if self.handle == -1 or self.handle == 0xFFFFFFFF:
            err = ctypes.get_last_error() or ctypes.windll.kernel32.GetLastError()
            raise PermissionError(
                f"Cannot open volume {self.drive}: — error {err}. "
                "Run as Administrator."
            )

    def close(self):
        if self.handle and self.handle not in (-1, 0xFFFFFFFF):
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None

    def ioctl(self, code: int, in_buf: bytes, out_size: int = 65536) -> bytes:
        """Issue DeviceIoControl and return the output buffer."""
        out_buf = ctypes.create_string_buffer(out_size)
        bytes_returned = wt.DWORD(0)
        ok = ctypes.windll.kernel32.DeviceIoControl(
            self.handle,
            code,
            in_buf, len(in_buf) if in_buf else 0,
            out_buf, out_size,
            ctypes.byref(bytes_returned),
            None,
        )
        if not ok:
            err = ctypes.get_last_error() or ctypes.windll.kernel32.GetLastError()
            raise OSError(f"DeviceIoControl failed — error {err}")
        return out_buf.raw[: bytes_returned.value]

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()


# ── USN Journal Info ──────────────────────────────────────────────────

def _query_journal(vol: _VolumeHandle) -> Dict[str, int]:
    """Query the USN Journal metadata (ID, first/next USN, etc.)."""
    data = vol.ioctl(FSCTL_QUERY_USN_JOURNAL, b"", 80)
    (
        journal_id,
        first_usn,
        next_usn,
        lowest_valid_usn,
        max_usn,
        max_size,
        allocation_delta,
    ) = struct.unpack_from("<QQQQQQQ", data, 0)
    return {
        "journal_id": journal_id,
        "first_usn": first_usn,
        "next_usn": next_usn,
        "lowest_valid_usn": lowest_valid_usn,
        "max_usn": max_usn,
    }


# ── Streaming Monitor ────────────────────────────────────────────────

class LiveUSNMonitor:
    """
    Continuously reads the NTFS USN Change Journal on a live volume.
    Yields parsed USN records that match the suspicious-reason filter.
    """

    def __init__(self, drive_letter: str = "C", poll_interval: float = 1.0):
        self.drive = drive_letter
        self.poll_interval = poll_interval
        self._vol: Optional[_VolumeHandle] = None
        self._journal_id: int = 0
        self._next_usn: int = 0
        self._running = False
        # Sliding window for rapid-event detection (entry_number → list of timestamps)
        self._recent_events: Dict[int, List[float]] = {}

    async def start(self, callback: Optional[Callable] = None):
        """Open the volume and begin the polling loop."""
        self._vol = _VolumeHandle(self.drive)
        try:
            self._vol.open()
        except PermissionError as e:
            logger.error(str(e))
            if callback:
                await callback({"type": "error", "message": str(e)})
            return

        # Query journal to get the current position (start from *now*, not history)
        try:
            info = _query_journal(self._vol)
        except OSError as e:
            logger.error(f"Failed to query USN journal: {e}")
            if callback:
                await callback({"type": "error", "message": f"USN Journal query failed: {e}"})
            self._vol.close()
            return

        self._journal_id = info["journal_id"]
        self._next_usn = info["next_usn"]  # start from the current tip
        self._running = True

        if callback:
            await callback({
                "type": "status",
                "message": f"🟢 Live USN monitor started on {self.drive}: — Journal ID 0x{self._journal_id:X}, "
                           f"watching from USN 0x{self._next_usn:X}",
            })

        logger.info(
            "USN monitor started — drive=%s journal=0x%X next_usn=0x%X",
            self.drive, self._journal_id, self._next_usn,
        )

        await self._poll_loop(callback)

    async def stop(self):
        """Gracefully stop the polling loop."""
        self._running = False
        if self._vol:
            self._vol.close()
            self._vol = None

    async def _poll_loop(self, callback: Optional[Callable]):
        """Core polling loop: reads new USN records every poll_interval seconds."""
        READ_BUF_SIZE = 65536

        while self._running:
            try:
                # Build READ_USN_JOURNAL_DATA_V0 input struct (40 bytes):
                #   LONGLONG  StartUsn            (Q)
                #   DWORD     ReasonMask           (I)
                #   DWORD     ReturnOnlyOnClose    (I)
                #   ULONGLONG Timeout              (Q)  ← 8 bytes, not 4
                #   ULONGLONG BytesToWaitFor       (Q)  ← required field, was missing
                #   DWORDLONG UsnJournalID         (Q)
                in_buf = struct.pack(
                    "<QIIQQQ",
                    self._next_usn,    # StartUsn
                    0xFFFFFFFF,        # ReasonMask — all reasons
                    0,                 # ReturnOnlyOnClose (0 = return immediately)
                    0,                 # Timeout (ULONGLONG)
                    0,                 # BytesToWaitFor (ULONGLONG)
                    self._journal_id,  # UsnJournalID
                )

                try:
                    # ensure volume handle still exists (stop() may have closed it)
                    if self._vol is None:
                        await asyncio.sleep(self.poll_interval)
                        continue
                    vol = self._vol
                    data = vol.ioctl(FSCTL_READ_USN_JOURNAL, in_buf, READ_BUF_SIZE)
                except OSError:
                    # Journal may have been deleted or volume is busy — wait and retry
                    await asyncio.sleep(self.poll_interval * 2)
                    continue

                if len(data) <= 8:
                    # Only the next-USN was returned, no new records
                    self._next_usn = struct.unpack_from("<q", data, 0)[0]
                    await asyncio.sleep(self.poll_interval)
                    continue

                # First 8 bytes = next USN to read from
                new_next_usn = struct.unpack_from("<q", data, 0)[0]
                offset = 8

                records_this_batch = []
                while offset < len(data):
                    rec = _parse_usn_record_v2(data, offset)
                    if rec is None:
                        break
                    records_this_batch.append(rec)
                    offset += rec["record_length"]
                    # Align to 8-byte boundary
                    offset = (offset + 7) & ~7

                self._next_usn = new_next_usn

                # Filter and emit suspicious records
                for rec in records_this_batch:
                    is_suspicious = bool(rec["reason"] & SUSPICIOUS_REASONS)
                    is_rapid = self._check_rapid_events(rec)

                    if is_suspicious or is_rapid:
                        event = {
                            "type": "usn_event",
                            "timestamp": rec["timestamp"],
                            "filename": rec["filename"],
                            "entry_number": rec["entry_number"],
                            "parent_entry": rec["parent_entry"],
                            "reason_flags": rec["reason_flags"],
                            "reason_raw": rec["reason"],
                            "usn": rec["usn"],
                            "is_rapid": is_rapid,
                            "sequence_number": rec["sequence_number"],
                        }
                        if callback:
                            await callback(event)

            except Exception as e:
                logger.error("USN poll error: %s", e, exc_info=True)
                if callback:
                    await callback({"type": "error", "message": f"Poll error: {e}"})
                await asyncio.sleep(self.poll_interval * 3)
                continue

            await asyncio.sleep(self.poll_interval)

        # Cleanup
        if self._vol:
            self._vol.close()
            self._vol = None

    def _check_rapid_events(self, rec: Dict) -> bool:
        """
        Detect rapid sequential BASIC_INFO_CHANGE events for the same file
        (signature of programmatic timestomping tools like SetMACE / timestomp).
        Returns True if 2+ BASIC_INFO_CHANGE events within a 2-second window.
        """
        if not (rec["reason"] & USN_REASON_BASIC_INFO_CHANGE):
            return False

        now = time.monotonic()
        entry = rec["entry_number"]

        if entry not in self._recent_events:
            self._recent_events[entry] = [now]
            return False

        # Prune old entries (> 5 seconds)
        self._recent_events[entry] = [
            t for t in self._recent_events[entry] if now - t < 5.0
        ]
        self._recent_events[entry].append(now)

        # 2+ events within 2 seconds → rapid rewrite
        recent = [t for t in self._recent_events[entry] if now - t < 2.0]
        return len(recent) >= 2
