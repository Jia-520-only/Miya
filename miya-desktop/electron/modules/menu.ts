import { app, Menu, shell, dialog } from 'electron'
import { getMainWindow } from './window'

export function createMenu(): void {
  const template: Electron.MenuItemConstructorOptions[] = [
    {
      label: '弥娅',
      submenu: [
        {
          label: '关于',
          click: () => {
            const win = getMainWindow()
            if (win) {
              win.show()
              win.webContents.send('navigate', '/about')
            }
          }
        },
        { type: 'separator' },
        {
          label: '设置',
          click: () => {
            const win = getMainWindow()
            if (win) {
              win.show()
              win.webContents.send('navigate', '/settings')
            }
          }
        },
        { type: 'separator' },
        { role: 'quit', label: '退出' }
      ]
    },
    {
      label: '编辑',
      submenu: [
        { role: 'undo', label: '撤销' },
        { role: 'redo', label: '重做' },
        { type: 'separator' },
        { role: 'cut', label: '剪切' },
        { role: 'copy', label: '复制' },
        { role: 'paste', label: '粘贴' },
        { role: 'selectall', label: '全选' }
      ]
    },
    {
      label: '窗口',
      submenu: [
        { role: 'minimize', label: '最小化' },
        { role: 'close', label: '关闭' }
      ]
    },
    {
      label: '帮助',
      submenu: [
        {
          label: '在线文档',
          click: () => {
            shell.openExternal('https://github.com/Jia-520-only/Miya')
          }
        },
        {
          label: '报告问题',
          click: () => {
            shell.openExternal('https://github.com/Jia-520-only/Miya/issues')
          }
        },
        { type: 'separator' },
        {
          label: '开发者工具',
          click: () => {
            const win = getMainWindow()
            if (win) {
              if (win.webContents.isDevToolsOpened()) {
                win.webContents.closeDevTools()
              } else {
                win.webContents.openDevTools()
              }
            }
          }
        }
      ]
    }
  ]

  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
}
