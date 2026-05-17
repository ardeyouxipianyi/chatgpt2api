@echo off
setlocal

echo [chatgpt2api] Stopping service on port 3000...

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
  taskkill /PID %%p /F >nul 2>nul
)

echo [chatgpt2api] Done.
pause
