# poe2lab: setup and start on Windows with one double-click (start.bat runs this).
# Steps, each skipped when already done: Python 3.12+ (offers to install it with winget), a private virtual
# environment in .venv with the dependencies, Path of Building and the game's texts (python -m poe2lab setup),
# then the interface in the browser - its server runs in the background with no window (the interface has a Stop
# button), and this window closes by itself.
param(
    [switch]$NoStart,  # prepare everything but do not launch the interface
    [int]$Port = 8765,
    [switch]$NoBrowser  # start the server without opening the browser (checks)
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if ($Root.Length -gt 140) {
    Write-Host "Путь к папке слишком длинный ($($Root.Length) символов): файлы Path of Building не поместятся в лимит" -ForegroundColor Red
    Write-Host "Windows на длину пути. Переместите папку poe2lab ближе к корню диска, например в C:\poe2lab." -ForegroundColor Red
    exit 1
}
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Yellow }
function Fail($text) { Write-Host ""; Write-Host $text -ForegroundColor Red; exit 1 }

function Find-Python {
    # the py launcher knows every installed version; plain "python" may be the Microsoft Store stub
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) { $candidates += , @("py", "-3") }
    if (Get-Command python -ErrorAction SilentlyContinue) { $candidates += , @("python") }
    $local = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $local) {
        Get-ChildItem $local -Directory | Sort-Object Name -Descending | ForEach-Object {
            $exe = Join-Path $_.FullName "python.exe"
            if (Test-Path $exe) { $candidates += , @($exe) }
        }
    }
    foreach ($c in $candidates) {
        $exe = $c[0]; $rest = @($c | Select-Object -Skip 1)
        try {
            $v = & $exe @rest -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v) {
                $parts = $v.Trim().Split(".")
                if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 12) { return , $c }
            }
        } catch { }
    }
    return $null
}

Step "Python 3.12+"
$py = Find-Python
if (-not $py) {
    Write-Host "Python 3.12 или новее не найден."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "Установите Python 3.12+ с https://www.python.org/downloads/ (галочка 'Add python.exe to PATH') и запустите start.bat снова."
    }
    $answer = Read-Host "Установить Python 3.12 через winget? (y/n)"
    if ($answer -notmatch "^[yYдД]") { Fail "Без Python poe2lab не запустится. Установите его и запустите start.bat снова." }
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    $py = Find-Python
    if (-not $py) { Fail "Python установлен, но не найден в этом окне. Закройте окно и запустите start.bat ещё раз." }
}
$pyExe = $py[0]; $pyArgs = @($py | Select-Object -Skip 1)
Write-Host ("ok: " + (& $pyExe @pyArgs --version))

Step "Окружение и зависимости"
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "Не удалось создать окружение .venv" }
}
# reinstall only when the dependency list changed
$stamp = Join-Path $Root ".venv\poe2lab-installed.txt"
$wanted = (Get-FileHash (Join-Path $Root "pyproject.toml")).Hash
if (-not (Test-Path $stamp) -or (Get-Content $stamp -Raw).Trim() -ne $wanted) {
    & $venvPy -m pip install --disable-pip-version-check -q --upgrade pip
    & $venvPy -m pip install --disable-pip-version-check -q -e ".[anthropic]"
    if ($LASTEXITCODE -ne 0) { Fail "Не удалось установить зависимости — сообщение выше (нужен интернет)." }
    Set-Content -Path $stamp -Value $wanted -Encoding ascii
}
Write-Host "ok"

Step "Path of Building и тексты игры"
& $venvPy -m poe2lab setup
if ($LASTEXITCODE -ne 0) { Fail "Подготовка не удалась — сообщение выше." }

if ($NoStart) { Write-Host ""; Write-Host "Готово." -ForegroundColor Green; exit 0 }

# The server runs in the background with no window: closing this window does not stop it; the interface's
# "Stop poe2lab" button does. Started again while it runs, it only opens the browser.
$url = "http://127.0.0.1:$Port/"
function Test-Running {
    try { return (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 ($url + "api/status")).StatusCode -eq 200 } catch { return $false }
}
if (Test-Running) {
    Write-Host ""; Write-Host "poe2lab уже запущен — открываю в браузере: $url" -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $url }
    Start-Sleep -Seconds 2
    exit 0
}
Step "Запуск"
$logDir = Join-Path $env:APPDATA "poe2lab"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "ui.log"
$errLog = Join-Path $logDir "ui-errors.log"
$uiArgs = @("-m", "poe2lab", "ui", "--port", "$Port")
if ($NoBrowser) { $uiArgs += "--no-browser" }
Start-Process -FilePath $venvPy -ArgumentList $uiArgs -WorkingDirectory $Root -WindowStyle Hidden `
    -RedirectStandardOutput $log -RedirectStandardError $errLog
for ($i = 0; $i -lt 60 -and -not (Test-Running); $i++) { Start-Sleep -Seconds 1 }
if (-not (Test-Running)) {
    Write-Host "Интерфейс не запустился. Последние строки журнала ($errLog):" -ForegroundColor Red
    if (Test-Path $errLog) { Get-Content $errLog -Tail 20 }
    Fail "Если порт $Port занят другой программой — закройте её и запустите start.bat снова."
}
Write-Host ""
Write-Host "poe2lab запущен: $url" -ForegroundColor Green
Write-Host "Он работает в фоне — это окно закроется само. Остановить poe2lab — кнопка «⏻ Остановить poe2lab» внизу слева в приложении."
Start-Sleep -Seconds 4
exit 0
