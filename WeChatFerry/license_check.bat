@echo off
setlocal
cd /d %~dp0

set "FLAG=.license_accepted.flag"

if /I "%CI%"=="true" (
    > "%FLAG%" echo accepted
    exit /b 0
)

if /I "%WCF_AUTO_ACCEPT_LICENSE%"=="true" (
    > "%FLAG%" echo accepted
    exit /b 0
)

if exist "%FLAG%" exit /b 0
if exist "license_accepted.flag" exit /b 0

if not exist "DISCLAIMER.md" (
    echo Missing DISCLAIMER.md
    exit /b 1
)

powershell -NoProfile -Command ^
    "$text = [System.IO.File]::ReadAllText('DISCLAIMER.md', [System.Text.Encoding]::UTF8);" ^
    "Add-Type -AssemblyName PresentationFramework;" ^
    "$result = [System.Windows.MessageBox]::Show($text, 'Disclaimer', 'OKCancel', 'Warning');" ^
    "if ($result -ne 'OK') { exit 1 }"

if errorlevel 1 exit /b 1

> "%FLAG%" echo accepted
exit /b 0
