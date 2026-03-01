import React, { useState } from 'react';
import { useCaseStore } from './store/caseStore';
import { useMonitorStore } from './store/monitorStore';
import UploadPanel from './components/UploadPanel';
import ProgressPanel from './components/ProgressPanel';
import Dashboard from './components/Dashboard';
import FileDeepDive from './components/FileDeepDive';
import TimelineViewer from './components/TimelineViewer';
import ReportPanel from './components/ReportPanel';
import LiveMonitor from './components/LiveMonitor';
import {
  LayoutDashboard, Clock, CheckSquare, PlusCircle, Zap,
  Radio, Shield, FileSearch, ArrowLeftRight
} from 'lucide-react';
import './App.css';

export default function App() {
  const { status, resetStore } = useCaseStore();
  const [mode, setMode] = useState('select'); // 'select', 'image', 'live'
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedFile, setSelectedFile] = useState(null);

  const navigate = (tab) => {
    setSelectedFile(null);
    setActiveTab(tab);
  };

  const switchMode = (newMode) => {
    setMode(newMode);
    setActiveTab('dashboard');
    setSelectedFile(null);
  };

  // ── Mode Select Screen ─────────────────────────────────────────
  if (mode === 'select') {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#050810' }}>
        <div className="max-w-3xl w-full mx-auto px-8">
          <div className="text-center mb-12">
            <div className="flex items-center justify-center gap-3 mb-4">
              <Zap className="w-10 h-10 text-[#00D4FF] drop-shadow-[0_0_12px_rgba(0,212,255,0.5)]" />
              <h1 className="text-4xl font-bold text-white font-mono tracking-widest">CHRONOTRACE</h1>
            </div>
            <p className="text-[#8B9BB4] font-mono text-sm">NTFS Anti-Forensics Detection Framework</p>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <button
              onClick={() => switchMode('image')}
              className="group rounded-2xl border border-[#1E2D3D] p-8 text-left transition-all duration-300 hover:border-[#00D4FF]/40 hover:shadow-[0_0_30px_rgba(0,212,255,0.1)]"
              style={{ background: '#0D1117' }}
            >
              <div className="bg-[#00D4FF]/10 w-14 h-14 rounded-xl flex items-center justify-center mb-5 group-hover:bg-[#00D4FF]/20 transition">
                <FileSearch className="w-7 h-7 text-[#00D4FF]" />
              </div>
              <h2 className="text-xl font-bold text-white mb-2 font-mono">IMAGE ANALYSIS</h2>
              <p className="text-[#8B9BB4] text-sm leading-relaxed">
                Upload E01 disk images for post-mortem forensic analysis. Parses $MFT, $UsnJrnl, and $LogFile
                to detect timestamp manipulation and anti-forensic artifacts.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <Tag text="E01 Images" />
                <Tag text="Post-Mortem" />
                <Tag text="15 Rules" />
                <Tag text="Court Reports" />
              </div>
            </button>

            <button
              onClick={() => switchMode('live')}
              className="group rounded-2xl border border-[#1E2D3D] p-8 text-left transition-all duration-300 hover:border-[#00FF88]/40 hover:shadow-[0_0_30px_rgba(0,255,136,0.1)]"
              style={{ background: '#0D1117' }}
            >
              <div className="bg-[#00FF88]/10 w-14 h-14 rounded-xl flex items-center justify-center mb-5 group-hover:bg-[#00FF88]/20 transition">
                <Radio className="w-7 h-7 text-[#00FF88]" />
              </div>
              <h2 className="text-xl font-bold text-white mb-2 font-mono">LIVE MONITOR</h2>
              <p className="text-[#8B9BB4] text-sm leading-relaxed">
                Real-time monitoring of a live NTFS volume. Watches the USN Change Journal and running
                processes to detect anti-forensic activity as it happens.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <Tag text="Real-Time" color="#00FF88" />
                <Tag text="USN Journal" color="#00FF88" />
                <Tag text="21 Rules" color="#00FF88" />
                <Tag text="Process Watch" color="#00FF88" />
              </div>
            </button>
          </div>

          <p className="text-center text-[#8B9BB4]/50 font-mono text-xs mt-8">
            Live Monitor requires Administrator privileges for USN Journal / MFT access
          </p>
        </div>
      </div>
    );
  }

  // ── Image Analysis Mode (original flow) ────────────────────────
  if (mode === 'image') {
    if (status === 'idle') return (
      <div className="min-h-screen" style={{ background: '#050810' }}>
        <ModeBar mode={mode} switchMode={switchMode} />
        <div className="pt-2"><UploadPanel /></div>
      </div>
    );
    if (status === 'uploading' || status === 'analyzing') return (
      <div className="min-h-screen" style={{ background: '#050810' }}>
        <ModeBar mode={mode} switchMode={switchMode} />
        <div className="pt-2"><ProgressPanel /></div>
      </div>
    );

    if (selectedFile) {
      return (
        <div className="min-h-screen flex" style={{ background: '#050810' }}>
          <ImageSidebar activeTab={activeTab} navigate={navigate} resetStore={resetStore} switchMode={switchMode} />
          <div className="flex-1 ml-64 p-8">
            <FileDeepDive file={selectedFile} onBack={() => setSelectedFile(null)} onNavigate={navigate} />
          </div>
        </div>
      );
    }

    return (
      <div className="min-h-screen flex" style={{ background: '#050810' }}>
        <ImageSidebar activeTab={activeTab} navigate={navigate} resetStore={resetStore} switchMode={switchMode} />
        <div className="flex-1 ml-64 p-8">
          {activeTab === 'dashboard' && <Dashboard onSelectFile={setSelectedFile} onNavigate={navigate} />}
          {activeTab === 'timeline' && <TimelineViewer onNavigate={navigate} />}
          {activeTab === 'report' && <ReportPanel onNavigate={navigate} />}
        </div>
      </div>
    );
  }

  // ── Live Monitor Mode ──────────────────────────────────────────
  if (mode === 'live') {
    return (
      <div className="min-h-screen flex" style={{ background: '#050810' }}>
        <LiveSidebar activeTab={activeTab} navigate={navigate} switchMode={switchMode} />
        <div className="flex-1 ml-64 p-8">
          <LiveMonitor />
        </div>
      </div>
    );
  }

  return null;
}

// ── Mode Bar ─────────────────────────────────────────────────────────

function ModeBar({ mode, switchMode }) {
  return (
    <div className="flex items-center justify-between px-6 py-3 border-b border-[#1E2D3D]" style={{ background: '#0D1117' }}>
      <div className="flex items-center gap-2 text-[#00D4FF] font-bold font-mono text-sm tracking-widest">
        <Zap className="w-4 h-4" /> CHRONOTRACE
      </div>
      <button
        onClick={() => switchMode('select')}
        className="flex items-center gap-2 text-[#8B9BB4] hover:text-white font-mono text-xs transition border border-[#1E2D3D] px-3 py-1.5 rounded-lg hover:border-[#00D4FF]/30"
      >
        <ArrowLeftRight className="w-3.5 h-3.5" /> Switch Mode
      </button>
    </div>
  );
}

// ── Image Sidebar ────────────────────────────────────────────────────

function ImageSidebar({ activeTab, navigate, resetStore, switchMode }) {
  return (
    <div className="w-64 border-r border-[#1E2D3D] flex flex-col h-screen fixed" style={{ background: '#0D1117' }}>
      <div className="p-5 border-b border-[#1E2D3D]">
        <button onClick={() => navigate('dashboard')} className="font-bold text-sm flex items-center gap-2 text-[#00D4FF] uppercase tracking-widest font-mono hover:opacity-80 transition">
          <Zap className="w-4 h-4" /> CHRONOTRACE
        </button>
      </div>
      <nav className="flex-1 p-4 flex flex-col gap-1.5">
        <NavButton icon={<LayoutDashboard />} label="Dashboard" active={activeTab === 'dashboard'} onClick={() => navigate('dashboard')} />
        <NavButton icon={<Clock />} label="Timeline Logic" active={activeTab === 'timeline'} onClick={() => navigate('timeline')} />
        <NavButton icon={<CheckSquare />} label="Final Report" active={activeTab === 'report'} onClick={() => navigate('report')} />
        <div className="mt-auto pt-4 space-y-2 border-t border-[#1E2D3D]">
          <button onClick={() => switchMode('live')}
            className="flex items-center gap-3 px-4 py-3 w-full text-left rounded-lg text-[#00FF88] hover:bg-[#00FF88]/10 font-mono text-sm transition border border-transparent hover:border-[#00FF88]/20">
            <Radio className="w-4 h-4" /> Live Monitor
          </button>
          <button onClick={resetStore}
            className="flex items-center gap-3 px-4 py-3 w-full text-left rounded-lg text-[#FF2D2D] hover:bg-[#FF2D2D]/10 font-mono text-sm transition">
            <PlusCircle className="w-4 h-4" /> NEW CASE
          </button>
        </div>
      </nav>
    </div>
  );
}

// ── Live Sidebar ─────────────────────────────────────────────────────

function LiveSidebar({ activeTab, navigate, switchMode }) {
  return (
    <div className="w-64 border-r border-[#1E2D3D] flex flex-col h-screen fixed" style={{ background: '#0D1117' }}>
      <div className="p-5 border-b border-[#1E2D3D]">
        <button onClick={() => navigate('dashboard')} className="font-bold text-sm flex items-center gap-2 text-[#00FF88] uppercase tracking-widest font-mono hover:opacity-80 transition">
          <Radio className="w-4 h-4" /> LIVE MONITOR
        </button>
      </div>
      <nav className="flex-1 p-4 flex flex-col gap-1.5">
        <NavButton icon={<Shield />} label="Alert Feed" active={activeTab === 'dashboard'} onClick={() => navigate('dashboard')} color="#00FF88" />
        <div className="mt-auto pt-4 space-y-2 border-t border-[#1E2D3D]">
          <button onClick={() => switchMode('image')}
            className="flex items-center gap-3 px-4 py-3 w-full text-left rounded-lg text-[#00D4FF] hover:bg-[#00D4FF]/10 font-mono text-sm transition border border-transparent hover:border-[#00D4FF]/20">
            <FileSearch className="w-4 h-4" /> Image Analysis
          </button>
          <button onClick={() => switchMode('select')}
            className="flex items-center gap-3 px-4 py-3 w-full text-left rounded-lg text-[#8B9BB4] hover:bg-[#111927] font-mono text-sm transition">
            <ArrowLeftRight className="w-4 h-4" /> Switch Mode
          </button>
        </div>
      </nav>
    </div>
  );
}

// ── Shared Components ────────────────────────────────────────────────

function NavButton({ icon, label, active, onClick, color = '#00D4FF' }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg transition font-mono text-sm w-full text-left
        ${active
          ? 'border shadow-[0_0_10px_rgba(0,212,255,0.1)]'
          : 'text-[#8B9BB4] hover:bg-[#111927] hover:text-white border border-transparent'
        }`}
      style={active ? { color, borderColor: `${color}33`, backgroundColor: `${color}11` } : {}}
    >
      {React.cloneElement(icon, { className: 'w-4 h-4' })} {label}
    </button>
  );
}

function Tag({ text, color = '#00D4FF' }) {
  return (
    <span className="px-2.5 py-1 rounded-full text-[10px] font-mono font-bold tracking-wider"
      style={{ color, background: `${color}15`, border: `1px solid ${color}30` }}>
      {text}
    </span>
  );
}
