# MCN installer for Windows.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/LeninPrakash41/mcn/main/install.ps1 | iex"
#
# Installs MCN and its private runtime into %USERPROFILE%\.mcn (nothing else on
# the system is touched) and adds `mcn` to your user PATH. Re-run it, or run
# `mcn upgrade`, to update. Remove everything with `mcn uninstall`.
#
# Options (environment variables): MCN_HOME, MCN_SOURCE, MCN_NO_MODIFY_PATH=1

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$McnHome   = if ($env:MCN_HOME) { $env:MCN_HOME } else { Join-Path $env:USERPROFILE ".mcn" }
$Source    = if ($env:MCN_SOURCE) { $env:MCN_SOURCE } else { "https://github.com/LeninPrakash41/mcn/archive/refs/heads/main.tar.gz" }
$Runtime   = Join-Path $McnHome "runtime"
$Bin       = Join-Path $McnHome "bin"
$Log       = Join-Path $McnHome "logs\install.log"
$UvVersion = "0.12.24"   # bootstrap tool that provisions the runtime; pinned and checksum-verified

function Step($text) { Write-Host "› $text" -ForegroundColor DarkGray }
function Fail($text) {
    Write-Host "✗ $text" -ForegroundColor Red
    if (Test-Path $Log) { Write-Host "`nDetails ($Log):"; Get-Content $Log -Tail 15 }
    exit 1
}

Write-Host "`nInstalling MCN`n" -ForegroundColor White
New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "bin"), $Bin, (Split-Path $Log) | Out-Null
Set-Content -Path $Log -Value ""

# 1. Bootstrap tool
$Tool = Join-Path $Runtime "bin\uv.exe"
$haveTool = (Test-Path $Tool) -and ((& $Tool --version 2>$null) -match [regex]::Escape($UvVersion))
if (-not $haveTool) {
    Step "Downloading the MCN runtime"
    $arch = switch ($env:PROCESSOR_ARCHITECTURE) {
        "AMD64" { "x86_64" }
        "ARM64" { "aarch64" }
        default { Fail "MCN doesn't support the $($env:PROCESSOR_ARCHITECTURE) processor yet." }
    }
    $archive = "uv-$arch-pc-windows-msvc.zip"
    $url = "https://github.com/astral-sh/uv/releases/download/$UvVersion/$archive"
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("mcn-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        Invoke-WebRequest -Uri $url -OutFile (Join-Path $tmp $archive) -UseBasicParsing
        $expected = ((Invoke-WebRequest -Uri "$url.sha256" -UseBasicParsing).Content -split "\s+")[0]
    } catch { Fail "Couldn't download the runtime. Check your internet connection." }
    $actual = (Get-FileHash (Join-Path $tmp $archive) -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $expected.ToLower()) { Fail "The runtime download was corrupted. Run the installer again." }
    Expand-Archive -Path (Join-Path $tmp $archive) -DestinationPath $tmp -Force
    $uvExe = Get-ChildItem -Path $tmp -Recurse -Filter "uv.exe" | Select-Object -First 1
    Copy-Item $uvExe.FullName $Tool -Force
    Remove-Item $tmp -Recurse -Force
}

# 2. MCN itself, in an isolated environment with its own interpreter
Step "Installing MCN"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Runtime "interpreters"
$env:UV_TOOL_DIR           = Join-Path $Runtime "tools"
$env:UV_TOOL_BIN_DIR       = $Bin
$env:UV_CACHE_DIR          = Join-Path $Runtime "cache"
$env:UV_PYTHON_PREFERENCE  = "only-managed"   # never depend on whatever is on the system
$env:UV_NO_PROGRESS        = "1"
& $Tool tool install --force --python 3.12 --quiet "mcn-lang @ $Source" *>> $Log
if ($LASTEXITCODE -ne 0) { Fail "Installing MCN failed." }
& $Tool cache clean --quiet *>> $Log
$Mcn = Join-Path $Bin "mcn.exe"
$version = & $Mcn --version 2>$null
if ($LASTEXITCODE -ne 0) { Fail "MCN was installed but doesn't start." }
Set-Content -Path (Join-Path $Runtime "source") -Value $Source

# 3. PATH
if ($env:MCN_NO_MODIFY_PATH -ne "1") {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (($userPath -split ";") -contains $Bin)) {
        [Environment]::SetEnvironmentVariable("Path", (($Bin, $userPath) -join ";").TrimEnd(";"), "User")
    }
}
if (-not (($env:Path -split ";") -contains $Bin)) { $env:Path = "$Bin;$env:Path" }

Write-Host "`n✓ $version installed`n" -ForegroundColor Green
Write-Host "Open a new terminal if 'mcn' isn't found, then get started:"
Write-Host "  mcn init my-app"
Write-Host "  cd my-app"
Write-Host "  mcn studio .`n"
