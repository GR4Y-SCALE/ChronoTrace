import React from 'react';
import { ArrowLeft, Copy, FileDown, FileWarning, Eye, Search, Zap, Database, Shield } from 'lucide-react';

const RULE_DESCRIPTIONS = {
    "RULE_01": "$SI modified timestamp predates $FN arrival on this volume by X days. Timestamp backdating confirmed.",
    "RULE_02": "$SI timestamp predates $FN creation on this device. File cannot have been modified before it existed here.",
    "RULE_03": "USN Journal contains only FILE_CREATE. No modification history exists despite $SI claiming prior edits.",
    "RULE_04": "LogFile LSN gap of X detected. Expected 1-2, got X. Missing entries indicate log manipulation.",
    "RULE_05": "File hash contradicts $SI modification date. Content was changed after timestamp was set.",
    "RULE_06": "EXIF timestamp contradicts $SI modified date. Internal metadata was not updated when NTFS timestamps were manipulated.",
    "RULE_07": "Zone.Identifier ADS is missing. Was deliberately stripped to hide transfer origin.",
    "RULE_08": "Embedded Volume Serial Number does not match this device. File originated on a different volume.",
    "RULE_09": "$SI shows modification but no USN_REASON_DATA_OVERWRITE exists in journal. Live tampering signature.",
    "RULE_10": "Multiple $SI updates within milliseconds. Programmatic timestomping pattern detected.",
    "RULE_11": "$I30 directory slack is fully zeroed. Deliberately wiped to hide file existence.",
    "RULE_12": "Some MAC timestamps changed, others left in impossible chronological state. Incomplete timestomping.",
    "RULE_13": "Undeclared Alternate Data Streams detected. Data is hidden in ADS.",
    "RULE_14": "MFT sequence number inconsistent with file age claimed by $SI. MFT record was manipulated.",
    "RULE_15": "RULE_01 + RULE_02 + RULE_03 all triggered. Cross-device transfer with pre-transfer timestamp manipulation confirmed."
};

const RULE_SEVERITIES = {
    "RULE_01": "CRITICAL", "RULE_02": "CRITICAL", "RULE_03": "HIGH", "RULE_04": "HIGH",
    "RULE_05": "HIGH", "RULE_06": "MEDIUM", "RULE_07": "MEDIUM", "RULE_08": "MEDIUM",
    "RULE_09": "HIGH", "RULE_10": "MEDIUM", "RULE_11": "LOW", "RULE_12": "HIGH",
    "RULE_13": "MEDIUM", "RULE_14": "HIGH", "RULE_15": "CRITICAL"
};

const SEV_COLORS = {
    "CRITICAL": { bg: '#FF2D2D', text: '#FF2D2D' },
    "HIGH": { bg: '#FF8C00', text: '#FF8C00' },
    "MEDIUM": { bg: '#FFD700', text: '#FFD700' },
    "LOW": { bg: '#00D4FF', text: '#00D4FF' }
};

export default function FileDeepDive({ file, onBack, onNavigate }) {
    if (!file) return null;

    const hasLiveTampering = file.rules_triggered.includes("RULE_04") || file.rules_triggered.includes("RULE_09");

    return (
        <div className="max-w-7xl mx-auto p-8 space-y-6 animate-fade-in-up">
            {/* HEADER */}
            <header className="flex justify-between items-center border-b border-[#1E2D3D] pb-4">
                <button onClick={onBack} className="flex items-center gap-2 text-[#8B9BB4] hover:text-[#00D4FF] transition font-mono text-sm">
                    <ArrowLeft className="w-4 h-4" /> Back to Dashboard
                </button>
                <div className="flex items-center gap-3">
                    <button className="flex items-center gap-2 border border-[#1E2D3D] bg-[#0D1117] text-[#8B9BB4] px-4 py-2 rounded-lg text-sm font-mono hover:text-white hover:border-[#00D4FF]/30 transition">
                        <Copy className="w-3 h-3" /> COPY EVIDENCE
                    </button>
                    <button className="flex items-center gap-2 bg-[#00D4FF]/10 border border-[#00D4FF]/30 text-[#00D4FF] px-4 py-2 rounded-lg text-sm font-mono hover:bg-[#00D4FF]/20 transition">
                        <FileDown className="w-3 h-3" /> EXPORT
                    </button>
                </div>
            </header>

            {/* FILE HEADER CARD */}
            <div className="rounded-xl border border-[#FF2D2D]/30 p-6 flex justify-between items-start"
                style={{ background: 'linear-gradient(135deg, #111927 0%, rgba(255,45,45,0.05) 100%)' }}>
                <div>
                    <h1 className="text-3xl font-mono font-bold text-[#00D4FF] mb-2 flex items-center gap-3">
                        <FileWarning className="w-8 h-8 text-[#FF2D2D]" />
                        {file.filename}
                    </h1>
                    <div className="flex gap-5 text-sm font-mono text-[#8B9BB4]">
                        <span>MFT Entry: #{file.mft_entry}</span>
                        <span>Size: {(file.size_bytes / 1024).toFixed(2)} KB</span>
                        <span>Cluster: {file.evidence.cluster}</span>
                    </div>
                </div>
                <div className="text-right flex flex-col items-end gap-1">
                    <span className={`px-4 py-1.5 rounded text-sm font-bold font-mono ${file.risk_level === 'CRITICAL'
                        ? 'bg-[#FF2D2D] text-white shadow-[0_0_15px_rgba(255,45,45,0.4)]'
                        : 'bg-[#FF8C00] text-white'
                        }`}>{file.risk_level}</span>
                    <span className="text-[#8B9BB4] font-mono text-sm">{file.confidence_score}% Confidence</span>
                </div>
            </div>

            {/* LIVE TAMPERING BADGE */}
            {hasLiveTampering && (
                <div className="bg-[#FF2D2D]/5 border border-[#FF2D2D]/40 p-4 rounded-xl flex items-center gap-4 animate-glow-red">
                    <div className="bg-[#FF2D2D] p-3 rounded-full text-white shadow-[0_0_20px_rgba(255,45,45,0.4)]">
                        <Zap className="w-7 h-7" />
                    </div>
                    <div>
                        <h2 className="text-[#FF2D2D] font-bold text-lg tracking-wider font-mono">⚡ LIVE TAMPERING DETECTED</h2>
                        <p className="text-[#8B9BB4] font-mono text-sm">
                            Tampering occurred on a running system &bull; Evidence: LSN sequence gap + missing USN reason code
                        </p>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-2 gap-6">
                {/* LEFT COLUMN */}
                <div className="space-y-6">
                    {/* SECTION 1: TIMESTAMP COMPARISON */}
                    <div className="rounded-xl border border-[#1E2D3D] overflow-hidden" style={{ background: '#111927' }}>
                        <h3 className="p-4 text-sm font-bold text-white uppercase tracking-wider border-b border-[#1E2D3D] bg-[#0D1117] flex items-center gap-2">
                            <Search className="w-4 h-4 text-[#00D4FF]" /> TIMESTAMP COMPARISON
                        </h3>
                        <table className="w-full text-left font-mono text-sm">
                            <thead className="bg-[#050810] text-[#8B9BB4] text-xs uppercase tracking-wider">
                                <tr>
                                    <th className="p-3">Source</th>
                                    <th className="p-3">Created</th>
                                    <th className="p-3">Modified</th>
                                    <th className="p-3">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {file.timestamp_comparison.map((ts, idx) => (
                                    <tr key={idx} className={`border-t border-[#1E2D3D]/50 ${ts.status.includes('Sus') ? 'bg-[#FF2D2D]/5' : ''}`}>
                                        <td className="p-3 font-bold text-[#00D4FF]">{ts.source}</td>
                                        <td className="p-3 text-[#8B9BB4]">{ts.created}</td>
                                        <td className="p-3 text-[#8B9BB4]">{ts.modified}</td>
                                        <td className={`p-3 font-bold ${ts.status.includes('Sus') ? 'text-[#FF2D2D]' : 'text-[#00FF88]'}`}>
                                            {ts.status.includes('Sus') ? '🔴 SUSPICIOUS' : '🟢 VERIFIED'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* SECTION 2: $LOGFILE TRANSACTION ANALYSIS */}
                    <div className="rounded-xl border border-[#1E2D3D] overflow-hidden" style={{ background: '#111927' }}>
                        <h3 className="p-4 text-sm font-bold text-[#00D4FF] uppercase tracking-wider border-b border-[#1E2D3D] bg-[#0D1117] flex items-center gap-2">
                            <Database className="w-4 h-4" /> $LOGFILE TRANSACTION ANALYSIS
                        </h3>
                        <div className="p-5 space-y-4 font-mono text-sm">
                            <table className="w-full text-left">
                                <thead className="text-[#8B9BB4] text-xs uppercase tracking-wider border-b border-[#1E2D3D]/50">
                                    <tr>
                                        <th className="pb-2">LSN</th>
                                        <th className="pb-2">Operation</th>
                                        <th className="pb-2">Timestamp</th>
                                        <th className="pb-2">Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(file.logfile_analysis?.transactions || []).map((tx, idx) => (
                                        <tr key={idx} className={`border-t border-[#1E2D3D]/30 ${tx.status === 'GAP' ? 'bg-[#FF2D2D]/5' : ''}`}>
                                            <td className={`py-2.5 ${tx.status === 'GAP' ? 'text-[#FF2D2D] font-bold' : 'text-[#8B9BB4]'}`}>{tx.lsn}</td>
                                            <td className="text-white">{tx.operation}</td>
                                            <td className="text-[#8B9BB4]">{tx.timestamp}</td>
                                            <td className={tx.status === 'GAP' ? 'text-[#FF2D2D] font-bold' : 'text-[#00FF88]'}>
                                                {tx.status === 'GAP' ? '⚠️ GAP' : '✅ OK'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            {file.logfile_analysis?.gap_detected && (
                                <div className="bg-[#FF2D2D]/5 border border-[#FF2D2D]/20 p-3 rounded-lg">
                                    <p className="text-[#FF2D2D]">{file.logfile_analysis.gap_detail}</p>
                                    <p className="text-[#8B9BB4] text-xs mt-1">Missing entries indicate log manipulation or live tampering.</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* SECTION 3: USN JOURNAL CORRELATION */}
                    <div className="rounded-xl border border-[#1E2D3D] overflow-hidden" style={{ background: '#111927' }}>
                        <h3 className="p-4 text-sm font-bold text-[#00D4FF] uppercase tracking-wider border-b border-[#1E2D3D] bg-[#0D1117] flex items-center gap-2">
                            <Database className="w-4 h-4" /> $USN JOURNAL CORRELATION
                        </h3>
                        <div className="grid grid-cols-2 divide-x divide-[#1E2D3D]">
                            {/* PRESENT */}
                            <div className="p-4">
                                <h4 className="text-xs text-[#00FF88] font-bold mb-3 uppercase tracking-wider">✅ ENTRIES PRESENT</h4>
                                <div className="space-y-2">
                                    {(file.usn_analysis?.present || []).map((entry, idx) => (
                                        <div key={idx} className="bg-[#00FF88]/5 border border-[#00FF88]/20 p-3 rounded font-mono text-sm">
                                            <span className="text-[#8B9BB4]">{entry.usn_seq ? `0x${Number(entry.usn_seq).toString(16).toUpperCase()}` : ''}</span>
                                            <span className="text-white ml-2">{entry.reason}</span>
                                            <span className="text-[#8B9BB4] ml-2">{(entry.timestamp || '').slice(0, 10)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            {/* MISSING */}
                            <div className="p-4">
                                <h4 className="text-xs text-[#FF2D2D] font-bold mb-3 uppercase tracking-wider">❌ ENTRIES MISSING</h4>
                                <div className="space-y-2">
                                    {(file.usn_analysis?.missing || []).length > 0 ? (
                                        file.usn_analysis.missing.map((entry, idx) => (
                                            <div key={idx} className="border border-dashed border-[#FF2D2D]/30 p-3 rounded font-mono text-sm bg-[#FF2D2D]/5">
                                                <span className="text-[#FF2D2D] font-bold">[MISSING]</span>
                                                <span className="text-[#8B9BB4] ml-2">{entry.reason}</span>
                                                <span className="text-[#FF2D2D] ml-2">⚠️</span>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-[#00FF88] font-mono text-sm p-3">No missing entries</div>
                                    )}
                                </div>
                            </div>
                        </div>
                        {file.usn_analysis?.conclusion && (
                            <div className={`p-4 border-t font-mono text-sm ${file.usn_analysis.missing?.length > 0
                                ? 'bg-[#FF2D2D]/5 border-[#FF2D2D]/20'
                                : 'bg-[#00FF88]/5 border-[#00FF88]/20'
                            }`}>
                                <p className={file.usn_analysis.missing?.length > 0 ? 'text-[#FF2D2D] font-bold' : 'text-[#00FF88]'}>
                                    {file.usn_analysis.conclusion}
                                </p>
                            </div>
                        )}
                    </div>
                </div>

                {/* RIGHT COLUMN */}
                <div className="space-y-6">
                    {/* SECTION 4: RULES TRIGGERED */}
                    <div className="rounded-xl border border-[#1E2D3D] overflow-hidden" style={{ background: '#111927' }}>
                        <h3 className="p-4 text-sm font-bold text-[#FF2D2D] uppercase tracking-wider border-b border-[#1E2D3D] bg-[#0D1117]">
                            RULES TRIGGERED ({file.rules_triggered.length})
                        </h3>
                        <div className="p-4 space-y-3 max-h-[500px] overflow-y-auto">
                            {file.rules_triggered.map(rule => {
                                const sev = RULE_SEVERITIES[rule] || 'MEDIUM';
                                const col = SEV_COLORS[sev];
                                return (
                                    <div key={rule} className="p-3 rounded-lg border border-[#1E2D3D] bg-[#0D1117]">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="font-mono font-bold text-sm text-white">{rule}</span>
                                            <span className="text-xs px-2 py-0.5 rounded font-mono font-bold" style={{ color: col.text, background: `${col.bg}15`, border: `1px solid ${col.bg}40` }}>
                                                {sev}
                                            </span>
                                        </div>
                                        <p className="text-xs text-[#8B9BB4] leading-relaxed">{RULE_DESCRIPTIONS[rule]}</p>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* SECTION 5: EVIDENCE REFERENCES */}
                    <div className="rounded-xl border border-[#1E2D3D] overflow-hidden" style={{ background: '#111927' }}>
                        <h3 className="p-4 text-sm font-bold text-white uppercase tracking-wider border-b border-[#1E2D3D] bg-[#0D1117] flex items-center gap-2">
                            <Shield className="w-4 h-4 text-[#00D4FF]" /> EVIDENCE REFERENCES
                        </h3>
                        <div className="p-5 font-mono text-sm bg-[#050810] rounded-b-xl space-y-3">
                            <EvidenceRow label="USN Record ID" value={file.evidence.usn_record_id || 'N/A'} />
                            <EvidenceRow label="LogFile LSN" value={file.evidence.logfile_lsn || 'N/A'} />
                            <EvidenceRow label="MFT Sequence" value={file.evidence.mft_sequence || 'N/A'} />
                            <EvidenceRow label="Cluster" value={file.evidence.cluster || 'N/A'} />
                        </div>
                    </div>
                </div>
            </div>

            {/* SECTION 6: COURT EXPLANATION */}
            <div className="rounded-xl overflow-hidden border border-[#1E2D3D]">
                <h3 className="p-4 text-sm font-bold text-white uppercase tracking-wider border-b border-[#1E2D3D] bg-[#0D1117] flex items-center gap-2">
                    <Eye className="w-4 h-4 text-[#00D4FF]" /> COURT EXPLANATION
                    <span className="text-xs font-normal text-[#8B9BB4] ml-2">(Plain English for juries/reports)</span>
                </h3>
                <div className="p-8 relative" style={{ background: '#FAFAFA' }}>
                    {/* Watermark */}
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.04] select-none">
                        <span className="text-6xl font-bold text-black rotate-[-30deg] tracking-[0.3em]">FORENSIC</span>
                    </div>
                    <div className="relative border-l-4 border-[#00D4FF] pl-6">
                        <p className="text-gray-800 text-base leading-relaxed" style={{ fontFamily: "'Georgia', serif" }}>
                            "{file.court_explanation}"
                        </p>
                        <p className="text-gray-400 text-xs mt-4 italic" style={{ fontFamily: "'Georgia', serif" }}>
                            This document is forensically generated by ChronoTrace v1.0
                        </p>
                    </div>
                </div>
            </div>

            {/* QUICK NAVIGATION */}
            <div className="flex gap-4 justify-center pt-4">
                <button onClick={onBack} className="flex items-center gap-2 text-sm border border-[#1E2D3D] text-[#8B9BB4] px-5 py-2.5 rounded-xl font-mono hover:text-[#00D4FF] hover:border-[#00D4FF]/30 transition">
                    <ArrowLeft className="w-4 h-4" /> Back to Dashboard
                </button>
                <button onClick={() => onNavigate('timeline')} className="flex items-center gap-2 text-sm border border-[#1E2D3D] text-[#8B9BB4] px-5 py-2.5 rounded-xl font-mono hover:text-[#00D4FF] hover:border-[#00D4FF]/30 transition">
                    View Timeline →
                </button>
                <button onClick={() => onNavigate('report')} className="flex items-center gap-2 text-sm border border-[#1E2D3D] text-[#8B9BB4] px-5 py-2.5 rounded-xl font-mono hover:text-[#00D4FF] hover:border-[#00D4FF]/30 transition">
                    View Report →
                </button>
            </div>
        </div>
    );
}

function EvidenceRow({ label, value }) {
    return (
        <div className="flex justify-between items-center py-1 border-b border-[#1E2D3D]/30 last:border-0">
            <span className="text-[#8B9BB4]">{label}</span>
            <span className="text-[#00D4FF] cursor-pointer hover:text-[#00FF88] transition" title="Click to copy">{String(value)}</span>
        </div>
    );
}
