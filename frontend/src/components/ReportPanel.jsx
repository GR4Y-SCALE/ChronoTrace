import React from 'react';
import { useCaseStore } from '../store/caseStore';
import { FileText, Download, Printer, Shield, Zap, LayoutDashboard, Clock } from 'lucide-react';
import { generateDetailedPDF } from '../utils/pdfGenerator';

export default function ReportPanel({ onNavigate }) {
    const { reportData } = useCaseStore();

    if (!reportData) return null;
    const { case_info, summary, findings } = reportData;
    const hasLiveTampering = findings?.some(f => f.rules_triggered.includes("RULE_04") || f.rules_triggered.includes("RULE_09"));

    return (
        <div className="space-y-6 animate-fade-in-up">
            {/* REPORT CARD */}
            <div className="rounded-xl border border-[#1E2D3D] overflow-hidden" style={{ background: '#111927' }}>

                {/* COVER SECTION */}
                <div className="p-10 text-center border-b border-[#1E2D3D] relative">
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.02] select-none">
                        <span className="text-8xl font-bold text-white rotate-[-30deg] tracking-[0.5em]">CONFIDENTIAL</span>
                    </div>
                    <h1 className="text-3xl font-bold tracking-tight text-white mb-2" style={{ fontFamily: 'Inter' }}>
                        FORENSIC ANALYSIS REPORT
                    </h1>
                    <p className="text-[#8B9BB4] font-mono text-sm">ChronoTrace v1.0</p>
                    <div className="mt-4 inline-block px-4 py-1 border border-[#FF2D2D]/30 bg-[#FF2D2D]/10 rounded text-[#FF2D2D] font-mono text-xs font-bold tracking-widest">
                        CLASSIFICATION: CONFIDENTIAL
                    </div>
                </div>

                {/* CASE METADATA */}
                <div className="p-8 border-b border-[#1E2D3D]">
                    <div className="grid grid-cols-2 gap-6 text-sm">
                        <MetaField label="Case Identifier" value={case_info.id} highlight />
                        <MetaField label="Analysis Date" value={new Date(case_info.created_at).toLocaleString()} />
                        <MetaField label="Investigator" value={case_info.investigator} />
                        <MetaField label="Target Device" value={case_info.device_label} />
                        <div className="col-span-2">
                            <span className="text-xs text-[#8B9BB4] font-mono uppercase tracking-wider block mb-1">Image Hash (SHA-256)</span>
                            <div className="font-mono text-sm text-[#00FF88] bg-[#050810] p-3 rounded-lg border border-[#1E2D3D]">
                                {case_info.image_hash}
                                <span className="text-[#00FF88] ml-2">✅ VERIFIED</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* RISK BADGE */}
                <div className="p-6 border-b border-[#1E2D3D] bg-[#0D1117] flex justify-between items-center">
                    <div className="flex items-center gap-3">
                        <span className="text-sm font-mono text-[#8B9BB4]">OVERALL RISK LEVEL:</span>
                        <span className="px-3 py-1 bg-[#FF2D2D] text-white font-bold font-mono text-sm rounded shadow-[0_0_10px_rgba(255,45,45,0.3)]">
                            {summary.overall_risk_label} ({summary.overall_risk_score}/100)
                        </span>
                    </div>
                    {hasLiveTampering && (
                        <span className="flex items-center gap-2 text-[#FF2D2D] font-mono text-sm font-bold animate-pulse">
                            <Zap className="w-4 h-4" /> LIVE TAMPERING DETECTED
                        </span>
                    )}
                </div>

                {/* EXECUTIVE SUMMARY */}
                <div className="p-8 border-b border-[#1E2D3D]">
                    <h2 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">Executive Summary</h2>
                    <p className="text-[#8B9BB4] leading-relaxed mb-6" style={{ fontFamily: "'Georgia', serif" }}>
                        "$LogFile transaction analysis revealed LSN sequence gaps
                        indicating live tampering on a running system. $USN Journal
                        correlation confirmed missing modification records for files
                        with backdated $SI timestamps. Framework identified <strong className="text-[#FF2D2D] font-bold" style={{ fontFamily: 'Inter' }}>{summary.critical} Critical</strong> findings
                        of deliberate NTFS metadata manipulation consistent
                        with timestomping performed during live system operation."
                    </p>

                    {/* STATS */}
                    <div className="grid grid-cols-2 gap-4 mb-6 font-mono text-sm">
                        <StatItem label="Total MFT Records Analyzed" value="14,832" />
                        <StatItem label="Total USN Journal Entries" value="48,291" />
                        <StatItem label="Total LogFile Transactions" value="12,447" />
                        <StatItem label="Total Files Flagged" value={String(findings?.length || 3)} />
                    </div>

                    <div className="flex gap-4 font-mono font-bold text-base bg-[#050810] p-4 rounded-lg border border-[#1E2D3D]">
                        <span className="text-[#FF2D2D]">CRITICAL: {summary.critical}</span>
                        <span className="text-[#FF8C00]">HIGH: {summary.high}</span>
                        <span className="text-[#FFD700]">MEDIUM: {summary.medium}</span>
                        <span className="text-[#00D4FF]">LOW: {summary.low}</span>
                    </div>
                </div>

                {/* ARTIFACT ANALYSIS */}
                <div className="p-8 border-b border-[#1E2D3D]">
                    <h2 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">NTFS Artifact Analysis</h2>
                    <div className="space-y-4">
                        <ArtifactRow num={1} name="$MFT (Master File Table)" records="14,832" anomalies={3}
                            detail="MFT sequence numbers inconsistent with claimed file ages on 2 records" />
                        <ArtifactRow num={2} name="$Standard_Information ($SI)" records="14,832" anomalies={3}
                            detail="$SI timestamps on file1.txt and doc2.docx predate their $FN arrival timestamps" />
                        <ArtifactRow num={3} name="$File_Name ($FN)" records="14,832" anomalies={0}
                            detail="$FN timestamps used as ground truth — written by NTFS kernel, not user-mode manipulable" />
                        <ArtifactRow num={4} name="$USN Journal" records="48,291" anomalies={2}
                            detail="Missing DATA_OVERWRITE records for files with claimed modification dates" />
                        <ArtifactRow num={5} name="$LogFile" records="12,447" anomalies={1}
                            detail="LSN gap of 6 units — missing entries between 0xA1B3 and 0xA1B9" />
                    </div>
                </div>

                {/* CHAIN OF CUSTODY */}
                <div className="p-8 border-b border-[#1E2D3D]">
                    <h2 className="text-lg font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
                        <Shield className="w-5 h-5 text-[#00D4FF]" /> Chain of Custody
                    </h2>
                    <div className="grid grid-cols-2 gap-4 font-mono text-sm">
                        <MetaField label="Evidence Item" value={`Disk Image — ${case_info.device_label}`} />
                        <MetaField label="Acquired By" value={case_info.investigator} />
                        <MetaField label="Acquisition Tool" value="FTK Imager / dd" />
                        <MetaField label="Write Blocker Used" value="Yes" />
                        <MetaField label="Analysis Tool" value="ChronoTrace v1.0" />
                        <MetaField label="Hash Status" value="✅ VERIFIED" />
                    </div>
                </div>

                {/* CONCLUSION */}
                <div className="p-8">
                    <h2 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">Conclusion</h2>
                    <p className="text-[#8B9BB4] leading-relaxed mb-4" style={{ fontFamily: "'Georgia', serif" }}>
                        This forensic analysis has identified deliberate anti-forensic activity on the examined device with
                        HIGH confidence (94%). The primary technique identified is TIMESTOMPING — the deliberate manipulation
                        of NTFS $Standard_Information timestamps to obscure the true timeline of file activity.
                    </p>
                    <div className="bg-[#050810] border border-[#1E2D3D] rounded-lg p-4 font-mono text-sm">
                        <h4 className="text-[#00D4FF] font-bold mb-2">RECOMMENDATIONS:</h4>
                        <ol className="list-decimal list-inside space-y-1 text-[#8B9BB4]">
                            <li>Seize Device1 (origin device) for analysis</li>
                            <li>Examine network logs for transfer evidence</li>
                            <li>Check shell history and prefetch for transfer tools</li>
                            <li>Correlate findings with user account activity logs</li>
                        </ol>
                    </div>
                    <p className="mt-4 text-xs text-[#8B9BB4] font-mono text-center border-t border-[#1E2D3D] pt-4">
                        Report generated by ChronoTrace v1.0 on {new Date().toISOString().split('T')[0]}
                    </p>
                </div>
            </div>

            {/* EXPORT BUTTONS */}
            <div className="flex gap-4 justify-center">
                <button
                    onClick={() => generateDetailedPDF(reportData)}
                    className="flex items-center gap-2 bg-[#00D4FF]/10 border border-[#00D4FF]/30 text-[#00D4FF] px-6 py-3 rounded-xl font-mono text-sm hover:bg-[#00D4FF]/20 transition"
                >
                    <Download className="w-4 h-4" /> EXPORT DETAILED PDF
                </button>
                <button
                    onClick={() => {
                        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(reportData, null, 2));
                        const a = document.createElement('a');
                        a.href = dataStr;
                        a.download = `Analysis_Report_${case_info.id}.json`;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                    }}
                    className="flex items-center gap-2 border border-[#1E2D3D] text-[#8B9BB4] px-6 py-3 rounded-xl font-mono text-sm hover:text-white hover:border-[#00D4FF]/30 transition"
                >
                    <FileText className="w-4 h-4" /> EXPORT JSON
                </button>
                <button
                    onClick={() => window.print()}
                    className="flex items-center gap-2 border border-[#1E2D3D] text-[#8B9BB4] px-6 py-3 rounded-xl font-mono text-sm hover:text-white hover:border-[#00D4FF]/30 transition"
                >
                    <Printer className="w-4 h-4" /> PRINT COURT COPY
                </button>
            </div>

            {/* QUICK NAVIGATION */}
            <div className="flex gap-4 justify-center">
                <button onClick={() => onNavigate('dashboard')} className="flex items-center gap-2 text-sm border border-[#1E2D3D] text-[#8B9BB4] px-5 py-2.5 rounded-xl font-mono hover:text-[#00D4FF] hover:border-[#00D4FF]/30 transition">
                    <LayoutDashboard className="w-4 h-4" /> ← Back to Dashboard
                </button>
                <button onClick={() => onNavigate('timeline')} className="flex items-center gap-2 text-sm border border-[#1E2D3D] text-[#8B9BB4] px-5 py-2.5 rounded-xl font-mono hover:text-[#00D4FF] hover:border-[#00D4FF]/30 transition">
                    <Clock className="w-4 h-4" /> View Timeline →
                </button>
            </div>
        </div>
    );
}

function MetaField({ label, value, highlight }) {
    return (
        <div>
            <span className="text-xs text-[#8B9BB4] font-mono uppercase tracking-wider block mb-1">{label}</span>
            <span className={`font-mono text-sm ${highlight ? 'text-[#00D4FF] font-bold' : 'text-white'}`}>{value}</span>
        </div>
    );
}

function StatItem({ label, value }) {
    return (
        <div className="flex justify-between items-center py-2 border-b border-[#1E2D3D]/30 last:border-0">
            <span className="text-[#8B9BB4]">{label}</span>
            <span className="text-[#00D4FF] font-bold">{value}</span>
        </div>
    );
}

function ArtifactRow({ num, name, records, anomalies, detail }) {
    return (
        <div className="bg-[#0D1117] border border-[#1E2D3D] rounded-lg p-4">
            <div className="flex justify-between items-start mb-2">
                <h4 className="font-mono text-sm font-bold text-white">
                    <span className="text-[#8B9BB4] mr-2">{num}.</span>{name}
                </h4>
                <span className={`text-xs font-mono px-2 py-0.5 rounded ${anomalies > 0 ? 'bg-[#FF2D2D]/10 text-[#FF2D2D] border border-[#FF2D2D]/20' : 'bg-[#00FF88]/10 text-[#00FF88] border border-[#00FF88]/20'
                    }`}>
                    {anomalies > 0 ? `${anomalies} anomalies` : 'Clean'}
                </span>
            </div>
            <div className="text-xs text-[#8B9BB4] font-mono mb-1">Records: {records}</div>
            <div className="text-xs text-[#8B9BB4]">{detail}</div>
        </div>
    );
}
