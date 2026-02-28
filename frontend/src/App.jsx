import React, { useState } from 'react';
import { useCaseStore } from './store/caseStore';
import UploadPanel from './components/UploadPanel';
import ProgressPanel from './components/ProgressPanel';
import Dashboard from './components/Dashboard';
import FileDeepDive from './components/FileDeepDive';
import TimelineViewer from './components/TimelineViewer';
import ReportPanel from './components/ReportPanel';
import { LayoutDashboard, Clock, CheckSquare, PlusCircle, Zap } from 'lucide-react';
import './App.css';

export default function App() {
  const { status, resetStore } = useCaseStore();
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedFile, setSelectedFile] = useState(null);

  // Navigation helper passed to all child components
  const navigate = (tab) => {
    setSelectedFile(null);
    setActiveTab(tab);
  };

  if (status === 'idle') return <UploadPanel />;
  if (status === 'uploading' || status === 'analyzing') return <ProgressPanel />;

  if (selectedFile) {
    return (
      <div className="min-h-screen flex" style={{ background: '#050810' }}>
        <Sidebar activeTab={activeTab} navigate={navigate} resetStore={resetStore} />
        <div className="flex-1 ml-64 p-8">
          <FileDeepDive
            file={selectedFile}
            onBack={() => setSelectedFile(null)}
            onNavigate={navigate}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex" style={{ background: '#050810' }}>
      <Sidebar activeTab={activeTab} navigate={navigate} resetStore={resetStore} />
      <div className="flex-1 ml-64 p-8">
        {activeTab === 'dashboard' && <Dashboard onSelectFile={setSelectedFile} onNavigate={navigate} />}
        {activeTab === 'timeline' && <TimelineViewer onNavigate={navigate} />}
        {activeTab === 'report' && <ReportPanel onNavigate={navigate} />}
      </div>
    </div>
  );
}

function Sidebar({ activeTab, navigate, resetStore }) {
  return (
    <div className="w-64 border-r border-[#1E2D3D] flex flex-col h-screen fixed" style={{ background: '#0D1117' }}>
      <div className="p-5 border-b border-[#1E2D3D]">
        <button onClick={() => navigate('dashboard')} className="font-bold text-sm flex items-center gap-2 text-[#00D4FF] uppercase tracking-widest font-mono hover:opacity-80 transition">
          <Zap className="w-4 h-4" />
          CHRONOTRACE
        </button>
      </div>

      <nav className="flex-1 p-4 flex flex-col gap-1.5">
        <NavButton icon={<LayoutDashboard />} label="Dashboard" active={activeTab === 'dashboard'} onClick={() => navigate('dashboard')} />
        <NavButton icon={<Clock />} label="Timeline Logic" active={activeTab === 'timeline'} onClick={() => navigate('timeline')} />
        <NavButton icon={<CheckSquare />} label="Final Report" active={activeTab === 'report'} onClick={() => navigate('report')} />

        <div className="mt-auto pt-8 border-t border-[#1E2D3D]">
          <button
            onClick={resetStore}
            className="flex items-center gap-3 px-4 py-3 w-full text-left rounded-lg text-[#FF2D2D] hover:bg-[#FF2D2D]/10 font-mono text-sm transition"
          >
            <PlusCircle className="w-4 h-4" />
            NEW CASE
          </button>
        </div>
      </nav>
    </div>
  );
}

function NavButton({ icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg transition font-mono text-sm w-full text-left
        ${active
          ? 'bg-[#00D4FF]/10 text-[#00D4FF] border border-[#00D4FF]/20 shadow-[0_0_10px_rgba(0,212,255,0.1)]'
          : 'text-[#8B9BB4] hover:bg-[#111927] hover:text-white border border-transparent'
        }`}
    >
      {React.cloneElement(icon, { className: 'w-4 h-4' })} {label}
    </button>
  );
}
