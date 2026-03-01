from fastapi import APIRouter, File, UploadFile, BackgroundTasks, HTTPException
from models.case import Case, CaseCreate
from models.finding import Finding
from models.report import FullReport
from core.parser import NTFSParser
from core.correlator import Correlator
from core.detector import Detector
from core.timeline import TimelineGenerator
from core.reporter import Reporter
from api.websocket import manager
from datetime import datetime
from pathlib import Path
import hashlib
import uuid
import json

router = APIRouter()

# In-memory database for hackathon scenario
CASES_DB = {}
REPORTS_DB = {}

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


async def run_analysis(case_id: str):
    import asyncio
    await asyncio.sleep(0.5)  # let frontend WS connect
    case = CASES_DB[case_id]
    case.status = "analyzing"

    case_dir = UPLOAD_DIR / case_id

    async def send_progress(msg: str):
        await manager.send_message(msg, case_id)

    # Look for uploaded disk image — prefer standalone single-segment images
    # (no .E02 sibling) over multi-part split sets so Evidence01.E01 is always
    # favoured even when EVIDENCE02.E01-E08 segments are also present.
    image_path = None
    all_e01s = sorted(
        list(case_dir.glob("*.E01")) + list(case_dir.glob("*.e01")),
        key=lambda p: p.name.lower(),
    )
    # First pass – standalone (no matching .E02 / .e02)
    for cand in all_e01s:
        stem = cand.stem
        if not (cand.parent / f"{stem}.E02").exists() and \
           not (cand.parent / f"{stem}.e02").exists():
            image_path = cand
            break
    # Second pass – fall back to first multi-segment set
    if image_path is None and all_e01s:
        image_path = all_e01s[0]

    if not image_path:
        await send_progress("❌ No disk image found in upload directory")
        case.status = "failed"
        return

    await send_progress(f"✅ Disk image located: {image_path.name}")
    parser = NTFSParser.from_image(str(image_path), str(case_dir))
    opened = await parser.open_image(send_progress)
    if not opened:
        await send_progress("❌ Failed to open NTFS volume from disk image")
        case.status = "failed"
        return

    # Phase 1: Parse
    mft_df = await parser.parse_mft(send_progress)
    case.progress = 20
    await send_progress(json.dumps({"progress": 20}))

    usn_df = await parser.parse_usn(send_progress)
    if usn_df.empty:
        await send_progress("❌ $USN Journal is required for strict analysis")
        case.status = "failed"
        return
    case.progress = 35
    await send_progress(json.dumps({"progress": 35}))

    logfile = await parser.parse_logfile(send_progress)
    if logfile.get("total_transactions", 0) <= 0:
        await send_progress("❌ $LogFile data is required for strict analysis")
        case.status = "failed"
        return
    case.progress = 50
    await send_progress(json.dumps({"progress": 50}))

    # Phase 2: Correlate & flag candidates
    correlator = Correlator(mft_df, usn_df, logfile)
    correlated = await correlator.correlate(send_progress)
    case.progress = 70
    await send_progress(json.dumps({"progress": 70}))

    # Phase 3+4: Feature scoring + rule detection
    detector = Detector(correlated)
    findings = await detector.analyze(send_progress)
    case.progress = 90
    await send_progress(json.dumps({"progress": 90, "findings_count": len(findings)}))

    # Timeline
    timeline_gen = TimelineGenerator(findings)
    timeline_events = timeline_gen.generate()

    # Report
    await send_progress("⏳ Reporter — Generating final court report...")
    parser_stats = {
        "total_mft": parser.total_mft,
        "total_usn": parser.total_usn,
        "total_logfile": logfile.get("total_transactions", 0),
    }
    reporter = Reporter(case, findings, timeline_events, parser_stats)
    full_report = reporter.generate_report_object()

    REPORTS_DB[case_id] = full_report

    case.status = "completed"
    case.progress = 100
    await send_progress(json.dumps({"progress": 100, "status": "completed"}))


@router.post("/cases", response_model=Case)
async def create_case(case_data: CaseCreate):
    case_id = f"CASE-{str(uuid.uuid4())[:8].upper()}"
    new_case = Case(
        **case_data.model_dump(), 
        id=case_id,
        image_hash="PENDING_UPLOAD",
        created_at=datetime.utcnow()
    )
    CASES_DB[case_id] = new_case
    return new_case

@router.post("/cases/{case_id}/upload")
async def upload_image(case_id: str, file: UploadFile = File(...)):
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail="Case not found")

    case = CASES_DB[case_id]

    # Create case directory and save the uploaded file
    case_dir = UPLOAD_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    filename = file.filename or "upload.bin"
    file_path = case_dir / filename
    sha256 = hashlib.sha256()

    with open(file_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)  # 1 MB chunks
            if not chunk:
                break
            f.write(chunk)
            sha256.update(chunk)

    case.image_hash = f"SHA256:{sha256.hexdigest()}"

    return {"status": "ok", "message": "File uploaded successfully", "hash": case.image_hash, "case": case}

@router.post("/cases/{case_id}/analyze")
async def start_analysis(case_id: str, background_tasks: BackgroundTasks):
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail="Case not found")
        
    background_tasks.add_task(run_analysis, case_id)
    return {"status": "Analysis started"}

@router.get("/cases/{case_id}", response_model=Case)
async def get_case(case_id: str):
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail="Case not found")
    return CASES_DB[case_id]

@router.get("/cases/{case_id}/report")
async def get_report(case_id: str):
    if case_id not in REPORTS_DB:
        raise HTTPException(status_code=404, detail="Report not ready or missing")
    return REPORTS_DB[case_id].model_dump()

