@echo off
setlocal enableextensions
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0portable_g1_runner.py"
  goto check
)
where python >nul 2>nul
if not errorlevel 1 (
  python "%~dp0portable_g1_runner.py"
  goto check
)
echo BLOQUEO: Python no esta disponible en PATH. No se ha instalado nada ni generado cargos.
goto done
:check
if errorlevel 1 (
  echo BLOQUEO: Revisar el mensaje anterior. La prueba falla cerrado.
) else (
  echo Prueba sintetica ejecutada; abre EVIDENCE_OUTPUT y conserva el recibo ZIP.
)
:done
pause
