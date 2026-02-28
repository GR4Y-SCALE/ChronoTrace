from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from api import routes, websocket
import json
import asyncio

app = FastAPI(title="Anti-Forensics Detection Framework", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")
app.include_router(websocket.router, prefix="/ws")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Anti-Forensics Detect API running"}
