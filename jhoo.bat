@echo off
cd /d "%~dp0"
echo Starting jhoo Flask server...
start cmd /k "cd /d "%~dp0" && python app.py"
timeout /t 4 /nobreak >nul
start chrome --profile-directory="Profile 1" http://localhost:5007
