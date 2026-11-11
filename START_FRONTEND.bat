@echo off
setlocal
cd /d "%~dp0frontend"
echo ===============================
echo LifePilot Frontend - React
 echo ===============================
if not exist "node_modules" (
  echo Installing frontend dependencies...
  call npm install
  if errorlevel 1 goto :failed
)
echo Open http://127.0.0.1:5173
call npm run dev
if errorlevel 1 goto :failed
goto :end
:failed
echo ERROR - please see the messages above.
pause
:end
