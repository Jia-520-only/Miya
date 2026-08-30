import { globalShortcut, BrowserWindow } from 'electron'
import { getMainWindow, getFloatingState } from './window'

let shortcutsRegistered = false

export function registerHotkeys(): void {
  if (shortcutsRegistered) return

  // Alt+Space 显示/隐藏主窗口
  globalShortcut.register('Alt+Space', () => {
    const win = getMainWindow()
    if (!win) return

    if (win.isVisible()) {
      win.hide()
    } else {
      win.show()
      win.focus()
    }
  })

  // Alt+F 进入/退出悬浮球模式
  globalShortcut.register('Alt+F', () => {
    const win = getMainWindow()
    if (!win) return

    const state = getFloatingState()
    if (state === 'classic') {
      win.webContents.send('floating:enter')
    } else {
      win.webContents.send('floating:exit')
    }
  })

  // Alt+C 快速聊天(展开悬浮球)
  globalShortcut.register('Alt+C', () => {
    const win = getMainWindow()
    if (!win) return

    const state = getFloatingState()
    if (state === 'classic') {
      win.webContents.send('floating:enter')
    }

    win.show()
    win.focus()
    win.webContents.send('quick:chat')
  })

  shortcutsRegistered = true
}

export function unregisterHotkeys(): void {
  if (!shortcutsRegistered) return

  globalShortcut.unregisterAll()
  shortcutsRegistered = false
}
