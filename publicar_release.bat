@echo off
cd /d "%~dp0"
set "PYTHON_EXE=C:\Users\AB-ADVOGADOS\AppData\Local\Programs\Python\Python311\python.exe"

if not exist "%PYTHON_EXE%" (
    echo ERRO: Python nao encontrado em %PYTHON_EXE%
    pause
    exit /b 1
)

"%PYTHON_EXE%" publicar_release.py %*

if errorlevel 1 (
    echo.
    echo ERRO: A automacao de release falhou.
    pause
    exit /b 1
)

pause
