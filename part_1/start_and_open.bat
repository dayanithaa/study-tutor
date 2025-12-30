@echo off
echo Starting Document Intelligence Platform...
echo.

REM Start the server in background
start /B python app.py

REM Wait 3 seconds for server to start
timeout /t 3 /nobreak >nul

REM Open browser
echo Opening browser...
start http://localhost:8001

echo.
echo Server is running at: http://localhost:8001
echo Press any key to stop the server...
pause >nul

REM Kill the python process when done
taskkill /f /im python.exe >nul 2>&1