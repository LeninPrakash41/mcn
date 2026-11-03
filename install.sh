#!/bin/sh
# MCN installer for macOS and Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/LeninPrakash41/mcn/main/install.sh | sh
#
# Installs MCN and its private runtime into ~/.mcn (nothing else on the system
# is touched) and puts `mcn` on your PATH. Re-run it, or run `mcn upgrade`, to
# update. Remove everything with `mcn uninstall`.
#
# Options (environment variables):
#   MCN_HOME=~/.mcn           where to install
#   MCN_SOURCE=<url or path>  install a different build (default: the main branch)
#   MCN_NO_MODIFY_PATH=1      don't add ~/.mcn/bin to your shell profile
set -eu

MCN_HOME="${MCN_HOME:-$HOME/.mcn}"
MCN_SOURCE="${MCN_SOURCE:-https://github.com/LeninPrakash41/mcn/archive/refs/heads/main.tar.gz}"
RUNTIME="$MCN_HOME/runtime"
BIN="$MCN_HOME/bin"
LOG="$MCN_HOME/logs/install.log"
UV_VERSION="0.12.24"   # bootstrap tool that provisions the runtime; pinned and checksum-verified

if [ -t 1 ]; then BOLD="$(printf '\033[1m')"; DIM="$(printf '\033[2m')"; GREEN="$(printf '\033[32m')"; RED="$(printf '\033[31m')"; RESET="$(printf '\033[0m')"
else BOLD=""; DIM=""; GREEN=""; RED=""; RESET=""; fi

step() { printf '%s›%s %s\n' "$DIM" "$RESET" "$1"; }
fail() {
  printf '%s✗ %s%s\n' "$RED" "$1" "$RESET" >&2
  if [ -s "$LOG" ]; then printf '\nDetails (%s):\n' "$LOG" >&2; tail -n 15 "$LOG" >&2; fi
  exit 1
}
need() { command -v "$1" >/dev/null 2>&1 || fail "This installer needs '$1'. Install it and run the command again."; }

download() {  # url dest
  if command -v curl >/dev/null 2>&1; then curl -fsSL --retry 3 -o "$2" "$1" >>"$LOG" 2>&1
  elif command -v wget >/dev/null 2>&1; then wget -q -O "$2" "$1" >>"$LOG" 2>&1
  else fail "This installer needs curl or wget."; fi
}

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

target() {
  os="$(uname -s)"; arch="$(uname -m)"
  case "$arch" in
    x86_64|amd64) arch="x86_64" ;;
    arm64|aarch64) arch="aarch64" ;;
    *) fail "MCN doesn't support the $arch processor yet." ;;
  esac
  case "$os" in
    Darwin) echo "$arch-apple-darwin" ;;
    Linux)
      if ldd --version 2>&1 | grep -qi musl; then echo "$arch-unknown-linux-musl"; else echo "$arch-unknown-linux-gnu"; fi ;;
    *) fail "Use install.ps1 on Windows. This installer supports macOS and Linux." ;;
  esac
}

printf '\n%sInstalling MCN%s\n\n' "$BOLD" "$RESET"
mkdir -p "$RUNTIME/bin" "$BIN" "$(dirname "$LOG")"
: > "$LOG"
need tar
need uname

# 1. Bootstrap tool
TOOL="$RUNTIME/bin/uv"
if [ ! -x "$TOOL" ] || ! "$TOOL" --version 2>/dev/null | grep -q "$UV_VERSION"; then
  step "Downloading the MCN runtime"
  TRIPLE="$(target)"
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  ARCHIVE="uv-$TRIPLE.tar.gz"
  URL="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$ARCHIVE"
  download "$URL" "$TMP/$ARCHIVE" || fail "Couldn't download the runtime. Check your internet connection."
  download "$URL.sha256" "$TMP/$ARCHIVE.sha256" || fail "Couldn't download the runtime checksum."
  [ "$(sha256 "$TMP/$ARCHIVE")" = "$(cut -d' ' -f1 "$TMP/$ARCHIVE.sha256")" ] || fail "The runtime download was corrupted. Run the installer again."
  tar -xzf "$TMP/$ARCHIVE" -C "$TMP" >>"$LOG" 2>&1 || fail "Couldn't unpack the runtime."
  cp "$TMP/uv-$TRIPLE/uv" "$TOOL" && chmod +x "$TOOL"
fi

# 2. MCN itself, in an isolated environment with its own interpreter
step "Installing MCN"
export UV_PYTHON_INSTALL_DIR="$RUNTIME/interpreters"
export UV_TOOL_DIR="$RUNTIME/tools"
export UV_TOOL_BIN_DIR="$BIN"
export UV_CACHE_DIR="$RUNTIME/cache"
export UV_PYTHON_PREFERENCE="only-managed"   # never depend on whatever is on the system
export UV_NO_PROGRESS=1
"$TOOL" tool install --force --python 3.12 --quiet "mcn-lang @ $MCN_SOURCE" >>"$LOG" 2>&1 \
  || fail "Installing MCN failed."
"$TOOL" cache clean --quiet >>"$LOG" 2>&1 || true
"$BIN/mcn" --version >>"$LOG" 2>&1 || fail "MCN was installed but doesn't start."
VERSION="$("$BIN/mcn" --version 2>/dev/null)"
printf '%s\n' "$MCN_SOURCE" > "$RUNTIME/source"

# 3. PATH
ENV_FILE="$MCN_HOME/env"
cat > "$ENV_FILE" <<EOF
# Added by the MCN installer
case ":\$PATH:" in *":$BIN:"*) ;; *) export PATH="$BIN:\$PATH" ;; esac
EOF
ADDED=""
if [ "${MCN_NO_MODIFY_PATH:-}" != "1" ]; then
  for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile"; do
    case "$rc" in
      */.zshrc) [ -n "${ZSH_VERSION:-}" ] || [ "${SHELL##*/}" = "zsh" ] || [ -f "$rc" ] || continue ;;
      *) [ -f "$rc" ] || continue ;;
    esac
    grep -qs "$ENV_FILE" "$rc" || printf '\n. "%s"\n' "$ENV_FILE" >> "$rc"
    ADDED="$ADDED ${rc##*/}"
  done
  if [ -z "$ADDED" ]; then printf '\n. "%s"\n' "$ENV_FILE" >> "$HOME/.profile"; ADDED=" .profile"; fi
  FISH="$HOME/.config/fish/conf.d"
  if [ -d "$HOME/.config/fish" ]; then
    mkdir -p "$FISH"; printf 'fish_add_path -g "%s"\n' "$BIN" > "$FISH/mcn.fish"; ADDED="$ADDED fish"
  fi
fi

printf '\n%s✓ %s installed%s\n\n' "$GREEN" "$VERSION" "$RESET"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) printf 'Open a new terminal, or run this to use mcn now:\n  %s. "%s"%s\n\n' "$BOLD" "$ENV_FILE" "$RESET" ;;
esac
printf 'Get started:\n  mcn init my-app\n  cd my-app\n  mcn studio .\n\n'
