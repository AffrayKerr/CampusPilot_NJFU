@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "APP_FILE=%BACKEND_DIR%\app.py"
set "VENV_PYTHON=%ROOT_DIR%\.venv\Scripts\python.exe"
set "BROWSER_URL=http://127.0.0.1:5000/"

if not exist "%APP_FILE%" (
    echo [错误] 未找到 backend\app.py
    echo 请确认此启动器与 CampusPilot_NJFU 项目根目录放在一起。
    pause
    exit /b 1
)

set "PYTHON_CMD="
if exist "%VENV_PYTHON%" (
    set "PYTHON_CMD=%VENV_PYTHON%"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [错误] 未找到 Python。
        echo 请先安装 Python 3，并确保 python 已加入 PATH，或在项目根目录创建 .venv。
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

echo [信息] 使用 Python: %PYTHON_CMD%
echo [信息] 项目目录: %ROOT_DIR%
echo [信息] 正在启动 CampusPilot 后端...

start "CampusPilot Backend" cmd /k "cd /d "%BACKEND_DIR%" && "%PYTHON_CMD%" app.py"

timeout /t 2 /nobreak >nul
start "" "%BROWSER_URL%"

echo [完成] 已尝试启动后端，并打开浏览器：%BROWSER_URL%
echo 如果浏览器未成功打开，请手动访问上面的地址。
timeout /t 2 /nobreak >nul
exit /b 0
