# MCN Desktop

**MCN Studio** is a native macOS desktop application that wraps the [MCN Web Playground](../web-playground/) in an Electron shell, providing a polished native experience with file system access, native menus, auto-updates, and DMG distribution.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Electron App                       │
│                                                     │
│  ┌─────────────┐        ┌──────────────────────┐   │
│  │ Main Process│        │  BrowserWindow        │   │
│  │             │  IPC   │  (Renderer Process)   │   │
│  │  index.ts   │◄──────►│                       │   │
│  │  menu.ts    │        │  Loads:               │   │
│  │  window.ts  │        │  http://localhost:PORT│   │
│  │  updater.ts │        │  (MCN Web Playground) │   │
│  └──────┬──────┘        └──────────────────────┘   │
│         │                                           │
│         │ spawn                                     │
│         ▼                                           │
│  ┌─────────────┐                                    │
│  │ mcn-server  │  Manages lifecycle of:             │
│  │    .ts      │  python3 server.py --port PORT     │
│  └─────────────┘  (from ../web-playground/)         │
└─────────────────────────────────────────────────────┘
```

### Key Components

| File | Role |
|------|------|
| `src/main/index.ts` | App entry — orchestrates startup, IPC handlers |
| `src/main/mcn-server.ts` | Spawns & manages `server.py`, health-checks, auto-restarts |
| `src/main/window.ts` | `BrowserWindow` factory with macOS-native chrome |
| `src/main/menu.ts` | Native macOS menu (File/Edit/View/Help) |
| `src/main/updater.ts` | `electron-updater` auto-update integration |
| `src/preload/index.ts` | Secure context bridge → `window.mcnDesktop` API |
| `src/renderer/index.html` | Startup splash screen (replaced by playground once server is ready) |

---

## Prerequisites

- **Node.js** ≥ 18
- **npm** ≥ 9
- **Python 3** (must be on `$PATH` as `python3`)
- The MCN web-playground at `../web-playground/` relative to this directory

---

## Development

```bash
# Install dependencies
npm install

# Run in dev mode (hot-reload with electron-vite)
npm run dev
```

In dev mode, `electron-vite` watches for changes and the app auto-reloads. The Python MCN server is spawned pointing at `../../web-playground` (two levels up from `out/main/`).

### Dev Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

---

## Building & Packaging

### Build TypeScript → JS

```bash
npm run build
```

Output goes to `out/`.

### Package to DMG (macOS)

```bash
# Universal binary (arm64 + x86_64)
npm run package:mac

# Or just the current arch
npm run package
```

The DMG will appear in `dist/`. The `web-playground/` directory is bundled automatically via `extraResources` in `electron-builder.yml`.

### What gets bundled

- `out/**` — compiled Electron main/preload
- `resources/` — icon, entitlements
- `../web-playground/**` → `Resources/web-playground/` inside the `.app` bundle (excluding `__pycache__`, `.pyc`, logs, DB)

---

## Auto-Updates

Auto-updates use [electron-updater](https://www.electron.build/auto-update). The updater checks for updates 5 seconds after launch.

### Setup

1. Add a `publish` block to `electron-builder.yml`:

```yaml
publish:
  provider: github
  owner: your-github-username
  repo: mcn
```

2. Create a GitHub release with the built artifacts (`.dmg`, `latest-mac.yml`).

3. The app will automatically detect new releases and notify the renderer via:
   - `updater:update-available` — new version found
   - `updater:download-progress` — download in progress
   - `updater:ready-to-install` — downloaded, prompt user to restart

### Renderer Integration

The playground UI can hook into updates via `window.mcnDesktop`:

```js
window.mcnDesktop.onUpdateAvailable((info) => {
  // Show "Update available" banner
})
window.mcnDesktop.onReadyToInstall(() => {
  // Show "Restart to update" prompt
})
```

---

## Native File API

The preload exposes `window.mcnDesktop` with these methods:

```typescript
// Open a .mcn/.mx file via native file picker
const file = await window.mcnDesktop.openFile()
// → { path: '/Users/.../script.mcn', content: '...' } | null

// Save to an existing path
await window.mcnDesktop.saveFile(path, content)

// Save As — prompts for location
const saved = await window.mcnDesktop.saveFileAs(content)
// → { path: '/Users/.../new.mcn', success: true } | null

// Open a URL in the system browser
await window.mcnDesktop.openExternal('https://github.com/zeroappz/mcn')

// Detect desktop vs. browser
if (window.mcnDesktop?.isDesktop) {
  // Running inside MCN Desktop
}
```

---

## macOS Signing & Notarization

For distribution outside the Mac App Store:

1. Set environment variables before packaging:
   ```bash
   export CSC_NAME="Developer ID Application: Your Name (TEAMID)"
   export APPLE_ID="you@example.com"
   export APPLE_APP_SPECIFIC_PASSWORD="xxxx-xxxx-xxxx-xxxx"
   export APPLE_TEAM_ID="TEAMID"
   ```

2. Add `afterSign` hook in `electron-builder.yml` for notarization (or use `notarize` package).

3. Run `npm run package:mac`.

---

## Project Structure

```
desktop/
├── package.json
├── tsconfig.json
├── electron.vite.config.ts
├── electron-builder.yml
├── .env.example
├── src/
│   ├── main/
│   │   ├── index.ts          ← App entry & IPC
│   │   ├── mcn-server.ts     ← Python server lifecycle
│   │   ├── menu.ts           ← Native macOS menus
│   │   ├── updater.ts        ← Auto-updater
│   │   └── window.ts         ← BrowserWindow factory
│   ├── preload/
│   │   └── index.ts          ← Context bridge (window.mcnDesktop)
│   └── renderer/
│       └── index.html        ← Startup splash screen
├── resources/
│   ├── icon.png              ← 512×512 app icon (add yours here)
│   └── entitlements.mac.plist
└── README.md
```

> **Icon**: Place a 512×512 PNG at `resources/icon.png` before packaging.
> electron-builder will generate `icns` automatically from it.
