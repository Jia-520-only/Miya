<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import NavigationTabs from '../components/NavigationTabs.vue'

// 状态
const activeTab = ref('analyze')
const isLoading = ref(false)
const analysisResult = ref<any>(null)
const chartData = ref<any>(null)
const error = ref('')

// 分析参数
const analysisParams = ref({
  file_path: '',
  analysis_type: 'basic', // basic, correlation, trend, anomaly
  chart_type: 'bar' // bar, line, pie, scatter
})

// 调研参数
const researchParams = ref({
  topic: '',
  keywords: '',
  max_results: 10,
  report_type: 'summary' // summary, detailed, competitive
})

// 报告内容
const reportContent = ref('')

// 文件上传
const selectedFile = ref<File | null>(null)
const uploadProgress = ref(0)

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    selectedFile.value = input.files[0]
    analysisParams.value.file_path = selectedFile.value.name
  }
}

// 数据分析
async function runAnalysis() {
  if (!selectedFile.value && !analysisParams.value.file_path) {
    error.value = '请选择要分析的文件'
    return
  }

  isLoading.value = true
  error.value = ''

  try {
    const response = await axios.post('http://localhost:8000/api/tools/data_analyze', {
      file_path: analysisParams.value.file_path,
      analysis_type: analysisParams.value.analysis_type
    })
    analysisResult.value = response.data
  } catch (err: any) {
    error.value = err.response?.data?.detail || '分析失败，请检查文件路径'
  } finally {
    isLoading.value = false
  }
}

// 生成图表
async function generateChart() {
  if (!analysisResult.value) {
    error.value = '请先运行数据分析'
    return
  }

  isLoading.value = true
  error.value = ''

  try {
    const response = await axios.post('http://localhost:8000/api/tools/chart_generate', {
      data: analysisResult.value,
      chart_type: analysisParams.value.chart_type
    })
    chartData.value = response.data
  } catch (err: any) {
    error.value = err.response?.data?.detail || '图表生成失败'
  } finally {
    isLoading.value = false
  }
}

// 网络调研
async function runResearch() {
  if (!researchParams.value.topic) {
    error.value = '请输入调研主题'
    return
  }

  isLoading.value = true
  error.value = ''

  try {
    const response = await axios.post('http://localhost:8000/api/tools/web_research', {
      topic: researchParams.value.topic,
      keywords: researchParams.value.keywords,
      max_results: researchParams.value.max_results,
      report_type: researchParams.value.report_type
    })
    reportContent.value = response.data.report || response.data.content
  } catch (err: any) {
    error.value = err.response?.data?.detail || '调研失败'
  } finally {
    isLoading.value = false
  }
}

// 生成报告
async function generateReport() {
  if (!reportContent.value && !analysisResult.value) {
    error.value = '请先进行数据调研或分析'
    return
  }

  isLoading.value = true
  error.value = ''

  try {
    const response = await axios.post('http://localhost:8000/api/tools/report_generate', {
      content: reportContent.value || JSON.stringify(analysisResult.value),
      report_type: 'markdown'
    })
    reportContent.value = response.data.report || response.data.content
  } catch (err: any) {
    error.value = err.response?.data?.detail || '报告生成失败'
  } finally {
    isLoading.value = false
  }
}

// 导出报告
function exportReport() {
  if (!reportContent.value) return

  const blob = new Blob([reportContent.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `report_${Date.now()}.md`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="analytics-view">
    <NavigationTabs />

    <div class="view-header">
      <h2>数据分析与报告</h2>
      <div class="tab-buttons">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'analyze' }"
          @click="activeTab = 'analyze'"
        >
          数据分析
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'research' }"
          @click="activeTab = 'research'"
        >
          网络调研
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'report' }"
          @click="activeTab = 'report'"
        >
          报告生成
        </button>
      </div>
    </div>

    <div class="view-content">
      <!-- 数据分析面板 -->
      <div v-if="activeTab === 'analyze'" class="panel-section">
        <div class="input-group">
          <label>选择数据文件</label>
          <div class="file-input">
            <input type="file" accept=".csv,.xlsx,.xls,.json" @change="handleFileSelect" />
            <span v-if="selectedFile" class="file-name">{{ selectedFile.name }}</span>
          </div>
        </div>

        <div class="input-row">
          <div class="input-group">
            <label>分析类型</label>
            <select v-model="analysisParams.analysis_type">
              <option value="basic">基本统计</option>
              <option value="correlation">相关性分析</option>
              <option value="trend">趋势分析</option>
              <option value="anomaly">异常检测</option>
            </select>
          </div>
          <div class="input-group">
            <label>图表类型</label>
            <select v-model="analysisParams.chart_type">
              <option value="bar">柱状图</option>
              <option value="line">折线图</option>
              <option value="pie">饼图</option>
              <option value="scatter">散点图</option>
            </select>
          </div>
        </div>

        <div class="action-buttons">
          <button class="action-btn primary" @click="runAnalysis" :disabled="isLoading">
            {{ isLoading ? '分析中...' : '开始分析' }}
          </button>
          <button class="action-btn" @click="generateChart" :disabled="isLoading || !analysisResult">
            生成图表
          </button>
        </div>

        <!-- 分析结果 -->
        <div v-if="analysisResult" class="result-card">
          <div class="result-header">
            <i class="pi pi-chart-bar"></i>
            <span>分析结果</span>
          </div>
          <pre class="result-content">{{ JSON.stringify(analysisResult, null, 2) }}</pre>
        </div>
      </div>

      <!-- 网络调研面板 -->
      <div v-if="activeTab === 'research'" class="panel-section">
        <div class="input-group">
          <label>调研主题</label>
          <input
            v-model="researchParams.topic"
            type="text"
            placeholder="输入调研主题，如：AI大模型发展趋势"
          />
        </div>

        <div class="input-group">
          <label>关键词（逗号分隔）</label>
          <input
            v-model="researchParams.keywords"
            type="text"
            placeholder="输入关键词，如：GPT、LLM、Transformer"
          />
        </div>

        <div class="input-row">
          <div class="input-group">
            <label>最大结果数</label>
            <input v-model.number="researchParams.max_results" type="number" min="1" max="50" />
          </div>
          <div class="input-group">
            <label>报告类型</label>
            <select v-model="researchParams.report_type">
              <option value="summary">摘要</option>
              <option value="detailed">详细</option>
              <option value="competitive">竞品分析</option>
            </select>
          </div>
        </div>

        <div class="action-buttons">
          <button class="action-btn primary" @click="runResearch" :disabled="isLoading">
            {{ isLoading ? '调研中...' : '开始调研' }}
          </button>
        </div>
      </div>

      <!-- 报告生成面板 -->
      <div v-if="activeTab === 'report'" class="panel-section">
        <div class="action-buttons">
          <button class="action-btn primary" @click="generateReport" :disabled="isLoading">
            {{ isLoading ? '生成中...' : '生成报告' }}
          </button>
          <button class="action-btn" @click="exportReport" :disabled="!reportContent">
            导出报告
          </button>
        </div>

        <div v-if="reportContent" class="report-preview">
          <div class="report-header">
            <i class="pi pi-file"></i>
            <span>报告预览</span>
          </div>
          <div class="report-content">{{ reportContent }}</div>
        </div>
      </div>

      <!-- 错误提示 -->
      <div v-if="error" class="error-message">
        <i class="pi pi-exclamation-circle"></i>
        {{ error }}
      </div>

      <!-- 加载状态 -->
      <div v-if="isLoading" class="loading-overlay">
        <div class="spinner"></div>
        <span>处理中...</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.analytics-view {
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
  transition: all 0.2s;
}

.tab-btn:hover {
  background: rgba(45, 212, 191, 0.1);
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
  position: relative;
}

.panel-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-group label {
  font-size: 13px;
  color: #94a3b8;
}

.input-group input,
.input-group select {
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 8px;
  color: #e0f2fe;
  font-size: 14px;
  outline: none;
}

.input-group input:focus,
.input-group select:focus {
  border-color: #2dd4bf;
}

.file-input {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-input input[type="file"] {
  padding: 8px;
}

.file-name {
  color: #2dd4bf;
  font-size: 13px;
}

.input-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.action-btn {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  color: #e0f2fe;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  background: rgba(45, 212, 191, 0.15);
  border-color: rgba(45, 212, 191, 0.4);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn.primary {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.3), rgba(14, 165, 233, 0.3));
  border-color: #2dd4bf;
  color: #2dd4bf;
}

.result-card,
.report-preview {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 10px;
  overflow: hidden;
}

.result-header,
.report-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(45, 212, 191, 0.1);
  border-bottom: 1px solid rgba(45, 212, 191, 0.2);
  color: #2dd4bf;
  font-size: 14px;
}

.result-content {
  padding: 16px;
  margin: 0;
  font-size: 12px;
  color: #e0f2fe;
  font-family: 'Courier New', monospace;
  white-space: pre-wrap;
  max-height: 300px;
  overflow-y: auto;
}

.report-content {
  padding: 16px;
  font-size: 14px;
  color: #e0f2fe;
  line-height: 1.6;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
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

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #2dd4bf;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(45, 212, 191, 0.2);
  border-top-color: #2dd4bf;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
