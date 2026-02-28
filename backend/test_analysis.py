import asyncio
from core.parser import NTFSParser
from core.correlator import Correlator
from core.detector import Detector
from core.timeline import TimelineGenerator
from core.reporter import Reporter
from models.case import Case
from datetime import datetime

async def main():
    case = Case(id="CASE-123", investigator="Aarzoo", device_label="Test", analysis_mode="Fast", created_at=datetime.utcnow(), status="analyzing", progress=0, image_hash="PENDING")
    
    async def mock_callback(msg):
        pass

    print("Running Correlator...")
    correlator = Correlator({}, {}, {})
    correlated = await correlator.correlate(mock_callback)
    
    print("Running Detector...")
    detector = Detector(correlated)
    findings = await detector.analyze(mock_callback)
    
    print("Running Timeline...")
    timeline_gen = TimelineGenerator(findings)
    timeline_events = timeline_gen.generate()
    
    print("Running Reporter...")
    reporter = Reporter(case, findings, timeline_events)
    full_report = reporter.generate_report_object()
    
    print("Success!")

asyncio.run(main())
