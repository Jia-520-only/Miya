<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

interface Tool {
  name: string
  description: string
  category: string
  parameters: Record<string, any>
}

const tools = ref<Tool[]>([])
const isLoading = ref(false)
const selectedTool = ref<Tool | null>(null)
const parameters = ref<Record<string, any>>({})
const toolOutput = ref('')

const loadTools = async () => {
  isLoading.value = true

  try {
    const response = await axios.get('http://localhost:8000/api/desktop/tools/available')
    tools.value = response.data.tools || []
  } catch (error: any) {
    console.error('加载工具列表失败:', error)
  } finally {
    isLoading.value = false
  }
}

const selectTool = (tool: Tool) => {
  selectedTool.value = tool
  parameters.value = {}
  toolOutput.value = ''
}

const executeTool = async () => {
  if (!selectedTool.value) return

  try {
    const response = await axios.post('http://localhost:8000/api/chat', {
      message: `使用工具 ${selectedTool.value.name}: ${JSON.stringify(parameters.value)}`,
      session_id: 'desktop_tools'
    })

    toolOutput.value = JSON.stringify(response.data, null, 2)
  } catch (error: any) {
    toolOutput.value = JSON.stringify(error.response?.data || error.message, null, 2)
  }
}

onMounted(() => {
  loadTools()
})
</script>

<template>
  <div class="tools-view">
    <div class="tools-header">
      <h2>可用工具 (MCP/Skill)</h2>
      <button class="refresh-btn" @click="loadTools" :disabled="isLoading">
        <i class="pi pi-refresh"></i>
        刷新
      </button>
    </div>

    <div class="tools-content">
      <div class="tools-list">
        <div v-if="isLoading" class="loading">
          <div class="spinner"></div>
          <span>加载中...</span>
        </div>

        <div v-else class="tools-grid">
          <div
            v-for="tool in tools"
            :key="tool.name"
            class="tool-card"
            :class="{ selected: selectedTool?.name === tool.name }"
            @click="selectTool(tool)"
          >
            <div class="tool-icon">
              <i class="pi pi-wrench"></i>
            </div>
            <div class="tool-info">
              <div class="tool-name">{{ tool.name }}</div>
              <div class="tool-desc">{{ tool.description }}</div>
              <div class="tool-category">{{ tool.category }}</div>
            </div>
          </div>

          <div v-if="tools.length === 0" class="empty">
            <i class="pi pi-box"></i>
            <span>暂无工具</span>
          </div>
        </div>
      </div>

      <div v-if="selectedTool" class="tool-panel">
        <div class="panel-header">
          <h3>{{ selectedTool.name }}</h3>
          <button class="close-btn" @click="selectedTool = null">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="panel-content">
          <div class="tool-desc-full">
            <strong>描述:</strong> {{ selectedTool.description }}
          </div>

          <div class="tool-params">
            <h4>参数</h4>
            <div
              v-for="(value, key) in selectedTool.parameters"
              :key="key"
              class="param-item"
            >
              <label>{{ key }}</label>
              <input
                v-model="parameters[key]"
                :placeholder="value"
                type="text"
                class="param-input"
              >
            </div>

            <div v-if="Object.keys(selectedTool.parameters).length === 0" class="no-params">
              此工具无需参数
            </div>
          </div>

          <button class="execute-btn" @click="executeTool">
            <i class="pi pi-play"></i>
            执行工具
          </button>

          <div v-if="toolOutput" class="output-area">
            <h4>输出</h4>
            <pre>{{ toolOutput }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tools-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1a2e;
}

.tools-header {
  padding: 20px;
  border-bottom: 1px solid #2a2a4a;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tools-header h2 {
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

.tools-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.tools-list {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  border-right: 1px solid #2a2a4a;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
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

@keyframes spin {
  to { transform: rotate(360deg); }
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.tool-card {
  background: #16213e;
  border: 2px solid transparent;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.tool-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(233, 69, 96, 0.1);
}

.tool-card.selected {
  border-color: #e94560;
  background: rgba(233, 69, 96, 0.05);
}

.tool-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: linear-gradient(135deg, #e94560, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
  flex-shrink: 0;
}

.tool-info {
  flex: 1;
  min-width: 0;
}

.tool-name {
  font-size: 14px;
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 4px;
}

.tool-desc {
  font-size: 12px;
  color: #a0a0a0;
  margin-bottom: 8px;
  line-height: 1.4;
}

.tool-category {
  display: inline-block;
  padding: 2px 8px;
  background: rgba(233, 69, 96, 0.1);
  border-radius: 4px;
  font-size: 11px;
  color: #e94560;
}

.empty {
  grid-column: 1 / -1;
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

.tool-panel {
  width: 400px;
  background: #0d1117;
  border-left: 1px solid #2a2a4a;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 16px 20px;
  border-bottom: 1px solid #2a2a4a;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: #e0e0e0;
}

.close-btn {
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #a0a0a0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #2a2a4a;
  color: #e0e0e0;
}

.panel-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.tool-desc-full {
  margin-bottom: 20px;
  padding: 12px;
  background: #16213e;
  border-radius: 8px;
  font-size: 13px;
  color: #e0e0e0;
  line-height: 1.6;
}

.tool-params {
  margin-bottom: 20px;
}

.tool-params h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #e0e0e0;
}

.param-item {
  margin-bottom: 12px;
}

.param-item label {
  display: block;
  font-size: 12px;
  color: #a0a0a0;
  margin-bottom: 4px;
}

.param-input {
  width: 100%;
  padding: 8px 12px;
  background: #16213e;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.param-input:focus {
  border-color: #e94560;
}

.no-params {
  padding: 20px;
  text-align: center;
  color: #666;
  font-size: 13px;
}

.execute-btn {
  width: 100%;
  padding: 12px;
  background: #22c55e;
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
  margin-bottom: 20px;
}

.execute-btn:hover {
  background: #16a34a;
  transform: translateY(-1px);
}

.output-area {
  padding: 12px;
  background: #16213e;
  border-radius: 8px;
  overflow: auto;
}

.output-area h4 {
  margin: 0 0 8px 0;
  font-size: 12px;
  color: #a0a0a0;
}

.output-area pre {
  margin: 0;
  padding: 12px;
  background: #0d1117;
  border-radius: 6px;
  font-size: 12px;
  color: #22c55e;
  overflow-x: auto;
}
</style>
