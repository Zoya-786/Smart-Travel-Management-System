@echo off
cd /d %~dp0
if not exist venv (python -m venv venv)
call venv\Scripts\activate
pip install -r requirements.txt
echo Open http://127.0.0.1:5000 in your browser
python app.py
pause
