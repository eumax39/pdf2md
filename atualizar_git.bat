@echo off
cd /d "%~dp0"

echo.
echo ========================================
echo  ATUALIZANDO REPOSITORIO GIT
echo ========================================
echo.
echo Pasta atual: %CD%
echo.

if not exist ".git" (
    echo ERRO: Nao foi encontrada a pasta .git
    pause
    exit /b 1
)

echo [1/4] Verificando alteracoes...
git status --porcelain > temp_git_status.txt

findstr /r "." temp_git_status.txt > nul
if errorlevel 1 (
    echo Nenhuma alteracao detectada.
    del temp_git_status.txt
    pause
    exit /b 0
)
del temp_git_status.txt

echo.
echo [2/4] Arquivos modificados/adicionados:
git status -s
echo.

echo [3/4] Adicionando arquivos...
git add .

echo.
echo [4/4] Realizando commit e push...
for /f "delims=" %%i in ('powershell -Command "Get-Date -Format 'yyyy-MM-dd HH:mm'"') do set DATA_HORA=%%i
set COMMIT_MSG=Atualizacao automatica - %DATA_HORA%
echo Commit: %COMMIT_MSG%

git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo.
    echo AVISO: Nenhuma alteracao para commit.
    pause
    exit /b 0
)

git push
if errorlevel 1 (
    echo.
    echo ERRO: Falha ao enviar para o GitHub.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  ✅ REPOSITORIO ATUALIZADO COM SUCESSO!
echo ========================================
echo.
echo Commit: %COMMIT_MSG%
pause