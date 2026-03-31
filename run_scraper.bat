@echo off
cd /d "%~dp0"
echo Running jhoo scraper %date% %time% >> scraper_log.txt
C:\Users\Chase\AppData\Local\Programs\Python\Python314\python.exe scraper.py >> scraper_log.txt 2>&1
C:\Users\Chase\AppData\Local\Programs\Python\Python314\python.exe gemini_scorer.py >> scraper_log.txt 2>&1
echo Done %date% %time% >> scraper_log.txt
