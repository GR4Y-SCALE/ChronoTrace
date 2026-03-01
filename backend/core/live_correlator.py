"""
ChronoTrace — Live Correlator (Streaming Mode)
Replaces the batch correlator for live monitoring.
When the USN monitor or process watcher emits an event, this module:
  1. Reads the live MFT record for the flagged file
  2. Builds the same correlation data structure the detector expects
  3. Runs the detection rules
  4. Emits alerts for any triggered rules

This is the glue between the sensors (USN monitor + process watcher)
and the existing detection rule engine.
"""

import asyncio
import uuid
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Any

from core.live_mft_reader import LiveMFTReader
from core.live_usn_monitor import LiveUSNMonitor, SUSPICIOUS_REASONS, USN_REASON_BASIC_INFO_CHANGE
from core.process_watcher import ProcessWatcher
from rules.detection_rules import evaluate_rules, RULES
from rules.live_rules import evaluate_live_rules, LIVE_RULES

logger = logging.getLogger("chronotrace.live_correlator")


class LiveAlert:
    """Represents a single live anti-forensic alert."""

    def __init__(self, **kwargs):
        self.id = str(uuid.uuid4())
        self.timestamp = kwargs.get("timestamp", datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
        self.alert_type = kwargs.get("alert_type", "unknown")  # usn_anomaly, process_tool, journal_attack
        self.filename = kwargs.get("filename", "")
        self.entry_number = kwargs.get("entry_number", 0)
        self.risk_level = kwargs.get("risk_level", "MEDIUM")
        self.confidence_score = kwargs.get("confidence_score", 50)
        self.rules_triggered = kwargs.get("rules_triggered", [])
        self.description = kwargs.get("description", "")
        self.details = kwargs.get("details", {})
        self.timestamps = kwargs.get("timestamps", {})
        self.process_info = kwargs.get("process_info", None)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "alert_type": self.alert_type,
            "filename": self.filename,
            "entry_number": self.entry_number,
            "risk_level": self.risk_level,
            "confidence_score": self.confidence_score,
            "rules_triggered": self.rules_triggered,
            "description": self.description,
            "details": self.details,
            "timestamps": self.timestamps,
        }
        if self.process_info:
            d["process_info"] = self.process_info
        return d


class LiveCorrelator:
    """
    Orchestrates the full live monitoring pipeline:
      USN Monitor  ─┐
                     ├─▶  Correlate  ─▶  Detect  ─▶  Alert
    Process Watcher ─┘
    """

    # ── Noise suppression ─────────────────────────────────────────────
    # Filenames that generate constant benign BASIC_INFO_CHANGE events from
    # browsers, Windows Update, shader caches, etc.  These are excluded from
    # correlation so they never reach the rule engine.
    _EXCLUDED_FILENAMES: frozenset = frozenset({
        # Chrome / Edge profile files (constantly rewritten)
        "Local State", "TransportSecurity", "Cookies", "History",
        "Visited Links", "Web Data", "Bookmarks", "Preferences",
        "Secure Preferences", "Network Action Predictor",
        "Login Data", "Extension Cookies", "Favicons",
        # Windows registry hives (legitimate OS writes)
        "DRIVERS", "SYSTEM", "SOFTWARE", "SAM", "SECURITY",
        "NTUSER.DAT", "UsrClass.dat",
        # Common volatile Windows files
        "desktop.ini", "thumbs.db",
    })

    # File extensions whose entire namespace is volatile/cache — skip entirely
    _EXCLUDED_EXTENSIONS: frozenset = frozenset({
        ".etl",   # Windows event trace logs
        ".log",   # generic logs
        ".tmp",   # temp files
        ".nvph",  # NVIDIA shader pipeline cache
        ".nvpk",  # NVIDIA pipeline key cache
        ".nv_cache",
        ".db-shm", ".db-wal",  # SQLite WAL/shared memory
    })

    @classmethod
    def _is_excluded(cls, filename: str) -> bool:
        """Return True if this filename should never be correlated."""
        if filename in cls._EXCLUDED_FILENAMES:
            return True
        lower = filename.lower()
        for ext in cls._EXCLUDED_EXTENSIONS:
            if lower.endswith(ext):
                return True
        return False

    def __init__(self, drive_letter: str = "C", poll_interval: float = 1.0):
        self.drive = drive_letter
        self.poll_interval = poll_interval
        self._mft_reader: Optional[LiveMFTReader] = None
        self._usn_monitor: Optional[LiveUSNMonitor] = None
        self._process_watcher: Optional[ProcessWatcher] = None
        self._running = False

        # Alert storage (in-memory ring buffer, last 1000 alerts)
        self.alerts: List[Dict[str, Any]] = []
        self._max_alerts = 1000

        # Stats
        self.stats = {
            "started_at": None,
            "usn_events_processed": 0,
            "process_events_processed": 0,
            "alerts_generated": 0,
            "rules_triggered_counts": defaultdict(int),
        }

        # Dedup: avoid alerting on the same file repeatedly within the window.
        # key = entry_number → last_alert_time
        # NOTE: the key is intentionally just entry_number — including the rule
        # frozenset caused a new alert every time the accumulator gained one more
        # rule, flooding the feed with duplicates for a single file operation.
        self._dedup_cache: Dict[int, float] = {}
        self._dedup_window = 30.0  # seconds

        # Per-file debounce tasks — we schedule a delayed correlation so we
        # wait for the accumulator to build up before running the rule engine.
        # This prevents the same timestomping operation from firing 4+ partial
        # correlations, each with a growing rule set.
        self._pending_correlations: Dict[int, asyncio.Task] = {}

        # Per-file USN event accumulator for building correlation context
        self._usn_accumulator: Dict[int, List[Dict]] = defaultdict(list)
        self._accumulator_ttl = 10.0  # seconds to keep events before correlating

        # External callback for pushing alerts to WebSocket
        self._alert_callback: Optional[Callable] = None
        self._status_callback: Optional[Callable] = None

    async def start(self, alert_callback: Optional[Callable] = None,
                    status_callback: Optional[Callable] = None):
        """Launch all sensors and begin live monitoring."""
        self._alert_callback = alert_callback
        self._status_callback = status_callback
        self._running = True
        self.stats["started_at"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        # Open MFT reader
        try:
            self._mft_reader = LiveMFTReader(self.drive)
            self._mft_reader.open()
        except PermissionError as e:
            await self._emit_status(f"❌ {e}")
            return

        await self._emit_status(f"🟢 Live MFT reader opened on {self.drive}:")

        # Launch sensors concurrently
        self._usn_monitor = LiveUSNMonitor(self.drive, self.poll_interval)
        self._process_watcher = ProcessWatcher(poll_interval=2.0)

        await asyncio.gather(
            self._usn_monitor.start(callback=self._on_usn_event),
            self._process_watcher.start(callback=self._on_process_event),
            self._accumulator_flush_loop(),
        )

    async def stop(self):
        """Stop all sensors."""
        self._running = False

        # Cancel any pending debounced correlation tasks so they don't fire
        # after the monitor has been torn down.
        for task in self._pending_correlations.values():
            if not task.done():
                task.cancel()
        self._pending_correlations.clear()

        if self._usn_monitor:
            await self._usn_monitor.stop()
        if self._process_watcher:
            await self._process_watcher.stop()
        if self._mft_reader:
            self._mft_reader.close()

        await self._emit_status("🔴 Live monitor stopped")

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self.stats,
            "rules_triggered_counts": dict(self.stats["rules_triggered_counts"]),
            "total_alerts": len(self.alerts),
            "is_running": self._running,
        }

    def get_alerts(self, limit: int = 50, severity: Optional[str] = None) -> List[Dict]:
        alerts = self.alerts
        if severity:
            alerts = [a for a in alerts if a.get("risk_level") == severity]
        return alerts[-limit:]

    # ── Sensor Callbacks ──────────────────────────────────────────────

    async def _on_usn_event(self, event: Dict[str, Any]):
        """Called by the USN monitor for each suspicious event."""
        if event.get("type") == "error":
            await self._emit_status(f"⚠️ USN: {event.get('message')}")
            return
        if event.get("type") == "status":
            await self._emit_status(event.get("message", ""))
            return
        if event.get("type") != "usn_event":
            return

        self.stats["usn_events_processed"] += 1
        entry = event["entry_number"]
        filename = event["filename"]

        # Skip known-noisy files (browser state, registry hives, shader cache…)
        # before they ever reach the rule engine.
        if self._is_excluded(filename):
            return

        # Accumulate events per file for batch correlation
        self._usn_accumulator[entry].append({
            "reason": event["reason_flags"],
            "reason_raw": event["reason_raw"],
            "timestamp": event["timestamp"],
            "usn": event["usn"],
            "filename": event["filename"],
            "is_rapid": event.get("is_rapid", False),
            "received_at": time.monotonic(),
        })

        # For high-priority events (BASIC_INFO_CHANGE), schedule a debounced
        # correlation.  We intentionally wait a short window so the accumulator
        # can absorb all events from a rapid-rewrite burst (e.g. SetMACE sets
        # C/M/A in three quick .NET calls) before running the rule engine.
        # Without the debounce, each BIC event triggers an immediate partial
        # correlation with an ever-growing rule set, and because the dedup key
        # used to include the frozenset(rules), every one passed dedup and
        # generated its own alert — turning 1 file operation into 3-5 alerts.
        if event["reason_raw"] & USN_REASON_BASIC_INFO_CHANGE:
            await self._schedule_correlation(entry, event["filename"])

    async def _on_process_event(self, event: Dict[str, Any]):
        """Called by the process watcher when an anti-forensic tool is detected."""
        if event.get("type") == "status":
            await self._emit_status(event.get("message", ""))
            return
        if event.get("type") != "process_alert":
            return

        self.stats["process_events_processed"] += 1

        # Build a process-based alert (no MFT correlation needed)
        alert = LiveAlert(
            timestamp=event["timestamp"],
            alert_type="process_tool",
            filename=event["process_name"],
            risk_level=event["severity"],
            confidence_score=95,
            rules_triggered=[event["tool_id"]],
            description=event["description"],
            details={
                "pid": event["pid"],
                "cmdline": event["cmdline"],
                "username": event["username"],
                "category": event["tool_category"],
            },
            process_info={
                "pid": event["pid"],
                "name": event["process_name"],
                "cmdline": event["cmdline"],
                "username": event["username"],
            },
        )

        await self._emit_alert(alert)

    # ── Correlation Engine ────────────────────────────────────────────

    async def _schedule_correlation(self, entry_number: int, filename: str,
                                     delay: float = 2.0):
        """
        Debounce helper: cancel any already-pending correlation task for this
        MFT entry and replace it with a new one that fires after *delay* seconds.
        This ensures that a burst of BASIC_INFO_CHANGE events (e.g. SetMACE
        setting C/M/A/E in rapid succession) results in a single correlation
        call that sees the full accumulated event set, not one call per event.
        """
        existing = self._pending_correlations.get(entry_number)
        if existing and not existing.done():
            existing.cancel()

        async def _delayed_correlate():
            try:
                await asyncio.sleep(delay)
                await self._correlate_file(entry_number, filename)
            except asyncio.CancelledError:
                pass  # task was superseded by a more recent event — that's fine

        self._pending_correlations[entry_number] = asyncio.create_task(
            _delayed_correlate()
        )

    async def _correlate_file(self, entry_number: int, filename: str):
        """Read the live MFT record and run detection rules for a specific file."""
        if not self._mft_reader:
            return

        logger.info(
            "[DIAG] CORRELATE entry=0x%X  file=%s  acc_events=%d",
            entry_number, filename, len(self._usn_accumulator.get(entry_number, []))
        )

        # Read MFT record
        try:
            mft_data = self._mft_reader.read_mft_record(entry_number)
        except Exception as e:
            logger.warning("MFT read failed for entry %d: %s", entry_number, e)
            return

        if mft_data is None:
            return

        # Build the correlation dict that evaluate_rules() expects
        accumulated = self._usn_accumulator.get(entry_number, [])
        usn_history = [
            {"reason": e["reason"], "timestamp": e["timestamp"], "usn_seq": e.get("usn", 0)}
            for e in accumulated
        ]

        has_bic = any("BASIC_INFO_CHANGE" in e.get("reason", "") for e in accumulated)
        has_data_overwrite = any("DATA_OVERWRITE" in e.get("reason", "") for e in accumulated)
        is_rapid = any(e.get("is_rapid", False) for e in accumulated)

        file_data = {
            "filename": mft_data.get("filename") or filename,
            "size_bytes": mft_data.get("file_size", 0),
            "mft_entry": entry_number,
            "parent_path": "",
            "timestamps": mft_data["timestamps"],
            "usn_history": usn_history,
            "evidence": {
                "usn_record_id": f"0x{accumulated[-1]['usn']:016X}" if accumulated else "N/A",
                "logfile_lsn": f"0x{mft_data.get('lsn', 0):08X}",
                "mft_sequence": mft_data.get("sequence_number", 0),
                "cluster": f"0x{entry_number * 2:04X}",
            },
            "has_basic_info_change": has_bic,
            "has_data_overwrite": has_data_overwrite,
            "usn_event_count": len(usn_history),
            "logfile_analysis": {"gap_detected": False, "transactions": []},
            "usn_analysis": {"present": usn_history, "missing": [], "conclusion": ""},
        }

        # Run the original 15 detection rules
        triggered = evaluate_rules(file_data)

        # Run live-only rules (16-21)
        live_context = {
            "is_rapid": is_rapid,
            "accumulated_events": accumulated,
            "mft_data": mft_data,
        }
        live_triggered = evaluate_live_rules(file_data, live_context)
        triggered.extend(live_triggered)

        logger.info(
            "[DIAG] RULES entry=0x%X  file=%s  triggered=%s  si_m=%s  fn_c=%s",
            entry_number, file_data["filename"],
            triggered or "(none)",
            file_data["timestamps"].get("si_modified", "?"),
            file_data["timestamps"].get("fn_created", "?"),
        )

        if not triggered:
            return

        # Dedup check — keyed only on entry_number so a single file operation
        # generates at most one alert per dedup window, regardless of which
        # rules happen to be in the triggered set at correlation time.
        dedup_key = entry_number
        now = time.monotonic()
        if dedup_key in self._dedup_cache:
            if now - self._dedup_cache[dedup_key] < self._dedup_window:
                logger.info(
                    "[DIAG] DEDUP BLOCKED entry=0x%X  file=%s  (%.1fs ago)",
                    entry_number, file_data["filename"],
                    now - self._dedup_cache[dedup_key],
                )
                return
        self._dedup_cache[dedup_key] = now

        # Compute severity
        all_rules = {**RULES, **LIVE_RULES}
        severities = [all_rules[r]["severity"] for r in triggered if r in all_rules]
        if "CRITICAL" in severities:
            risk = "CRITICAL"
        elif "HIGH" in severities:
            risk = "HIGH"
        elif "MEDIUM" in severities:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        # Compute confidence
        severity_bonus = {"CRITICAL": 30, "HIGH": 22, "MEDIUM": 14, "LOW": 8}
        confidence = min(99, 35 + len(triggered) * 6 + severity_bonus.get(risk, 8))

        # Build court explanation
        explanation = self._build_explanation(file_data["filename"], triggered, all_rules)

        alert = LiveAlert(
            alert_type="usn_anomaly",
            filename=file_data["filename"],
            entry_number=entry_number,
            risk_level=risk,
            confidence_score=confidence,
            rules_triggered=triggered,
            description=explanation,
            timestamps=mft_data["timestamps"],
            details={
                "usn_events": len(accumulated),
                "has_basic_info_change": has_bic,
                "has_data_overwrite": has_data_overwrite,
                "is_rapid_rewrite": is_rapid,
                "mft_sequence": mft_data.get("sequence_number", 0),
            },
        )

        await self._emit_alert(alert)

    async def _accumulator_flush_loop(self):
        """Periodically clean old entries from the USN event accumulator."""
        while self._running:
            now = time.monotonic()
            expired_entries = []
            for entry_number, events in self._usn_accumulator.items():
                # Remove events older than TTL
                self._usn_accumulator[entry_number] = [
                    e for e in events if now - e.get("received_at", 0) < self._accumulator_ttl
                ]
                if not self._usn_accumulator[entry_number]:
                    expired_entries.append(entry_number)
            for e in expired_entries:
                del self._usn_accumulator[e]

            # Also prune dedup cache
            self._dedup_cache = {
                k: t for k, t in self._dedup_cache.items()
                if now - t < self._dedup_window * 2
            }

            # Prune completed pending-correlation tasks so the dict doesn't grow
            self._pending_correlations = {
                k: t for k, t in self._pending_correlations.items()
                if not t.done()
            }

            await asyncio.sleep(5.0)

    # ── Helpers ───────────────────────────────────────────────────────

    def _build_explanation(self, filename: str, rules: List[str], all_rules: Dict) -> str:
        """Build a human-readable explanation for triggered rules."""
        if "RULE_15" in rules:
            return (
                f"🚨 {filename}: Cross-device transfer with pre-manipulation detected in real-time. "
                f"$SI timestamps predate $FN arrival — definitive timestomping."
            )
        if "RULE_20" in rules:
            return (
                f"🚨 {filename}: All four $SI timestamps set to identical value — "
                f"classic SetMACE/timestomp tool fingerprint detected live."
            )
        if "RULE_16" in rules:
            return (
                f"🚨 USN Journal deletion attempt detected — attacker trying to "
                f"destroy the change journal to hide their tracks."
            )

        # Generic: list triggered rules
        rule_names = [all_rules[r]["name"] for r in rules if r in all_rules]
        return f"Anti-forensic activity on {filename}: {', '.join(rule_names)}"

    async def _emit_alert(self, alert: LiveAlert):
        """Store alert and push to WebSocket callback."""
        alert_dict = alert.to_dict()
        self.alerts.append(alert_dict)
        if len(self.alerts) > self._max_alerts:
            self.alerts = self.alerts[-self._max_alerts:]

        self.stats["alerts_generated"] += 1
        for rule in alert.rules_triggered:
            self.stats["rules_triggered_counts"][rule] += 1

        logger.warning(
            "ALERT: [%s] %s — %s (rules: %s)",
            alert.risk_level, alert.filename, alert.description,
            ", ".join(alert.rules_triggered),
        )

        if self._alert_callback:
            await self._alert_callback(alert_dict)

    async def _emit_status(self, message: str):
        """Push a status message to the WebSocket."""
        logger.info("Status: %s", message)
        if self._status_callback:
            await self._status_callback({
                "type": "status",
                "message": message,
                "timestamp": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            })
