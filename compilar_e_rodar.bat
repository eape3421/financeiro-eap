@echo off
cd /d "%~dp0"

call venv\Scripts\activate.bat

pyinstaller --onefile --windowed --name "FinanceiroEAP" ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "instance;instance" ^
  app.py

xcopy instance dist\instance /E /I /Y >nul

start "" dist\FinanceiroEAP.exe
pause
