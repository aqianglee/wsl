$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$work = Join-Path $root "build"
$dist = Join-Path $root "dist"
$python = Join-Path $root ".venv\Scripts\python.exe"

# 先由 app_icon.py 的同一份繪製邏輯生成 exe 圖標，確保與 App 內部圖標一致
& $python (Join-Path $root "installer\make_app_icon.py")
if ($LASTEXITCODE -ne 0) {
    throw "建置失敗：生成圖標失敗"
}

& $python -m PyInstaller `
    --noconfirm --clean `
    --workpath $work `
    --distpath $dist `
    "$root\WSL Deck.spec"

$exe = Join-Path $dist "WSL Deck\WSL Deck.exe"
if (-not (Test-Path $exe)) {
    throw "建置失敗：找不到 $exe"
}

$config = Join-Path $dist "WSL Deck\config.json"
if (-not (Test-Path $config)) {
    Copy-Item (Join-Path $root "config.json") $config
}

Write-Host "完成：$exe"
