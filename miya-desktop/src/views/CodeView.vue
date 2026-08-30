<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import NavigationTabs from '../components/NavigationTabs.vue'

const codeContent = ref('// 欢迎使用弥娅代码编辑器\n// 简单版本 - 正在添加高级功能...\n')
const language = ref('typescript')
const output = ref('')
const isSaving = ref(false)
const unsavedChanges = ref(false)
const activeTab = ref('editor')

const languages = [
  { name: 'TypeScript', value: 'typescript' },
  { name: 'JavaScript', value: 'javascript' },
  { name: 'Python', value: 'python' },
  { name: 'HTML', value: 'html' },
  { name: 'CSS', value: 'css' },
  { name: 'JSON', value: 'json' }
]

const fileStatus = computed(() => {
  if (unsavedChanges.value) return '未保存'
  return '已保存'
})

const lineCount = computed(() => {
  return codeContent.value.split('\n').length
})

const charCount = computed(() => {
  return codeContent.value.length
})

const saveFile = async () => {
  if (isSaving.value) return
  isSaving.value = true
  try {
    output.value = '文件保存成功'
    unsavedChanges.value = false
  } catch (error) {
    console.error('保存文件失败:', error)
    output.value = '保存文件失败: ' + (error as Error).message
  } finally {
    isSaving.value = false
  }
}

onMounted(() => {
  console.log('弥娅代码编辑器已启动')
})
</script>

<template>
  <div class="code-view">
    <!-- 导航标签 -->
    <div class="navigation-wrapper">
      <NavigationTabs />
    </div>

    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <h2 class="toolbar-title">
          <i class="pi pi-code"></i>
          弥娅代码编辑器
        </h2>
        <div class="file-status" :class="{ unsaved: unsavedChanges }">
          {{ fileStatus }}
        </div>
      </div>

      <div class="toolbar-center">
        <select v-model="language" class="language-select">
          <option v-for="lang in languages" :key="lang.value" :value="lang.value">
            {{ lang.name }}
          </option>
        </select>
      </div>

      <div class="toolbar-right">
        <button
          class="toolbar-btn primary"
          @click="saveFile"
          :disabled="isSaving"
          title="保存文件"
        >
          <i class="pi" :class="isSaving ? 'pi-spin pi-spinner' : 'pi-save'"></i>
          保存
        </button>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-container">
      <!-- 编辑器区域 -->
      <div class="editor-area">
        <textarea
          v-model="codeContent"
          class="code-editor"
          :class="`lang-${language}`"
          spellcheck="false"
          @input="unsavedChanges = true"
        ></textarea>
      </div>

      <!-- 右侧信息面板 -->
      <div class="info-sidebar">
        <!-- 文件信息卡片 -->
        <div class="info-card">
          <div class="info-card-header">
            <i class="pi pi-file-code"></i>
            <span>文件信息</span>
          </div>
          <div class="info-card-content">
            <div class="info-row">
              <span class="info-label">语言</span>
              <span class="info-value">{{ language }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">行数</span>
              <span class="info-value">{{ lineCount }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">字符数</span>
              <span class="info-value">{{ charCount }}</span>
            </div>
          </div>
        </div>

        <!-- 编辑器设置卡片 -->
        <div class="info-card">
          <div class="info-card-header">
            <i class="pi pi-cog"></i>
            <span>编辑器设置</span>
          </div>
          <div class="info-card-content">
            <div class="setting-row">
              <span class="setting-label">字体大小</span>
              <span class="setting-value">14px</span>
            </div>
            <div class="setting-row">
              <span class="setting-label">Tab大小</span>
              <span class="setting-value">2 空格</span>
            </div>
            <div class="setting-row">
              <span class="setting-label">自动换行</span>
              <span class="setting-value">关闭</span>
            </div>
          </div>
        </div>

        <!-- 快捷提示卡片 -->
        <div class="info-card">
          <div class="info-card-header">
            <i class="pi pi-lightbulb"></i>
            <span>快捷提示</span>
          </div>
          <div class="info-card-content">
            <div class="tip-item">
              <kbd>Ctrl</kbd> + <kbd>S</kbd>
              <span>保存文件</span>
            </div>
            <div class="tip-item">
              <kbd>Ctrl</kbd> + <kbd>Z</kbd>
              <span>撤销</span>
            </div>
            <div class="tip-item">
              <kbd>Ctrl</kbd> + <kbd>Y</kbd>
              <span>重做</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部状态栏 -->
    <div class="statusbar">
      <div class="statusbar-left">
        <span class="status-item">
          <i class="pi pi-globe"></i>
          {{ language }}
        </span>
      </div>
      <div class="statusbar-right">
        <span class="status-item">
          <i class="pi pi-check"></i>
          {{ unsavedChanges ? '未保存' : '已保存' }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.code-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: transparent;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  position: relative;
  padding: 8px;
  box-sizing: border-box;
}

.code-view::before {
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

/* 顶部工具栏 */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(45, 212, 191, 0.25);
  min-height: 60px;
  border-radius: 10px 10px 0 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.toolbar-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #e0f2fe;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.file-status {
  font-size: 12px;
  color: #858585;
  padding: 4px 12px;
  border-radius: 4px;
  background: #2d2d2d;
}

.file-status.unsaved {
  color: #e8c16d;
  background: rgba(232, 193, 109, 0.1);
}

.toolbar-center {
  display: flex;
  align-items: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.language-select {
  padding: 6px 12px;
  background: #3c3c3c;
  border: 1px solid #555;
  border-radius: 4px;
  color: #cccccc;
  font-size: 13px;
  outline: none;
  cursor: pointer;
  transition: all 0.2s;
}

.language-select:hover {
  border-color: #777;
}

.language-select:focus {
  border-color: #007acc;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 12px;
  background: #3c3c3c;
  border: 1px solid #555;
  border-radius: 4px;
  color: #cccccc;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 80px;
}

.toolbar-btn:hover:not(:disabled) {
  background: #4c4c4c;
  border-color: #777;
}

.toolbar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toolbar-btn.primary {
  background: #0e639c;
  border-color: #0e639c;
}

.toolbar-btn.primary:hover:not(:disabled) {
  background: #1177bb;
}

/* 主容器 */
.main-container {
  flex: 1;
  display: flex;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 0 0 10px 10px;
}

/* 编辑器区域 */
.editor-area {
  flex: 1;
  display: flex;
  overflow: hidden;
  background: transparent;
}

.code-editor {
  flex: 1;
  padding: 24px;
  background: transparent;
  color: #e0f2fe;
  border: none;
  outline: none;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  tab-size: 2;
}

/* 右侧信息面板 */
.info-sidebar {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: rgba(45, 212, 191, 0.05);
  border-left: 1px solid rgba(45, 212, 191, 0.15);
  overflow-y: auto;
}

.info-card {
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.info-card-header {
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

.info-card-header i {
  font-size: 14px;
}

.info-card-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-row,
.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(45, 212, 191, 0.08);
  border-radius: 8px;
}

.info-label,
.setting-label {
  font-size: 12px;
  color: #94a3b8;
}

.info-value,
.setting-value {
  font-size: 13px;
  font-weight: 600;
  color: #e0f2fe;
}

.tip-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: rgba(45, 212, 191, 0.08);
  border-radius: 8px;
  font-size: 12px;
  color: #e0f2fe;
}

.tip-item kbd {
  display: inline-block;
  padding: 4px 8px;
  background: rgba(45, 212, 191, 0.2);
  border: 1px solid rgba(45, 212, 191, 0.3);
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px;
  color: #2dd4bf;
}

.tip-item span {
  flex: 1;
  color: #94a3b8;
}

/* 亮色主题适配 */
:deep(.light-mode .info-sidebar) {
  background: rgba(13, 148, 136, 0.05);
  border-left-color: rgba(13, 148, 136, 0.15);
}

:deep(.light-mode .info-card) {
  background: rgba(255, 255, 255, 0.6);
  border-color: rgba(13, 148, 136, 0.2);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

:deep(.light-mode .info-card-header) {
  color: #0d9488;
}

:deep(.light-mode .info-value),
:deep(.light-mode .setting-value) {
  color: #0f766e;
}

:deep(.light-mode .info-row),
:deep(.light-mode .setting-row) {
  background: rgba(13, 148, 136, 0.08);
}

:deep(.light-mode .tip-item) {
  color: #0f766e;
}

:deep(.light-mode .tip-item span) {
  color: #64748b;
}

:deep(.light-mode .tip-item kbd) {
  background: rgba(13, 148, 136, 0.15);
  border-color: rgba(13, 148, 136, 0.25);
  color: #0d9488;
}

.code-editor:focus {
  color: #f0fdfa;
}

/* 语法高亮简单模拟 */
.code-editor.lang-javascript,
.code-editor.lang-typescript {
  color: #9cdcfe;
}

.code-editor.lang-python {
  color: #569cd6;
}

.code-editor.lang-html {
  color: #d4d4d4d;
}

.code-editor.lang-css {
  color: #ce9178;
}

.code-editor.lang-json {
  color: #9cdcfe;
}

/* 状态栏 */
.statusbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.3) 0%, rgba(13, 148, 136, 0.3) 100%);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  color: #e0f2fe;
  font-size: 12px;
  height: 26px;
  flex-shrink: 0;
  border-top: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 0 0 12px 12px;
}

.statusbar-left,
.statusbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
  opacity: 0.9;
}

.status-item i {
  font-size: 12px;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #424242;
  border-radius: 5px;
}

::-webkit-scrollbar-thumb:hover {
  background: #4f4f4f;
}
</style>
