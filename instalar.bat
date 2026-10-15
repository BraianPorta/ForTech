@echo off
setlocal
cd /d "%~dp0"
echo Preparando el entorno local de Circuit Lab...
python -m venv .venv
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Instalacion completada. Ejecuta iniciar.bat.
pause
exit /b 0
:error
echo.
echo No se pudo completar la instalacion. Revisa los mensajes anteriores.
pause
exit /b 1
