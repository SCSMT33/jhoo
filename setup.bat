@echo off
echo Installing dependencies into Python313...
C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe -m pip install httpx python-dotenv requests feedparser flask google-generativeai
C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe -m pip install supabase==2.3.0
echo Setup complete. You can now run jhoo.bat
pause
