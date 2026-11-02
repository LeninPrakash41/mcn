import { Menu, BrowserWindow, app, shell, dialog } from 'electron'
import { readFile } from 'fs/promises'

export function buildMenu(win: BrowserWindow): void {
  const template: Electron.MenuItemConstructorOptions[] = [
    {
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        {
          label: 'Check for Updates…',
          click: () => win.webContents.send('updater:check')
        },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { type: 'separator' },
        { role: 'quit' }
      ]
    },
    {
      label: 'File',
      submenu: [
        {
          label: 'New Script',
          accelerator: 'Cmd+N',
          click: () => win.webContents.send('menu:new-file')
        },
        {
          label: 'Open…',
          accelerator: 'Cmd+O',
          click: async () => {
            const result = await dialog.showOpenDialog(win, {
              properties: ['openFile'],
              filters: [{ name: 'MCN Scripts', extensions: ['mcn', 'mx'] }]
            })
            if (!result.canceled && result.filePaths[0]) {
              const content = await readFile(result.filePaths[0], 'utf-8')
              win.webContents.send('menu:open-file', { path: result.filePaths[0], content })
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Save',
          accelerator: 'Cmd+S',
          click: () => win.webContents.send('menu:save')
        },
        {
          label: 'Save As…',
          accelerator: 'Cmd+Shift+S',
          click: () => win.webContents.send('menu:save-as')
        },
        { type: 'separator' },
        { role: 'close' }
      ]
    },
    { role: 'editMenu' },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Register Installation…',
          click: () => win.webContents.executeJavaScript('openCommunityModal("register")')
        },
        {
          label: 'Submit Feedback & Report Issue…',
          click: () => win.webContents.executeJavaScript('openFeedbackModal()')
        },
        { type: 'separator' },
        {
          label: 'Documentation',
          click: () => shell.openExternal('https://github.com/zeroappz/mcn')
        },
        {
          label: 'Open Web Playground',
          click: () => shell.openExternal(`http://localhost:7842`)
        }
      ]
    }
  ]

  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
}
