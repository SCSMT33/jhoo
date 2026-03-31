@echo off
cd /d "%~dp0"
python scraper.py
python gemini_scorer.py
pause
