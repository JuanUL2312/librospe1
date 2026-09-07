@echo off
REM ============================================
REM  LibrosPE - Arranque LOCAL (desarrollo)
REM  Usa el entorno virtual de Windows .venv-live
REM ============================================
cd /d "%~dp0"

if not exist ".venv-live\Scripts\python.exe" (
    echo [ERROR] No se encontro el entorno virtual .venv-live
    echo Ejecuta primero:  python -m venv .venv-live
    echo Luego instala:    .venv-live\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

call ".venv-live\Scripts\activate.bat"

echo.
echo ============================================
echo  LibrosPE - Servidor LOCAL
echo  Abre en tu navegador: http://localhost:8000
echo  Presiona Ctrl+C para detener
echo ============================================
echo.

cd www
python app.py
