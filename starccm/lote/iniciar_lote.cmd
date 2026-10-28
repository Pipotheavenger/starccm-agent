@echo off
rem Lanza el lote CFD (argumentos opcionales: --solo G002,G047). Salida en lote\orquestador.log; avance en lote\eventos.log
rem y en Desktop\Geometrias_Prueba\_lote_simulacion.csv. Parar con calma: crear el archivo lote\PARAR.
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
cd /d "%~dp0.."
".venv\Scripts\python.exe" lote\orquestador.py %* >> "%~dp0orquestador.log" 2>&1
