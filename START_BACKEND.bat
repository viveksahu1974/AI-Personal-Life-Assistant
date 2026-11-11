@echo off
setlocal
cd /d "%~dp0backend"
echo ===============================
echo LifePilot Backend - FastAPI
 echo ===============================
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  py -m venv .venv || python -m venv .venv
  if errorlevel 1 goto :failed
)
echo Installing backend dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
if not exist ".env" copy ".env.example" ".env" >nul
echo Backend docs: http://127.0.0.1:8000/docs
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
if errorlevel 1 goto :failed
goto :end
:failed
echo ERROR - please see the messages above.
pause
:end
