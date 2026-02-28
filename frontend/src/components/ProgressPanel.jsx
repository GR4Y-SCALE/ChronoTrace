import React, { useEffect, useRef, useState } from 'react';
import { useCaseStore } from '../store/caseStore';
import { WS_BASE_URL, api } from '../api/client';
import { Activity, CheckCircle2, ChevronRight, XCircle, FileSearch, Cpu } from 'lucide-react';

export default function ProgressPanel() {
    const { currentCase, setReportData, progress, setProgress, status, setStatus, logs, addLog } = useCaseStore();
    const wsRef = useRef(null);
    const logEndRef = useRef(null);
    const [scannedCount, setScannedCount] = useState(null);

    useEffect(() => {
        if (status === 'analyzing' && currentCase?.id && !wsRef.current) {
            const ws = new WebSocket(`${WS_BASE_URL}/${currentCase.id}/progress`);
            wsRef.current = ws;

            ws.onmessage = async (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.progress !== undefined) {
                        setProgress(data.progress);
                    }
                    if (data.findings_count !== undefined) {
                        setScannedCount(prev => prev); // keep existing
                    }
                    if (data.status === 'completed') {
                        const report = await api.getReport(currentCase.id);
                        setReportData(report);
                        setStatus('completed');
                        if (wsRef.current) wsRef.current.close();
                    }
                } catch (e) {
                    const msg = event.data;
                    addLog(msg);
                    // Extract real record counts from parser messages
                    const mftMatch = msg.match(/([\d,]+)\s*records?\s*found/i);
                    const usnMatch = msg.match(/([\d,]+)\s*entries/i);
                    if (mftMatch) {
                        setScannedCount(mftMatch[1]);
                    } else if (usnMatch) {
                        const current = parseInt((usnMatch[1] || '0').replace(/,/g, ''));
                        setScannedCount(prev => {
                            const prevNum = parseInt((prev || '0').toString().replace(/,/g, ''));
                            return (prevNum + current).toLocaleString();
                        });
                    }
                }
            };

            return () => {
                if (wsRef.current) {
                    wsRef.current.close();
                    wsRef.current = null;
                }
            };
        }
    }, [status, currentCase, setProgress, setStatus, addLog, setReportData]);

    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    if (!currentCase) return null;

    return (
        <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #050810 0%, #0D1117 50%, #050810 100%)' }}>
            <div className="w-full max-w-5xl mx-auto p-8 animate-fade-in-up">
                {/* CARD */}
                <div className="rounded-xl border border-[#1E2D3D] p-8" style={{ background: '#111927' }}>

                    {/* HEADER */}
                    <div className="mb-8 border-b border-[#1E2D3D] pb-6 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-3 h-3 rounded-full bg-[#00D4FF] animate-pulse shadow-[0_0_10px_rgba(0,212,255,0.6)]" />
                            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                                ANALYZING: <span className="text-[#00D4FF] font-mono text-xl">{currentCase.device_label}</span>
                            </h1>
                        </div>
                        <span className="text-sm font-mono px-4 py-1.5 bg-[#050810] rounded-full border border-[#1E2D3D] text-[#8B9BB4]">
                            Case: {currentCase.id}
                        </span>
                    </div>

                    {/* PROGRESS BAR */}
                    <div className="mb-10">
                        <div className="flex justify-between text-sm font-mono mb-2">
                            <span className="text-[#8B9BB4]">Overall Progress</span>
                            <span className="text-[#00D4FF] font-bold">{progress}%</span>
                        </div>
                        <div className="w-full bg-[#050810] rounded-full h-5 overflow-hidden border border-[#1E2D3D] relative">
                            <div
                                className="h-full transition-all duration-500 rounded-full progress-shimmer"
                                style={{
                                    width: `${progress}%`,
                                    background: `linear-gradient(90deg, #00D4FF 0%, ${progress > 70 ? '#00FF88' : '#00D4FF'} 100%)`,
                                    boxShadow: `0 0 15px rgba(0,212,255,0.5), 0 0 30px rgba(0,212,255,0.2)`
                                }}
                            />
                        </div>
                    </div>

                    {/* MAIN GRID */}
                    <div className="grid grid-cols-3 gap-6 mb-8">
                        {/* LOG PANEL */}
                        <div className="col-span-2 space-y-2">
                            <h3 className="text-xs font-mono text-[#8B9BB4] flex items-center gap-2 uppercase tracking-widest mb-3">
                                <ChevronRight className="w-3 h-3 text-[#00D4FF]" /> LIVE EXECUTION LOG
                            </h3>
                            <div className="bg-[#050810] border border-[#1E2D3D] rounded-lg p-4 h-64 overflow-y-auto font-mono text-sm shadow-inner relative">
                                {logs.length === 0 && (
                                    <span className="text-[#8B9BB4] animate-pulse flex items-center gap-2">
                                        <Cpu className="w-4 h-4" /> Initializing forensic engine...
                                    </span>
                                )}
                                {logs.map((log, i) => (
                                    <div key={i} className="mb-1.5 flex gap-2 animate-slide-in" style={{ animationDelay: `${i * 0.05}s` }}>
                                        <span className="text-[#1E2D3D] select-none">[{new Date().toISOString().substring(11, 19)}]</span>
                                        <span className={
                                            log.includes('✅') ? 'text-[#00FF88]' :
                                                log.includes('🔴') ? 'text-[#FF2D2D]' :
                                                    log.includes('⏳') ? 'text-[#00D4FF]' :
                                                        log.includes('⚙️') ? 'text-[#FF8C00]' :
                                                            'text-[#8B9BB4]'
                                        }>{log}</span>
                                    </div>
                                ))}
                                <div ref={logEndRef} />
                            </div>
                        </div>

                        {/* MODULE STATUS */}
                        <div className="space-y-6">
                            <div>
                                <h3 className="text-xs font-mono text-[#8B9BB4] mb-4 uppercase tracking-widest">Module Status</h3>
                                <div className="space-y-3">
                                    <ModuleCard label="Parser" active={progress >= 0 && progress < 40} done={progress >= 40} />
                                    <ModuleCard label="Correlator" active={progress >= 40 && progress < 70} done={progress >= 70} />
                                    <ModuleCard label="Detector" active={progress >= 70 && progress < 90} done={progress >= 90} />
                                    <ModuleCard label="Timeline" active={progress >= 90 && progress < 100} done={progress >= 100} />
                                    <ModuleCard label="Reporter" active={progress === 100} done={progress === 100} />
                                </div>
                            </div>

                            <div className="rounded-lg p-4 border border-[#1E2D3D]" style={{ background: '#0D1117' }}>
                                <div className="flex items-center gap-2 text-[#8B9BB4] text-xs font-mono mb-2 uppercase tracking-wider">
                                    <FileSearch className="w-3 h-3" /> Objects Scanned
                                </div>
                                <div className="text-3xl font-mono font-bold text-[#00D4FF]">
                                    {scannedCount || '...'}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* CANCEL */}
                    <div className="flex justify-end pt-6 border-t border-[#1E2D3D]">
                        <button
                            onClick={() => {
                                if (wsRef.current) wsRef.current.close();
                                setStatus('idle');
                            }}
                            className="flex items-center gap-2 px-6 py-2.5 border border-[#FF2D2D]/30 text-[#FF2D2D] hover:bg-[#FF2D2D]/10 rounded-lg font-mono text-sm transition-all"
                        >
                            <XCircle className="w-4 h-4" />
                            CANCEL ANALYSIS
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

function ModuleCard({ label, active, done }) {
    return (
        <div
            className={`flex items-center justify-between p-3 rounded-lg border transition-all duration-300 ${done
                    ? 'bg-[#00FF88]/5 border-[#00FF88]/30 text-[#00FF88]'
                    : active
                        ? 'bg-[#00D4FF]/5 border-[#00D4FF]/30 text-[#00D4FF] animate-glow-cyan'
                        : 'bg-[#050810] border-[#1E2D3D] text-[#8B9BB4]'
                }`}
        >
            <span className="font-mono text-sm font-medium">{label}</span>
            {done ? (
                <CheckCircle2 className="w-4 h-4 animate-counter-pop" />
            ) : active ? (
                <Activity className="w-4 h-4 animate-spin" />
            ) : (
                <div className="w-4 h-4 rounded-full border border-dashed border-[#1E2D3D]" />
            )}
        </div>
    );
}
