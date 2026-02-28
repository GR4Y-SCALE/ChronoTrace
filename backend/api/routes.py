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
from typing import List
from datetime import datetime
import uuid
import json

router = APIRouter()

# In-memory database for hackathon scenario
CASES_DB = {}
REPORTS_DB = {}

async def run_analysis(case_id: str, image_path: str):
    import asyncio
    await asyncio.sleep(0.5) # Allow time for frontend WebSocket to connect
    case = CASES_DB[case_id]
    case.status = "analyzing"
    
    async def send_progress(msg: str):
        await manager.send_message(msg, case_id)

    parser = NTFSParser(image_path)
    
    await send_progress("✅ Image mounted successfully")
    await send_progress("✅ NTFS partition detected")
    
    mft = await parser.parse_mft(send_progress)
    case.progress = 25
    await send_progress(json.dumps({"progress": 25}))
    
    usn = await parser.parse_usn(send_progress)
    case.progress = 40
    await send_progress(json.dumps({"progress": 40}))
    
    logfile = await parser.parse_logfile(send_progress)
    case.progress = 55
    await send_progress(json.dumps({"progress": 55}))
    
    correlator = Correlator(mft, usn, logfile)
    correlated = await correlator.correlate(send_progress)
    case.progress = 70
    await send_progress(json.dumps({"progress": 70}))
    
    detector = Detector(correlated)
    findings = await detector.analyze(send_progress)
    case.progress = 90
    await send_progress(json.dumps({"progress": 90, "findings_count": len(findings)}))
    
    timeline_gen = TimelineGenerator(findings)
    timeline_events = timeline_gen.generate()
    
    await send_progress("⏳ Reporter — Generating final court report...")
    reporter = Reporter(case, findings, timeline_events)
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
    # Simulating saving the file and generating a hash
    case.image_hash = "SHA256:3a4f8b9c... (Simulated Hash for " + file.filename + ")"
    return {"status": "ok", "message": "File uploaded successfully", "case": case}

@router.post("/cases/{case_id}/analyze")
async def start_analysis(case_id: str, background_tasks: BackgroundTasks):
    if case_id not in CASES_DB:
        raise HTTPException(status_code=404, detail="Case not found")
        
    background_tasks.add_task(run_analysis, case_id, "mock_image_path.dd")
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

@router.get("/cases/{case_id}/pdf")
async def get_report_pdf(case_id: str):
    from fastapi.responses import Response
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    import io

    if case_id not in REPORTS_DB:
        raise HTTPException(status_code=404, detail="Report not ready or missing")
    
    report = REPORTS_DB[case_id]
    case_info = report.case_info
    summary = report.summary
    findings = report.findings

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 20)
    c.setStrokeColorRGB(1, 0, 0)
    c.drawString(1 * inch, height - 1 * inch, "ANTI-FORENSICS ANALYSIS REPORT")
    c.line(1 * inch, height - 1.1 * inch, width - 1 * inch, height - 1.1 * inch)

    # Case Info
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1 * inch, height - 1.5 * inch, f"Case ID: {case_info.id}")
    c.setFont("Helvetica", 10)
    c.drawString(1 * inch, height - 1.7 * inch, f"Investigator: {case_info.investigator}")
    c.drawString(1 * inch, height - 1.9 * inch, f"Device Label: {case_info.device_label}")
    c.drawString(1 * inch, height - 2.1 * inch, f"Date: {case_info.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    c.drawString(1 * inch, height - 2.3 * inch, f"Risk Score: {summary.overall_risk_score}/100 ({summary.overall_risk_label})")

    y = height - 2.8 * inch
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1 * inch, y, "Flagged Artifacts:")
    y -= 0.3 * inch
    
    c.setFont("Helvetica", 10)
    for finding in findings:
        if y < 1 * inch:
            c.showPage()
            y = height - 1 * inch
            c.setFont("Helvetica", 10)
            
        c.setFont("Helvetica-Bold", 10)
        c.drawString(1 * inch, y, f"File: {finding.filename} (Risk: {finding.risk_level})")
        y -= 0.2 * inch
        
        c.setFont("Helvetica", 9)
        c.drawString(1.2 * inch, y, f"Court Explanation: {finding.court_explanation}")
        y -= 0.3 * inch

    c.save()
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Analysis_Report_{case_id}.pdf"}
    )

