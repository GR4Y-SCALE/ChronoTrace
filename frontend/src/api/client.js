import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';
export const WS_BASE_URL = 'ws://localhost:8000/ws';

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const api = {
    createCase: async (caseData) => {
        const response = await apiClient.post('/cases', caseData);
        return response.data;
    },
    uploadImage: async (caseId, file) => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await apiClient.post(`/cases/${caseId}/upload`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            }
        });
        return response.data;
    },
    startAnalysis: async (caseId) => {
        const response = await apiClient.post(`/cases/${caseId}/analyze`);
        return response.data;
    },
    getCase: async (caseId) => {
        const response = await apiClient.get(`/cases/${caseId}`);
        return response.data;
    },
    getReport: async (caseId) => {
        const response = await apiClient.get(`/cases/${caseId}/report`);
        return response.data;
    }
};
