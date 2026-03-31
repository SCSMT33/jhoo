@echo off
cd /d "%~dp0"
echo Running jhoo scraper...
python scraper.py
echo.
echo Running Gemini scorer...
python gemini_scorer.py
pause
