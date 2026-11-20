$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
Set-Location $project

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Install Python 3.12+ for Windows first, then run this script again.'
}

py -3 -m venv .build-venv
& .\.build-venv\Scripts\python.exe -m pip install --upgrade pip
& .\.build-venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-windows.txt
& .\.build-venv\Scripts\pyinstaller.exe --noconfirm --clean packaging\NetDropLocal.spec

$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path $iscc)) {
    throw 'Install Inno Setup 6, then rerun this script to create the installer.'
}
& $iscc packaging\NetDropLocal.iss
Write-Host "Installer created in dist\installer\NetDrop-Local-Setup.exe"
