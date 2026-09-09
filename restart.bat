@echo off
REM ============================================
REM  LibrosPE - Reinicio LOCAL (Windows)
REM  Actualiza la marca de tiempo de www\tmp\restart.txt
REM  para que Passenger recargue la aplicacion.
REM ============================================
setlocal
cd /d "%~dp0"

if not exist "www\tmp" mkdir "www\tmp"

if not exist "www\tmp\restart.txt" type nul > "www\tmp\restart.txt"

REM touch: actualiza timestamp sin modificar contenido
copy /b "www\tmp\restart.txt"+,, "www\tmp\restart.txt" > nul

echo ============================================
echo  LibrosPE - Marcado para reinicio
echo  Archivo: www\tmp\restart.txt
echo ============================================
echo Passenger recargara la aplicacion en unos segundos.
endlocal
pause