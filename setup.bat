@echo off
echo Installing dependencies into Python313...
C:\Users\40721\AppData\Local\Programs\Python\Python313\python.exe -m pip install httpx==0.24.1 supabase==2.3.0 gotrue==1.3.0 postgrest==0.10.8 python-dotenv requests feedparser flask google-generativeai --force-reinstall
echo Setup complete. You can now run jhoo.bat
pause
