@echo off
cd /d "%~dp0"
C:\Users\40721\AppData\Local\Programs\Python\Python313\python.exe app.py
start chrome --profile-directory="Profile 1" http://localhost:5007
