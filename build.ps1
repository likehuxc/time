#Requires -Version 5.1
<#
.SYNOPSIS
  Build a Windows onedir distribution (exe + _internal) via PyInstaller.

.DESCRIPTION
  Creates/uses a project-local .venv, installs runtime dependencies and PyInstaller,
  then executes pyinstaller.spec. Output: dist\HouseholdLoadForecast\
#>
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$venvDir = Join-Path $PSScriptRoot '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating project virtual environment..." -ForegroundColor Cyan
    python -m venv $venvDir
}

Write-Host "Using virtual environment: $venvDir" -ForegroundColor Cyan

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip in project virtual environment."
}

& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install project requirements."
}

& $venvPython -m pip install "pyinstaller>=6.0.0"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install PyInstaller."
}

& $venvPython -m PyInstaller --noconfirm pyinstaller.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

Write-Host "Build finished. Run: dist\HouseholdLoadForecast\HouseholdLoadForecast.exe" -ForegroundColor Green
