@echo off
setlocal
echo QROS: diagnostico de componentes. No abre ni modifica MT5.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Test-Components.ps1"
set "QROS_RESULT=%ERRORLEVEL%"
echo Codigo de salida: %QROS_RESULT%
echo La ventana anterior indica el ZIP para adjuntar o el error de compresion.
pause
exit /b %QROS_RESULT%
