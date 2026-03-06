"""
ChronoTrace — Reporter
Generates the full forensic report from analysis results.
Computes summary stats, anomaly distribution, and artifact analysis from real data.
"""

from models.report import FullReport, SummaryStats, ArtifactStats
from models.finding import Finding
from rules.detection_rules import RULES


class Reporter:
    def __init__(self, case, findings, timeline, parser_stats=None):
        self.case = case
        self.findings = findings
        self.timeline = timeline
        self.parser_stats = parser_stats or {}

    def generate_report_object(self) -> FullReport:
        critical = sum(1 for f in self.findings if f["risk_level"] == "CRITICAL")
        high = sum(1 for f in self.findings if f["risk_level"] == "HIGH")
        medium = sum(1 for f in self.findings if f["risk_level"] == "MEDIUM")
        low = sum(1 for f in self.findings if f["risk_level"] == "LOW")

        # Risk score: weighted formula
        score = min(100, critical * 30 + high * 18 + medium * 8 + low * 3)
        if score < 10 and (critical + high + medium + low) > 0:
            score = 10
        label = "CRITICAL" if score >= 75 else "HIGH" if score >= 50 else "MEDIUM" if score >= 20 else "LOW"

        # Anomaly distribution — count rules by category
        anomaly_dist = {"Timestamp": 0, "Log Evasion": 0, "Cross-Device": 0, "Metadata": 0}
        rules_count = {}
        for f in self.findings:
            for rule_id in f.get("rules_triggered", []):
                rules_count[rule_id] = rules_count.get(rule_id, 0) + 1
                cat = RULES.get(rule_id, {}).get("category", "Metadata")
                if cat in anomaly_dist:
                    anomaly_dist[cat] += 1

        total_mft = self.parser_stats.get("total_mft", 0)
        total_usn = self.parser_stats.get("total_usn", 0)
        total_logfile = self.parser_stats.get("total_logfile", 0)

        summary = SummaryStats(
            critical=critical,
            high=high,
            medium=medium,
            low=low,
            overall_risk_score=score,
            overall_risk_label=label,
            anomaly_distribution=anomaly_dist,
            rules_triggered=rules_count,
            total_mft_records=total_mft,
            total_usn_entries=total_usn,
            total_logfile_transactions=total_logfile,
        )

        # Artifact analysis rows
        n_findings = len(self.findings)
        logfile_anomalies = sum(1 for f in self.findings if f.get("logfile_analysis", {}).get("gap_detected"))
        usn_anomalies = sum(1 for f in self.findings if f.get("usn_analysis", {}).get("missing"))

        artifacts = [
            ArtifactStats(
                name="$MFT (Master File Table)",
                records=total_mft,
                anomalies=n_findings,
                detail=f"SI/FN timestamp divergence detected on {n_findings} record(s)",
            ),
            ArtifactStats(
                name="$Standard_Information ($SI)",
                records=total_mft,
                anomalies=n_findings,
                detail=f"$SI timestamps on {n_findings} file(s) predate their $FN arrival timestamps",
            ),
            ArtifactStats(
                name="$File_Name ($FN)",
                records=total_mft,
                anomalies=0,
                detail="$FN timestamps used as ground truth — written by NTFS kernel, not user-mode manipulable",
            ),
            ArtifactStats(
                name="$USN Journal",
                records=total_usn,
                anomalies=usn_anomalies,
                detail=f"Missing DATA_OVERWRITE records for {usn_anomalies} file(s) with claimed modification dates",
            ),
            ArtifactStats(
                name="$LogFile",
                records=total_logfile,
                anomalies=logfile_anomalies,
                detail=f"LSN gaps detected in {logfile_anomalies} file(s) — missing entries indicate log manipulation",
            ),
        ]

        # Hydrate pydantic models
        parsed_findings = [Finding(**f, case_id=self.case.id) for f in self.findings]

        report = FullReport(
            case_info=self.case,
            summary=summary,
            findings=parsed_findings,
            timeline_events=self.timeline,
            artifact_analysis=artifacts,
        )
        return report
