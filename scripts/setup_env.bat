@echo off
REM Настройка виртуального окружения (Windows). Запускать из корня: scripts\setup_env.bat
cd /d "%~dp0\.."

echo Настройка виртуального окружения для ОбучAI...

python --version >nul 2>&1
if errorlevel 1 (
    echo Python не найден. Установите Python 3.8+
    pause
    exit /b 1
)

if not exist "venv" (
    echo Создание venv...
    python -m venv venv
) else (
    echo venv уже существует
)

call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Готово. Для активации: venv\Scripts\activate
pause
