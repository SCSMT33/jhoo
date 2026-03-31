@echo off
cd /d "%~dp0"
python app.py &
timeout /t 2 /nobreak >nul
start chrome --profile-directory="Profile 1" http://localhost:5007
