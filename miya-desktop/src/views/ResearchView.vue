<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import NavigationTabs from '../components/NavigationTabs.vue'

// 状态
const activeTask = ref('search')
const isLoading = ref(false)
const searchResults = ref<any[]>([])
const researchReport = ref('')
const error = ref('')

// 搜索参数
const searchParams = ref({
  query: '',
  max_results: 10,
  search_type: 'general' // general, academic, news
})

// 调研参数
const researchParams = ref({
  topic: '',
  keywords: '',
  depth: 'medium', // shallow, medium, deep
  include_sources: true
})

// 搜索
async function performSearch() {
  if (!searchParams.value.query) {
    error.value = '请输入搜索关键词'
    return
  }

  isLoading.value = true
  error.value = ''

  try {
    const response = await axios.post('http://localhost:8000/api/tools/web_search', {
      query: searchParams.value.query,
      max_results: searchParams.value.max_results
    })
    searchResults.value = response.data.results || []
  } catch (err: any) {
    error.value = err.response?.data?.detail || '搜索失败'
  } finally {
    isLoading.value = false
  }
}

// 深度调研
async function runDeepResearch() {
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
      max_results: 20,
      report_type: researchParams.value.depth === 'deep' ? 'detailed' : 'summary'
    })
    researchReport.value = response.data.report || JSON.stringify(response.data, null, 2)
  } catch (err: any) {
    error.value = err.response?.data?.detail || '调研失败'
  } finally {
    isLoading.value = false
  }
}

// 导出结果
function exportResults(type: 'search' | 'research') {
  const content = type === 'search'
    ? JSON.stringify(searchResults.value, null, 2)
    : researchReport.value

  if (!content) return

  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${type}_${Date.now()}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

// 快速搜索建议
const quickSearches = [
  { label: 'AI 发展', query: '人工智能发展趋势 2024' },
  { label: 'Python 技巧', query: 'Python 编程技巧' },
  { label: '前端框架', query: '前端框架对比 React Vue' },
  { label: '数据分析', query: '数据分析方法论' }
]
</script>

<template>
  <div class="research-view">
    <NavigationTabs />

    <div class="view-header">
      <h2>网络调研中心</h2>
      <div class="tab-buttons">
        <button
          class="tab-btn"
          :class="{ active: activeTask === 'search' }"
          @click="activeTask = 'search'"
        >
          快速搜索
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTask === 'research' }"
          @click="activeTask = 'research'"
        >
          深度调研
        </button>
      </div>
    </div>

    <div class="view-content">
      <!-- 快速搜索面板 -->
      <div v-if="activeTask === 'search'" class="panel-section">
        <div class="search-box">
          <input
            v-model="searchParams.query"
            type="text"
            placeholder="输入搜索关键词..."
            @keyup.enter="performSearch"
          />
          <button class="search-btn" @click="performSearch" :disabled="isLoading">
            <i class="pi pi-search"></i>
          </button>
        </div>

        <div class="search-options">
          <div class="option-group">
            <label>搜索类型</label>
            <select v-model="searchParams.search_type">
              <option value="general">综合搜索</option>
              <option value="academic">学术搜索</option>
              <option value="news">新闻搜索</option>
            </select>
          </div>
          <div class="option-group">
            <label>结果数量</label>
            <input v-model.number="searchParams.max_results" type="number" min="1" max="50" />
          </div>
        </div>

        <!-- 快速搜索建议 -->
        <div class="quick-suggestions">
          <span class="suggest-label">快速搜索：</span>
          <button
            v-for="qs in quickSearches"
            :key="qs.query"
            class="suggest-btn"
            @click="searchParams.query = qs.query; performSearch()"
          >
            {{ qs.label }}
          </button>
        </div>

        <!-- 搜索结果 -->
        <div v-if="searchResults.length > 0" class="results-section">
          <div class="results-header">
            <span>找到 {{ searchResults.length }} 个结果</span>
            <button class="export-btn" @click="exportResults('search')">
              <i class="pi pi-download"></i> 导出
            </button>
          </div>
          <div class="results-list">
            <div v-for="(result, index) in searchResults" :key="index" class="result-item">
              <div class="result-title">{{ result.title || result.name }}</div>
              <div class="result-snippet">{{ result.snippet || result.description || result.content }}</div>
              <a v-if="result.url" :href="result.url" target="_blank" class="result-link">
                查看原文 <i class="pi pi-external-link"></i>
              </a>
            </div>
          </div>
        </div>
      </div>

      <!-- 深度调研面板 -->
      <div v-if="activeTask === 'research'" class="panel-section">
        <div class="input-group">
          <label>调研主题</label>
          <input
            v-model="researchParams.topic"
            type="text"
            placeholder="输入调研主题，如：新能源汽车市场分析"
          />
        </div>

        <div class="input-group">
          <label>关键词（逗号分隔）</label>
          <input
            v-model="researchParams.keywords"
            type="text"
            placeholder="输入关键词，如：特斯拉、比亚迪、销量"
          />
        </div>

        <div class="input-row">
          <div class="input-group">
            <label>调研深度</label>
            <select v-model="researchParams.depth">
              <option value="shallow">浅度调研</option>
              <option value="medium">中度调研</option>
              <option value="deep">深度调研</option>
            </select>
          </div>
        </div>

        <div class="action-buttons">
          <button class="action-btn primary" @click="runDeepResearch" :disabled="isLoading">
            {{ isLoading ? '调研中...' : '开始深度调研' }}
          </button>
          <button class="action-btn" @click="exportResults('research')" :disabled="!researchReport">
            导出报告
          </button>
        </div>

        <!-- 调研报告 -->
        <div v-if="researchReport" class="report-card">
          <div class="report-header">
            <i class="pi pi-file-pdf"></i>
            <span>调研报告</span>
          </div>
          <div class="report-content">{{ researchReport }}</div>
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
        <span>{{ activeTask === 'search' ? '搜索中...' : '调研中...' }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.research-view {
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

.search-box {
  display: flex;
  gap: 12px;
}

.search-box input {
  flex: 1;
  padding: 14px 20px;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(45, 212, 191, 0.3);
  border-radius: 10px;
  color: #e0f2fe;
  font-size: 16px;
  outline: none;
}

.search-box input:focus {
  border-color: #2dd4bf;
  box-shadow: 0 0 20px rgba(45, 212, 191, 0.2);
}

.search-btn {
  width: 56px;
  background: linear-gradient(135deg, #2dd4bf, #0ea5e9);
  border: none;
  border-radius: 10px;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
}

.search-btn:hover:not(:disabled) {
  transform: scale(1.05);
}

.search-btn:disabled {
  opacity: 0.5;
}

.search-options {
  display: flex;
  gap: 16px;
}

.option-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.option-group label {
  font-size: 13px;
  color: #94a3b8;
}

.option-group select,
.option-group input {
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 6px;
  color: #e0f2fe;
  outline: none;
}

.quick-suggestions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.suggest-label {
  font-size: 13px;
  color: #94a3b8;
}

.suggest-btn {
  padding: 6px 12px;
  background: rgba(45, 212, 191, 0.1);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 20px;
  color: #2dd4bf;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.suggest-btn:hover {
  background: rgba(45, 212, 191, 0.2);
}

.results-section {
  margin-top: 16px;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  color: #94a3b8;
  font-size: 14px;
}

.export-btn {
  padding: 6px 12px;
  background: rgba(45, 212, 191, 0.1);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 6px;
  color: #2dd4bf;
  cursor: pointer;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-item {
  padding: 16px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.15);
  border-radius: 10px;
}

.result-title {
  font-size: 15px;
  color: #2dd4bf;
  margin-bottom: 8px;
  font-weight: 500;
}

.result-snippet {
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.5;
  margin-bottom: 8px;
}

.result-link {
  font-size: 12px;
  color: #0ea5e9;
  text-decoration: none;
}

.result-link:hover {
  text-decoration: underline;
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

.input-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.action-buttons {
  display: flex;
  gap: 12px;
}

.action-btn {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  color: #e0f2fe;
  cursor: pointer;
}

.action-btn.primary {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.3), rgba(14, 165, 233, 0.3));
  border-color: #2dd4bf;
  color: #2dd4bf;
}

.report-card {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 10px;
  overflow: hidden;
}

.report-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(45, 212, 191, 0.1);
  border-bottom: 1px solid rgba(45, 212, 191, 0.2);
  color: #2dd4bf;
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
