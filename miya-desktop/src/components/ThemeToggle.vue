<script setup lang="ts">
import { computed } from 'vue'
import { useSettingsStore } from '../stores/settings'

const settingsStore = useSettingsStore()

const isDark = computed(() => settingsStore.isDark)

function toggleTheme() {
  const newTheme = isDark.value ? 'light' : 'dark'
  settingsStore.updateSetting('theme', newTheme)
}
</script>

<template>
  <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '切换到亮色模式' : '切换到暗色模式'">
    <i v-if="isDark" class="pi pi-sun"></i>
    <i v-else class="pi pi-moon"></i>
  </button>
</template>

<style scoped>
.theme-toggle {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.theme-toggle:hover {
  background: rgba(233, 69, 96, 0.2);
  border-color: rgba(233, 69, 96, 0.3);
  transform: rotate(180deg);
}

.theme-toggle:active {
  transform: rotate(180deg) scale(0.95);
}

/* 亮色主题 */
:deep(.light-mode .theme-toggle) {
  background: rgba(0, 0, 0, 0.05);
  border-color: rgba(0, 0, 0, 0.1);
}

:deep(.light-mode .theme-toggle:hover) {
  background: rgba(233, 69, 96, 0.1);
}
</style>
