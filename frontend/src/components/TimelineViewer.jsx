import React from 'react';
import { useCaseStore } from '../store/caseStore';
import { Calendar, Download, ZoomIn, LayoutDashboard, CheckSquare } from 'lucide-react';

export default function TimelineViewer({ onNavigate }) {
    const { reportData } = useCaseStore();

    if (!reportData) return null;
    const { timeline_events } = reportData;

    // Format a datetime string to show both date and time
    const fmtDt = (evt) => {
        const dt = evt.datetime || evt.date || '';
        if (dt.length > 10) return dt.slice(0, 10) + ' ' + dt.slice(11, 19);
        const t = evt.time || '';
        if (t && t !== '00:00:00') return dt + ' ' + t;
        return dt;
    };

    // Separate claimed (fake) vs verified (real) events
    const claimed = timeline_events.filter(e => e.type === 'claimed');
    const verified = timeline_events.filter(e => e.type === 'verified');

    return (
        <div className="space-y-8 animate-fade-in-up">
            {/* HEADER */}
            <header className="flex justify-between items-center border-b border-[#1E2D3D] pb-5">
                <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                    <Calendar className="w-7 h-7 text-[#00D4FF] drop-shadow-[0_0_8px_rgba(0,212,255,0.5)]" />
                    TIMELINE RECONSTRUCTION
                </h1>
                <button className="flex items-center gap-2 bg-[#00D4FF]/10 border border-[#00D4FF]/30 text-[#00D4FF] px-4 py-2 rounded-lg text-sm font-mono hover:bg-[#00D4FF]/20 transition">
                    <Download className="w-4 h-4" /> EXPORT TIMELINE
                </button>
            </header>

            {/* HORIZONTAL TIMELINE */}
            <div className="rounded-xl border border-[#1E2D3D] p-8 overflow-hidden" style={{ background: '#111927' }}>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-8">Full Width Horizontal Timeline</h3>

                {/* CLAIMED (FAKE) - TOP */}
                <div className="mb-3">
                    <span className="text-xs font-mono text-[#FF2D2D] uppercase tracking-widest">❌ Claimed (Fabricated) Events</span>
                </div>
                <div className="relative h-24">
                    <div className="absolute inset-x-0 top-1/2 h-px bg-[#FF2D2D]/30 border-t border-dashed border-[#FF2D2D]/40" />
                    {claimed.map((evt, i) => (
                        <div
                            key={i}
                            className="absolute flex flex-col items-center animate-dot-appear group"
                            style={{
                                left: `${15 + i * 25}%`,
                                top: '50%',
                                transform: 'translate(-50%, -50%)',
                                animationDelay: `${i * 0.3}s`
                            }}
                        >
                            <div className="w-4 h-4 rounded-full bg-[#FF2D2D] shadow-[0_0_10px_rgba(255,45,45,0.6)] z-10" />
                            <div className="absolute -top-16 bg-[#050810] border border-[#FF2D2D]/30 rounded-lg p-2 text-xs font-mono text-[#FF2D2D] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-20">
                                <div className="font-bold">{fmtDt(evt)}</div>
                                <div className="text-[#8B9BB4] max-w-[200px] truncate">{evt.title}</div>
                            </div>
                            <span className="text-xs font-mono text-[#FF2D2D] mt-2 whitespace-nowrap">{fmtDt(evt)}</span>
                        </div>
                    ))}
                </div>

                {/* DIVIDER */}
                <div className="flex items-center gap-4 my-4">
                    <div className="flex-1 h-px bg-gradient-to-r from-[#FF2D2D]/20 via-[#1E2D3D] to-[#00FF88]/20" />
                    <span className="text-xs font-mono text-[#8B9BB4] shrink-0 px-3 py-1 bg-[#050810] rounded border border-[#1E2D3D]">TRUTH ↕ LIES</span>
                    <div className="flex-1 h-px bg-gradient-to-r from-[#00FF88]/20 via-[#1E2D3D] to-[#FF2D2D]/20" />
                </div>

                {/* VERIFIED (REAL) - BOTTOM */}
                <div className="mb-3">
                    <span className="text-xs font-mono text-[#00FF88] uppercase tracking-widest">✅ Verified (Real) Events</span>
                </div>
                <div className="relative h-24">
                    <div className="absolute inset-x-0 top-1/2 h-px bg-[#00FF88]/30" />
                    {verified.map((evt, i) => (
                        <div
                            key={i}
                            className="absolute flex flex-col items-center animate-dot-appear group"
                            style={{
                                left: `${60 + i * 15}%`,
                                top: '50%',
                                transform: 'translate(-50%, -50%)',
                                animationDelay: `${(claimed.length + i) * 0.3}s`
                            }}
                        >
                            <div className="w-4 h-4 rounded-full bg-[#00FF88] shadow-[0_0_10px_rgba(0,255,136,0.6)] z-10" />
                            <div className="absolute -bottom-16 bg-[#050810] border border-[#00FF88]/30 rounded-lg p-2 text-xs font-mono text-[#00FF88] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-20">
                                <div className="font-bold">{fmtDt(evt)}</div>
                                <div className="text-[#8B9BB4] max-w-[200px] truncate">{evt.title}</div>
                            </div>
                            <span className="text-xs font-mono text-[#00FF88] mt-2 whitespace-nowrap">{fmtDt(evt)}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* VERTICAL TIMELINE */}
            <div className="rounded-xl border border-[#1E2D3D] p-8" style={{ background: '#111927' }}>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-6">Event Details</h3>
                <div className="relative border-l-2 border-[#1E2D3D] ml-6 space-y-8 pb-4">
                    {timeline_events.map((evt, idx) => (
                        <div key={idx} className="relative animate-slide-in" style={{ animationDelay: `${idx * 0.15}s` }}>
                            <div className={`absolute -left-3 top-1.5 w-5 h-5 rounded-full border-4 border-[#111927] ${evt.risk === 'CRITICAL' ? 'bg-[#FF2D2D] shadow-[0_0_8px_rgba(255,45,45,0.5)]'
                                : evt.risk === 'HIGH' ? 'bg-[#FF8C00] shadow-[0_0_8px_rgba(255,140,0,0.5)]'
                                    : 'bg-[#FFD700] shadow-[0_0_8px_rgba(255,215,0,0.5)]'
                                }`} />
                            <div className="ml-8">
                                <span className="text-xs font-mono text-[#8B9BB4] bg-[#050810] px-2 py-1 rounded border border-[#1E2D3D]">{fmtDt(evt)}</span>
                                <div className="mt-2 bg-[#0D1117] border border-[#1E2D3D] p-4 rounded-xl">
                                    <h4 className="text-sm font-bold text-[#00D4FF] mb-1">{evt.title}</h4>
                                    <p className="text-[#8B9BB4] text-sm">{evt.description}</p>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* VERDICT BOX — driven by report data */}
            {(() => {
                // Compute verdict from actual timeline events
                const claimedDates = claimed.map(e => e.datetime || e.date).filter(Boolean).sort();
                const verifiedDates = verified.map(e => e.datetime || e.date).filter(Boolean).sort();
                const trueArrival = verifiedDates.length > 0 ? verifiedDates[0].slice(0, 10) : 'N/A';
                const claimedHistory = claimedDates.length > 0 ? claimedDates[0].slice(0, 10) : 'N/A';
                let gapDays = 0;
                if (trueArrival !== 'N/A' && claimedHistory !== 'N/A') {
                    const d1 = new Date(trueArrival);
                    const d2 = new Date(claimedHistory);
                    gapDays = Math.round(Math.abs((d1 - d2) / (1000 * 60 * 60 * 24)));
                }
                const maxConf = reportData.findings?.reduce((max, f) => Math.max(max, f.confidence_score || 0), 0) || 0;
                return (
                    <div className="rounded-xl border border-[#FF2D2D]/30 overflow-hidden" style={{ background: '#111927' }}>
                        <div className="p-4 bg-[#0D1117] border-b border-[#1E2D3D]">
                            <h3 className="text-sm font-bold text-[#FF2D2D] uppercase tracking-wider flex items-center gap-2">
                                <ZoomIn className="w-4 h-4" /> TIMELINE VERDICT
                            </h3>
                        </div>
                        <div className="p-6 font-mono text-sm space-y-3">
                            <div className="flex items-center gap-4">
                                <span className="text-[#8B9BB4] w-40">TRUE ARRIVAL</span>
                                <span className="text-[#00FF88] font-bold">{trueArrival}</span>
                                <span className="text-[#00FF88]">✅</span>
                            </div>
                            <div className="flex items-center gap-4">
                                <span className="text-[#8B9BB4] w-40">CLAIMED HISTORY</span>
                                <span className="text-[#FF2D2D] font-bold">{claimedHistory}</span>
                                <span className="text-[#FF2D2D]">❌ FABRICATED</span>
                            </div>
                            <div className="flex items-center gap-4">
                                <span className="text-[#8B9BB4] w-40">FABRICATED GAP</span>
                                <span className="text-[#FF8C00] font-bold text-lg">{gapDays.toLocaleString()} days</span>
                            </div>
                            <div className="flex items-center gap-4">
                                <span className="text-[#8B9BB4] w-40">CONFIDENCE</span>
                                <span className="text-[#00D4FF] font-bold">{maxConf}%</span>
                            </div>
                        </div>
                    </div>
                );
            })()}

            {/* QUICK NAVIGATION */}
            <div className="flex gap-4 justify-center pt-4">
                <button onClick={() => onNavigate('dashboard')} className="flex items-center gap-2 text-sm border border-[#1E2D3D] text-[#8B9BB4] px-5 py-2.5 rounded-xl font-mono hover:text-[#00D4FF] hover:border-[#00D4FF]/30 transition">
                    <LayoutDashboard className="w-4 h-4" /> ← Back to Dashboard
                </button>
                <button onClick={() => onNavigate('report')} className="flex items-center gap-2 text-sm border border-[#1E2D3D] text-[#8B9BB4] px-5 py-2.5 rounded-xl font-mono hover:text-[#00D4FF] hover:border-[#00D4FF]/30 transition">
                    <CheckSquare className="w-4 h-4" /> View Full Report →
                </button>
            </div>
        </div>
    );
}
