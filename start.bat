@echo off
echo Starting Anti-Forensics Detection Framework...

:: Set Node PATH dynamically just in case it's not in the system environment
set PATH=%PATH%;C:\Program Files\nodejs\

echo Starting Backend Server on port 8000...
start cmd /k "cd backend && uvicorn main:app --reload"

echo Starting Frontend Dev Server on port 5173...
start cmd /k "cd frontend && npm run dev"

echo Both servers are starting! You can view the frontend at http://localhost:5173 once it's ready.
pause
