@echo off
rem Starts the SLPHC Field Monitor server (port 8000) and dashboard (port 5173)
rem in two windows, then opens the dashboard. Close the windows to stop.
set ROOT=%~dp0
start "SLPHC server (port 8000)" cmd /k "cd /d "%ROOT%server" && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"
start "SLPHC dashboard (port 5173)" cmd /k "cd /d "%ROOT%dashboard" && npm run dev"
timeout /t 6 /nobreak >nul
start "" http://localhost:5173
