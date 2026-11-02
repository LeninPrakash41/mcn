import { BrowserWindow, shell } from 'electron'
import { join } from 'path'

export async function createWindow(serverPort: number): Promise<BrowserWindow> {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',    // macOS: traffic lights inset into window chrome
    vibrancy: 'sidebar',             // macOS frosted glass sidebar effect
    visualEffectState: 'active',
    backgroundColor: '#0A0F1D',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    },
    icon: join(__dirname, '../../resources/icon.png')
  })

  // Clear cache in development mode so UI updates always reflect immediately
  await win.webContents.session.clearCache()

  // Inject desktop flags so the playground UI can detect it's running in the app
  win.webContents.on('did-finish-load', () => {
    win.webContents.executeJavaScript(
      `window.__MCN_SERVER_PORT__ = ${serverPort}; window.__MCN_DESKTOP__ = true; document.documentElement.classList.add('is-desktop'); if (/(Mac|iPhone|iPod|iPad)/i.test(navigator.platform || navigator.userAgent)) document.documentElement.classList.add('is-mac-desktop');`
    ).catch(() => {})
  })

  // Load the MCN playground from the embedded Python server
  await win.loadURL(`http://localhost:${serverPort}`)

  // Open external links in the system default browser, not a new Electron window
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      shell.openExternal(url)
    }
    return { action: 'deny' }
  })

  return win
}
