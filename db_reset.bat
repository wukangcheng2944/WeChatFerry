@echo off
setlocal

cd /d "%~dp0"
docker compose down -v
if errorlevel 1 exit /b 1

docker compose up -d postgres
