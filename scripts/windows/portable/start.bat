@echo off
setlocal

cd /d "%~dp0"

set "ROOT=%~dp0"
set "APP_DIR=%ROOT%app"
set "PYTHON_EXE=%ROOT%runtime\python\python.exe"

if not exist "%PYTHON_EXE%" (
  echo [chatgpt2api] Missing runtime\python\python.exe
  echo Please use the complete Windows portable package.
  pause
  exit /b 1
)

if not exist "%APP_DIR%\main.py" (
  echo [chatgpt2api] Missing app\main.py
  echo Please keep the extracted package structure unchanged.
  pause
  exit /b 1
)

if not exist "%APP_DIR%\config.json" (
  if exist "%APP_DIR%\config.example.json" (
    copy "%APP_DIR%\config.example.json" "%APP_DIR%\config.json" >nul
  )
)

set "CHATGPT2API_HOST=0.0.0.0"
set "CHATGPT2API_PORT=3000"
set "PYTHONUTF8=1"
set "PYTHONPATH=%APP_DIR%;%APP_DIR%\python_packages"
set "PATH=%ROOT%runtime\python;%ROOT%runtime\python\Scripts;%ROOT%runtime\node;%PATH%"

echo [chatgpt2api] Starting...
echo [chatgpt2api] Web: http://localhost:3000
echo [chatgpt2api] API: http://localhost:3000/v1
echo.

start "chatgpt2api" /D "%APP_DIR%" "%PYTHON_EXE%" main.py

timeout /t 3 /nobreak >nul
start "" "http://localhost:3000"

echo [chatgpt2api] Started. You can close this window.
pause
