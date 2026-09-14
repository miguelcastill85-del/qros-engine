@echo off
setlocal EnableExtensions
title QROS Runner Actual-Terminal Fence Qualifier v2 - D04 fixed

set "ROOT=%~dp0"
set "RC=99"

cd /d "%ROOT%" 2>nul
if errorlevel 1 goto :CD_FAIL

echo ================================================================
echo QROS R2T v2 - D04 FIXED - LAUNCHER HARDENED
echo ================================================================
echo No Candidate3. No trade API. AllowLiveTrading=0.
echo QDB1.EXEC.CERT remains 0. Isolated MT5 clones only.
echo.

REM Guard against running the BAT directly from inside the ZIP.
if not exist "%ROOT%STATIC_GATE_QROS_RUNNER_ACTUAL_TERMINAL_FENCE_v2.ps1" goto :NOT_EXTRACTED
if not exist "%ROOT%QUALIFY_QROS_RUNNER_ACTUAL_TERMINAL_FENCE_v2.ps1" goto :NOT_EXTRACTED
if not exist "%ROOT%PACKAGE_MANIFEST_SHA256.json" goto :NOT_EXTRACTED
if not exist "%ROOT%MQL5\Experts\QROS_RUNNER_RUNTIME_FENCE_QUALIFIER_v1.mq5" goto :NOT_EXTRACTED

set "PS51=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS51%" (
    where powershell.exe >nul 2>&1
    if errorlevel 1 goto :NO_POWERSHELL
    set "PS51=powershell.exe"
)

echo [1/2] Ejecutando STATIC + MUTATION GATE...
echo.
"%PS51%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%STATIC_GATE_QROS_RUNNER_ACTUAL_TERMINAL_FENCE_v2.ps1"
set "SG=%ERRORLEVEL%"
echo.
echo STATIC GATE exit code: %SG%
if not "%SG%"=="0" (
    set "RC=%SG%"
    goto :STATIC_FAIL
)

echo.
echo [2/2] Ejecutando QUALIFIER NATIVO MT5...
echo Esta etapa puede tardar. NO cierres esta ventana.
echo.
"%PS51%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%QUALIFY_QROS_RUNNER_ACTUAL_TERMINAL_FENCE_v2.ps1"
set "RC=%ERRORLEVEL%"

echo.
echo ================================================================
echo QROS R2T v2 finalizo con codigo: %RC%
echo ================================================================
if "%RC%"=="0" (
    echo RESULTADO DEL LAUNCHER: proceso terminado sin error de salida.
    echo Revisa arriba el receipt y la ruta del ZIP de evidencia generado.
) else (
    echo RESULTADO DEL LAUNCHER: FAIL/diagnostico, codigo %RC%.
    echo NO significa fallo de Candidate3. Conserva la salida y el ZIP de evidencia.
)
goto :HOLD

:NOT_EXTRACTED
echo.
echo ERROR: EL PAQUETE NO ESTA EXTRAIDO COMPLETO.
echo.
echo Windows suele hacer esto si haces doble clic al BAT directamente
ECHO dentro del archivo ZIP. Extrae TODO el ZIP primero a una carpeta normal
echo y ejecuta este BAT desde esa carpeta.
echo.
echo Carpeta actual:
echo   %ROOT%
echo.
set "RC=96"
goto :HOLD

:NO_POWERSHELL
echo.
echo ERROR: Windows PowerShell 5.1 no fue encontrado.
set "RC=97"
goto :HOLD

:CD_FAIL
echo.
echo ERROR: no se pudo abrir la carpeta del paquete.
set "RC=98"
goto :HOLD

:STATIC_FAIL
echo.
echo STATIC GATE FAILED con codigo %RC%.
echo NO se ejecuto el qualifier nativo.
echo Copia o captura el mensaje mostrado arriba.
goto :HOLD

:HOLD
echo.
echo ---------------------------------------------------------------
echo La ventana se mantendra abierta para que puedas leer el resultado.
echo Pulsa una tecla SOLO despues de revisar o fotografiar el mensaje.
echo ---------------------------------------------------------------
pause
exit /b %RC%
