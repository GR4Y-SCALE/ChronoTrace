import React, { useState, useEffect } from 'react';
import { useCaseStore } from '../store/caseStore';
import { ShieldAlert, AlertTriangle, AlertCircle, Info, Download, ChevronRight, Zap, Clock, CheckSquare } from 'lucide-react';
import { generateDetailedPDF } from '../utils/pdfGenerator';

export default function Dashboard({ onSelectFile, onNavigate }) {
    const { reportData } = useCaseStore();

    if (!reportData) return null;

    const { case_info, summary, findings } = reportData;
    const hasLiveTampering = findings.some(f => f.rules_triggered.includes("RULE_04") || f.rules_triggered.includes("RULE_09"));

    return (
        <div className="space-y-6 animate-fade-in-up">
            {/* TOP BAR */}
            <header className="flex justify-between items-center border-b border-[#1E2D3D] pb-5">
                <h1 className="text-2xl font-bold flex items-center gap-3 text-white">
                    <Zap className="w-7 h-7 text-[#00D4FF] drop-shadow-[0_0_8px_rgba(0,212,255,0.5)]" />
                    CHRONOTRACE DASHBOARD
                </h1>
                <div className="flex items-center gap-4">
                    <span className="font-mono text-[#8B9BB4] text-sm border border-[#1E2D3D] px-4 py-1.5 rounded-full bg-[#050810]">
                        {case_info.id}
                    </span>
                    <span className={`px-3 py-1 rounded text-sm font-bold font-mono ${summary.overall_risk_label === 'CRITICAL'
                        ? 'bg-[#FF2D2D]/15 text-[#FF2D2D] border border-[#FF2D2D]/30'
                        : 'bg-[#FF8C00]/15 text-[#FF8C00] border border-[#FF8C00]/30'
                        }`}>
                        🔴 {summary.overall_risk_label}
                    </span>
                </div>
            </header>

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

            {/* STAT CARDS */}
            <div className="grid grid-cols-4 gap-4">
                <StatCard title="CRITICAL" count={summary.critical} color="#FF2D2D" icon={<ShieldAlert />} />
                <StatCard title="HIGH" count={summary.high} color="#FF8C00" icon={<AlertTriangle />} />
                <StatCard title="MEDIUM" count={summary.medium} color="#FFD700" icon={<AlertCircle />} />
                <StatCard title="LOW" count={summary.low} color="#00D4FF" icon={<Info />} />
            </div>

            {/* RISK SCORE */}
            <div className="rounded-xl border border-[#1E2D3D] p-6" style={{ background: '#111927' }}>
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-lg font-bold text-white">OVERALL RISK SCORE</h2>
                    <div className="text-3xl font-mono font-bold text-[#FF2D2D]">{summary.overall_risk_score}/100</div>
                </div>
                <div className="w-full bg-[#050810] rounded-full h-5 overflow-hidden border border-[#1E2D3D]">
                    <div
                        className="h-full rounded-full transition-all duration-1000 progress-shimmer"
                        style={{
                            width: `${summary.overall_risk_score}%`,
                            background: `linear-gradient(90deg, #00FF88 0%, #FFD700 40%, #FF8C00 70%, #FF2D2D 100%)`,
                            boxShadow: '0 0 15px rgba(255,45,45,0.4)'
                        }}
                    />
                </div>
            </div>

            {/* CHARTS ROW */}
            <div className="grid grid-cols-2 gap-6">
                {/* Rules Triggered */}
                <div className="rounded-xl border border-[#1E2D3D] p-6" style={{ background: '#111927' }}>
                    <h3 className="text-sm font-bold text-white mb-5 uppercase tracking-wider">Rules Triggered</h3>
                    <div className="space-y-3">
                        {Array.from(new Set(findings.map(f => f.rules_triggered).flat())).map((rule, i) => (
                            <div key={rule} className="flex items-center gap-3 animate-slide-in" style={{ animationDelay: `${i * 0.1}s` }}>
                                <span className="font-mono text-xs text-[#8B9BB4] w-20 shrink-0">{rule}</span>
                                <div className="flex-1 bg-[#050810] rounded-full h-3 overflow-hidden border border-[#1E2D3D]/50">
                                    <div className="h-full rounded-full" style={{
                                        width: '100%',
                                        background: rule.includes('15') || rule.includes('01') || rule.includes('02')
                                            ? 'linear-gradient(90deg, #FF2D2D, #FF2D2D)'
                                            : rule.includes('03') ? 'linear-gradient(90deg, #FF8C00, #FF8C00)'
                                                : 'linear-gradient(90deg, #FFD700, #FFD700)',
                                        boxShadow: `0 0 6px ${rule.includes('15') ? 'rgba(255,45,45,0.5)' : 'rgba(255,140,0,0.3)'}`
                                    }} />
                                </div>
                                <span className="text-[#FF2D2D] text-xs font-mono font-bold">HIT</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Anomaly Distribution */}
                <div className="rounded-xl border border-[#1E2D3D] p-6" style={{ background: '#111927' }}>
                    <h3 className="text-sm font-bold text-white mb-5 uppercase tracking-wider">Anomaly Category Distribution</h3>
                    <div className="flex items-center gap-8">
                        {/* Simple donut */}
                        <div className="relative w-40 h-40 shrink-0">
                            <svg viewBox="0 0 36 36" className="w-full h-full transform -rotate-90">
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#1E2D3D" strokeWidth="3" />
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#FF2D2D" strokeWidth="3"
                                    strokeDasharray="39.6 88" strokeDashoffset="0" className="drop-shadow-[0_0_4px_rgba(255,45,45,0.5)]" />
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#FF8C00" strokeWidth="3"
                                    strokeDasharray="22 88" strokeDashoffset="-39.6" className="drop-shadow-[0_0_4px_rgba(255,140,0,0.5)]" />
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#FFD700" strokeWidth="3"
                                    strokeDasharray="17.6 88" strokeDashoffset="-61.6" className="drop-shadow-[0_0_4px_rgba(255,215,0,0.5)]" />
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#00D4FF" strokeWidth="3"
                                    strokeDasharray="8.8 88" strokeDashoffset="-79.2" className="drop-shadow-[0_0_4px_rgba(0,212,255,0.5)]" />
                            </svg>
                            <div className="absolute inset-0 flex items-center justify-center">
                                <span className="font-mono text-lg font-bold text-white">{findings.length}</span>
                            </div>
                        </div>
                        <div className="space-y-3 flex-1">
                            <LegendItem color="#FF2D2D" label="Timestamp Alteration" pct={45} />
                            <LegendItem color="#FF8C00" label="Log / Journal Evasion" pct={25} />
                            <LegendItem color="#FFD700" label="Cross-Device Trace" pct={20} />
                            <LegendItem color="#00D4FF" label="Metadata Contradiction" pct={10} />
                        </div>
                    </div>
                </div>
            </div>

            {/* FLAGGED FILES TABLE */}
            <div className="rounded-xl border border-[#1E2D3D] overflow-hidden" style={{ background: '#111927' }}>
                <div className="p-5 border-b border-[#1E2D3D] flex justify-between items-center bg-[#0D1117]">
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">FLAGGED FILES ({findings.length})</h3>
                    <button
                        onClick={() => generateDetailedPDF(reportData)}
                        className="flex items-center gap-2 text-sm bg-[#00D4FF]/10 border border-[#00D4FF]/30 text-[#00D4FF] px-4 py-2 rounded-lg transition hover:bg-[#00D4FF]/20 font-mono"
                    >
                        <Download className="w-4 h-4" /> Export PDF
                    </button>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="bg-[#050810] text-[#8B9BB4] text-xs font-mono uppercase tracking-wider">
                                <th className="p-4">#</th>
                                <th className="p-4">Filename</th>
                                <th className="p-4">Risk</th>
                                <th className="p-4">Rules Hit</th>
                                <th className="p-4 text-right">Confidence</th>
                                <th className="p-4 text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {findings.map((f, i) => (
                                <tr
                                    key={f.id}
                                    className="border-t border-[#1E2D3D]/50 hover:bg-[#FF2D2D]/5 transition cursor-pointer group"
                                    onClick={() => onSelectFile(f)}
                                >
                                    <td className="p-4 text-[#8B9BB4] font-mono">{i + 1}</td>
                                    <td className="p-4 font-mono text-[#00D4FF] font-medium">{f.filename}</td>
                                    <td className="p-4">
                                        <span className={`px-2.5 py-1 rounded text-xs font-bold font-mono ${f.risk_level === 'CRITICAL'
                                            ? 'bg-[#FF2D2D]/15 text-[#FF2D2D] border border-[#FF2D2D]/30'
                                            : f.risk_level === 'HIGH'
                                                ? 'bg-[#FF8C00]/15 text-[#FF8C00] border border-[#FF8C00]/30'
                                                : 'bg-[#FFD700]/15 text-[#FFD700] border border-[#FFD700]/30'
                                            }`}>
                                            {f.risk_level}
                                        </span>
                                    </td>
                                    <td className="p-4 text-[#8B9BB4] font-mono">{f.rules_triggered.length} rules</td>
                                    <td className="p-4 text-right font-mono text-white font-bold">{f.confidence_score}%</td>
                                    <td className="p-4 text-center">
                                        <ChevronRight className="w-5 h-5 mx-auto text-[#1E2D3D] group-hover:text-[#00D4FF] transition" />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* QUICK NAVIGATION */}
            <div className="flex gap-4 justify-center pt-4">
                <button onClick={() => onNavigate('timeline')} className="flex items-center gap-2 text-sm border border-[#1E2D3D] text-[#8B9BB4] px-5 py-2.5 rounded-xl font-mono hover:text-[#00D4FF] hover:border-[#00D4FF]/30 transition">
                    <Clock className="w-4 h-4" /> View Timeline Analysis →
                </button>
                <button onClick={() => onNavigate('report')} className="flex items-center gap-2 text-sm border border-[#1E2D3D] text-[#8B9BB4] px-5 py-2.5 rounded-xl font-mono hover:text-[#00D4FF] hover:border-[#00D4FF]/30 transition">
                    <CheckSquare className="w-4 h-4" /> View Full Report →
                </button>
            </div>
        </div>
    );
}

function StatCard({ title, count, color, icon }) {
    const [display, setDisplay] = useState(0);
    useEffect(() => {
        if (count === 0) return;
        let start = 0;
        const timer = setInterval(() => {
            start++;
            setDisplay(start);
            if (start >= count) clearInterval(timer);
        }, 100);
        return () => clearInterval(timer);
    }, [count]);

    return (
        <div
            className="rounded-xl border p-5 flex flex-col items-center justify-center gap-2 transition-all duration-300"
            style={{
                borderColor: `${color}30`,
                background: `${color}08`,
                boxShadow: count > 0 ? `0 0 15px ${color}20, inset 0 0 15px ${color}05` : 'none'
            }}
        >
            <div className="flex items-center gap-2 text-xs font-bold tracking-widest font-mono" style={{ color }}>
                {title} {React.cloneElement(icon, { className: 'w-4 h-4' })}
            </div>
            <div className="text-4xl font-mono font-bold text-white animate-counter-pop">{display}</div>
        </div>
    );
}

function LegendItem({ color, label, pct }) {
    return (
        <div className="flex items-center gap-3 text-sm">
            <div className="w-3 h-3 rounded-full shrink-0" style={{ background: color, boxShadow: `0 0 6px ${color}60` }} />
            <span className="text-[#8B9BB4] flex-1">{label}</span>
            <span className="font-mono font-bold text-white">{pct}%</span>
        </div>
    );
}
