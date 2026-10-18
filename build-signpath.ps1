$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$stage = Join-Path $env:USERPROFILE 'NH04-SignPath'
$appName = 'NeurixHub-Alpha-0.4'
Write-Host 'Neurix Hub Alpha 0.4 - Building Windows app' -ForegroundColor Cyan
New-Item -ItemType Directory -Path $stage -Force | Out-Null
foreach ($name in @('neurix_hub.py','cache_engine.py','distribution_engine.py','update_engine.py','requirements.txt','requirements-lock.txt','installer.iss')) {
    $inputPath = Join-Path $source $name
    if (!(Test-Path $inputPath)) { throw "Missing source file: $inputPath" }
    Copy-Item -LiteralPath $inputPath -Destination (Join-Path $stage $name) -Force
}
Push-Location $stage
try {
    $venvPython = Join-Path $stage '.venv\Scripts\python.exe'
    if (!(Test-Path $venvPython)) {
        py -3.13 -m venv (Join-Path $stage '.venv')        
if ($LASTEXITCODE -ne 0) { throw 'Cannot create virtual environment' }
    }
   & $venvPython -m pip install -r requirements-lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    & $venvPython -m PyInstaller --noconfirm --clean --windowed --onedir --name $appName --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtMultimedia 'neurix_hub.py'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
    $exe = Join-Path $stage "dist\$appName\$appName.exe"
    if (!(Test-Path $exe)) { throw "Executable missing: $exe" }
    Write-Host "BUILD OK: $exe" -ForegroundColor Green
    Write-Host "Inno Setup script: $(Join-Path $stage 'installer.iss')" -ForegroundColor Cyan
} finally {
    Pop-Location
}

