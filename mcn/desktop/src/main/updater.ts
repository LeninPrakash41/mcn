import { autoUpdater } from 'electron-updater'
import { BrowserWindow } from 'electron'

export function setupUpdater(win: BrowserWindow): void {
  autoUpdater.autoDownload = false
  autoUpdater.logger = console

  autoUpdater.on('update-available', (info) => {
    win.webContents.send('updater:update-available', info)
  })

  autoUpdater.on('update-not-available', () => {
    // Silently ignore — only notify on explicit user check
  })

  autoUpdater.on('download-progress', (progress) => {
    win.webContents.send('updater:download-progress', progress)
  })

  autoUpdater.on('update-downloaded', () => {
    win.webContents.send('updater:ready-to-install')
  })

  autoUpdater.on('error', (err) => {
    console.error('[Updater] Error:', err.message)
    win.webContents.send('updater:error', err.message)
  })

  // Check on startup after a 5-second delay to not block initial load
  setTimeout(() => {
    autoUpdater.checkForUpdates().catch((err) => {
      console.warn('[Updater] Check failed:', err.message)
    })
  }, 5000)
}
