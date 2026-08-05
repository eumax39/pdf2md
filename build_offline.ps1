$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm "$projectRoot\PDF2MD_V2.spec"

Write-Host "Build concluida em: $projectRoot\dist\PDF2MD_V2" -ForegroundColor Green
