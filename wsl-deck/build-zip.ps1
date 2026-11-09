# 用法：
#   .\build-zip.ps1                  # 版本讀自 installer\WSL Deck.iss，排除 config.json
#   .\build-zip.ps1 -IncludeConfig   # 納入 config.json
#   .\build-zip.ps1 -Version 1.1.0   # 指定版本號

param(
    [string]$Version = "",
    [switch]$IncludeConfig
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path $root "dist\WSL Deck"
$exe = Join-Path $dist "WSL Deck.exe"
$iss = Join-Path $root "installer\WSL Deck.iss"
$stageRoot = Join-Path $root "build\zip-stage"
$stage = Join-Path $stageRoot "WSL Deck"

if (-not (Test-Path $exe)) {
    throw "找不到 $exe，請先執行 .\build.ps1"
}

if (-not $Version) {
    $match = Select-String -Path $iss -Pattern '#define\s+MyAppVersion\s+"([^"]+)"' |
        Select-Object -First 1
    if ($match) {
        $Version = $match.Matches[0].Groups[1].Value
    } else {
        $Version = "1.0.0"
    }
}

$stamp = Get-Date -Format "yyyyMMdd"
$zip = Join-Path $root "dist\WSL-Deck-$Version-$stamp.zip"

if (Test-Path $stageRoot) {
    Remove-Item $stageRoot -Recurse -Force
}
New-Item $stage -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $dist "*") $stage -Recurse -Force

$logs = Join-Path $stage "logs"
if (Test-Path $logs) {
    Remove-Item $logs -Recurse -Force
}
if (-not $IncludeConfig) {
    $config = Join-Path $stage "config.json"
    if (Test-Path $config) {
        Remove-Item $config -Force
    }
}

# 壓縮改用 tar.exe（Windows 10+ 自帶 bsdtar），比 PowerShell Compress-Archive
# 對檔案鎖更魯棒、速度更快。保留 stage 目錄是因為要排除 logs / config.json。

if (Test-Path $stageRoot) {
    Remove-Item $stageRoot -Recurse -Force
}
New-Item $stage -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $dist "*") $stage -Recurse -Force

$logs = Join-Path $stage "logs"
if (Test-Path $logs) {
    Remove-Item $logs -Recurse -Force
}
if (-not $IncludeConfig) {
    $config = Join-Path $stage "config.json"
    if (Test-Path $config) {
        Remove-Item $config -Force
    }
}

& tar.exe -a -c -f $zip -C $stageRoot "WSL Deck"
if ($LASTEXITCODE -ne 0) {
    throw "壓縮失敗：tar.exe 結束碼 $LASTEXITCODE"
}
Remove-Item $stageRoot -Recurse -Force

$size = (Get-Item $zip).Length / 1MB
Write-Host ("完成：{0}（{1:N1} MB）" -f $zip, $size)
