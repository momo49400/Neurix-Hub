$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$stage = Join-Path $env:USERPROFILE 'NH04'
$builtExe = Join-Path $stage 'dist\NeurixHub-Alpha-0.4\NeurixHub-Alpha-0.4.exe'
if (!(Test-Path $builtExe)) {
    & (Join-Path $source 'build.ps1')
    if (!(Test-Path $builtExe)) { throw 'App build failed' }
}
$iss = Join-Path $stage 'installer.iss'
$isccCandidates = @()
foreach ($base in @(${env:ProgramFiles(x86)}, $env:ProgramFiles)) {
    if ($base) {
        $isccCandidates += Join-Path $base 'Inno Setup 7\ISCC.exe'
        $isccCandidates += Join-Path $base 'Inno Setup 6\ISCC.exe'
    }
}
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) {
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { $iscc = $cmd.Source }
}
if (-not $iscc) {
    Write-Host "Inno Setup compiler not found. Open this file in Inno Setup and press F9: $iss" -ForegroundColor Yellow
    exit 2
}
& $iscc $iss
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed' }
$setupExe = Join-Path $stage 'release\NeurixHub-Alpha-0.4-Setup.exe'
if (!(Test-Path $setupExe)) { throw "Setup not found: $setupExe" }
Write-Host "SETUP OK: $setupExe" -ForegroundColor Green
