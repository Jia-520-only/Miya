import { ref } from 'vue'
import type { FloatingState } from '@/electron.d'

const floatingState = ref<FloatingState>('classic')

export function useFloatingState() {
  const setFloatingState = (state: FloatingState) => {
    floatingState.value = state
    console.log('[FloatingState] 状态设置为:', state)
  }

  const toggleFloatingMode = () => {
    console.log('[FloatingState] 当前状态:', floatingState.value)
    if (floatingState.value === 'classic') {
      console.log('[FloatingState] 进入悬浮球模式')
      enterFloatingMode()
    } else {
      console.log('[FloatingState] 退出悬浮球模式')
      exitFloatingMode()
    }
  }

  const enterFloatingMode = async () => {
    if (typeof window !== 'undefined' && window.electronAPI) {
      console.log('[FloatingState] 调用 enterFloatingMode')
      try {
        await window.electronAPI.enterFloatingMode()
        floatingState.value = 'ball'
        console.log('[FloatingState] 成功进入悬浮球模式')
      } catch (error) {
        console.error('[FloatingState] 进入悬浮球模式失败:', error)
      }
    }
  }

  const exitFloatingMode = async () => {
    if (typeof window !== 'undefined' && window.electronAPI) {
      console.log('[FloatingState] 调用 exitFloatingMode')
      try {
        await window.electronAPI.exitFloatingMode()
        floatingState.value = 'classic'
        console.log('[FloatingState] 成功退出悬浮球模式')
      } catch (error) {
        console.error('[FloatingState] 退出悬浮球模式失败:', error)
      }
    }
  }

  // 监听来自主进程的状态变化
  if (typeof window !== 'undefined' && window.electronAPI?.onFloatingStateChanged) {
    window.electronAPI.onFloatingStateChanged((state: string) => {
      console.log('[FloatingState] 收到状态变化:', state)
      floatingState.value = state as FloatingState
    })
  }

  return {
    floatingState,
    setFloatingState,
    toggleFloatingMode,
    enterFloatingMode,
    exitFloatingMode
  }
}
