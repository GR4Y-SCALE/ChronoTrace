"""
ChronoTrace — Process Watcher
Lightweight WMI-based monitor for known anti-forensic tool execution.
NOT an EDR — narrowly scoped to detect specific anti-forensic behaviors:

 - Timestomping tools (timestomp.exe, SetMACE, NirCmd, BulkFileChanger)
 - USN journal destruction (fsutil usn deletejournal)
 - Event log clearing (wevtutil cl)
 - Shadow copy deletion (vssadmin delete shadows)
 - Secure wipers (SDelete, cipher /w, Eraser)
 - Prefetch wiping (mass deletion in C:\\Windows\\Prefetch)

Uses WMI Win32_Process events via the `wmi` library (or falls back to
periodic polling via `psutil`).
"""

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger("chronotrace.process_watcher")


# ── Known anti-forensic signatures ───────────────────────────────────

TOOL_SIGNATURES: List[Dict[str, Any]] = [
    # Timestomping tools
    {
        "id": "TOOL_TIMESTOMP",
        "pattern": r"(?i)(timestomp|setmace|setfiletime)",
        "match_on": "name_or_cmdline",
        "category": "Timestomping",
        "severity": "CRITICAL",
        "description": "Known timestomping tool detected",
    },
    {
        "id": "TOOL_NIRCMD_SETFILETIME",
        "pattern": r"(?i)nircmd.*setfiletime",
        "match_on": "cmdline",
        "category": "Timestomping",
        "severity": "CRITICAL",
        "description": "NirCmd setfiletime — timestamp manipulation command",
    },
    {
        "id": "TOOL_BULKFILECHANGER",
        "pattern": r"(?i)bulkfilechanger",
        "match_on": "name_or_cmdline",
        "category": "Timestomping",
        "severity": "HIGH",
        "description": "BulkFileChanger — batch timestamp modification tool",
    },
    {
        "id": "TOOL_POWERSHELL_SETTIME",
        "pattern": r"(?i)(Set-ItemProperty|\.CreationTime|\.LastWriteTime|\.LastAccessTime)\s*=",
        "match_on": "cmdline",
        "category": "Timestomping",
        "severity": "HIGH",
        "description": "PowerShell timestamp manipulation detected",
    },
    # USN Journal destruction
    {
        "id": "TOOL_USN_DELETE",
        "pattern": r"(?i)fsutil\s+usn\s+deletejournal",
        "match_on": "cmdline",
        "category": "Journal Destruction",
        "severity": "CRITICAL",
        "description": "USN Journal deletion attempt (fsutil usn deletejournal)",
    },
    # Event log clearing
    {
        "id": "TOOL_WEVTUTIL_CLEAR",
        "pattern": r"(?i)wevtutil\s+(cl|clear-log)",
        "match_on": "cmdline",
        "category": "Log Clearing",
        "severity": "CRITICAL",
        "description": "Windows Event Log clearing via wevtutil",
    },
    {
        "id": "TOOL_POWERSHELL_CLEARLOG",
        "pattern": r"(?i)(Clear-EventLog|Remove-EventLog|wevtutil\s+cl)",
        "match_on": "cmdline",
        "category": "Log Clearing",
        "severity": "CRITICAL",
        "description": "Event log clearing via PowerShell",
    },
    # Shadow copy deletion
    {
        "id": "TOOL_VSSADMIN_DELETE",
        "pattern": r"(?i)vssadmin\s+(delete\s+shadows|resize\s+shadowstorage\s+.*\/MaxSize=)",
        "match_on": "cmdline",
        "category": "Shadow Copy Destruction",
        "severity": "CRITICAL",
        "description": "Volume Shadow Copy deletion via vssadmin",
    },
    {
        "id": "TOOL_WMIC_SHADOWCOPY",
        "pattern": r"(?i)wmic\s+shadowcopy\s+delete",
        "match_on": "cmdline",
        "category": "Shadow Copy Destruction",
        "severity": "CRITICAL",
        "description": "Shadow copy deletion via WMIC",
    },
    # Secure deletion / wiping
    {
        "id": "TOOL_SDELETE",
        "pattern": r"(?i)(sdelete|sdelete64)",
        "match_on": "name_or_cmdline",
        "category": "Secure Deletion",
        "severity": "HIGH",
        "description": "Sysinternals SDelete — secure file deletion tool",
    },
    {
        "id": "TOOL_CIPHER_WIPE",
        "pattern": r"(?i)cipher\s+/w:",
        "match_on": "cmdline",
        "category": "Secure Deletion",
        "severity": "HIGH",
        "description": "cipher /w: — free space wiping to destroy deleted file remnants",
    },
    {
        "id": "TOOL_ERASER",
        "pattern": r"(?i)(eraser|eraserl)",
        "match_on": "name_or_cmdline",
        "category": "Secure Deletion",
        "severity": "HIGH",
        "description": "Eraser — anti-forensic secure deletion tool",
    },
    # Boot/recovery tampering
    {
        "id": "TOOL_BCDEDIT_SUPPRESS",
        "pattern": r"(?i)bcdedit\s+/set\s+.*bootstatuspolicy\s+ignoreallfailures",
        "match_on": "cmdline",
        "category": "Boot Tampering",
        "severity": "MEDIUM",
        "description": "bcdedit boot status policy suppression — hiding boot forensic artifacts",
    },
    # Prefetch clearing
    {
        "id": "TOOL_PREFETCH_CLEAR",
        "pattern": r"(?i)(del|remove-item|erase).*\\prefetch\\",
        "match_on": "cmdline",
        "category": "Artifact Destruction",
        "severity": "HIGH",
        "description": "Prefetch file deletion — destroying execution history artifacts",
    },
    # CCleaner and similar
    {
        "id": "TOOL_CCLEANER",
        "pattern": r"(?i)(ccleaner|bleachbit|privazer|privacyeraser)",
        "match_on": "name_or_cmdline",
        "category": "Artifact Destruction",
        "severity": "MEDIUM",
        "description": "System cleaner tool — potential anti-forensic artifact destruction",
    },
]

# Compiled regex patterns
_COMPILED_PATTERNS = [
    {**sig, "_regex": re.compile(sig["pattern"])}
    for sig in TOOL_SIGNATURES
]


def _check_process(name: str, cmdline: str) -> List[Dict[str, Any]]:
    """Check a process name + command line against all tool signatures."""
    hits = []
    for sig in _COMPILED_PATTERNS:
        match_on = sig["match_on"]
        regex = sig["_regex"]

        if match_on == "cmdline":
            if regex.search(cmdline):
                hits.append(sig)
        elif match_on == "name_or_cmdline":
            if regex.search(name) or regex.search(cmdline):
                hits.append(sig)
    return hits


# ── Process Watcher (psutil-based polling) ────────────────────────────

class ProcessWatcher:
    """
    Polls running processes for known anti-forensic tool signatures.
    Uses psutil for cross-compatibility (no WMI dependency).
    """

    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self._running = False
        self._seen_pids: Dict[int, float] = {}  # pid → first_seen time
        self._alerted_pids: set = set()          # pids we already alerted on

    async def start(self, callback: Optional[Callable] = None):
        """Begin polling for anti-forensic processes."""
        try:
            import psutil
        except ImportError:
            msg = "psutil not installed — process watching disabled. Install with: pip install psutil"
            logger.warning(msg)
            if callback:
                await callback({
                    "type": "status",
                    "message": f"⚠️ {msg}",
                })
            return

        self._running = True
        if callback:
            await callback({
                "type": "status",
                "message": "🟢 Process watcher started — monitoring for anti-forensic tools",
            })

        logger.info("Process watcher started with %d signatures", len(TOOL_SIGNATURES))

        while self._running:
            try:
                await self._scan_processes(psutil, callback)
            except Exception as e:
                logger.error("Process scan error: %s", e, exc_info=True)

            # Prune old seen-pids (> 60s old)
            now = time.monotonic()
            self._seen_pids = {
                pid: t for pid, t in self._seen_pids.items()
                if now - t < 60.0
            }

            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        self._running = False

    async def _scan_processes(self, psutil, callback: Optional[Callable]):
        """Scan all current processes against anti-forensic signatures."""
        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time", "username"]):
            try:
                info = proc.info
                pid = info["pid"]

                # Skip already-alerted processes
                if pid in self._alerted_pids:
                    continue

                name = (info.get("name") or "").strip()
                cmdline_parts = info.get("cmdline") or []
                cmdline = " ".join(cmdline_parts) if cmdline_parts else name

                hits = _check_process(name, cmdline)
                if not hits:
                    continue

                # New detection!
                self._alerted_pids.add(pid)

                for sig in hits:
                    event = {
                        "type": "process_alert",
                        "timestamp": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                        "pid": pid,
                        "process_name": name,
                        "cmdline": cmdline,
                        "username": info.get("username", "UNKNOWN"),
                        "tool_id": sig["id"],
                        "tool_category": sig["category"],
                        "severity": sig["severity"],
                        "description": sig["description"],
                    }

                    logger.warning(
                        "ANTI-FORENSIC TOOL DETECTED: %s (PID %d) — %s",
                        name, pid, sig["description"],
                    )

                    if callback:
                        await callback(event)

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
