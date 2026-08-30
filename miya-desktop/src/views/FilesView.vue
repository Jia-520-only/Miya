<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import NavigationTabs from '../components/NavigationTabs.vue'

interface FileItem {
  name: string
  path: string
  is_dir: boolean
  size: number
  modified: string
}

const currentPath = ref('.')
const files = ref<FileItem[]>([])
const isLoading = ref(false)
const selectedFile = ref<FileItem | null>(null)
const fileContent = ref('')
const showContent = ref(false)

const formatSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr)
  return date.toLocaleString()
}

const loadFiles = async (path = currentPath.value) => {
  currentPath.value = path
  isLoading.value = true

  try {
    const response = await axios.get('http://localhost:8000/api/desktop/files/list', {
      params: { path, recursive: false }
    })

    files.value = response.data.files || []
  } catch (error: any) {
    console.error('加载文件列表失败:', error)
    alert(error.response?.data?.detail || '加载失败')
  } finally {
    isLoading.value = false
  }
}

const openFile = async (file: FileItem) => {
  if (file.is_dir) {
    await loadFiles(file.path)
  } else {
    selectedFile.value = file
    isLoading.value = true
    showContent.value = true

    try {
      const response = await axios.get('http://localhost:8000/api/desktop/files/read', {
        params: { path: file.path, limit: 1000 }
      })

      fileContent.value = response.data.lines.join('\n')
    } catch (error: any) {
      console.error('读取文件失败:', error)
      alert(error.response?.data?.detail || '读取失败')
    } finally {
      isLoading.value = false
    }
  }
}

const saveFile = async () => {
  if (!selectedFile.value) return

  try {
    await axios.post('http://localhost:8000/api/desktop/files/write', null, {
      params: { path: selectedFile.value.path },
      data: { content: fileContent.value }
    })

    alert('保存成功')
  } catch (error: any) {
    console.error('保存文件失败:', error)
    alert(error.response?.data?.detail || '保存失败')
  }
}

const deleteFile = async (file: FileItem) => {
  if (!confirm(`确定要删除 ${file.is_dir ? '目录' : '文件'} "${file.name}" 吗？`)) return

  try {
    await axios.delete('http://localhost:8000/api/desktop/files/delete', {
      params: { path: file.path }
    })

    await loadFiles()
  } catch (error: any) {
    console.error('删除失败:', error)
    alert(error.response?.data?.detail || '删除失败')
  }
}

const goBack = () => {
  const parentPath = currentPath.value.split('/').slice(0, -1).join('/') || '.'
  loadFiles(parentPath)
}

onMounted(() => {
  loadFiles()
})
</script>

<template>
  <div class="files-view">
    <!-- 导航标签 -->
    <div class="navigation-wrapper">
      <NavigationTabs />
    </div>

    <div class="files-header">
      <h2>文件浏览器</h2>
      <div class="path-nav">
        <button class="nav-btn" @click="loadFiles('.')" :disabled="currentPath === '.'">
          <i class="pi pi-home"></i>
        </button>
        <button class="nav-btn" @click="goBack" :disabled="currentPath === '.'">
          <i class="pi pi-arrow-left"></i>
        </button>
        <div class="current-path">{{ currentPath }}</div>
      </div>
    </div>

    <div class="files-content">
      <!-- 文件列表区域 -->
      <div class="files-main">
        <div v-if="isLoading && !showContent" class="loading">
          <div class="spinner"></div>
          <span>加载中...</span>
        </div>

        <div v-else-if="!showContent" class="file-list">
          <div
            v-for="file in files"
            :key="file.path"
            class="file-item"
            :class="{ directory: file.is_dir }"
            @click="openFile(file)"
            @contextmenu.prevent="deleteFile(file)"
          >
            <i :class="file.is_dir ? 'pi pi-folder' : 'pi pi-file'" class="file-icon"></i>
            <div class="file-info">
              <div class="file-name">{{ file.name }}</div>
              <div class="file-meta">
                {{ file.is_dir ? '目录' : formatSize(file.size) }}
                <span class="separator">|</span>
                {{ formatDate(file.modified) }}
              </div>
            </div>
          </div>

          <div v-if="files.length === 0" class="empty">
            <i class="pi pi-folder-open"></i>
            <span>目录为空</span>
          </div>
        </div>

        <div v-else class="file-editor">
          <div class="editor-header">
            <button class="close-btn" @click="showContent = false">
              <i class="pi pi-times"></i>
              关闭
            </button>
            <div class="file-title">{{ selectedFile?.name }}</div>
            <button class="save-btn" @click="saveFile">
              <i class="pi pi-save"></i>
              保存
            </button>
          </div>
          <textarea
            v-model="fileContent"
            class="file-content-area"
            spellcheck="false"
          ></textarea>
        </div>
      </div>

      <!-- 右侧信息面板 -->
      <div class="files-sidebar">
        <!-- 统计信息卡片 -->
        <div class="info-card">
          <div class="info-card-header">
            <i class="pi pi-chart-pie"></i>
            <span>统计信息</span>
          </div>
          <div class="info-card-content">
            <div class="stat-row">
              <span class="stat-label">文件数</span>
              <span class="stat-value">{{ files.filter(f => !f.is_dir).length }}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">目录数</span>
              <span class="stat-value">{{ files.filter(f => f.is_dir).length }}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">总大小</span>
              <span class="stat-value">{{ formatSize(files.filter(f => !f.is_dir).reduce((a, b) => a + b.size, 0)) }}</span>
            </div>
          </div>
        </div>

        <!-- 当前路径卡片 -->
        <div class="info-card">
          <div class="info-card-header">
            <i class="pi pi-folder"></i>
            <span>当前位置</span>
          </div>
          <div class="info-card-content">
            <div class="path-display">
              {{ currentPath }}
            </div>
          </div>
        </div>

        <!-- 操作提示卡片 -->
        <div class="info-card">
          <div class="info-card-header">
            <i class="pi pi-info-circle"></i>
            <span>操作提示</span>
          </div>
          <div class="info-card-content">
            <div class="tip-item">
              <i class="pi pi-mouse-pointer"></i>
              <span>左键点击: 打开文件/目录</span>
            </div>
            <div class="tip-item">
              <i class="pi pi-trash"></i>
              <span>右键点击: 删除文件</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.files-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: transparent;
  position: relative;
  padding: 8px;
  box-sizing: border-box;
}

.files-view::before {
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

.files-header {
  padding: 16px 24px;
  border-bottom: 1px solid rgba(45, 212, 191, 0.25);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 10px 10px 0 0;
}

.files-header h2 {
  margin: 0;
  font-size: 18px;
  color: #e0f2fe;
  font-weight: 600;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.path-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-btn {
  width: 36px;
  height: 36px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 6px;
  color: #e0f2fe;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.nav-btn:hover:not(:disabled) {
  background: rgba(45, 212, 191, 0.2);
  border-color: rgba(45, 212, 191, 0.4);
  color: #2dd4bf;
}

.nav-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.current-path {
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(45, 212, 191, 0.15);
  border-radius: 6px;
  font-size: 13px;
  color: #94a3b8;
  font-family: 'Courier New', Consolas, monospace;
}

.files-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 0 0 10px 10px;
}

.files-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
  color: #94a3b8;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(45, 212, 191, 0.2);
  border-top-color: #2dd4bf;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.file-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

/* 右侧侧边栏 */
.files-sidebar {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: rgba(45, 212, 191, 0.05);
  border-left: 1px solid rgba(45, 212, 191, 0.15);
  overflow-y: auto;
}

.files-sidebar .info-card {
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.files-sidebar .info-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  color: #2dd4bf;
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.files-sidebar .info-card-header i {
  font-size: 14px;
}

.files-sidebar .info-card-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(45, 212, 191, 0.08);
  border-radius: 8px;
}

.stat-label {
  font-size: 12px;
  color: #94a3b8;
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: #e0f2fe;
}

.path-display {
  padding: 12px;
  background: rgba(45, 212, 191, 0.1);
  border-radius: 8px;
  font-family: 'Courier New', Consolas, monospace;
  font-size: 12px;
  color: #2dd4bf;
  word-break: break-all;
  line-height: 1.6;
}

.tip-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(45, 212, 191, 0.08);
  border-radius: 8px;
  font-size: 12px;
  color: #e0f2fe;
}

.tip-item i {
  font-size: 14px;
  color: #2dd4bf;
}

.tip-item span {
  flex: 1;
  color: #94a3b8;
}

/* 亮色主题适配 */
:deep(.light-mode .files-sidebar) {
  background: rgba(13, 148, 136, 0.05);
  border-left-color: rgba(13, 148, 136, 0.15);
}

:deep(.light-mode .files-sidebar .info-card) {
  background: rgba(255, 255, 255, 0.6);
  border-color: rgba(13, 148, 136, 0.2);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

:deep(.light-mode .files-sidebar .info-card-header) {
  color: #0d9488;
}

:deep(.light-mode .files-sidebar .stat-value) {
  color: #0f766e;
}

:deep(.light-mode .files-sidebar .path-display) {
  background: rgba(13, 148, 136, 0.1);
  color: #0d9488;
}

:deep(.light-mode .files-sidebar .tip-item) {
  color: #0f766e;
}

:deep(.light-mode .files-sidebar .tip-item i) {
  color: #0d9488;
}

:deep(.light-mode .files-sidebar .tip-item span) {
  color: #64748b;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.file-item:hover {
  background: rgba(45, 212, 191, 0.1);
  transform: translateX(4px);
  border-color: rgba(45, 212, 191, 0.2);
}

.file-item.directory {
  background: rgba(233, 69, 96, 0.05);
}

.file-item.directory:hover {
  background: rgba(233, 69, 96, 0.1);
  border-color: rgba(233, 69, 96, 0.2);
}

.file-icon {
  font-size: 24px;
  color: #2dd4bf;
}

.file-item.directory .file-icon {
  color: #fbbf24;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  color: #e0f2fe;
  margin-bottom: 4px;
  word-break: break-all;
}

.file-meta {
  font-size: 12px;
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 8px;
}

.separator {
  opacity: 0.3;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 16px;
  color: #64748b;
}

.empty i {
  font-size: 48px;
}

.file-editor {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: transparent;
}

.editor-header {
  padding: 12px 20px;
  background: rgba(0, 0, 0, 0.3);
  border-bottom: 1px solid rgba(45, 212, 191, 0.2);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.file-title {
  font-size: 14px;
  color: #e0f2fe;
  font-family: 'Courier New', Consolas, monospace;
}

.close-btn, .save-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.close-btn {
  background: transparent;
  color: #94a3b8;
}

.close-btn:hover {
  background: rgba(45, 212, 191, 0.1);
  color: #e0f2fe;
}

.save-btn {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.3) 0%, rgba(22, 163, 74, 0.3) 100%);
  color: #4ade80;
  border-color: rgba(34, 197, 94, 0.4);
}

.save-btn:hover {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.4) 0%, rgba(22, 163, 74, 0.4) 100%);
  color: #86efac;
}

.file-content-area {
  flex: 1;
  background: transparent;
  border: none;
  padding: 20px;
  color: #e0f2fe;
  font-size: 13px;
  font-family: 'Courier New', Consolas, monospace;
  line-height: 1.6;
  resize: none;
  outline: none;
}
</style>
