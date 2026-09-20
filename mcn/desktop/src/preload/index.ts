import { contextBridge, ipcRenderer } from 'electron'

export interface MCNDesktopAPI {
  // File operations
  openFile: () => Promise<{ path: string; content: string } | null>
  saveFile: (path: string, content: string) => Promise<{ success: boolean }>
  saveFileAs: (content: string) => Promise<{ path: string; success: boolean } | null>

  // Shell
  openExternal: (url: string) => Promise<void>

  // Theme
  getSystemTheme: () => Promise<'dark' | 'light'>

  // Menu-driven events (renderer registers callbacks)
  onMenuNewFile: (cb: () => void) => void
  onMenuOpenFile: (cb: (data: { path: string; content: string }) => void) => void
  onMenuSave: (cb: () => void) => void
  onMenuSaveAs: (cb: () => void) => void

  // Updater events
  onUpdateAvailable: (cb: (info: unknown) => void) => void
  onDownloadProgress: (cb: (progress: unknown) => void) => void
  onReadyToInstall: (cb: () => void) => void

  // App metadata
  isDesktop: true
  platform: NodeJS.Platform
}

const api: MCNDesktopAPI = {
  // File operations
  openFile: () => ipcRenderer.invoke('file:open'),
  saveFile: (path: string, content: string) =>
    ipcRenderer.invoke('file:save', { path, content }),
  saveFileAs: (content: string) =>
    ipcRenderer.invoke('file:saveAs', { content }),

  // Shell
  openExternal: (url: string) => ipcRenderer.invoke('shell:openExternal', url),

  // Theme
  getSystemTheme: () => ipcRenderer.invoke('theme:get'),

  // Menu events
  onMenuNewFile: (cb: () => void) => {
    ipcRenderer.on('menu:new-file', cb)
  },
  onMenuOpenFile: (cb: (data: { path: string; content: string }) => void) => {
    ipcRenderer.on('menu:open-file', (_event, data) => cb(data))
  },
  onMenuSave: (cb: () => void) => {
    ipcRenderer.on('menu:save', cb)
  },
  onMenuSaveAs: (cb: () => void) => {
    ipcRenderer.on('menu:save-as', cb)
  },

  // Updater events
  onUpdateAvailable: (cb: (info: unknown) => void) => {
    ipcRenderer.on('updater:update-available', (_event, info) => cb(info))
  },
  onDownloadProgress: (cb: (progress: unknown) => void) => {
    ipcRenderer.on('updater:download-progress', (_event, progress) => cb(progress))
  },
  onReadyToInstall: (cb: () => void) => {
    ipcRenderer.on('updater:ready-to-install', cb)
  },

  // App metadata
  isDesktop: true,
  platform: process.platform
}

contextBridge.exposeInMainWorld('mcnDesktop', api)
