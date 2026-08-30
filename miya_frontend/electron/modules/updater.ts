import type { BrowserWindow } from 'electron'

let autoUpdater: any = null

export async function setupAutoUpdater(win: BrowserWindow): Promise<void> {
  try {
    const pkg = await import('electron-updater')
    autoUpdater = pkg.autoUpdater ?? pkg.default?.autoUpdater ?? pkg.default ?? null
  }
  catch {
    console.warn('[Updater] electron-updater not available')
    return
  }

  if (!autoUpdater || typeof autoUpdater.checkForUpdates !== 'function') {
    console.warn('[Updater] autoUpdater unavailable after import')
    autoUpdater = null
    return
  }

  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  autoUpdater.on('update-available', (info: any) => {
    win.webContents.send('updater:update-available', {
      version: info.version,
      releaseNotes: info.releaseNotes,
    })
  })

  autoUpdater.on('update-not-available', () => {
    win.webContents.send('updater:update-not-available')
  })

  autoUpdater.on('download-progress', (progress: any) => {
    win.webContents.send('updater:download-progress', {
      percent: progress.percent,
      bytesPerSecond: progress.bytesPerSecond,
    })
  })

  autoUpdater.on('update-downloaded', () => {
    win.webContents.send('updater:update-downloaded')
  })

  autoUpdater.on('error', (err: Error) => {
    win.webContents.send('updater:error', err.message)
  })

  setTimeout(() => {
    autoUpdater.checkForUpdates().catch(() => {})
  }, 3000)
}

export function downloadUpdate(): void {
  autoUpdater?.downloadUpdate()
}

export function installUpdate(): void {
  autoUpdater?.quitAndInstall()
}
