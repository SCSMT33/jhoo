@echo off
:: jhoo — Windows Task Scheduler setup for Computer B
:: Run this once to register the daily scraper task.
:: Picks a random start time between 7:00 AM and 9:00 AM.

cd /d "%~dp0"

:: Generate a random minute offset (0–119) for a time between 07:00 and 08:59
set /a OFFSET=%RANDOM% %% 120
set /a HOUR=7 + (%OFFSET% / 60)
set /a MIN=%OFFSET% %% 60

:: Zero-pad minute
if %MIN% LSS 10 (set MIN=0%MIN%)

set TASKTIME=%HOUR%:%MIN%

echo Registering jhoo-daily-scraper to run at %TASKTIME% daily...

schtasks /create ^
  /tn "jhoo-daily-scraper" ^
  /tr "C:\Documents\jhoo\run_scraper.bat" ^
  /sc daily ^
  /st %TASKTIME% ^
  /ru SYSTEM ^
  /rl HIGHEST ^
  /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Task registered successfully: jhoo-daily-scraper at %TASKTIME% daily.
    echo To verify: schtasks /query /tn "jhoo-daily-scraper"
    echo To remove:  schtasks /delete /tn "jhoo-daily-scraper" /f
) else (
    echo.
    echo ERROR: Failed to register task. Try running this .bat as Administrator.
)
pause
