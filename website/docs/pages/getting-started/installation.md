# Installation

MCN installs with one command on macOS, Linux and Windows. Everything it needs comes with it, so there's nothing else to set up first.

## Install

**macOS and Linux**

```bash
curl -fsSL https://raw.githubusercontent.com/LeninPrakash41/mcn/main/install.sh | sh
```

**Windows** (PowerShell)

```bash
powershell -c "irm https://raw.githubusercontent.com/LeninPrakash41/mcn/main/install.ps1 | iex"
```

Then open a new terminal and check it works:

```bash
mcn --version
```

MCN installs into a single folder, `~/.mcn` (`%USERPROFILE%\.mcn` on Windows), and adds `mcn` to your PATH. It doesn't change anything else on your computer.

## Check it works

```bash
mcn init hello-app
cd hello-app
mcn test backend/main.mcn
```

You should see two passing tests. Continue with the [quick start](#/getting-started/quick-start).

## Upgrade and uninstall

```bash
mcn upgrade          # latest version, keeping any features you've added
mcn uninstall        # removes MCN; your projects aren't touched
```

## Optional features

Most of MCN is included from the start. A few heavier features are added on demand:

```bash
mcn add              # list them
mcn add ml           # train() and predict()
mcn add postgres     # PostgreSQL databases
mcn add mongodb      # MongoDB databases
mcn add scheduler    # schedule blocks on a cron timetable
mcn add iot          # real hardware: Raspberry Pi pins, Arduino/ESP32 over USB, MQTT
```

The installer also works on a Raspberry Pi running 64-bit Raspberry Pi OS. See [IoT and hardware](#/guide/iot).

| Also useful | For |
|---|---|
| `ANTHROPIC_API_KEY` | Real AI answers instead of mock replies ([configuration](#/reference/configuration)) |
| `mcn vscode` | The VS Code extension ([details](#/getting-started/vscode)) |
| [Node.js 18+](https://nodejs.org) | Running the React app that `mcn build` generates |
| [Flutter](https://docs.flutter.dev/get-started/install) | Running the generated mobile app |

## Troubleshooting

| Problem | Fix |
|---|---|
| `mcn: command not found` right after installing | Open a new terminal, so it picks up the updated PATH |
| The installer stops with an error | It prints the last lines of its log; the full log is `~/.mcn/logs/install.log`. Re-running it is safe |
| Behind a proxy | Set `HTTPS_PROXY` before running the installer |
| Install somewhere else | Set `MCN_HOME=/path/to/folder` before running the installer |
