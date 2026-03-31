@echo off
echo Installing dependencies into Python313...
C:\Users\40721\AppData\Local\Programs\Python\Python313\python.exe -m pip install httpx==0.27.0 supabase==2.7.4 python-dotenv requests feedparser flask google-generativeai --force-reinstall
echo Setup complete. You can now run jhoo.bat
pause
