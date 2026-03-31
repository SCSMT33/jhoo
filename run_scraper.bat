@echo off
cd /d "%~dp0"
C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe scraper.py
C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe gemini_scorer.py
pause
