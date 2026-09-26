@echo off
setlocal

REM =====================================================
REM Build manual do PDF2MD_V2 (PyInstaller)
REM =====================================================

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=C:\Users\AB-ADVOGADOS\AppData\Local\Programs\Python\Python311\python.exe"
set "SPEC_FILE=PDF2MD_V2.spec"

echo.
echo [1/6] Validando Python...
if not exist "%PYTHON_EXE%" (
  echo ERRO: Python nao encontrado em:
  echo %PYTHON_EXE%
  echo Ajuste o caminho dentro deste arquivo .bat e rode novamente.
  exit /b 1
)

cd /d "%PROJECT_DIR%"

echo.
echo [2/6] Limpando build anterior...
taskkill /F /IM PDF2MD_V2.exe >nul 2>nul
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist build (
  echo ERRO: Nao foi possivel limpar a pasta build. Algum arquivo ainda esta em uso.
  echo Feche o PDF2MD_V2.exe, Explorer aberto na pasta, antivirus/indexador e tente novamente.
  exit /b 1
)
if exist dist (
  echo ERRO: Nao foi possivel limpar a pasta dist. Algum arquivo ainda esta em uso.
  echo Feche o PDF2MD_V2.exe, Explorer aberto na pasta, antivirus/indexador e tente novamente.
  exit /b 1
)

echo.
echo [3/6] Atualizando instalador de pacotes...
"%PYTHON_EXE%" -m pip install -U pip
if errorlevel 1 (
  echo ERRO: Falha ao atualizar pip.
  exit /b 1
)

echo.
echo [4/6] Instalando dependencias do projeto (inclui PaddleX OCR)...
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERRO: Falha ao instalar dependencias do requirements.txt.
  exit /b 1
)

echo.
echo [5/6] Validando OCR no ambiente de build...
"%PYTHON_EXE%" -c "from ocr.manager import ocr_engine; ocr_engine.inicializar_se_necessario(); import sys; sys.exit(0 if ocr_engine.motor != 'ERRO' else 1)"
if errorlevel 1 (
  echo ERRO: OCR nao inicializou no ambiente de build.
  echo Verifique dependencias e modelos antes de empacotar.
  exit /b 1
)

echo.
echo [6/6] Gerando executavel...
"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm "%SPEC_FILE%"
if errorlevel 1 (
  echo ERRO: Build falhou.
  exit /b 1
)

echo.
echo Concluido com sucesso.
echo Executavel: %PROJECT_DIR%dist\PDF2MD_V2\PDF2MD_V2.exe
echo Pasta completa: %PROJECT_DIR%dist\PDF2MD_V2
echo.
pause
endlocal
