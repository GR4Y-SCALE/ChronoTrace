import { create } from 'zustand';

const WS_URL = 'ws://localhost:8000/api/monitor/ws';
const API_URL = 'http://localhost:8000/api/monitor';

export const useMonitorStore = create((set, get) => ({
    // Connection state
    isConnected: false,
    isMonitoring: false,
    ws: null,

    // Data
    alerts: [],
    statusMessages: [],
    stats: null,
    rules: {},

    // Config
    driveFilter: 'C',
    severityFilter: null,

    // ── Actions ──────────────────────────────────────────

    connectWebSocket: () => {
        const existing = get().ws;
        if (existing && existing.readyState === WebSocket.OPEN) return;

        const ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            set({ isConnected: true, ws });
        };

        ws.onclose = () => {
            set({ isConnected: false, ws: null });
            // Auto-reconnect after 3 seconds
            setTimeout(() => {
                if (get().isMonitoring) {
                    get().connectWebSocket();
                }
            }, 3000);
        };

        ws.onerror = () => {
            set({ isConnected: false });
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                const state = get();

                if (msg.type === 'init') {
                    set({
                        isMonitoring: msg.data.is_running,
                        stats: msg.data.stats,
                        alerts: msg.data.recent_alerts || [],
                    });
                } else if (msg.type === 'alert') {
                    set({
                        alerts: [...state.alerts.slice(-499), msg.data],
                    });
                } else if (msg.type === 'status') {
                    set({
                        statusMessages: [
                            ...state.statusMessages.slice(-99),
                            { ...msg.data, received_at: new Date().toISOString() },
                        ],
                    });
                } else if (msg.type === 'stats') {
                    set({ stats: msg.data });
                }
            } catch (e) {
                console.error('WS message parse error:', e);
            }
        };

        set({ ws });
    },

    disconnectWebSocket: () => {
        const ws = get().ws;
        if (ws) {
            ws.close();
            set({ ws: null, isConnected: false });
        }
    },

    startMonitor: async (driveLetter = 'C') => {
        try {
            const resp = await fetch(`${API_URL}/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ drive_letter: driveLetter, poll_interval: 1.0 }),
            });
            if (resp.ok) {
                set({ isMonitoring: true, driveFilter: driveLetter });
                // Connect WebSocket if not already
                get().connectWebSocket();
            }
            return resp.ok;
        } catch (e) {
            console.error('Start monitor failed:', e);
            return false;
        }
    },

    stopMonitor: async () => {
        try {
            const resp = await fetch(`${API_URL}/stop`, { method: 'POST' });
            if (resp.ok) {
                set({ isMonitoring: false });
            }
            return resp.ok;
        } catch (e) {
            console.error('Stop monitor failed:', e);
            return false;
        }
    },

    fetchAlerts: async (limit = 100, severity = null) => {
        try {
            let url = `${API_URL}/alerts?limit=${limit}`;
            if (severity) url += `&severity=${severity}`;
            const resp = await fetch(url);
            if (resp.ok) {
                const data = await resp.json();
                set({ alerts: data.alerts });
            }
        } catch (e) {
            console.error('Fetch alerts failed:', e);
        }
    },

    fetchRules: async () => {
        try {
            const resp = await fetch(`${API_URL}/rules`);
            if (resp.ok) {
                const data = await resp.json();
                set({ rules: data.rules });
            }
        } catch (e) {
            console.error('Fetch rules failed:', e);
        }
    },

    fetchStats: () => {
        const ws = get().ws;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ command: 'get_stats' }));
        }
    },

    clearAlerts: () => set({ alerts: [] }),
    clearStatusMessages: () => set({ statusMessages: [] }),
    setSeverityFilter: (sev) => set({ severityFilter: sev }),

    reset: () => {
        get().disconnectWebSocket();
        set({
            isConnected: false,
            isMonitoring: false,
            ws: null,
            alerts: [],
            statusMessages: [],
            stats: null,
            severityFilter: null,
        });
    },
}));
