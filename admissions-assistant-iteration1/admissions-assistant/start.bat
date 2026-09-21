@echo off
title Smart Admissions Assistant Server

echo ===================================================
echo   Smart University Admissions Assistant
echo ===================================================
echo.

REM Проверяем наличие виртуального окружения и активируем его
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [WARN] Virtual environment 'venv' not found. Using global Python environment.
)

echo [INFO] Opening browser...
start http://127.0.0.1:8000

echo [INFO] Starting FastAPI backend server...
echo [INFO] Press Ctrl+C to stop the server.
echo.

REM Запускаем сервер
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

echo.
echo [ERROR] Server stopped!
pause
