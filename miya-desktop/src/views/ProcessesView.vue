<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

interface Process {
  pid: number
  name: string
  username: string
  cpu_percent: number
  memory_percent: number
}

const processes = ref<Process[]>([])
const isLoading = ref(false)
let refreshInterval: number | null = null

const loadProcesses = async () => {
  isLoading.value = true

  try {
    const response = await axios.get('http://localhost:8000/api/desktop/processes')
    processes.value = response.data.processes || []
  } catch (error: any) {
    console.error('加载进程列表失败:', error)
  } finally {
    isLoading.value = false
  }
}

const killProcess = async (pid: number) => {
  if (!confirm(`确定要终止进程 ${pid} 吗？`)) return

  try {
    await axios.post('http://localhost:8000/api/desktop/processes/kill', null, {
      params: { pid }
    })

    await loadProcesses()
  } catch (error: any) {
    console.error('终止进程失败:', error)
    alert(error.response?.data?.detail || '终止失败')
  }
}

const getCpuColor = (percent: number): string => {
  if (percent < 30) return '#22c55e'
  if (percent < 70) return '#fbbf24'
  return '#ef4444'
}

const getMemoryColor = (percent: number): string => {
  if (percent < 50) return '#22c55e'
  if (percent < 80) return '#fbbf24'
  return '#ef4444'
}

onMounted(() => {
  loadProcesses()
  refreshInterval = window.setInterval(loadProcesses, 5000) // 每5秒刷新
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<template>
  <div class="processes-view">
    <div class="processes-header">
      <h2>进程管理</h2>
      <button class="refresh-btn" @click="loadProcesses" :disabled="isLoading">
        <i class="pi pi-refresh" :class="{ spinning: isLoading }"></i>
        刷新
      </button>
    </div>

    <div class="processes-content">
      <div v-if="isLoading" class="loading">
        <div class="spinner"></div>
        <span>加载中...</span>
      </div>

      <div v-else class="processes-table">
        <div class="table-header">
          <div class="col pid">PID</div>
          <div class="col name">进程名</div>
          <div class="col cpu">CPU%</div>
          <div class="col memory">内存%</div>
          <div class="col user">用户</div>
          <div class="col actions">操作</div>
        </div>

        <div class="table-body">
          <div
            v-for="proc in processes"
            :key="proc.pid"
            class="table-row"
          >
            <div class="col pid">{{ proc.pid }}</div>
            <div class="col name">{{ proc.name }}</div>
            <div class="col cpu" :style="{ color: getCpuColor(proc.cpu_percent) }">
              {{ proc.cpu_percent.toFixed(1) }}%
            </div>
            <div class="col memory" :style="{ color: getMemoryColor(proc.memory_percent) }">
              {{ proc.memory_percent.toFixed(1) }}%
            </div>
            <div class="col user">{{ proc.username || '-' }}</div>
            <div class="col actions">
              <button class="kill-btn" @click="killProcess(proc.pid)">
                <i class="pi pi-times"></i>
                终止
              </button>
            </div>
          </div>

          <div v-if="processes.length === 0" class="empty">
            <i class="pi pi-cog"></i>
            <span>暂无进程数据</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.processes-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1a2e;
}

.processes-header {
  padding: 20px;
  border-bottom: 1px solid #2a2a4a;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.processes-header h2 {
  margin: 0;
  font-size: 18px;
  color: #e0e0e0;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #16213e;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: #2a2a4a;
  border-color: #e94560;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.refresh-btn i.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.processes-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
  color: #a0a0a0;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #2a2a4a;
  border-top-color: #e94560;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.processes-table {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.table-header {
  display: flex;
  padding: 12px 20px;
  background: #0d1117;
  border-bottom: 1px solid #2a2a4a;
  font-weight: 600;
  color: #a0a0a0;
  font-size: 13px;
}

.table-header .col {
  display: flex;
  align-items: center;
  padding: 0 12px;
}

.table-header .pid { width: 80px; }
.table-header .name { flex: 1; }
.table-header .cpu { width: 80px; }
.table-header .memory { width: 80px; }
.table-header .user { width: 150px; }
.table-header .actions { width: 100px; }

.table-body {
  flex: 1;
  overflow-y: auto;
}

.table-row {
  display: flex;
  padding: 12px 20px;
  border-bottom: 1px solid #2a2a4a;
  transition: background 0.2s;
}

.table-row:hover {
  background: rgba(233, 69, 96, 0.05);
}

.table-row .col {
  display: flex;
  align-items: center;
  padding: 0 12px;
  font-size: 13px;
  color: #e0e0e0;
}

.table-row .pid { width: 80px; font-family: 'Courier New', Consolas, monospace; }
.table-row .name { flex: 1; font-weight: 500; }
.table-row .cpu { width: 80px; font-weight: 600; }
.table-row .memory { width: 80px; font-weight: 600; }
.table-row .user { width: 150px; color: #a0a0a0; }
.table-row .actions { width: 100px; }

.kill-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 4px;
  color: #ef4444;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.kill-btn:hover {
  background: #ef4444;
  color: white;
  border-color: #ef4444;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 16px;
  color: #666;
}

.empty i {
  font-size: 48px;
}
</style>
