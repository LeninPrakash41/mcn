# MCN Installation Script for Windows
# Run with: powershell -ExecutionPolicy Bypass -File install.ps1

Write-Host "🚀 Installing MCN (Macincode Scripting Language)..." -ForegroundColor Green

# Check Python version
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python (\d+\.\d+)") {
        $version = [version]$matches[1]
        $requiredVersion = [version]"3.8"

        if ($version -lt $requiredVersion) {
            Write-Host "❌ Python 3.8+ required. Found: $($matches[1])" -ForegroundColor Red
            exit 1
        }

        Write-Host "✅ Python $($matches[1]) detected" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Python not found. Please install Python 3.8+ first." -ForegroundColor Red
    exit 1
}

# Install MCN
try {
    Write-Host "Installing MCN package..." -ForegroundColor Yellow
    pip install mcn-lang
    Write-Host "✅ MCN installed successfully!" -ForegroundColor Green
} catch {
    Write-Host "❌ Installation failed. Please check your pip installation." -ForegroundColor Red
    exit 1
}

# Verify installation
try {
    $mcnVersion = mcn --version 2>&1
    Write-Host "🎉 Installation complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Try these commands:" -ForegroundColor Cyan
    Write-Host "  mcn --help"
    Write-Host "  mcn repl"
    Write-Host "  echo 'echo(`"Hello MCN!`")' > hello.mcn && mcn run hello.mcn"
} catch {
    Write-Host "⚠️  MCN command not found in PATH. Try:" -ForegroundColor Yellow
    Write-Host "  python -m ms_lang.core_engine.mcn_cli --help"
}
