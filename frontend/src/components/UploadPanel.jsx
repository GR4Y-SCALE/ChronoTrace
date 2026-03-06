import React, { useState, useRef, useEffect } from 'react';
import { api } from '../api/client';
import { useCaseStore } from '../store/caseStore';
import { UploadCloud, Zap, Shield } from 'lucide-react';

// Lightweight particle canvas
function ParticleBackground() {
    const canvasRef = useRef(null);
    useEffect(() => {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        let animId;
        const particles = [];
        const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
        resize();
        window.addEventListener('resize', resize);
        for (let i = 0; i < 60; i++) {
            particles.push({
                x: Math.random() * canvas.width, y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4,
                r: Math.random() * 1.5 + 0.5
            });
        }
        const draw = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            for (let i = 0; i < particles.length; i++) {
                const p = particles[i];
                p.x += p.vx; p.y += p.vy;
                if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
                if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(0,212,255,0.5)';
                ctx.fill();
                for (let j = i + 1; j < particles.length; j++) {
                    const q = particles[j];
                    const dx = p.x - q.x, dy = p.y - q.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < 120) {
                        ctx.beginPath();
                        ctx.moveTo(p.x, p.y);
                        ctx.lineTo(q.x, q.y);
                        ctx.strokeStyle = `rgba(0,212,255,${0.15 * (1 - dist / 120)})`;
                        ctx.lineWidth = 0.5;
                        ctx.stroke();
                    }
                }
            }
            animId = requestAnimationFrame(draw);
        };
        draw();
        return () => { cancelAnimationFrame(animId); window.removeEventListener('resize', resize); };
    }, []);
    return <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none z-0" />;
}

export default function UploadPanel() {
    const { setCase, setStatus, setProgress, clearLogs } = useCaseStore();
    const [files, setFiles] = useState([]);
    const [dragging, setDragging] = useState(false);
    const [formData, setFormData] = useState({
        investigator: '',
        device_label: '',
        notes: ''
    });

    // Derived state
    const fileReady = files.length > 0;

    const normalizeAndSortSegments = (fileList) => {
        const picked = Array.from(fileList || []);
        const ewfFiles = picked.filter((f) => /\.e\d\d$/i.test(f.name));
        ewfFiles.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }));
        return ewfFiles;
    };

    const handleFileSelect = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            setFiles(normalizeAndSortSegments(e.target.files));
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            setFiles(normalizeAndSortSegments(e.dataTransfer.files));
        }
    };

    const handleStart = async () => {
        if (files.length === 0 || !formData.investigator || !formData.device_label) return;
        try {
            setStatus('uploading');
            clearLogs();
            setProgress(0);
            const newCase = await api.createCase(formData);
            setCase(newCase);
            for (const file of files) {
                await api.uploadImage(newCase.id, file);
            }
            setStatus('analyzing');
            await api.startAnalysis(newCase.id);
        } catch (err) {
            console.error(err);
            setStatus('error');
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center relative overflow-hidden" style={{ background: 'linear-gradient(135deg, #050810 0%, #0D1117 50%, #050810 100%)' }}>
            <ParticleBackground />

            <div className="relative z-10 w-full max-w-3xl mx-auto p-8 animate-fade-in-up">
                {/* HEADER */}
                <div className="text-center mb-10">
                    <div className="flex items-center justify-center gap-3 mb-3">
                        <Zap className="w-10 h-10 text-[#00D4FF] drop-shadow-[0_0_10px_rgba(0,212,255,0.6)]" />
                        <h1 className="text-4xl font-bold tracking-tight text-white" style={{ fontFamily: 'Inter' }}>
                            CHRONO<span className="text-[#00D4FF]">TRACE</span>
                        </h1>
                    </div>
                    <p className="text-[#8B9BB4] font-mono text-sm tracking-widest">NTFS Forensic Artifact Correlation Engine</p>
                </div>

                {/* CARD */}
                <div className="rounded-xl border border-[#1E2D3D] p-8" style={{ background: 'linear-gradient(180deg, #111927 0%, #0D1117 100%)' }}>

                    {/* DROP ZONE */}
                    <div
                        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                        onDragLeave={() => setDragging(false)}
                        onDrop={handleDrop}
                        onClick={() => document.getElementById('file-upload').click()}
                        className={`relative w-full border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-all duration-300 mb-8 overflow-hidden py-8 ${dragging
                            ? 'drop-zone-active border-[#00D4FF]'
                            : 'border-[#1E2D3D] hover:border-[#00D4FF]/50'
                            }`}
                        style={{ background: dragging ? 'rgba(0,212,255,0.05)' : 'rgba(5,8,16,0.6)' }}
                    >
                        {/* Scan line */}
                        <div className="absolute inset-0 pointer-events-none overflow-hidden">
                            <div className="absolute h-full w-1/3 bg-gradient-to-r from-transparent via-[#00D4FF]/10 to-transparent animate-scan" />
                        </div>

                        <UploadCloud className="w-12 h-12 text-[#00D4FF]/70 mb-3" />
                        <h2 className="text-lg font-semibold text-white mb-1 font-mono">
                            DROP DISK IMAGE FILES
                        </h2>
                        <p className="text-[#8B9BB4] text-xs mb-4 font-mono">
                            Supports split EWF sets (.E01, .E02, .E03, ...)
                        </p>
                        <button className="px-6 py-2 border border-[#1E2D3D] bg-[#111927] text-[#00D4FF] rounded-md font-mono text-sm hover:bg-[#1E2D3D] transition">
                            BROWSE FILES
                        </button>
                        <input
                            id="file-upload"
                            type="file"
                            className="hidden"
                            multiple
                            onChange={handleFileSelect}
                        />
                        <div className="mt-4 flex gap-6 text-xs font-mono">
                            <span className={files.length > 0 ? 'text-[#00FF88]' : 'text-[#8B9BB4]'}>
                                {files.length > 0
                                    ? `✅ ${files.length} file(s) selected — ${(files.reduce((a, f) => a + f.size, 0) / 1024 / 1024).toFixed(1)} MB`
                                    : '⬜ No files selected'}
                            </span>
                        </div>
                    </div>

                    {/* FORM FIELDS */}
                    <div className="grid grid-cols-2 gap-4 mb-6">
                        <InputField label="Investigator" value={formData.investigator} onChange={(v) => setFormData({ ...formData, investigator: v })} placeholder="e.g. John Doe" />
                        <InputField label="Device Label" value={formData.device_label} onChange={(v) => setFormData({ ...formData, device_label: v })} placeholder='e.g. "Suspect-Device2"' />
                        <InputField label="Case ID" value="" onChange={() => { }} placeholder="Auto-generated" disabled />
                        <div>
                            <label className="block text-xs text-[#8B9BB4] mb-1.5 font-mono uppercase tracking-wider">Notes</label>
                            <textarea
                                className="w-full bg-[#050810] border border-[#1E2D3D] rounded-lg px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF]/30 h-[38px] resize-none transition"
                                value={formData.notes}
                                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                                placeholder="Case context..."
                            />
                        </div>
                    </div>

                    {/* LAUNCH BUTTON */}
                    <button
                        onClick={handleStart}
                        disabled={!fileReady || !formData.investigator || !formData.device_label}
                        className="w-full py-4 rounded-xl font-bold text-lg transition-all duration-300 flex items-center justify-center gap-3 disabled:opacity-30 disabled:cursor-not-allowed group"
                        style={{
                            background: (!fileReady || !formData.investigator || !formData.device_label)
                                ? '#1E2D3D'
                                : 'linear-gradient(135deg, #FF2D2D 0%, #FF0000 100%)',
                            boxShadow: (!fileReady || !formData.investigator || !formData.device_label)
                                ? 'none'
                                : '0 0 20px rgba(255,45,45,0.3), 0 0 60px rgba(255,45,45,0.1)'
                        }}
                    >
                        <span className="text-white text-xl">🚀</span>
                        <span className="text-white tracking-wider">LAUNCH ANALYSIS</span>
                    </button>

                    {/* FOOTER */}
                    <div className="mt-6 text-center">
                        <div className="h-px bg-gradient-to-r from-transparent via-[#1E2D3D] to-transparent mb-4" />
                        <p className="text-[#8B9BB4] text-xs font-mono flex items-center justify-center gap-2">
                            <Shield className="w-3 h-3" /> SHA-256 integrity hash auto-computed on upload
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}

function InputField({ label, value, onChange, placeholder, disabled }) {
    return (
        <div>
            <label className="block text-xs text-[#8B9BB4] mb-1.5 font-mono uppercase tracking-wider">{label}</label>
            <input
                className="w-full bg-[#050810] border border-[#1E2D3D] rounded-lg px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF]/30 transition disabled:opacity-40"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                disabled={disabled}
            />
        </div>
    );
}
