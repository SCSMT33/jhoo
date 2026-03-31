@echo off
echo Registering jhoo-daily-scraper task...
schtasks /create /tn "jhoo-daily-scraper" /tr "python C:\Users\Chase\Documents\GitHub\jhoo\scraper.py && python C:\Users\Chase\Documents\GitHub\jhoo\gemini_scorer.py" /sc daily /st 05:00 /ru SYSTEM /f
if %errorlevel% == 0 (
    echo Success. Task registered to run daily at 05:00.
) else (
    echo Failed. Try right-clicking schedule_setup.bat and choosing Run as Administrator.
)
pause
