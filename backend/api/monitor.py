"""
ChronoTrace — Live Monitor API Routes & WebSocket
REST endpoints and WebSocket for the live anti-forensics monitoring mode.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel

from core.live_correlator import LiveCorrelator

logger = logging.getLogger("chronotrace.monitor_api")

router = APIRouter()

# ── Global monitor state ──────────────────────────────────────────────

_correlator: Optional[LiveCorrelator] = None
_monitor_ws_connections: List[WebSocket] = []


class MonitorStartRequest(BaseModel):
    drive_letter: str = "C"
    poll_interval: float = 1.0


class MonitorStopRequest(BaseModel):
    pass


# ── WebSocket broadcast helpers ───────────────────────────────────────

async def _broadcast_alert(alert: Dict):
    """Push an alert to all connected WebSocket clients."""
    msg = json.dumps({"type": "alert", "data": alert})
    disconnected = []
    for ws in _monitor_ws_connections:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _monitor_ws_connections.remove(ws)


async def _broadcast_status(status: Dict):
    """Push a status message to all connected WebSocket clients."""
    msg = json.dumps({"type": "status", "data": status})
    disconnected = []
    for ws in _monitor_ws_connections:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _monitor_ws_connections.remove(ws)


# ── REST Endpoints ────────────────────────────────────────────────────

@router.post("/start")
async def start_monitor(req: MonitorStartRequest):
    """Start the live anti-forensics monitor on the specified drive."""
    global _correlator

    if _correlator and _correlator._running:
        raise HTTPException(status_code=409, detail="Monitor is already running")

    _correlator = LiveCorrelator(
        drive_letter=req.drive_letter,
        poll_interval=req.poll_interval,
    )

    # Launch in background — don't block the HTTP response
    asyncio.create_task(_run_monitor())

    return {
        "status": "starting",
        "message": f"Live monitor starting on {req.drive_letter}:",
        "drive": req.drive_letter,
    }


async def _run_monitor():
    """Background task that runs the correlator."""
    global _correlator
    if _correlator:
        try:
            await _correlator.start(
                alert_callback=_broadcast_alert,
                status_callback=_broadcast_status,
            )
        except Exception as e:
            logger.error("Monitor crashed: %s", e, exc_info=True)
            await _broadcast_status({
                "type": "status",
                "message": f"❌ Monitor crashed: {e}",
                "timestamp": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            })


@router.post("/stop")
async def stop_monitor():
    """Stop the live monitor."""
    global _correlator

    if not _correlator or not _correlator._running:
        raise HTTPException(status_code=409, detail="Monitor is not running")

    await _correlator.stop()
    return {"status": "stopped", "message": "Live monitor stopped"}


@router.get("/status")
async def monitor_status():
    """Get current monitor status and statistics."""
    if not _correlator:
        return {
            "is_running": False,
            "stats": None,
            "message": "Monitor has not been started",
        }

    return {
        "is_running": _correlator._running,
        "stats": _correlator.get_stats(),
    }


@router.get("/alerts")
async def get_alerts(
    limit: int = Query(50, ge=1, le=500),
    severity: Optional[str] = Query(None, regex="^(CRITICAL|HIGH|MEDIUM|LOW)$"),
):
    """Get recent alerts with optional severity filter."""
    if not _correlator:
        return {"alerts": [], "total": 0}

    alerts = _correlator.get_alerts(limit=limit, severity=severity)
    return {
        "alerts": alerts,
        "total": len(alerts),
    }


@router.get("/alerts/{alert_id}")
async def get_alert_detail(alert_id: str):
    """Get a specific alert by ID."""
    if not _correlator:
        raise HTTPException(status_code=404, detail="Monitor not running")

    for alert in _correlator.alerts:
        if alert.get("id") == alert_id:
            return alert

    raise HTTPException(status_code=404, detail="Alert not found")


@router.get("/rules")
async def get_rules():
    """Get all detection rules (original 15 + live 6)."""
    from rules.detection_rules import RULES
    from rules.live_rules import LIVE_RULES

    all_rules = {}
    for rule_id, rule in {**RULES, **LIVE_RULES}.items():
        all_rules[rule_id] = {
            "id": rule_id,
            "name": rule["name"],
            "severity": rule["severity"],
            "description": rule["description"],
            "explanation": rule["explanation"],
            "category": rule["category"],
            "is_live_only": rule_id in LIVE_RULES,
        }
    return {"rules": all_rules}


# ── WebSocket Endpoint ────────────────────────────────────────────────

@router.websocket("/ws")
async def monitor_websocket(websocket: WebSocket):
    """
    WebSocket for real-time alert streaming.
    Clients connect here to receive live alerts and status updates.
    """
    await websocket.accept()
    _monitor_ws_connections.append(websocket)

    logger.info("Monitor WebSocket client connected (total: %d)", len(_monitor_ws_connections))

    # Send current state on connect
    if _correlator:
        await websocket.send_text(json.dumps({
            "type": "init",
            "data": {
                "is_running": _correlator._running,
                "stats": _correlator.get_stats(),
                "recent_alerts": _correlator.get_alerts(limit=20),
            },
        }))
    else:
        await websocket.send_text(json.dumps({
            "type": "init",
            "data": {
                "is_running": False,
                "stats": None,
                "recent_alerts": [],
            },
        }))

    try:
        while True:
            # Keep connection alive; handle client messages if needed
            data = await websocket.receive_text()
            # Could handle commands like "clear_alerts", "change_filter" etc.
            try:
                msg = json.loads(data)
                if msg.get("command") == "get_stats" and _correlator:
                    await websocket.send_text(json.dumps({
                        "type": "stats",
                        "data": _correlator.get_stats(),
                    }))
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        _monitor_ws_connections.remove(websocket)
        logger.info("Monitor WebSocket client disconnected (remaining: %d)", len(_monitor_ws_connections))
