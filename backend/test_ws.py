import asyncio
import websockets
import json
import httpx

async def test_ws():
    # Simulate API call to create case
    async with httpx.AsyncClient() as client:
        r = await client.post("http://localhost:8000/api/cases", json={"investigator": "Aarzoo", "device_label": "Test", "notes": "", "analysis_mode": "Fast"})
        case = r.json()
        case_id = case["id"]
        
        # Start analysis
        r = await client.post(f"http://localhost:8000/api/cases/{case_id}/analyze")
        
    # Quickly connect to websocket
    print(f"Connecting to ws://localhost:8000/ws/{case_id}/progress")
    async with websockets.connect(f"ws://localhost:8000/ws/{case_id}/progress") as websocket:
        print("Connected")
        while True:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                print(f"Received: {message}")
                if "status" in message and "completed" in message:
                    break
            except asyncio.TimeoutError:
                print("Timeout waiting for message")
                break

asyncio.run(test_ws())
