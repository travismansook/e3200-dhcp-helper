@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Helper.ps1" %*
exit /b %errorlevel%
