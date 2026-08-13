@echo off
setlocal

REM =====================================================
REM Build manual do PDF2MD_V2 (PyInstaller + ZIP)
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
echo [3/7] Atualizando instalador de pacotes...
"%PYTHON_EXE%" -m pip install -U pip
if errorlevel 1 (
  echo ERRO: Falha ao atualizar pip.
  exit /b 1
)

echo.
echo [4/7] Instalando dependencias do projeto (inclui PaddleX OCR)...
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERRO: Falha ao instalar dependencias do requirements.txt.
  exit /b 1
)

echo.
echo [5/8] Validando OCR no ambiente de build...
"%PYTHON_EXE%" -c "from ocr.manager import ocr_engine; ocr_engine.inicializar_se_necessario(); import sys; sys.exit(0 if ocr_engine.motor != 'ERRO' else 1)"
if errorlevel 1 (
  echo ERRO: OCR nao inicializou no ambiente de build.
  echo Verifique dependencias e modelos antes de empacotar.
  exit /b 1
)

echo.
echo [6/8] Gerando executavel...
"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm "%SPEC_FILE%"
if errorlevel 1 (
  echo ERRO: Build falhou.
  exit /b 1
)

echo.
echo [7/8] Compactando pacote portable...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Set-Location '%PROJECT_DIR%\dist'; if (Test-Path '.\PDF2MD_V2_portable.zip') { Remove-Item -Force '.\PDF2MD_V2_portable.zip' }; Compress-Archive -Path '.\PDF2MD_V2' -DestinationPath '.\PDF2MD_V2_portable.zip' -CompressionLevel Optimal -ErrorAction Stop; if (-not (Test-Path '.\PDF2MD_V2_portable.zip')) { throw 'ZIP nao foi criado.' }; exit 0 } catch { Write-Host ('ERRO ao compactar ZIP: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
  echo AVISO: Executavel gerado, mas nao foi possivel criar o ZIP.
  echo Feche o app PDF2MD_V2.exe, antivirus/indexador que esteja usando arquivos da pasta dist e rode novamente para gerar o ZIP.
  goto :show_paths
)

:show_paths
echo.
echo [8/8] Concluido.
echo Executavel: %PROJECT_DIR%dist\PDF2MD_V2\PDF2MD_V2.exe
echo Pasta completa: %PROJECT_DIR%dist\PDF2MD_V2
echo ZIP portable: %PROJECT_DIR%dist\PDF2MD_V2_portable.zip
echo.
echo IMPORTANTE: para outro computador, envie a pasta inteira
echo dist\PDF2MD_V2 (ou o ZIP gerado), nunca apenas o .exe.
echo.
pause
endlocal
