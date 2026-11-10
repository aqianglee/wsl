$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
$iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "找不到 ISCC.exe，请先安装 Inno Setup 6"
}

& $iscc (Join-Path $root "installer\WSL Deck.iss")

$setup = Join-Path $root "dist\WSL-Deck-Setup-1.0.1.exe"
if (-not (Test-Path $setup)) {
    throw "建置失败：找不到 $setup"
}

Write-Host "完成：$setup"
