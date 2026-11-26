$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
Set-Location $project

function Assert-NativeCommandSuccess($operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$operation failed with exit code $LASTEXITCODE."
    }
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Install Python 3.12+ for Windows first, then run this script again.'
}

py -3 -m venv .build-venv
Assert-NativeCommandSuccess 'Creating the build environment'
& .\.build-venv\Scripts\python.exe -m pip install --upgrade pip
Assert-NativeCommandSuccess 'Upgrading pip'
& .\.build-venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-packaging.txt
Assert-NativeCommandSuccess 'Installing build requirements'
& .\.build-venv\Scripts\pyinstaller.exe --noconfirm --clean packaging\NetDropLocal.spec
Assert-NativeCommandSuccess 'Building the NetDrop Local application'

$iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path $iscc)) {
    throw 'Install Inno Setup 6, then rerun this script to create the installer.'
}
& $iscc packaging\NetDropLocal.iss
Assert-NativeCommandSuccess 'Compiling the installer'
Write-Host "Installer created in dist\installer\NetDrop-Local-Setup.exe"
