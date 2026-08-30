const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // 窗口控制
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:isMaximized'),

  // 悬浮球控制
  enterFloatingMode: () => ipcRenderer.invoke('floating:enter'),
  exitFloatingMode: () => ipcRenderer.invoke('floating:exit'),

  // Live2D 控制
  live2d: {
    create: () => ipcRenderer.invoke('live2d:create'),
    get: () => ipcRenderer.invoke('live2d:get'),
    close: () => {
      console.log('[Preload] live2d:close 被调用，发送 IPC 请求')
      return ipcRenderer.invoke('live2d:close')
    },
    toggle: () => ipcRenderer.invoke('live2d:toggle'),
    setSize: (width: number, height: number) => ipcRenderer.invoke('live2d:setSize', width, height),
    getSize: () => ipcRenderer.invoke('live2d:getSize'),
    setPosition: (x: number, y: number) => ipcRenderer.invoke('live2d:setPosition', x, y),
    setAlwaysOnTop: (alwaysOnTop: boolean) => ipcRenderer.invoke('live2d:setAlwaysOnTop', alwaysOnTop),
    sendExpression: (index: number) => {
      ipcRenderer.send('live2d:setExpression', index)
    },
    sendMotion: (index: number) => {
      ipcRenderer.send('live2d:setMotion', index)
    },
    sendModelChange: (modelId: string) => {
      ipcRenderer.send('live2d:setModelChange', modelId)
    },
    onExpression: (callback: (index: number) => void) => {
      ipcRenderer.on('live2d:setExpression', (_event: any, index: number) => callback(index))
    },
    onMotion: (callback: (index: number) => void) => {
      ipcRenderer.on('live2d:setMotion', (_event: any, index: number) => callback(index))
    },
    onModelChange: (callback: (modelId: string) => void) => {
      ipcRenderer.on('live2d:setModelChange', (_event: any, modelId: string) => callback(modelId))
    },
    onClosed: (callback: () => void) => {
      ipcRenderer.on('live2d:closed', () => callback())
    }
  },

  // 控制鼠标穿透（用于桌宠）
  setIgnoreMouseEvents: (ignore: boolean, options?: { forward?: boolean }) => {
    ipcRenderer.send('set-ignore-mouse-events', ignore, options)
  },

  // 应用控制
  quit: () => ipcRenderer.send('app:quit'),

  // 控制主窗口 Live2D 显示/隐藏（避免与桌宠窗口 WebGL 冲突）
  sendHideMainLive2D: () => ipcRenderer.send('main-live2d:hide'),
  sendShowMainLive2D: () => ipcRenderer.send('main-live2d:show'),

  // 监听事件
  onFloatingStateChanged: (callback: (state: string) => void) => {
    ipcRenderer.on('floating:stateChanged', (_event: any, state: string) => callback(state))
  },
  onNavigate: (callback: (path: string) => void) => {
    ipcRenderer.on('navigate', (_event: any, path: string) => callback(path))
  },
  onQuickChat: (callback: () => void) => {
    ipcRenderer.on('quick:chat', () => callback())
  },
  // 主窗口 Live2D 显示/隐藏事件
  onMainLive2DHide: (callback: () => void) => {
    ipcRenderer.on('main-live2d:hide', () => callback())
  },
  onMainLive2DShow: (callback: () => void) => {
    ipcRenderer.on('main-live2d:show', () => callback())
  },

  // 移除监听
  removeAllListeners: () => {
    ipcRenderer.removeAllListeners('floating:stateChanged')
    ipcRenderer.removeAllListeners('navigate')
    ipcRenderer.removeAllListeners('quick:chat')
    ipcRenderer.removeAllListeners('live2d:setExpression')
    ipcRenderer.removeAllListeners('live2d:setMotion')
    ipcRenderer.removeAllListeners('live2d:setModelChange')
    ipcRenderer.removeAllListeners('main-live2d:hide')
    ipcRenderer.removeAllListeners('main-live2d:show')
  },

  // 桌宠窗口专用 API
  startDrag: () => ipcRenderer.send('live2d:startDrag'),

  onLive2DSetExpression: (callback: (index: number) => void) => {
    ipcRenderer.on('live2d:setExpression', (_event: any, index: number) => callback(index))
  },
  onLive2DSetMotion: (callback: (index: number) => void) => {
    ipcRenderer.on('live2d:setMotion', (_event: any, index: number) => callback(index))
  },
  onLive2DSetModelChange: (callback: (modelId: string) => void) => {
    ipcRenderer.on('live2d:setModelChange', (_event: any, modelId: string) => callback(modelId))
  }
})

// 平台信息
contextBridge.exposeInMainWorld('platform', {
  platform: process.platform,
  arch: process.arch
})

