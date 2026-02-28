from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, case_id: str):
        await websocket.accept()
        if case_id not in self.active_connections:
            self.active_connections[case_id] = []
        self.active_connections[case_id].append(websocket)

    def disconnect(self, websocket: WebSocket, case_id: str):
        if case_id in self.active_connections:
            self.active_connections[case_id].remove(websocket)

    async def send_message(self, message: str, case_id: str):
        if case_id in self.active_connections:
            for connection in self.active_connections[case_id]:
                await connection.send_text(message)

manager = ConnectionManager()

@router.websocket("/{case_id}/progress")
async def websocket_endpoint(websocket: WebSocket, case_id: str):
    await manager.connect(websocket, case_id)
    try:
        while True:
            data = await websocket.receive_text()
            # In a real app we might receive client commands here (like 'cancel')
    except WebSocketDisconnect:
        manager.disconnect(websocket, case_id)
