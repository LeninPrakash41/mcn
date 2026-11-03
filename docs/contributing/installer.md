# Installer and runtime

Developers install MCN with one command and never manage its implementation language. This page explains what that command sets up.

```bash
curl -fsSL https://raw.githubusercontent.com/LeninPrakash41/mcn/main/install.sh | sh          # macOS, Linux
powershell -c "irm https://raw.githubusercontent.com/LeninPrakash41/mcn/main/install.ps1 | iex"  # Windows
```

## What the installer does

1. Downloads [uv](https://github.com/astral-sh/uv) (a single static binary, version pinned in the script as `UV_VERSION`) and verifies its SHA-256 checksum.
2. Uses it to create a private environment with its own managed Python 3.12 (`UV_PYTHON_PREFERENCE=only-managed`, so the system Python is never used or modified) and installs the `mcn-lang` package into it, from `MCN_SOURCE` (default: the `main` branch archive, so git isn't needed either).
3. Puts the `mcn` launcher in `~/.mcn/bin` and adds that folder to the PATH: a line sourcing `~/.mcn/env` in the shell profile on macOS/Linux, the user `Path` on Windows.
4. Prunes the download cache.

Output is limited to three steps and a summary; everything else goes to `~/.mcn/logs/install.log`, whose tail is printed on failure.

```text
~/.mcn/
├── bin/mcn                     # the command developers run
├── env                         # PATH snippet sourced by the shell profile
├── logs/install.log
└── runtime/
    ├── bin/uv                  # bootstrap tool
    ├── interpreters/           # managed interpreter
    ├── tools/mcn-lang/         # MCN's isolated environment
    ├── source                  # where MCN was installed from (used by upgrade)
    └── features                # optional features added with `mcn add`
```

## mcn add, upgrade, uninstall

`mcn/core_engine/runtime_manager.py` detects an installer-managed copy by finding `runtime/bin/uv` above `sys.prefix`.

- `mcn add <feature>` reinstalls MCN with the extra (`mcn-lang[ml] @ <source>`), so features survive upgrades. The extras are `EXTRAS_REQUIRE` in `setup.py`; keep `FEATURES` and `_FEATURE_PACKAGES` in `runtime_manager.py` in step with it.
- `mcn upgrade` reinstalls from the saved source with the saved features.
- `mcn uninstall` removes `bin/`, `runtime/` and `env`, and the PATH entries; `--all` removes the whole `~/.mcn`.

From a source checkout (`pip install -e .`), `add` falls back to installing into the current environment, and `upgrade`/`uninstall` explain that they don't apply.

## Dependencies

Runtime dependencies are `INSTALL_REQUIRES` in `setup.py` — declared there, not read from a file, so every kind of build gets the same list. Anything heavy or rarely needed is an extra, imported lazily, with an error that names the `mcn add` command when it's missing.

## Testing the installer

```bash
env -i HOME=/tmp/mcn-home PATH=/usr/bin:/bin SHELL=/bin/zsh \
    MCN_SOURCE="file://$PWD" sh install.sh
```

`MCN_SOURCE=file://…` installs the working tree instead of `main`; the empty environment proves nothing from the host leaks in.

## Developer-facing wording

User-facing text — the website, `mcn` messages, Studio, the VS Code extension, files generated for users' projects — describes MCN as its own language and tools. Don't tell developers to run `pip`, mention virtual environments, or name the implementation language there; give the `mcn` command that does the job (`mcn add`, `mcn upgrade`). Contributor docs like this folder are the place for implementation details.
