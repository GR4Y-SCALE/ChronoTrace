# CHRONOTRACE

**NTFS Anti-Forensics Detection Framework**

ChronoTrace is a forensic analysis tool that detects timestamp manipulation, log evasion, and other anti-forensic techniques on NTFS file systems. It operates in two modes: post-mortem disk image analysis and real-time live monitoring.

---

## Features

### Image Analysis Mode
Upload EnCase `.E01` disk images (single-part or multi-segment) for offline forensic analysis:

- Parses `$MFT`, `$UsnJrnl`, and `$LogFile` NTFS structures
- Correlates `$SI` (Standard Information) and `$FN` (File Name) timestamps
- Detects 15 deterministic anti-forensics rules (see below)
- Generates a full case timeline and exportable PDF report
- Real-time progress updates via WebSocket

### Live Monitor Mode
Real-time monitoring of a running Windows system:

- Polls the live `$MFT` and USN Journal for changes
- Detects anti-forensic activity as it happens
- Streams alerts to the UI over WebSocket

### Detection Rules

| Rule | Severity | Category | Description |
|------|----------|----------|-------------|
| `SI_FN_DIVERGENCE` | CRITICAL | Timestamp | `$SI` and `$FN` modified timestamps diverge by > 1 hour |
| `BACKDATING_DETECTED` | CRITICAL | Timestamp | File modified before it existed on this volume |
| `MISSING_USN_HISTORY` | HIGH | Log Evasion | USN journal doesn't reflect modifications claimed by `$SI` |
| `LSN_SEQUENCE_BREAK` | HIGH | Log Evasion | LogFile LSN gaps indicate log tampering |
| `HASH_METADATA_MISMATCH` | HIGH | Metadata | File content changed after timestamp manipulation |
| `EMBEDDED_TIMESTAMP_CONFLICT` | MEDIUM | Metadata | EXIF/Office/PDF timestamp contradicts NTFS `$SI` |
| `ZONE_IDENTIFIER_ABSENT` | MEDIUM | Metadata | Mark-of-the-Web ADS deliberately stripped |
| `VOLUME_SERIAL_MISMATCH` | MEDIUM | Cross-Device | File originated on a different NTFS volume |
| `USN_REASON_CODE_GAP` | HIGH | Log Evasion | Modification with no corresponding USN journal entry |
| `RAPID_METADATA_REWRITE` | MEDIUM | Timestamp | Multiple `$SI` updates within a 2-second window |
| *(+ 5 more rules)* | | | |

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python · FastAPI · Uvicorn |
| Frontend | React 19 · Vite · Tailwind CSS · Recharts |
| State | Zustand |
| Realtime | WebSockets |
| Parsing | Custom NTFS parser (pyewf / libewf) |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- `libewf` installed on the host (required for `.E01` parsing)

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.

---

## Project Structure

```
ChronoTrace/
├── backend/
│   ├── main.py               # FastAPI app entry point
│   ├── api/
│   │   ├── routes.py         # Image analysis endpoints
│   │   ├── monitor.py        # Live monitor endpoints & WebSocket
│   │   └── websocket.py      # WebSocket connection manager
│   ├── core/
│   │   ├── parser.py         # NTFS / EWF image parser
│   │   ├── correlator.py     # $SI / $FN / USN / LogFile correlator
│   │   ├── detector.py       # Rule-based anomaly detection
│   │   ├── timeline.py       # Timeline generation
│   │   ├── reporter.py       # Report builder
│   │   ├── live_mft_reader.py
│   │   ├── live_usn_monitor.py
│   │   └── live_correlator.py
│   ├── models/               # Pydantic models (Case, Finding, Report)
│   ├── rules/
│   │   ├── detection_rules.py  # 15 static detection rules
│   │   └── live_rules.py       # Rules for live monitoring
│   └── uploads/              # Per-case uploaded evidence files
└── frontend/
    └── src/
        ├── components/
        │   ├── UploadPanel.jsx
        │   ├── Dashboard.jsx
        │   ├── TimelineViewer.jsx
        │   ├── FileDeepDive.jsx
        │   ├── ReportPanel.jsx
        │   └── LiveMonitor.jsx
        ├── store/
        │   ├── caseStore.js
        │   └── monitorStore.js
        └── utils/
            └── pdfGenerator.js
```

---

## Scripts

### `start.bat` — Launch Everything
Double-click (or run from a terminal) to start both servers in one step:

```bat
start.bat
```

- Activates the `.venv` Python virtual environment
- Launches the FastAPI backend on `http://localhost:8000`
- Launches the Vite frontend on `http://localhost:5173`

> **Note:** For Live Monitor mode, run `start.bat` as Administrator.

---

### `simulate_live.ps1` — Live Demo Simulator
Generates **real** NTFS anti-forensic events on the local machine to trigger Live Monitor alerts during a demonstration. Must be run in an **elevated (Administrator) PowerShell** terminal while the Live Monitor is active on drive `C:`.

```powershell
.\simulate_live.ps1
```

Simulated scenarios include:

| Scenario | Actions | Rules Triggered |
|----------|---------|-----------------|
| Timestamp Manipulation | Backdates `$SI` timestamps via PowerShell on `.docx`/`.txt`/`.xlsx` test files | `SI_FN_DIVERGENCE`, `RAPID_METADATA_REWRITE`, SetMACE fingerprint |
| *(additional scenarios in script)* | USN journal events, process-based detections | Various |

Test files are created under `C:\ChronoTrace_SimTest\` and cleaned up after the run.

---

### `_kill_old.ps1` — Kill Stale Process
One-liner utility to forcefully terminate a leftover backend process by PID when restarting during development.

```powershell
.\_kill_old.ps1
```

---

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/cases` | Create a new case |
| `POST` | `/api/cases/{id}/upload` | Upload evidence file(s) |
| `POST` | `/api/cases/{id}/analyze` | Start analysis |
| `GET` | `/api/cases/{id}/report` | Fetch full analysis report |
| `WS` | `/ws/{case_id}` | Analysis progress stream |
| `POST` | `/api/monitor/start` | Start live monitoring |
| `POST` | `/api/monitor/stop` | Stop live monitoring |
| `WS` | `/api/monitor/ws` | Live alert stream |
