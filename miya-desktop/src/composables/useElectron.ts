import { ref, computed } from 'vue'

const isMaximized = ref(false)
const isElectron = typeof window !== 'undefined' && window.electronAPI !== undefined

export function useElectron() {
  // 检查是否最大化
  const checkMaximized = async () => {
    if (isElectron) {
      isMaximized.value = await window.electronAPI.isMaximized()
    }
  }

  // 窗口控制
  const minimize = () => {
    if (isElectron) window.electronAPI.minimize()
  }

  const maximize = () => {
    if (isElectron) window.electronAPI.maximize()
  }

  const close = () => {
    if (isElectron) window.electronAPI.close()
  }

  const quit = () => {
    if (isElectron) window.electronAPI.quit()
  }

  return {
    isElectron,
    isMaximized,
    checkMaximized,
    minimize,
    maximize,
    close,
    quit
  }
}
