@echo off
setlocal

cd /d "%~dp0"

if not exist ".env" (
    echo Missing .env in repository root.
    echo Copy .env.example to .env and fill in DATABASE_URL and OpenAI settings first.
    exit /b 1
)

if not exist "clients\python\wcferry\SDK.dll" (
    echo Missing clients\python\wcferry\SDK.dll
    echo Run WeChatFerry\build_vs2022.cmd Release first.
    exit /b 1
)

if not exist "clients\python\wcferry\spy.dll" (
    echo Missing clients\python\wcferry\spy.dll
    echo Run WeChatFerry\build_vs2022.cmd Release first.
    exit /b 1
)

if not exist "clients\python\.venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv "clients\python\.venv"
    if errorlevel 1 exit /b 1
)

call "clients\python\.venv\Scripts\activate.bat"
if errorlevel 1 exit /b 1

echo Installing Python dependencies...
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r "requirements.txt"
if errorlevel 1 exit /b 1

cd /d "%~dp0clients\python"
python openai_bot.py
