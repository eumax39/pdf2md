@echo off
setlocal enabledelayedexpansion

REM =====================================================
REM Script para atualizar o repositório Git
REM =====================================================

echo.
echo ========================================
echo  ATUALIZANDO REPOSITORIO GIT
echo ========================================
echo.

REM ==========================================
REM PASSO 1: Verifica se está na pasta certa
REM ==========================================
if not exist ".git" (
    echo ERRO: Nao foi encontrada a pasta .git
    echo Voce esta na pasta correta do projeto?
    echo Pressione qualquer tecla para sair...
    pause >nul
    exit /b 1
)

REM ==========================================
REM PASSO 2: Verifica se há alterações
REM ==========================================
echo [1/5] Verificando alteracoes...
git status --porcelain > temp_git_status.txt
set /p STATUS=<temp_git_status.txt
del temp_git_status.txt

if "%STATUS%"=="" (
    echo Nenhuma alteracao detectada. Nada a enviar.
    echo.
    pause
    exit /b 0
)

REM ==========================================
REM PASSO 3: Mostra o que vai ser enviado
REM ==========================================
echo.
echo [2/5] Arquivos modificados/adicionados:
echo ----------------------------------------
git status -s
echo ----------------------------------------
echo.

REM ==========================================
REM PASSO 4: Pergunta a mensagem de commit
REM ==========================================
echo [3/5] Digite a mensagem do commit (ou deixe em branco para usar automatica):
set /p COMMIT_MSG="Mensagem: "

if "%COMMIT_MSG%"=="" (
    for /f "tokens=1-6 delims=/: " %%a in ("%DATE% %TIME%") do (
        set DATA_HORA=%%a%%b%%c_%%d%%e%%f
    )
    set COMMIT_MSG=Atualizacao automatica - %DATA_HORA%
    echo Usando mensagem automatica: %COMMIT_MSG%
) else (
    echo Commit com mensagem: %COMMIT_MSG%
)

REM ==========================================
REM PASSO 5: Adiciona, commita e faz push
REM ==========================================
echo.
echo [4/5] Adicionando arquivos...
git add .

echo.
echo [5/5] Realizando commit e push...
git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo.
    echo ERRO: Falha ao fazer commit. Verifique suas alteracoes.
    pause
    exit /b 1
)

git push
if errorlevel 1 (
    echo.
    echo ERRO: Falha ao enviar para o GitHub.
    echo Verifique sua conexao com a internet e credenciais.
    pause
    exit /b 1
)

REM ==========================================
REM FINALIZADO
REM ==========================================
echo.
echo ========================================
echo  ✅ REPOSITORIO ATUALIZADO COM SUCESSO!
echo ========================================
echo.
echo Commit: %COMMIT_MSG%
echo.
pause
endlocal