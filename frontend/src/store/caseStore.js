import { create } from 'zustand';

export const useCaseStore = create((set) => ({
    currentCase: null,
    reportData: null,
    progress: 0,
    status: 'idle', // idle, uploading, analyzing, completed, error
    logs: [],

    setCase: (caseData) => set({ currentCase: caseData }),
    setReportData: (data) => set({ reportData: data }),
    setProgress: (prog) => set({ progress: prog }),
    setStatus: (status) => set({ status: status }),
    addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),
    clearLogs: () => set({ logs: [] }),
    resetStore: () => set({
        currentCase: null,
        reportData: null,
        progress: 0,
        status: 'idle',
        logs: []
    })
}));
