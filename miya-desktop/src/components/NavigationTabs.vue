<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const tabs = [
  { name: '对话', path: '/chat', icon: 'pi-comments' },
  { name: '代码', path: '/code', icon: 'pi-code' },
  { name: '终端', path: '/terminal', icon: 'pi-terminal' },
  { name: '文件', path: '/files', icon: 'pi-folder' },
  { name: '分析', path: '/analytics', icon: 'pi-chart-line' },
  { name: '调研', path: '/research', icon: 'pi-search' },
  { name: '任务', path: '/tasks', icon: 'pi-bolt' },
  { name: '监控', path: '/monitor', icon: 'pi-chart-bar' }
]

const activeTab = computed(() => {
  return tabs.find(tab => route.path.startsWith(tab.path))?.path || '/chat'
})

const navigateTo = (path: string) => {
  router.push(path)
}
</script>

<template>
  <div class="navigation-tabs">
    <div
      v-for="tab in tabs"
      :key="tab.path"
      class="tab-item"
      :class="{ active: activeTab === tab.path }"
      @click="navigateTo(tab.path)"
    >
      <i :class="tab.icon"></i>
      <span>{{ tab.name }}</span>
    </div>
  </div>
</template>

<style scoped>
.navigation-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(45, 212, 191, 0.2);
  overflow-x: auto;
  pointer-events: auto;
  position: relative;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: transparent;
  border-radius: 8px;
  color: rgba(45, 212, 191, 0.7);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  white-space: nowrap;
  pointer-events: auto;
  user-select: none;
  border: 1px solid transparent;
}

.tab-item:hover {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.15) 0%, rgba(13, 148, 136, 0.15) 100%);
  color: #2dd4bf;
  border-color: rgba(45, 212, 191, 0.3);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(45, 212, 191, 0.2);
}

.tab-item:active {
  transform: translateY(0) scale(0.98);
}

.tab-item.active {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.25) 0%, rgba(13, 148, 136, 0.25) 100%);
  color: #2dd4bf;
  border-color: #2dd4bf;
  box-shadow: 0 0 20px rgba(45, 212, 191, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1);
  font-weight: 600;
}

.tab-item i {
  font-size: 16px;
  opacity: 0.85;
}

.tab-item.active i {
  opacity: 1;
  filter: drop-shadow(0 0 6px rgba(45, 212, 191, 0.5));
}

/* 亮色主题 */
:deep(.light-mode .navigation-tabs) {
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom-color: rgba(13, 148, 136, 0.2);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

:deep(.light-mode .tab-item) {
  color: #0d9488;
}

:deep(.light-mode .tab-item:hover) {
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.1) 0%, rgba(6, 95, 70, 0.1) 100%);
  color: #0f766e;
  border-color: rgba(13, 148, 136, 0.3);
}

:deep(.light-mode .tab-item.active) {
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.15) 0%, rgba(6, 95, 70, 0.15) 100%);
  color: #0f766e;
  border-color: #0d9488;
  box-shadow: 0 0 20px rgba(13, 148, 136, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.3);
}
</style>
