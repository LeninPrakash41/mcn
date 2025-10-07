#!/bin/bash
# MCN Installation Script

set -e

echo "🚀 Installing MCN (Macincode Scripting Language)..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.8+ required. Found: $python_version"
    exit 1
fi

echo "✅ Python $python_version detected"

# Install MCN
if command -v pip3 &> /dev/null; then
    pip3 install mcn-lang
elif command -v pip &> /dev/null; then
    pip install mcn-lang
else
    echo "❌ pip not found. Please install pip first."
    exit 1
fi

echo "✅ MCN installed successfully!"

# Verify installation
if command -v mcn &> /dev/null; then
    echo "🎉 Installation complete!"
    echo ""
    echo "Try these commands:"
    echo "  mcn --help"
    echo "  mcn repl"
    echo "  echo 'echo(\"Hello MCN!\")' > hello.mcn && mcn run hello.mcn"
else
    echo "⚠️  MCN command not found in PATH. Try:"
    echo "  python3 -m ms_lang.core_engine.mcn_cli --help"
fi
