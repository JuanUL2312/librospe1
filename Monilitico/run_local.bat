@echo off
REM Monolito LibrosPE - arranque local (puerto 8000, 1 sola BD)
cd /d %~dp0
if not exist .venv-live (python -m venv .venv-live)
call .venv-live\Scripts\activate
pip install -r requirements.txt
cd www
python app.py
