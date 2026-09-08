@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0QROS_V224_C3_COMPILE_ONLY.ps1"
set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (echo QROS V224 Candidate3 compile-only finalizado correctamente.) else (echo QROS V224 Candidate3 compile-only fallo. Codigo %RC%.)
pause
exit /b %RC%
