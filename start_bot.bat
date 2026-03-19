@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

set "MODE=%~1"
if "%MODE%"=="" set "MODE=wechat"

if /I not "%MODE%"=="wechat" if /I not "%MODE%"=="db" (
    echo Usage: start_bot.bat [wechat^|db]
    exit /b 1
)

if not exist ".env" (
    echo Missing .env in repository root.
    echo Copy .env.example to .env and fill in DATABASE_URL and OpenAI settings first.
    exit /b 1
)

set "PYTHON_CMD="
set "USE_DEPS=0"

if exist "clients\python\.venv\Scripts\python.exe" (
    set "PYTHON_CMD=clients\python\.venv\Scripts\python.exe"
) else (
    echo Creating virtual environment...
    python -m venv "clients\python\.venv"
    if exist "clients\python\.venv\Scripts\python.exe" (
        set "PYTHON_CMD=clients\python\.venv\Scripts\python.exe"
    ) else (
        echo Virtual environment creation failed. Falling back to local .deps directory.
        set "USE_DEPS=1"
        set "PYTHON_CMD=python"
    )
)

echo Installing Python dependencies...
if "!USE_DEPS!"=="0" (
    "!PYTHON_CMD!" -m pip install --upgrade pip
    if errorlevel 1 exit /b 1

    "!PYTHON_CMD!" -m pip install -r "requirements.txt"
    if errorlevel 1 exit /b 1
) else (
    "!PYTHON_CMD!" -m pip install --target ".deps" -r "requirements.txt"
    if errorlevel 1 exit /b 1
    set "PYTHONPATH=%CD%\.deps;%PYTHONPATH%"
)

if /I "%MODE%"=="db" (
    echo Running database smoke mode...
    "!PYTHON_CMD!" "db_smoke.py"
    exit /b %ERRORLEVEL%
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

echo Running WeChat bot mode...
"!PYTHON_CMD!" "clients\python\openai_bot.py"
