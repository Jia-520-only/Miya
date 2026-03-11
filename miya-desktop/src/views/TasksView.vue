<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import NavigationTabs from '../components/NavigationTabs.vue'

// 任务类型
interface Task {
  id: string
  name: string
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
  result?: any
  error?: string
}

// 任务模板
interface TaskTemplate {
  id: string
  name: string
  description: string
  icon: string
  params: any
}

// 状态
const tasks = ref<Task[]>([])
const isLoading = ref(false)
const error = ref('')
const activeTab = ref('create')
const pollingInterval = ref<ReturnType<typeof setInterval> | null>(null)

// 任务模板列表
const taskTemplates: TaskTemplate[] = [
  {
    id: 'file_organize',
    name: '文件整理',
    description: '自动整理指定目录的文件',
    icon: '📁',
    params: {
      source_dir: '',
      rule: 'by_type'
    }
  },
  {
    id: 'data_analyze',
    name: '数据分析',
    description: '分析数据文件并生成报告',
    icon: '📊',
    params: {
      file_path: '',
      analysis_type: 'basic'
    }
  },
  {
    id: 'backup',
    name: '文件备份',
    description: '自动备份重要文件',
    icon: '💾',
    params: {
      source: '',
      destination: ''
    }
  },
  {
    id: 'web_research',
    name: '网络调研',
    description: '自动搜集网络信息',
    icon: '🔍',
    params: {
      topic: '',
      keywords: ''
    }
  }
]

// 新任务表单
const newTask = ref({
  templateId: '',
  name: '',
  params: {} as any
})

// 快速任务
const quickTask = ref({
  command: '',
  description: ''
})

// 创建任务
async function createTask() {
  if (!newTask.value.templateId || !newTask.value.name) {
    error.value = '请选择任务模板并填写名称'
    return
  }

  isLoading.value = true
  error.value = ''

  try {
    const response = await axios.post('http://localhost:8000/api/tools/task_create', {
      name: newTask.value.name,
      type: newTask.value.templateId,
      params: newTask.value.params
    })
    tasks.value.unshift(response.data)
    newTask.value = { templateId: '', name: '', params: {} }
    startPolling()
  } catch (err: any) {
    error.value = err.response?.data?.detail || '创建任务失败'
  } finally {
    isLoading.value = false
  }
}

// 执行快速命令
async function runQuickTask() {
  if (!quickTask.value.command) {
    error.value = '请输入任务命令'
    return
  }

  isLoading.value = true
  error.value = ''

  const task: Task = {
    id: Date.now().toString(),
    name: quickTask.value.description || '快速任务',
    type: 'quick',
    status: 'running',
    created_at: new Date().toISOString()
  }
  tasks.value.unshift(task)

  try {
    const response = await axios.post('http://localhost:8000/api/tools/task_execute', {
      command: quickTask.value.command
    })
    const index = tasks.value.findIndex(t => t.id === task.id)
    if (index !== -1) {
      // API返回格式: {success: true, result: "...", exit_code: 0}
      const data = response.data
      if (data.success) {
        tasks.value[index] = {
          ...task,
          status: 'completed',
          result: data.result  // 取result字段的值
        }
      } else {
        tasks.value[index] = {
          ...task,
          status: 'failed',
          error: data.error || '执行失败'
        }
      }
    }
    quickTask.value = { command: '', description: '' }
  } catch (err: any) {
    const index = tasks.value.findIndex(t => t.id === task.id)
    if (index !== -1) {
      tasks.value[index] = {
        ...task,
        status: 'failed',
        error: err.response?.data?.detail || '执行失败'
      }
    }
  } finally {
    isLoading.value = false
  }
}

// 轮询任务状态
async function pollTasks() {
  try {
    const response = await axios.get('http://localhost:8000/api/tools/task_list')
    tasks.value = response.data.tasks || []
  } catch (err) {
    console.error('获取任务列表失败:', err)
  }
}

// 启动轮询
function startPolling() {
  if (pollingInterval.value) return
  pollTasks()
  pollingInterval.value = setInterval(pollTasks, 3000)
}

// 停止轮询
function stopPolling() {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
}

// 选择模板
function selectTemplate(template: TaskTemplate) {
  newTask.value.templateId = template.id
  newTask.value.name = template.name
  newTask.value.params = { ...template.params }
}

// 删除任务
async function deleteTask(taskId: string) {
  try {
    await axios.delete(`http://localhost:8000/api/tools/task_delete?id=${taskId}`)
    tasks.value = tasks.value.filter(t => t.id !== taskId)
  } catch (err: any) {
    error.value = err.response?.data?.detail || '删除失败'
  }
}

// 格式化时间
function formatTime(isoString: string) {
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN')
}

// 获取状态颜色
function getStatusColor(status: string) {
  const colors: Record<string, string> = {
    pending: '#94a3b8',
    running: '#2dd4bf',
    completed: '#22c55e',
    failed: '#ef4444'
  }
  return colors[status] || '#94a3b8'
}

// 获取状态文字
function getStatusText(status: string) {
  const texts: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败'
  }
  return texts[status] || status
}

onMounted(() => {
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="tasks-view">
    <NavigationTabs />

    <div class="view-header">
      <h2>自动化任务中心</h2>
      <div class="tab-buttons">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'create' }"
          @click="activeTab = 'create'"
        >
          创建任务
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'history' }"
          @click="activeTab = 'history'"
        >
          任务历史
        </button>
      </div>
    </div>

    <div class="view-content">
      <!-- 创建任务面板 -->
      <div v-if="activeTab === 'create'" class="panel-section">
        <!-- 快速命令 -->
        <div class="quick-task-card">
          <div class="card-header">
            <i class="pi pi-bolt"></i>
            <span>快速执行</span>
          </div>
          <div class="card-content">
            <input
              v-model="quickTask.description"
              type="text"
              placeholder="任务描述（可选）"
              class="task-input"
            />
            <textarea
              v-model="quickTask.command"
              placeholder="输入要执行的命令或任务描述..."
              class="task-textarea"
            ></textarea>
            <button class="run-btn" @click="runQuickTask" :disabled="isLoading">
              <i class="pi pi-play"></i>
              {{ isLoading ? '执行中...' : '立即执行' }}
            </button>
          </div>
        </div>

        <!-- 任务模板 -->
        <div class="templates-section">
          <h3>任务模板</h3>
          <div class="templates-grid">
            <div
              v-for="template in taskTemplates"
              :key="template.id"
              class="template-card"
              :class="{ selected: newTask.templateId === template.id }"
              @click="selectTemplate(template)"
            >
              <div class="template-icon">{{ template.icon }}</div>
              <div class="template-info">
                <div class="template-name">{{ template.name }}</div>
                <div class="template-desc">{{ template.description }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 任务配置 -->
        <div v-if="newTask.templateId" class="task-config">
          <h3>任务配置</h3>
          <div class="config-form">
            <div class="input-group">
              <label>任务名称</label>
              <input v-model="newTask.name" type="text" placeholder="输入任务名称" />
            </div>

            <div v-if="newTask.templateId === 'file_organize'" class="input-group">
              <label>源目录</label>
              <input v-model="newTask.params.source_dir" type="text" placeholder="如：D:/Downloads" />
            </div>

            <div v-if="newTask.templateId === 'data_analyze'" class="input-group">
              <label>数据文件</label>
              <input v-model="newTask.params.file_path" type="text" placeholder="数据文件路径" />
            </div>

            <div v-if="newTask.templateId === 'backup'" class="input-row">
              <div class="input-group">
                <label>源路径</label>
                <input v-model="newTask.params.source" type="text" placeholder="要备份的文件/目录" />
              </div>
              <div class="input-group">
                <label>目标路径</label>
                <input v-model="newTask.params.destination" type="text" placeholder="备份存放位置" />
              </div>
            </div>

            <div v-if="newTask.templateId === 'web_research'" class="input-row">
              <div class="input-group">
                <label>调研主题</label>
                <input v-model="newTask.params.topic" type="text" placeholder="调研主题" />
              </div>
              <div class="input-group">
                <label>关键词</label>
                <input v-model="newTask.params.keywords" type="text" placeholder="关键词" />
              </div>
            </div>

            <button class="create-btn" @click="createTask" :disabled="isLoading">
              <i class="pi pi-plus"></i>
              创建任务
            </button>
          </div>
        </div>
      </div>

      <!-- 任务历史面板 -->
      <div v-if="activeTab === 'history'" class="panel-section">
        <div class="tasks-header">
          <span>共 {{ tasks.length }} 个任务</span>
        </div>

        <div v-if="tasks.length === 0" class="empty-state">
          <i class="pi pi-inbox"></i>
          <span>暂无任务记录</span>
        </div>

        <div v-else class="tasks-list">
          <div v-for="task in tasks" :key="task.id" class="task-item">
            <div class="task-icon">
              <i v-if="task.status === 'running'" class="pi pi-spin pi-spinner"></i>
              <i v-else-if="task.status === 'completed'" class="pi pi-check-circle"></i>
              <i v-else-if="task.status === 'failed'" class="pi pi-times-circle"></i>
              <i v-else class="pi pi-clock"></i>
            </div>

            <div class="task-info">
              <div class="task-name">{{ task.name }}</div>
              <div class="task-meta">
                <span class="task-type">{{ task.type }}</span>
                <span class="task-time">{{ formatTime(task.created_at) }}</span>
              </div>
            </div>

            <div class="task-status" :style="{ color: getStatusColor(task.status) }">
              {{ getStatusText(task.status) }}
            </div>

            <!-- 任务结果 -->
            <div v-if="task.result" class="task-result">
              <pre>{{ typeof task.result === 'object' ? JSON.stringify(task.result, null, 2) : task.result }}</pre>
            </div>

            <!-- 错误信息 -->
            <div v-if="task.error" class="task-error">
              {{ task.error }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tasks-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 8px;
  box-sizing: border-box;
}

.view-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(12px);
  border-radius: 10px;
  border: 1px solid rgba(45, 212, 191, 0.15);
  margin-bottom: 8px;
}

.view-header h2 {
  margin: 0;
  font-size: 18px;
  color: #e0f2fe;
  font-weight: 600;
}

.tab-buttons {
  display: flex;
  gap: 8px;
}

.tab-btn {
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
}

.tab-btn.active {
  background: rgba(45, 212, 191, 0.2);
  border-color: #2dd4bf;
  color: #2dd4bf;
}

.view-content {
  flex: 1;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 10px;
  padding: 20px;
}

.panel-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.quick-task-card {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 12px;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.2), rgba(14, 165, 233, 0.2));
  border-bottom: 1px solid rgba(45, 212, 191, 0.2);
  color: #2dd4bf;
  font-weight: 500;
}

.card-content {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-input,
.task-textarea {
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 8px;
  color: #e0f2fe;
  outline: none;
}

.task-textarea {
  min-height: 80px;
  resize: vertical;
}

.run-btn {
  align-self: flex-end;
  padding: 10px 20px;
  background: linear-gradient(135deg, #2dd4bf, #0ea5e9);
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.run-btn:disabled {
  opacity: 0.5;
}

.templates-section h3,
.task-config h3 {
  font-size: 14px;
  color: #94a3b8;
  margin-bottom: 12px;
}

.templates-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.template-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.15);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.template-card:hover {
  background: rgba(45, 212, 191, 0.1);
}

.template-card.selected {
  border-color: #2dd4bf;
  background: rgba(45, 212, 191, 0.15);
}

.template-icon {
  font-size: 28px;
}

.template-name {
  font-size: 14px;
  color: #e0f2fe;
  font-weight: 500;
}

.template-desc {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.task-config {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.15);
  border-radius: 12px;
  padding: 16px;
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-group label {
  font-size: 13px;
  color: #94a3b8;
}

.input-group input {
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 8px;
  color: #e0f2fe;
  outline: none;
}

.input-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.create-btn {
  align-self: flex-start;
  padding: 10px 24px;
  background: rgba(45, 212, 191, 0.2);
  border: 1px solid #2dd4bf;
  border-radius: 8px;
  color: #2dd4bf;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tasks-header {
  padding: 8px 0;
  color: #94a3b8;
  font-size: 14px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 12px;
  color: #64748b;
}

.empty-state i {
  font-size: 48px;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.1);
  border-radius: 10px;
}

.task-icon {
  font-size: 20px;
}

.task-icon .pi-check-circle {
  color: #22c55e;
}

.task-icon .pi-times-circle {
  color: #ef4444;
}

.task-icon .pi-clock {
  color: #94a3b8;
}

.task-icon .pi-spinner {
  color: #2dd4bf;
}

.task-info {
  flex: 1;
}

.task-name {
  font-size: 14px;
  color: #e0f2fe;
}

.task-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.task-status {
  font-size: 13px;
  font-weight: 500;
}

.delete-btn {
  padding: 8px;
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
}

.delete-btn:hover {
  color: #ef4444;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #f87171;
  margin-top: 12px;
}

/* 任务结果样式 */
.task-result {
  margin-top: 8px;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 6px;
  border: 1px solid rgba(45, 212, 191, 0.15);
}

.task-result pre {
  margin: 0;
  font-size: 12px;
  color: #94a3b8;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Consolas', 'Monaco', monospace;
}

.task-error {
  margin-top: 8px;
  padding: 10px 12px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 6px;
  border: 1px solid rgba(239, 68, 68, 0.3);
  font-size: 12px;
  color: #f87171;
}
</style>
