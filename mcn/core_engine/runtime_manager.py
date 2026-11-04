"""
`mcn add`, `mcn upgrade` and `mcn uninstall`: managing an MCN installation.

The one-line installer (install.sh / install.ps1) puts MCN in a private
runtime under ~/.mcn/runtime, provisioned by a bundled tool at
~/.mcn/runtime/bin/uv. Optional features are reinstalled into that runtime as
extras, so they survive upgrades. A copy installed some other way (a source
checkout) falls back to installing into the current environment.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

# feature → (what it enables, setup.py extra)
FEATURES = {
    "postgres":  "PostgreSQL for query() via connect_postgresql()",
    "mongodb":   "MongoDB via connect_mongodb()",
    "ml":        "train(), predict() and the other machine-learning built-ins",
    "scheduler": "schedule blocks that run on a cron timetable",
    "iot":       "real hardware for device(): Raspberry Pi pins, Arduino/ESP32 over USB, MQTT",
}

_FEATURE_PACKAGES = {      # mirrors EXTRAS_REQUIRE in setup.py, for source checkouts
    "postgres": ["psycopg2-binary>=2.9.0"],
    "mongodb": ["pymongo>=4.0.0"],
    "ml": ["scikit-learn>=1.3.0", "pandas>=2.0.0", "numpy>=1.24.0"],
    "scheduler": ["apscheduler>=3.10.0"],
    "iot": ["pyserial>=3.5", "paho-mqtt>=2.0", "gpiozero>=2.0; platform_system == 'Linux'"],
}


def _runtime() -> Path | None:
    """The installer's runtime folder, if this copy of MCN lives in one."""
    prefix = Path(sys.prefix).resolve()
    for parent in prefix.parents:
        if (parent / "bin" / ("uv.exe" if os.name == "nt" else "uv")).exists() and parent.name == "runtime":
            return parent
    return None


def _tool_env(runtime: Path) -> dict:
    home = runtime.parent
    return {**os.environ,
            "UV_PYTHON_INSTALL_DIR": str(runtime / "interpreters"),
            "UV_TOOL_DIR": str(runtime / "tools"),
            "UV_TOOL_BIN_DIR": str(home / "bin"),
            "UV_CACHE_DIR": str(runtime / "cache"),
            "UV_PYTHON_PREFERENCE": "only-managed",
            "UV_NO_PROGRESS": "1"}


def _features_file(runtime: Path) -> Path:
    return runtime / "features"


def _installed_features(runtime: Path) -> list:
    f = _features_file(runtime)
    return f.read_text().split() if f.exists() else []


def _reinstall(runtime: Path, features: list) -> int:
    """Install MCN (with the given features) into the runtime from the saved source."""
    uv = runtime / "bin" / ("uv.exe" if os.name == "nt" else "uv")
    source_file = runtime / "source"
    source = source_file.read_text().strip() if source_file.exists() else \
        "https://github.com/LeninPrakash41/mcn/archive/refs/heads/main.tar.gz"
    extras = f"[{','.join(sorted(features))}]" if features else ""
    log = runtime.parent / "logs" / "install.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w") as out:
        rc = subprocess.call([str(uv), "tool", "install", "--force", "--reinstall-package", "mcn-lang",
                              "--python", "3.12", "--quiet", f"mcn-lang{extras} @ {source}"],
                             env=_tool_env(runtime), stdout=out, stderr=subprocess.STDOUT)
    if rc != 0:
        print(f"✗ That didn't work. Details are in {log}")
        return 1
    subprocess.call([str(uv), "cache", "clean", "--quiet"], env=_tool_env(runtime),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _features_file(runtime).write_text(" ".join(sorted(features)))
    return 0


def add_features(names: list) -> int:
    if not names:
        print("Optional features:\n")
        for name, what in FEATURES.items():
            print(f"  {name:<10} {what}")
        print("\nAdd one with:  mcn add ml")
        return 0
    unknown = [n for n in names if n not in FEATURES]
    if unknown:
        print(f"Unknown feature: {', '.join(unknown)}. Run `mcn add` to list them.")
        return 1
    runtime = _runtime()
    if runtime is None:
        packages = [p for n in names for p in _FEATURE_PACKAGES[n]]
        return subprocess.call([sys.executable, "-m", "pip", "install", "-q", *packages])
    features = sorted(set(_installed_features(runtime)) | set(names))
    print(f"Adding {', '.join(names)}…")
    if _reinstall(runtime, features):
        return 1
    print(f"✓ Added {', '.join(names)}")
    return 0


def upgrade() -> int:
    runtime = _runtime()
    if runtime is None:
        print("This copy of MCN was installed from source. Update it with `git pull` in the repository.")
        return 1
    from mcn.version import __version__ as before
    print("Upgrading MCN…")
    if _reinstall(runtime, _installed_features(runtime)):
        return 1
    mcn = runtime.parent / "bin" / ("mcn.exe" if os.name == "nt" else "mcn")
    after = subprocess.run([str(mcn), "--version"], capture_output=True, text=True).stdout.strip()
    print(f"✓ {after} (was {before})")
    return 0


def uninstall(everything: bool = False) -> int:
    runtime = _runtime()
    if runtime is None:
        print("This copy of MCN wasn't installed by the MCN installer, so there's nothing to remove here.")
        return 1
    home = runtime.parent
    targets = [home] if everything else [home / "bin", runtime, home / "env"]
    if os.name == "nt":
        _remove_windows_path(str(home / "bin"))
        # mcn.exe is running, so delete after this process exits
        cmd = " & ".join(f'rmdir /s /q "{t}"' if t.is_dir() or t == home else f'del /q "{t}"' for t in targets)
        subprocess.Popen(f'cmd /c ping -n 3 127.0.0.1 >nul & {cmd}', shell=True,
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    else:
        for t in targets:
            if t.is_dir():
                shutil.rmtree(t, ignore_errors=True)
            elif t.exists():
                t.unlink()
        # Remove the PATH line the installer added to shell profiles
        env_line = str(home / "env")
        for rc in (".zshrc", ".bashrc", ".bash_profile", ".profile"):
            path = Path.home() / rc
            if path.exists() and env_line in path.read_text():
                kept = [l for l in path.read_text().splitlines() if env_line not in l]
                path.write_text("\n".join(kept).rstrip("\n") + "\n")
        fish = Path.home() / ".config" / "fish" / "conf.d" / "mcn.fish"
        if fish.exists():
            fish.unlink()
    print("✓ MCN was uninstalled. Open a new terminal to finish.")
    if not everything:
        print(f"Your settings, logs and Studio workspace are still in {home}; delete that folder to remove them too.")
    return 0


def _remove_windows_path(bin_dir: str):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as key:
        try:
            value, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            return
        parts = [p for p in value.split(";") if p and os.path.normcase(p.rstrip("\\")) != os.path.normcase(bin_dir)]
        winreg.SetValueEx(key, "Path", 0, kind, ";".join(parts))
