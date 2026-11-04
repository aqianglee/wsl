$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$work = Join-Path $root "build"
$dist = Join-Path $root "dist"
$python = Join-Path $root ".venv\Scripts\python.exe"
$log = Join-Path $work "pyinstaller.log"

# PowerShell 5.1 會把 PyInstaller 的 stderr 當成終止錯誤，改用 Continue + 日誌檔
$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $python -m PyInstaller `
    --noconfirm --clean `
    --workpath $work `
    --distpath $dist `
    "$root\WSL Deck.spec" 2> $log

$exitCode = $LASTEXITCODE
$ErrorActionPreference = $previous
if ($exitCode -ne 0) {
    Get-Content $log -Tail 20
    throw "建置失敗：PyInstaller 結束碼 $exitCode"
}

$exe = Join-Path $dist "WSL Deck\WSL Deck.exe"
if (-not (Test-Path $exe)) {
    throw "建置失敗：找不到 $exe"
}

$config = Join-Path $dist "WSL Deck\config.json"
if (-not (Test-Path $config)) {
    Copy-Item (Join-Path $root "config.json") $config
}

Write-Host "完成：$exe"
