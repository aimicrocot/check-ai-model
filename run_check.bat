@echo off
chcp 65001 >nul
setlocal

rem Переходим в папку, где лежит сам .bat-файл (а значит и check_full.py),
rem чтобы можно было запускать двойным кликом откуда угодно.
cd /d "%~dp0"

echo ============================================================
echo   Проверка OpenAI-совместимого прокси
echo ============================================================
echo.

set /p PROXY_URL="Введи PROXY URL https://твой-прокси.com/v1: "
set /p PROXY_KEY="Введи PROXY KEY: "
set /p PROXY_MODEL="Введи PROXY MODEL: "

echo.
set /p USE_OFFICIAL="Сравнить с официальным доступом? (Y/N): "
if /i "%USE_OFFICIAL%"=="Y" (
    set /p OFFICIAL_URL="Введи OFFICIAL URL: "
    set /p OFFICIAL_KEY="Введи OFFICIAL KEY: "
)

echo.
echo Запускаю check_full.py...
echo ============================================================
echo.

python check_full.py
if errorlevel 9009 (
    echo.
    echo ОШИБКА: команда "python" не найдена. Убедись, что Python
    echo установлен и добавлен в PATH ^(при установке отметить
    echo галочку "Add Python to PATH"^).
)

echo.
echo ============================================================
echo Готово. Нажми любую клавишу, чтобы закрыть окно.
pause >nul