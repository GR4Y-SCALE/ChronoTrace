from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from api import routes, websocket
from api import monitor as monitor_api
import json
import asyncio
import logging

# Configure logging for the live monitor subsystem
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

app = FastAPI(title="Anti-Forensics Detection Framework", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Original image-analysis routes
app.include_router(routes.router, prefix="/api")
app.include_router(websocket.router, prefix="/ws")

# NEW: Live monitor routes
app.include_router(monitor_api.router, prefix="/api/monitor")

@app.get("/")
def read_root():
    return {
        "status": "ok",
        "message": "ChronoTrace Anti-Forensics Detection Framework",
        "modes": {
            "image_analysis": "/api — Upload & analyze E01 disk images",
            "live_monitor": "/api/monitor — Real-time anti-forensics monitoring",
        },
    }
