@echo off
echo Starting ChronoTrace - NTFS Anti-Forensics Detection Framework...
echo.
echo   Modes available:
echo     - Image Analysis: Upload E01 disk images for post-mortem analysis
echo     - Live Monitor:   Real-time anti-forensics detection (requires Admin)
echo.

:: Set Node PATH dynamically just in case it's not in the system environment
set PATH=%PATH%;C:\Program Files\nodejs\

echo Starting Backend Server on port 8000...
start cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && cd backend && uvicorn main:app --reload"

echo Starting Frontend Dev Server on port 5173...
start cmd /k "cd /d %~dp0frontend && npm run dev"

echo Both servers are starting! You can view the frontend at http://localhost:5173 once it's ready.
echo.
echo NOTE: For Live Monitor mode, run the backend as Administrator.
pause
