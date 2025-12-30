@echo off
echo ========================================
echo   DOCUMENT INTELLIGENCE PLATFORM
echo ========================================
echo.

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting Document Processing Platform...
echo Platform will be available at: http://localhost:8000
echo API docs at: http://localhost:8000/docs
echo.

python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000

pause