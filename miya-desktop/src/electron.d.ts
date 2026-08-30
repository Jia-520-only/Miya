// Live2D 控制类型
export interface Live2DControl {
  create: () => Promise<void>
  get: () => Promise<void>
  close: () => Promise<void>
  toggle: () => Promise<void>
  setSize: (width: number, height: number) => Promise<void>
  getSize: () => Promise<{ width: number; height: number }>
  setPosition: (x: number, y: number) => Promise<void>
  setAlwaysOnTop: (alwaysOnTop: boolean) => Promise<void>
  sendExpression: (index: number) => void
  sendMotion: (index: number) => void
  sendModelChange: (modelId: string) => void
  onExpression: (callback: (index: number) => void) => void
  onMotion: (callback: (index: number) => void) => void
  onModelChange: (callback: (modelId: string) => void) => void
}

// Electron API类型定义
export interface ElectronAPI {
  // 窗口控制
  minimize: () => void
  maximize: () => void
  close: () => void
  isMaximized: () => Promise<boolean>

  // 悬浮球控制
  enterFloatingMode: () => Promise<void>
  exitFloatingMode: () => Promise<void>

  // Live2D 控制
  live2d: Live2DControl

  // 控制鼠标穿透（用于桌宠）
  setIgnoreMouseEvents: (ignore: boolean, options?: { forward?: boolean }) => void

  // 应用控制
  quit: () => void

  // 监听事件
  onFloatingStateChanged: (callback: (state: string) => void) => void
  onNavigate: (callback: (path: string) => void) => void
  onQuickChat: (callback: () => void) => void

  // 移除监听
  removeAllListeners: () => void
}

// 悬浮球状态类型
export type FloatingState = 'classic' | 'ball' | 'compact' | 'full'

// 平台信息
export interface PlatformInfo {
  platform: NodeJS.Platform
  arch: string
}

// 全局声明
declare global {
  interface Window {
    electronAPI: ElectronAPI
    platform: PlatformInfo
  }
}

export {}
