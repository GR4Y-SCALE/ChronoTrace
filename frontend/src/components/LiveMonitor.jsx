import React, { useState, useEffect, useRef } from 'react';
import { useMonitorStore } from '../store/monitorStore';
import {
    ShieldAlert, AlertTriangle, AlertCircle, Info, Zap, Radio,
    Play, Square, Wifi, WifiOff, Clock, ChevronRight, Filter,
    Activity, Shield, Trash2, Eye, Terminal, FileWarning, HardDrive
} from 'lucide-react';

// ── Severity helpers ─────────────────────────────────────────────────

const SEV_CONFIG = {
    CRITICAL: { color: '#FF2D2D', icon: ShieldAlert, bg: 'rgba(255,45,45,0.08)', border: 'rgba(255,45,45,0.3)' },
    HIGH:     { color: '#FF8C00', icon: AlertTriangle, bg: 'rgba(255,140,0,0.08)', border: 'rgba(255,140,0,0.3)' },
    MEDIUM:   { color: '#FFD700', icon: AlertCircle, bg: 'rgba(255,215,0,0.08)', border: 'rgba(255,215,0,0.3)' },
    LOW:      { color: '#00D4FF', icon: Info, bg: 'rgba(0,212,255,0.08)', border: 'rgba(0,212,255,0.3)' },
};

const ALERT_TYPE_ICONS = {
    usn_anomaly: FileWarning,
    process_tool: Terminal,
    journal_attack: Trash2,
};

// ── Main Component ───────────────────────────────────────────────────

export default function LiveMonitor() {
    const {
        isConnected, isMonitoring, alerts, statusMessages, stats,
        connectWebSocket, startMonitor, stopMonitor, fetchRules,
        severityFilter, setSeverityFilter, fetchStats,
    } = useMonitorStore();

    const [driveLetter, setDriveLetter] = useState('C');
    const [selectedAlert, setSelectedAlert] = useState(null);
    const [showLog, setShowLog] = useState(false);
    const alertListRef = useRef(null);

    // Connect WebSocket on mount
    useEffect(() => {
        connectWebSocket();
        fetchRules();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Poll stats periodically
    useEffect(() => {
        if (!isMonitoring) return;
        const interval = setInterval(() => fetchStats(), 5000);
        return () => clearInterval(interval);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isMonitoring]);

    // Auto-scroll alert list
    useEffect(() => {
        if (alertListRef.current) {
            alertListRef.current.scrollTop = alertListRef.current.scrollHeight;
        }
    }, [alerts.length]);

    const filteredAlerts = severityFilter
        ? alerts.filter(a => a.risk_level === severityFilter)
        : alerts;

    const severityCounts = {
        CRITICAL: alerts.filter(a => a.risk_level === 'CRITICAL').length,
        HIGH: alerts.filter(a => a.risk_level === 'HIGH').length,
        MEDIUM: alerts.filter(a => a.risk_level === 'MEDIUM').length,
        LOW: alerts.filter(a => a.risk_level === 'LOW').length,
    };

    if (selectedAlert) {
        return <AlertDetail alert={selectedAlert} onBack={() => setSelectedAlert(null)} />;
    }

    return (
        <div className="space-y-6 animate-fade-in-up">
            {/* HEADER */}
            <header className="flex justify-between items-center border-b border-[#1E2D3D] pb-5">
                <h1 className="text-2xl font-bold flex items-center gap-3 text-white">
                    <Radio className={`w-7 h-7 ${isMonitoring ? 'text-[#00FF88] animate-pulse drop-shadow-[0_0_8px_rgba(0,255,136,0.5)]' : 'text-[#8B9BB4]'}`} />
                    LIVE MONITOR
                </h1>
                <div className="flex items-center gap-4">
                    {/* Connection status */}
                    <div className={`flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-full border ${
                        isConnected
                            ? 'text-[#00FF88] border-[#00FF88]/30 bg-[#00FF88]/5'
                            : 'text-[#FF2D2D] border-[#FF2D2D]/30 bg-[#FF2D2D]/5'
                    }`}>
                        {isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                        {isConnected ? 'CONNECTED' : 'DISCONNECTED'}
                    </div>

                    {/* Monitor controls */}
                    {!isMonitoring ? (
                        <div className="flex items-center gap-2">
                            <div className="flex items-center gap-1.5 bg-[#0D1117] border border-[#1E2D3D] rounded-lg px-3 py-1.5">
                                <HardDrive className="w-3.5 h-3.5 text-[#8B9BB4]" />
                                <input
                                    type="text"
                                    value={driveLetter}
                                    onChange={(e) => setDriveLetter(e.target.value.toUpperCase().replace(/[^A-Z]/g, '').slice(0, 1))}
                                    className="w-6 bg-transparent text-white font-mono text-sm text-center outline-none"
                                    maxLength={1}
                                />
                                <span className="text-[#8B9BB4] font-mono text-sm">:</span>
                            </div>
                            <button
                                onClick={() => startMonitor(driveLetter)}
                                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#00FF88]/10 text-[#00FF88] border border-[#00FF88]/30 hover:bg-[#00FF88]/20 transition font-mono text-sm font-bold"
                            >
                                <Play className="w-4 h-4" /> START
                            </button>
                        </div>
                    ) : (
                        <button
                            onClick={stopMonitor}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#FF2D2D]/10 text-[#FF2D2D] border border-[#FF2D2D]/30 hover:bg-[#FF2D2D]/20 transition font-mono text-sm font-bold"
                        >
                            <Square className="w-4 h-4" /> STOP
                        </button>
                    )}
                </div>
            </header>

            {/* MONITORING STATUS BANNER */}
            {isMonitoring && (
                <div className="bg-[#00FF88]/5 border border-[#00FF88]/30 p-4 rounded-xl flex items-center gap-4">
                    <div className="bg-[#00FF88] p-3 rounded-full text-black shadow-[0_0_20px_rgba(0,255,136,0.3)]">
                        <Shield className="w-6 h-6" />
                    </div>
                    <div className="flex-1">
                        <h2 className="text-[#00FF88] font-bold text-lg tracking-wider font-mono">
                            ● MONITORING ACTIVE — {driveLetter}:
                        </h2>
                        <p className="text-[#8B9BB4] font-mono text-sm">
                            USN Journal + Process Watcher • {alerts.length} alert{alerts.length !== 1 ? 's' : ''} •
                            {stats ? ` ${stats.usn_events_processed || 0} USN events processed` : ' Initializing...'}
                        </p>
                    </div>
                    <button
                        onClick={() => setShowLog(!showLog)}
                        className="text-[#8B9BB4] hover:text-white text-xs font-mono border border-[#1E2D3D] px-3 py-1.5 rounded-lg transition"
                    >
                        {showLog ? 'HIDE LOG' : 'SHOW LOG'}
                    </button>
                </div>
            )}

            {/* STATUS LOG */}
            {showLog && statusMessages.length > 0 && (
                <div className="rounded-xl border border-[#1E2D3D] p-4 max-h-40 overflow-y-auto font-mono text-xs" style={{ background: '#0D1117' }}>
                    {statusMessages.map((msg, i) => (
                        <div key={i} className="text-[#8B9BB4] py-0.5">
                            <span className="text-[#00D4FF]">[{msg.timestamp || msg.received_at}]</span>{' '}
                            {msg.message}
                        </div>
                    ))}
                </div>
            )}

            {/* SEVERITY CARDS */}
            <div className="grid grid-cols-4 gap-4">
                {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(sev => {
                    const cfg = SEV_CONFIG[sev];
                    const Icon = cfg.icon;
                    const isActive = severityFilter === sev;
                    return (
                        <button
                            key={sev}
                            onClick={() => setSeverityFilter(isActive ? null : sev)}
                            className={`rounded-xl border p-5 flex flex-col items-center justify-center gap-2 transition-all duration-300 cursor-pointer ${
                                isActive ? 'ring-2 ring-offset-2 ring-offset-[#050810]' : ''
                            }`}
                            style={{
                                borderColor: cfg.border,
                                background: cfg.bg,
                                boxShadow: severityCounts[sev] > 0 ? `0 0 15px ${cfg.color}20` : 'none',
                                ...(isActive ? { ringColor: cfg.color } : {}),
                            }}
                        >
                            <div className="flex items-center gap-2 text-xs font-bold tracking-widest font-mono" style={{ color: cfg.color }}>
                                {sev} <Icon className="w-4 h-4" />
                            </div>
                            <div className="text-4xl font-mono font-bold text-white">{severityCounts[sev]}</div>
                        </button>
                    );
                })}
            </div>

            {/* STATS ROW */}
            {stats && (
                <div className="grid grid-cols-3 gap-4">
                    <StatBox label="USN Events" value={stats.usn_events_processed || 0} icon={<Activity className="w-4 h-4" />} />
                    <StatBox label="Process Scans" value={stats.process_events_processed || 0} icon={<Eye className="w-4 h-4" />} />
                    <StatBox label="Uptime" value={stats.started_at ? _formatUptime(stats.started_at) : '—'} icon={<Clock className="w-4 h-4" />} />
                </div>
            )}

            {/* ALERT FEED */}
            <div className="rounded-xl border border-[#1E2D3D] overflow-hidden" style={{ background: '#111927' }}>
                <div className="p-5 border-b border-[#1E2D3D] flex justify-between items-center bg-[#0D1117]">
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                        <Zap className="w-4 h-4 text-[#00D4FF]" />
                        LIVE ALERT FEED ({filteredAlerts.length})
                    </h3>
                    {severityFilter && (
                        <button
                            onClick={() => setSeverityFilter(null)}
                            className="text-xs font-mono text-[#8B9BB4] hover:text-white border border-[#1E2D3D] px-2.5 py-1 rounded-lg transition flex items-center gap-1.5"
                        >
                            <Filter className="w-3 h-3" /> Clear Filter
                        </button>
                    )}
                </div>

                {filteredAlerts.length === 0 ? (
                    <div className="p-12 text-center">
                        <Shield className="w-12 h-12 text-[#1E2D3D] mx-auto mb-4" />
                        <p className="text-[#8B9BB4] font-mono text-sm">
                            {isMonitoring ? 'No alerts yet — monitoring for anti-forensic activity...' : 'Start the monitor to begin watching for anti-forensic activity'}
                        </p>
                    </div>
                ) : (
                    <div ref={alertListRef} className="max-h-[500px] overflow-y-auto divide-y divide-[#1E2D3D]/50">
                        {filteredAlerts.slice().reverse().map((alert) => (
                            <AlertRow key={alert.id} alert={alert} onClick={() => setSelectedAlert(alert)} />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}


// ── Sub-components ───────────────────────────────────────────────────

function AlertRow({ alert, onClick }) {
    const cfg = SEV_CONFIG[alert.risk_level] || SEV_CONFIG.MEDIUM;
    const TypeIcon = ALERT_TYPE_ICONS[alert.alert_type] || FileWarning;

    return (
        <div
            className="flex items-center gap-4 px-5 py-4 hover:bg-[#FF2D2D]/5 transition cursor-pointer group animate-slide-in"
            onClick={onClick}
        >
            {/* Severity dot */}
            <div className="w-3 h-3 rounded-full shrink-0 animate-pulse" style={{ background: cfg.color, boxShadow: `0 0 8px ${cfg.color}60` }} />

            {/* Type icon */}
            <TypeIcon className="w-5 h-5 shrink-0" style={{ color: cfg.color }} />

            {/* Content */}
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-1">
                    <span className="font-mono text-sm font-bold text-white truncate">{alert.filename}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono`}
                        style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
                        {alert.risk_level}
                    </span>
                    {alert.alert_type === 'process_tool' && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-purple-500/10 text-purple-400 border border-purple-500/30">
                            TOOL
                        </span>
                    )}
                </div>
                <p className="text-[#8B9BB4] text-xs font-mono truncate">{alert.description}</p>
            </div>

            {/* Rules */}
            <div className="text-right shrink-0">
                <div className="text-[#8B9BB4] text-xs font-mono">{alert.rules_triggered?.length || 0} rule{alert.rules_triggered?.length !== 1 ? 's' : ''}</div>
                <div className="text-[#8B9BB4] text-[10px] font-mono">{alert.timestamp}</div>
            </div>

            <ChevronRight className="w-5 h-5 text-[#1E2D3D] group-hover:text-[#00D4FF] transition shrink-0" />
        </div>
    );
}


function AlertDetail({ alert, onBack }) {
    const cfg = SEV_CONFIG[alert.risk_level] || SEV_CONFIG.MEDIUM;
    const { rules } = useMonitorStore();

    return (
        <div className="space-y-6 animate-fade-in-up">
            <button onClick={onBack} className="text-[#8B9BB4] hover:text-white font-mono text-sm transition">
                ← Back to Feed
            </button>

            {/* Header */}
            <div className="rounded-xl border p-6" style={{ borderColor: cfg.border, background: cfg.bg }}>
                <div className="flex items-center gap-4 mb-4">
                    <div className="p-3 rounded-full" style={{ background: cfg.color }}>
                        <ShieldAlert className="w-6 h-6 text-white" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-white font-mono">{alert.filename}</h2>
                        <p className="text-[#8B9BB4] text-sm font-mono">{alert.timestamp} • {alert.alert_type}</p>
                    </div>
                    <span className="ml-auto px-3 py-1.5 rounded text-sm font-bold font-mono"
                        style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
                        {alert.risk_level} — {alert.confidence_score}%
                    </span>
                </div>
                <p className="text-white font-mono text-sm leading-relaxed">{alert.description}</p>
            </div>

            {/* Timestamps */}
            {alert.timestamps && Object.keys(alert.timestamps).length > 0 && (
                <div className="rounded-xl border border-[#1E2D3D] p-6" style={{ background: '#111927' }}>
                    <h3 className="text-sm font-bold text-white mb-4 uppercase tracking-wider">Timestamp Analysis</h3>
                    <div className="grid grid-cols-2 gap-4">
                        {Object.entries(alert.timestamps).map(([key, val]) => (
                            <div key={key} className="flex justify-between items-center py-2 border-b border-[#1E2D3D]/30">
                                <span className="text-[#8B9BB4] font-mono text-xs uppercase">{key.replace(/_/g, ' ')}</span>
                                <span className={`font-mono text-sm ${
                                    key.startsWith('si_') && alert.timestamps.fn_created && val !== alert.timestamps.fn_created
                                        ? 'text-[#FF2D2D] font-bold' : 'text-white'
                                }`}>{val}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Rules Triggered */}
            <div className="rounded-xl border border-[#1E2D3D] p-6" style={{ background: '#111927' }}>
                <h3 className="text-sm font-bold text-white mb-4 uppercase tracking-wider">Rules Triggered</h3>
                <div className="space-y-3">
                    {alert.rules_triggered?.map(ruleId => {
                        const rule = rules[ruleId];
                        return (
                            <div key={ruleId} className="flex items-start gap-3 p-3 rounded-lg bg-[#050810] border border-[#1E2D3D]/50">
                                <span className="font-mono text-xs text-[#00D4FF] w-20 shrink-0 pt-0.5">{ruleId}</span>
                                <div className="flex-1">
                                    <p className="text-white font-mono text-sm font-bold">{rule?.name || ruleId}</p>
                                    <p className="text-[#8B9BB4] text-xs mt-1">{rule?.explanation || rule?.description || ''}</p>
                                </div>
                                <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded`}
                                    style={{
                                        color: SEV_CONFIG[rule?.severity]?.color || '#8B9BB4',
                                        background: SEV_CONFIG[rule?.severity]?.bg || 'transparent',
                                        border: `1px solid ${SEV_CONFIG[rule?.severity]?.border || '#1E2D3D'}`,
                                    }}>
                                    {rule?.severity || '?'}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Process Info (if tool detection) */}
            {alert.process_info && (
                <div className="rounded-xl border border-purple-500/30 p-6" style={{ background: 'rgba(168,85,247,0.05)' }}>
                    <h3 className="text-sm font-bold text-purple-400 mb-4 uppercase tracking-wider">Process Details</h3>
                    <div className="space-y-2 font-mono text-sm">
                        <Row label="PID" value={alert.process_info.pid} />
                        <Row label="Name" value={alert.process_info.name} />
                        <Row label="Command" value={alert.process_info.cmdline} highlight />
                        <Row label="User" value={alert.process_info.username} />
                    </div>
                </div>
            )}

            {/* Raw Details */}
            {alert.details && Object.keys(alert.details).length > 0 && (
                <div className="rounded-xl border border-[#1E2D3D] p-6" style={{ background: '#111927' }}>
                    <h3 className="text-sm font-bold text-white mb-4 uppercase tracking-wider">Event Details</h3>
                    <div className="space-y-2 font-mono text-sm">
                        {Object.entries(alert.details).map(([k, v]) => (
                            <Row key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}


function Row({ label, value, highlight }) {
    return (
        <div className="flex justify-between items-center py-1.5 border-b border-[#1E2D3D]/20">
            <span className="text-[#8B9BB4] text-xs uppercase">{label}</span>
            <span className={`text-sm ${highlight ? 'text-[#FF2D2D] break-all text-right max-w-[60%]' : 'text-white'}`}>{value}</span>
        </div>
    );
}


function StatBox({ label, value, icon }) {
    return (
        <div className="rounded-xl border border-[#1E2D3D] p-4 flex items-center gap-4" style={{ background: '#111927' }}>
            <div className="text-[#00D4FF]">{icon}</div>
            <div>
                <div className="text-[#8B9BB4] text-xs font-mono uppercase tracking-wider">{label}</div>
                <div className="text-white text-lg font-mono font-bold">{value}</div>
            </div>
        </div>
    );
}


function _formatUptime(startedAt) {
    try {
        const start = new Date(startedAt + 'Z');
        const now = new Date();
        const diff = Math.floor((now - start) / 1000);
        const h = Math.floor(diff / 3600);
        const m = Math.floor((diff % 3600) / 60);
        const s = diff % 60;
        if (h > 0) return `${h}h ${m}m`;
        if (m > 0) return `${m}m ${s}s`;
        return `${s}s`;
    } catch {
        return '—';
    }
}
