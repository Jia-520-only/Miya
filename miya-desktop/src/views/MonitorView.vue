<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSystemStore } from '../stores/system'
import { systemApi } from '../api/system'
import NavigationTabs from '../components/NavigationTabs.vue'
import ProgressChart from '../components/ProgressChart.vue'
import CircleChart from '../components/CircleChart.vue'

const systemStore = useSystemStore()

const refreshInterval = ref<NodeJS.Timeout | null>(null)
const activeTab = ref('overview')

onMounted(() => {
  loadSystemInfo()
  startAutoRefresh()
})

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
})

async function loadSystemInfo() {
  systemStore.setLoading(true)
  try {
    const info = await systemApi.getInfo()
    if (info) {
      systemStore.setInfo(info)
    }
  } catch (error) {
    console.error('Failed to load system info:', error)
  } finally {
    systemStore.setLoading(false)
  }
}

function startAutoRefresh() {
  refreshInterval.value = setInterval(() => {
    loadSystemInfo()
  }, 5000) // 每5秒刷新一次
}

function formatPercent(value: number): string {
  return value.toFixed(1) + '%'
}

// CPU 颜色
const cpuColor = computed(() => {
  const percent = systemStore.cpuUsagePercent
  if (percent < 50) return '#22c55e'
  if (percent < 80) return '#eab308'
  return '#ef4444'
})

// 内存颜色
const memoryColor = computed(() => {
  const percent = systemStore.memoryUsagePercent
  if (percent < 70) return '#22c55e'
  if (percent < 90) return '#eab308'
  return '#ef4444'
})

// 磁盘颜色
const diskColor = computed(() => {
  const percent = systemStore.diskUsagePercent
  if (percent < 70) return '#22c55e'
  if (percent < 90) return '#eab308'
  return '#ef4444'
})
</script>

<template>
  <div class="monitor-view">
    <!-- 导航标签 -->
    <div class="navigation-wrapper">
      <NavigationTabs />
    </div>

    <!-- 标签页导航 -->
    <div class="tabs">
      <button
        v-for="tab in ['overview', 'cpu', 'memory', 'disk']"
        :key="tab"
        class="tab"
        :class="{ active: activeTab === tab }"
        @click="activeTab = tab"
      >
        {{ tab === 'overview' ? '概览' : tab === 'cpu' ? 'CPU' : tab === 'memory' ? '内存' : '磁盘' }}
      </button>
    </div>

    <!-- 概览页面 -->
    <div v-if="activeTab === 'overview'" class="overview-content">
      <div class="overview-grid">
        <!-- 弥娅状态卡片 -->
        <div class="card personality-card">
          <div class="card-header">
            <h3>弥娅状态</h3>
            <span class="status-badge online">
              <i class="pi pi-check-circle"></i>
              在线
            </span>
          </div>
          <div class="personality-grid">
            <CircleChart
              :value="systemStore.emotion?.intensity * 100 || 50"
              :size="80"
              :label="systemStore.emotion?.dominant || '平静'"
              :color="systemStore.emotionColor"
            />
            <div class="personality-details">
              <div class="detail-item">
                <span class="detail-label">当前情绪</span>
                <span class="detail-value emotion">
                  {{ systemStore.emotionEmoji }} {{ systemStore.emotion?.dominant || '平静' }}
                </span>
              </div>
              <div class="detail-item">
                <span class="detail-label">主导人格</span>
                <span class="detail-value">{{ systemStore.personalityDominant }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">版本</span>
                <span class="detail-value">1.0.0</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 系统资源概览 -->
        <div class="card resources-card">
          <div class="card-header">
            <h3>系统资源</h3>
            <button class="refresh-btn" @click="loadSystemInfo" :disabled="systemStore.isLoading">
              <i class="pi pi-refresh" :class="{ spinning: systemStore.isLoading }"></i>
            </button>
          </div>
          <div class="resources-grid">
            <div class="resource-item">
              <CircleChart
                :value="systemStore.cpuUsagePercent"
                :size="100"
                label="CPU"
                :color="cpuColor"
              />
            </div>
            <div class="resource-item">
              <CircleChart
                :value="systemStore.memoryUsagePercent"
                :size="100"
                label="内存"
                :color="memoryColor"
              />
            </div>
            <div class="resource-item">
              <CircleChart
                :value="systemStore.diskUsagePercent"
                :size="100"
                label="磁盘"
                :color="diskColor"
              />
            </div>
          </div>
        </div>

        <!-- 网络状态卡片 -->
        <div class="card network-card">
          <div class="card-header">
            <h3>网络状态</h3>
          </div>
          <div class="network-info">
            <div class="network-item">
              <i class="pi pi-globe"></i>
              <div class="network-details">
                <span class="network-label">连接状态</span>
                <span class="network-value connected">已连接</span>
              </div>
            </div>
            <div class="network-item">
              <i class="pi pi-wifi"></i>
              <div class="network-details">
                <span class="network-label">延迟</span>
                <span class="network-value">12ms</span>
              </div>
            </div>
            <div class="network-item">
              <i class="pi pi-bolt"></i>
              <div class="network-details">
                <span class="network-label">API状态</span>
                <span class="network-value">正常</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 运行时间卡片 -->
        <div class="card uptime-card">
          <div class="card-header">
            <h3>运行信息</h3>
          </div>
          <div class="uptime-grid">
            <div class="uptime-item">
              <span class="uptime-label">运行时间</span>
              <span class="uptime-value">2小时34分</span>
            </div>
            <div class="uptime-item">
              <span class="uptime-label">消息总数</span>
              <span class="uptime-value">1,234</span>
            </div>
            <div class="uptime-item">
              <span class="uptime-label">会话数</span>
              <span class="uptime-value">56</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- CPU 详情 -->
    <div v-if="activeTab === 'cpu'" class="detail-content">
      <div class="card">
        <div class="card-header">
          <h3>CPU 使用率</h3>
        </div>
        <ProgressChart
          :value="systemStore.cpuUsagePercent"
          label="当前使用率"
          :color="cpuColor"
          size="lg"
        />
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">核心数</span>
            <span class="info-value">{{ systemStore.info?.cpu.count || 0 }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">处理器</span>
            <span class="info-value">{{ systemStore.info?.system.processor || 'Unknown' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 内存详情 -->
    <div v-if="activeTab === 'memory'" class="detail-content">
      <div class="card">
        <div class="card-header">
          <h3>内存使用</h3>
        </div>
        <ProgressChart
          :value="systemStore.memoryUsagePercent"
          label="使用率"
          :color="memoryColor"
          size="lg"
        />
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">总内存</span>
            <span class="info-value">{{ systemStore.formatBytes(systemStore.info?.memory.total || 0) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">可用内存</span>
            <span class="info-value">{{ systemStore.formatBytes(systemStore.info?.memory.available || 0) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">已用内存</span>
            <span class="info-value">{{ systemStore.formatBytes((systemStore.info?.memory.total || 0) - (systemStore.info?.memory.available || 0)) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 磁盘详情 -->
    <div v-if="activeTab === 'disk'" class="detail-content">
      <div class="card">
        <div class="card-header">
          <h3>磁盘使用</h3>
        </div>
        <ProgressChart
          :value="systemStore.diskUsagePercent"
          label="使用率"
          :color="diskColor"
          size="lg"
        />
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">总容量</span>
            <span class="info-value">{{ systemStore.formatBytes(systemStore.info?.disk.total || 0) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">已用空间</span>
            <span class="info-value">{{ systemStore.formatBytes(systemStore.info?.disk.used || 0) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">可用空间</span>
            <span class="info-value">{{ systemStore.formatBytes(systemStore.info?.disk.free || 0) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.monitor-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  position: relative;
  padding: 8px;
  box-sizing: border-box;
}

.monitor-view::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(6, 78, 59, 0.6) 0%, rgba(5, 46, 41, 0.8) 100%);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 12px;
  z-index: -1;
  border: 1px solid rgba(45, 212, 191, 0.15);
}

.navigation-wrapper {
  z-index: 100;
}

.tabs {
  display: flex;
  gap: 4px;
  padding: 12px 20px;
  background: rgba(0, 0, 0, 0.25);
  border-bottom: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 12px 12px 0 0;
}

.tab {
  padding: 8px 18px;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab:hover {
  background: rgba(45, 212, 191, 0.15);
  color: #e0f2fe;
}

.tab.active {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.3) 0%, rgba(13, 148, 136, 0.3) 100%);
  color: #2dd4bf;
  font-weight: 500;
}

.overview-content,
.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 16px;
}

.card {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 16px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.online {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.refresh-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border);
  color: var(--text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(233, 69, 96, 0.2);
  border-color: rgba(233, 69, 96, 0.3);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.refresh-btn .spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.personality-card {
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.1), rgba(139, 92, 246, 0.1));
}

.personality-grid {
  display: flex;
  align-items: center;
  gap: 24px;
}

.personality-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.detail-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.detail-value.emotion {
  font-size: 16px;
}

.resources-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 20px;
}

.resource-item {
  display: flex;
  justify-content: center;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-top: 20px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
}

.info-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.info-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* 网络状态卡片 */
.network-card {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.1), rgba(14, 165, 233, 0.1));
}

.network-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.network-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(45, 212, 191, 0.08);
  border-radius: 8px;
}

.network-item i {
  font-size: 20px;
  color: #2dd4bf;
  width: 24px;
}

.network-details {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.network-label {
  font-size: 12px;
  color: #94a3b8;
}

.network-value {
  font-size: 14px;
  font-weight: 600;
  color: #e0f2fe;
}

.network-value.connected {
  color: #22c55e;
}

/* 运行时间卡片 */
.uptime-card {
  background: linear-gradient(135deg, rgba(167, 139, 250, 0.1), rgba(139, 92, 246, 0.1));
}

.uptime-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 12px;
}

.uptime-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 16px;
  background: rgba(167, 139, 250, 0.08);
  border-radius: 8px;
}

.uptime-label {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.uptime-value {
  font-size: 18px;
  font-weight: 700;
  color: #a78bfa;
}

/* 滚动条 */
.overview-content::-webkit-scrollbar,
.detail-content::-webkit-scrollbar {
  width: 6px;
}

.overview-content::-webkit-scrollbar-track,
.detail-content::-webkit-scrollbar-track {
  background: transparent;
}

.overview-content::-webkit-scrollbar-thumb,
.detail-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

/* 亮色主题 */
:deep(.light-mode .card) {
  background: white;
  border-color: rgba(0, 0, 0, 0.1);
}

:deep(.light-mode .personality-card) {
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.05), rgba(139, 92, 246, 0.05));
}

:deep(.light-mode .info-item) {
  background: rgba(0, 0, 0, 0.03);
}

:deep(.light-mode .refresh-btn) {
  background: rgba(0, 0, 0, 0.05);
  border-color: rgba(0, 0, 0, 0.1);
}

:deep(.light-mode .network-card) {
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.08), rgba(14, 165, 233, 0.08));
}

:deep(.light-mode .network-item) {
  background: rgba(13, 148, 136, 0.06);
}

:deep(.light-mode .network-value) {
  color: #0f766e;
}

:deep(.light-mode .uptime-card) {
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.08), rgba(124, 58, 237, 0.08));
}

:deep(.light-mode .uptime-item) {
  background: rgba(139, 92, 246, 0.06);
}

:deep(.light-mode .uptime-value) {
  color: #8b5cf6;
}
</style>
