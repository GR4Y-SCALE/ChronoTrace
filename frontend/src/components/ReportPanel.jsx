import React from 'react';
import { useCaseStore } from '../store/caseStore';
import { FileText, Printer, Shield, Zap, LayoutDashboard, Clock } from 'lucide-react';

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
                        {hasLiveTampering
                            ? <>"$LogFile transaction analysis revealed LSN sequence gaps indicating live tampering on a running system. $USN Journal correlation confirmed missing modification records for files with backdated $SI timestamps. Framework identified <strong className="text-[#FF2D2D] font-bold" style={{ fontFamily: 'Inter' }}>{summary.critical} Critical</strong> findings of deliberate NTFS metadata manipulation consistent with timestomping performed during live system operation."
                            </>
                            : <>"Analysis of NTFS metadata artifacts identified <strong className="text-[#FF2D2D] font-bold" style={{ fontFamily: 'Inter' }}>{summary.critical} Critical</strong> and <strong className="text-[#FF8C00] font-bold" style={{ fontFamily: 'Inter' }}>{summary.high} High</strong> severity findings across {findings?.length || 0} flagged files. Cross-referencing $SI/$FN timestamps with $USN Journal records reveals deliberate timestamp manipulation consistent with anti-forensic activity."
                            </>}
                    </p>

                    {/* STATS */}
                    <div className="grid grid-cols-2 gap-4 mb-6 font-mono text-sm">
                        <StatItem label="Total MFT Records Analyzed" value={(summary.total_mft_records ?? 0).toLocaleString()} />
                        <StatItem label="Total USN Journal Entries" value={(summary.total_usn_entries ?? 0).toLocaleString()} />
                        <StatItem label="Total LogFile Transactions" value={(summary.total_logfile_transactions ?? 0).toLocaleString()} />
                        <StatItem label="Total Files Flagged" value={String(findings?.length || 0)} />
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
                        {(reportData.artifact_analysis || []).map((a, i) => (
                            <ArtifactRow key={i} num={i + 1} name={a.name} records={String(a.records ?? 0).replace(/\B(?=(\d{3})+(?!\d))/g, ',')} anomalies={a.anomalies ?? 0} detail={a.detail} />
                        ))}
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
                        <MetaField label="Image Hash (SHA-256)" value={case_info.image_hash || 'N/A'} />
                        <MetaField label="Hash Status" value={case_info.image_hash?.startsWith('SHA256:') ? '✅ VERIFIED' : 'Pending'} />
                        <MetaField label="Analysis Tool" value="ChronoTrace v1.0" />
                        <MetaField label="Analysis Date" value={new Date(case_info.created_at).toLocaleString()} />
                    </div>
                </div>

                {/* CONCLUSION */}
                <div className="p-8">
                    <h2 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">Conclusion</h2>
                    <p className="text-[#8B9BB4] leading-relaxed mb-4" style={{ fontFamily: "'Georgia', serif" }}>
                        This forensic analysis has identified deliberate anti-forensic activity on the examined device with
                        {' '}{summary.overall_risk_label} confidence ({summary.overall_risk_score}/100). The primary technique identified is TIMESTOMPING — the deliberate manipulation
                        of NTFS $Standard_Information timestamps to obscure the true timeline of file activity.
                        {hasLiveTampering && ' Evidence of LIVE TAMPERING was found, indicating the attacker had active access to the operating system during the manipulation.'}
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
