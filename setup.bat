@echo off
echo Finding Python...
for /f "tokens=*" %%i in ('where python 2^>nul') do set PYTHON_PATH=%%i
if "%PYTHON_PATH%"=="" (
    echo Python not found in PATH. Adding manually...
    setx PATH "%PATH%;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\Scripts;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\Scripts" /M
    echo Done. Please restart your command prompt and run this again.
) else (
    echo Python found at %PYTHON_PATH%
    echo Installing dependencies...
    python -m pip install httpx python-dotenv requests feedparser flask google-generativeai
    python -m pip install supabase==2.3.0
    echo Setup complete. You can now run jhoo.bat
)
pause
