<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useElectron } from '@composables/useElectron'
import { useFloatingState } from '@composables/useFloatingState'

const { isMaximized, minimize, maximize, close } = useElectron()
const { floatingState, toggleFloatingMode } = useFloatingState()

// 计算悬浮球按钮的图标和标题
const floatingButtonTitle = computed(() => {
  return floatingState.value === 'classic' ? '进入悬浮球模式' : '退出悬浮球模式'
})

const floatingButtonIcon = computed(() => {
  return floatingState.value === 'classic' ? 'pi-circle' : 'pi-window-minimize'
})

const isFloating = computed(() => {
  return floatingState.value !== 'classic'
})

onMounted(() => {
  // 监听最大化状态变化
  if (typeof window !== 'undefined' && window.electronAPI) {
    // Electron主进程会在最大化/还原时发送事件
    window.addEventListener('maximized', () => {
      isMaximized.value = true
    })
    window.addEventListener('unmaximized', () => {
      isMaximized.value = false
    })
  }
})
</script>

<template>
  <div class="titlebar">
    <div class="titlebar-left">
      <div class="app-icon">M</div>
      <span class="app-title">弥娅</span>
    </div>

    <div class="titlebar-center">
      <span class="window-title">数字生命伴侣</span>
    </div>

    <div class="titlebar-right">
      <button
        class="titlebar-button floating-btn"
        :class="{ active: isFloating }"
        @click="toggleFloatingMode"
        :title="floatingButtonTitle"
      >
        <i :class="floatingButtonIcon"></i>
      </button>
      <button class="titlebar-button minimize-btn" @click="minimize" title="最小化">
        <i class="pi pi-minus"></i>
      </button>
      <button
        class="titlebar-button maximize-btn"
        @click="maximize"
        :title="isMaximized ? '还原' : '最大化'"
      >
        <i :class="isMaximized ? 'pi pi-window-minimize' : 'pi pi-window-maximize'"></i>
      </button>
      <button class="titlebar-button close-btn" @click="close" title="关闭">
        <i class="pi pi-times"></i>
      </button>
    </div>
  </div>
</template>

<style scoped>
.titlebar {
  width: 100%;
  height: 32px;
  background: #16213e;
  border-bottom: 1px solid #2a2a4a;
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
  -webkit-app-region: drag;
}

.titlebar-left,
.titlebar-center,
.titlebar-right {
  display: flex;
  align-items: center;
}

.titlebar-left {
  padding-left: 12px;
  gap: 8px;
}

.app-icon {
  width: 16px;
  height: 16px;
  background: linear-gradient(135deg, #e94560, #8b5cf6);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 8px;
  font-weight: bold;
}

.app-title {
  font-size: 12px;
  font-weight: 500;
  color: #e0e0e0;
}

.titlebar-center {
  flex: 1;
  justify-content: center;
}

.window-title {
  font-size: 12px;
  color: #a0a0a0;
}

.titlebar-right {
  padding-right: 4px;
}

.titlebar-button {
  width: 46px;
  height: 32px;
  border: none;
  background: transparent;
  color: #e0e0e0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  -webkit-app-region: no-drag;
  transition: background 0.2s;
}

.titlebar-button:hover {
  background: rgba(233, 69, 96, 0.1);
}

.titlebar-button i {
  font-size: 14px;
}

.close-btn:hover {
  background: #e94560;
  color: white;
}

.floating-btn {
  color: #e94560;
}

.floating-btn.active {
  background: rgba(233, 69, 96, 0.2);
}
</style>
