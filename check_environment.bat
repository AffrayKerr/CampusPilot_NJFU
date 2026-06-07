@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "REQUIREMENTS_FILE=%BACKEND_DIR%\requirements.txt"
set "VENV_PYTHON=%ROOT_DIR%\.venv\Scripts\python.exe"
set "GIT_BASH=%ProgramFiles%\Git\bin\bash.exe"
set "GIT_BASH_X86=%ProgramFiles(x86)%\Git\bin\bash.exe"
set "CHROME_A=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
set "CHROME_B=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
set "CHROME_C=%LocalAppData%\Google\Chrome\Application\chrome.exe"
set "CHROMEDRIVER_A=%USERPROFILE%\.cache\selenium\chromedriver\win64\148.0.7778.178\chromedriver.exe"
set "CHROMEDRIVER_B=%ROOT_DIR%\chromedriver.exe"

set /a ERROR_COUNT=0
set /a WARN_COUNT=0

echo ================================
echo CampusPilot 环境检查
echo 项目目录：%ROOT_DIR%
echo ================================
echo.

if not exist "%BACKEND_DIR%\app.py" (
    echo [错误] 未找到 backend\app.py
    set /a ERROR_COUNT+=1
)

if not exist "%REQUIREMENTS_FILE%" (
    echo [错误] 未找到 backend\requirements.txt
    set /a ERROR_COUNT+=1
)

echo [1/6] 检查 Python...
set "PYTHON_CMD="
if exist "%VENV_PYTHON%" (
    set "PYTHON_CMD=%VENV_PYTHON%"
    echo [通过] 检测到项目虚拟环境 Python
    "%PYTHON_CMD%" --version
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [错误] 未找到 Python，请先安装 Python 3 并加入 PATH，或创建 .venv
        set /a ERROR_COUNT+=1
    ) else (
        set "PYTHON_CMD=python"
        echo [通过] 检测到系统 Python
        python --version
    )
)
echo.

echo [2/6] 检查 Python 依赖包...
if defined PYTHON_CMD (
    for %%P in (flask flask_cors cryptography requests selenium bs4) do (
        "%PYTHON_CMD%" -c "import %%P" >nul 2>nul
        if errorlevel 1 (
            echo [错误] 缺少 Python 包：%%P
            set /a ERROR_COUNT+=1
        ) else (
            echo [通过] 已安装：%%P
        )
    )
) else (
    echo [跳过] 因未检测到 Python，无法检查依赖包
)
echo.

echo [3/6] 检查 Git Bash...
if exist "%GIT_BASH%" (
    echo [通过] 检测到 Git Bash：%GIT_BASH%
) else if exist "%GIT_BASH_X86%" (
    echo [通过] 检测到 Git Bash：%GIT_BASH_X86%
) else (
    where bash >nul 2>nul
    if errorlevel 1 (
        echo [错误] 未检测到 bash 环境，请安装 Git for Windows（Git Bash）
        set /a ERROR_COUNT+=1
    ) else (
        echo [通过] 检测到 PATH 中的 bash
    )
)
echo.

echo [4/6] 检查 Google Chrome...
if exist "%CHROME_A%" (
    echo [通过] 检测到 Chrome：%CHROME_A%
) else if exist "%CHROME_B%" (
    echo [通过] 检测到 Chrome：%CHROME_B%
) else if exist "%CHROME_C%" (
    echo [通过] 检测到 Chrome：%CHROME_C%
) else (
    echo [错误] 未检测到 Google Chrome
    set /a ERROR_COUNT+=1
)
echo.

echo [5/6] 检查 ChromeDriver...
if exist "%CHROMEDRIVER_A%" (
    echo [通过] 检测到 ChromeDriver：%CHROMEDRIVER_A%
) else if exist "%CHROMEDRIVER_B%" (
    echo [通过] 检测到 ChromeDriver：%CHROMEDRIVER_B%
) else (
    where chromedriver >nul 2>nul
    if errorlevel 1 (
        echo [警告] 未检测到 ChromeDriver，Selenium 相关功能可能无法使用
        set /a WARN_COUNT+=1
    ) else (
        echo [通过] 检测到 PATH 中的 ChromeDriver
    )
)
echo.

echo [6/6] 检查关键目录...
for %%D in (frontend shell database) do (
    if exist "%ROOT_DIR%\%%D" (
        echo [通过] 目录存在：%%D
    ) else (
        echo [错误] 缺少目录：%%D
        set /a ERROR_COUNT+=1
    )
)
echo.

echo ================================
echo 检查完成
echo 错误：%ERROR_COUNT% 个
ECHO 警告：%WARN_COUNT% 个
echo ================================

if %ERROR_COUNT% GTR 0 (
    echo [结果] 当前环境不完整，请先根据提示补齐后再启动项目。
) else if %WARN_COUNT% GTR 0 (
    echo [结果] 基本环境可用，但仍有警告项，部分功能可能受影响。
) else (
    echo [结果] 环境检查通过，可以尝试启动 CampusPilot。
)

echo.
pause
exit /b 0
