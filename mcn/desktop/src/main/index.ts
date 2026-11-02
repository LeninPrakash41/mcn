import { app, BrowserWindow, ipcMain, dialog, shell, nativeTheme } from 'electron'
import { join } from 'path'
import { MCNServer } from './mcn-server'
import { buildMenu } from './menu'
import { createWindow } from './window'
import { setupUpdater } from './updater'

let mainWindow: BrowserWindow | null = null
let mcnServer: MCNServer | null = null

app.whenReady().then(async () => {
  // Start Python MCN server
  mcnServer = new MCNServer()
  const port = await mcnServer.start()

  // Create main window
  mainWindow = await createWindow(port)

  // Build native menu
  buildMenu(mainWindow)

  // Setup auto-updater
  setupUpdater(mainWindow)

  // IPC handlers
  setupIPC(mainWindow)
})

app.on('window-all-closed', () => {
  mcnServer?.stop()
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0 && mainWindow) {
    mainWindow.show()
  }
})

function setupIPC(win: BrowserWindow): void {
  // File operations
  ipcMain.handle('file:open', async () => {
    const result = await dialog.showOpenDialog(win, {
      properties: ['openFile'],
      filters: [{ name: 'MCN Scripts', extensions: ['mcn', 'mx'] }]
    })
    if (!result.canceled && result.filePaths[0]) {
      const { readFile } = await import('fs/promises')
      const content = await readFile(result.filePaths[0], 'utf-8')
      return { path: result.filePaths[0], content }
    }
    return null
  })

  ipcMain.handle('file:save', async (_, { path, content }: { path: string; content: string }) => {
    const { writeFile } = await import('fs/promises')
    await writeFile(path, content, 'utf-8')
    return { success: true }
  })

  ipcMain.handle('file:saveAs', async (_, { content }: { content: string }) => {
    const result = await dialog.showSaveDialog(win, {
      filters: [{ name: 'MCN Scripts', extensions: ['mcn', 'mx'] }]
    })
    if (!result.canceled && result.filePath) {
      const { writeFile } = await import('fs/promises')
      await writeFile(result.filePath, content, 'utf-8')
      return { path: result.filePath, success: true }
    }
    return null
  })

  ipcMain.handle('shell:openExternal', (_, url: string) => {
    shell.openExternal(url)
  })

  // Theme
  ipcMain.handle('theme:get', () => nativeTheme.shouldUseDarkColors ? 'dark' : 'light')
}
