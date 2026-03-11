<template>
  <div class="workspace">
    <!-- 左侧会话栏 -->
    <aside class="sidebar-left">
      <SessionSidebar
        @create-session="handleCreateSession"
        @select-session="handleSelectSession"
        @export-session="handleExportSession"
        @delete-session="handleDeleteSession"
      />
    </aside>

    <!-- 主工作区 -->
    <main class="workspace-main">
      <!-- 顶部导航栏 -->
      <header class="workspace-header">
        <div class="header-content">
          <h1 class="workspace-title">{{ currentTitle }}</h1>
          <div class="header-actions">
            <button class="icon-btn" @click="toggleQuickCommand" title="快捷指令">
              <i class="pi pi-bolt"></i>
            </button>
            <button class="icon-btn" @click="toggleToolbox" title="工具箱">
              <i class="pi pi-th-large"></i>
            </button>
            <button class="icon-btn" @click="toggleSettings" title="设置">
              <i class="pi pi-cog"></i>
            </button>
          </div>
        </div>
      </header>

      <!-- 快捷指令面板 -->
      <div v-if="showQuickCommand" class="quick-command-panel">
        <QuickCommand @execute="executeCommand" @close="showQuickCommand = false" />
      </div>

      <!-- 主内容区域 -->
      <div class="workspace-content">
        <!-- 聊天区域 -->
        <div class="chat-area">
          <MessageList
            :messages="messages"
            :is-typing="isTyping"
            @regenerate="handleRegenerate"
            @delete="handleDelete"
            @copy="handleCopy"
          />
          
          <!-- 输入区域 -->
          <div class="input-area">
            <ChatInput
              @send="sendMessage"
              :disabled="isLoading"
            />
          </div>
        </div>

        <!-- 结果预览区域 -->
        <div v-if="hasResultPreview" class="result-preview">
          <ResultPreview
            :result="currentResult"
            @close="closeResultPreview"
          />
        </div>
      </div>
    </main>

    <!-- 右侧工具箱 -->
    <aside v-if="showToolbox" class="sidebar-right">
      <Toolbox
        @open-file="handleOpenFile"
        @open-browser="handleOpenBrowser"
        @open-terminal="handleOpenTerminal"
        @open-mcp="handleOpenMCP"
      />
    </aside>

    <!-- Live2D 浮动卡片 -->
    <Live2DFloat
      :model-path="currentModelPath"
      :emotion="currentEmotion"
      :width="200"
      :height="280"
      :current-task="currentTask"
      @emotion-change="handleEmotionChange"
      @toggle-desktop="toggleDesktopPet"
      @open-settings="toggleSettings"
      @quick-command="executeCommand"
    />

    <!-- 设置面板 -->
    <div v-if="showSettings" class="settings-panel-overlay" @click.self="toggleSettings">
      <SettingsPanel
        :model-path="currentModelPath"
        @update-model="handleUpdateModel"
        @close="toggleSettings"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '../stores/chat'
import SessionSidebar from './SessionSidebar.vue'
import MessageList from './MessageList.vue'
import ChatInput from './ChatInput.vue'
import QuickCommand from './QuickCommand.vue'
import ResultPreview from './ResultPreview.vue'
import Toolbox from './Toolbox.vue'
import Live2DFloat from './Live2DFloat.vue'
import SettingsPanel from './SettingsPanel.vue'

const chatStore = useChatStore()

// 状态
const showQuickCommand = ref(false)
const showToolbox = ref(false)
const showSettings = ref(false)
const isDesktopPetMode = ref(false)
const isTyping = ref(false)
const isLoading = ref(false)
const currentTask = ref('')
const currentResult = ref<any>(null)
const currentModelPath = ref('/live2d/ht/ht.model3.json')
const currentEmotion = ref('平静')

// 计算属性
const currentTitle = computed(() => chatStore.currentSession?.title || '新对话')
const messages = computed(() => chatStore.currentMessages)
const hasResultPreview = computed(() => currentResult.value !== null)

// 会话操作
function handleCreateSession() {
  chatStore.createSession()
}

function handleSelectSession(id: string) {
  chatStore.switchSession(id)
}

function handleExportSession(format: string) {
  const session = chatStore.currentSession
  if (!session) {
    console.warn('没有选中的会话')
    return
  }

  const messages = chatStore.currentMessages
  const exportData = {
    sessionId: session.id,
    title: session.title,
    createdAt: session.createdAt,
    messages: messages.map(msg => ({
      role: msg.role,
      content: msg.content,
      timestamp: msg.timestamp || new Date().toISOString()
    }))
  }

  let filename = `${session.title}_${new Date().toISOString().slice(0, 10)}`
  let content = ''
  let mimeType = ''

  switch (format) {
    case 'json':
      content = JSON.stringify(exportData, null, 2)
      filename += '.json'
      mimeType = 'application/json'
      break
    case 'markdown':
      content = `# ${session.title}\n\n导出时间: ${new Date().toLocaleString()}\n\n---\n\n`
      messages.forEach(msg => {
        const role = msg.role === 'user' ? '👤 用户' : '🤖 弥娅'
        content += `## ${role}\n\n${msg.content}\n\n---\n\n`
      })
      filename += '.md'
      mimeType = 'text/markdown'
      break
    case 'txt':
      content = `会话标题: ${session.title}\n导出时间: ${new Date().toLocaleString()}\n\n`
      messages.forEach(msg => {
        const role = msg.role === 'user' ? '[用户]' : '[弥娅]'
        content += `${role}\n${msg.content}\n\n`
      })
      filename += '.txt'
      mimeType = 'text/plain'
      break
    default:
      console.warn('不支持的导出格式:', format)
      return
  }

  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)

  console.log('导出会话成功:', format)
}

function handleDeleteSession(id: string) {
  chatStore.deleteSession(id)
}

// 消息操作
async function sendMessage(content: string) {
  isLoading.value = true
  isTyping.value = true

  // 添加用户消息
  chatStore.addMessage({
    role: 'user',
    content,
    sessionId: chatStore.currentSessionId
  })

  try {
    // 模拟 API 调用
    await new Promise(resolve => setTimeout(resolve, 1000))

    // 添加助手消息
    chatStore.addMessage({
      role: 'assistant',
      content: '这是回复内容',
      sessionId: chatStore.currentSessionId
    })
  } catch (error) {
    console.error('发送消息失败:', error)
  } finally {
    isLoading.value = false
    isTyping.value = false
  }
}

function handleRegenerate(message: any) {
  console.log('重新生成:', message)
}

function handleDelete(message: any) {
  console.log('删除消息:', message)
}

function handleCopy(content: string) {
  navigator.clipboard.writeText(content)
}

// 快捷指令
function toggleQuickCommand() {
  showQuickCommand.value = !showQuickCommand.value
}

function executeCommand(command: string) {
  console.log('执行指令:', command)
  showQuickCommand.value = false
  
  // 添加到聊天
  sendMessage(command)
}

// 工具箱
function toggleToolbox() {
  showToolbox.value = !showToolbox.value
}

function handleOpenFile() {
  console.log('打开文件')
}

function handleOpenBrowser() {
  console.log('打开浏览器')
}

function handleOpenTerminal() {
  console.log('打开终端')
}

function handleOpenMCP() {
  console.log('打开 MCP')
}

// 结果预览
function closeResultPreview() {
  currentResult.value = null
}

// Live2D
function handleEmotionChange(emotion: string) {
  currentEmotion.value = emotion
}

function toggleDesktopPet() {
  isDesktopPetMode.value = !isDesktopPetMode.value

  if (isDesktopPetMode.value) {
    // 切换到桌宠模式：Live2D 窗口独立显示
    console.log('切换到桌宠模式')
    window.electronAPI?.openLive2DWindow?.()
  } else {
    // 切换回嵌入模式
    console.log('切换到嵌入模式')
    window.electronAPI?.closeLive2DWindow?.()
  }
}

function handleUpdateModel(modelPath: string) {
  currentModelPath.value = modelPath
  console.log('更新模型:', modelPath)
}

// 设置
function toggleSettings() {
  showSettings.value = !showSettings.value

  if (showSettings.value) {
    console.log('打开设置面板')
  } else {
    console.log('关闭设置面板')
  }
}
</script>

<style scoped>
.workspace {
  display: grid;
  grid-template-columns: 280px 1fr 300px;
  grid-template-rows: 60px 1fr;
  height: 100vh;
  background: var(--bg-primary);
  overflow: hidden;
}

.sidebar-left {
  grid-column: 1 / 2;
  grid-row: 1 / -1;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-secondary);
  display: flex;
  flex-direction: column;
}

.workspace-main {
  grid-column: 2 / 3;
  grid-row: 1 / -1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.sidebar-right {
  grid-column: 3 / 4;
  grid-row: 1 / -1;
  background: var(--bg-secondary);
  border-left: 1px solid var(--border-secondary);
  display: flex;
  flex-direction: column;
}

/* 顶部导航栏 */
.workspace-header {
  height: 60px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-secondary);
  padding: 0 var(--spacing-lg);
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.workspace-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.icon-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: transparent;
  border: 1px solid var(--border-tertiary);
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-base);
}

.icon-btn:hover {
  background: var(--bg-hover);
  border-color: var(--border-secondary);
  color: var(--text-primary);
}

.icon-btn i {
  font-size: 18px;
}

/* 快捷指令面板 */
.quick-command-panel {
  position: absolute;
  top: 70px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  width: 600px;
  max-width: 90%;
}

/* 主内容区域 */
.workspace-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.result-preview {
  flex: 0 0 400px;
  border-left: 1px solid var(--border-secondary);
  overflow-y: auto;
}

/* 输入区域 */
.input-area {
  padding: var(--spacing-lg);
  border-top: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
}

/* 设置面板覆盖层 */
.settings-panel-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

/* 响应式 */
@media (max-width: 1280px) {
  .workspace {
    grid-template-columns: 240px 1fr 0px;
  }
  
  .sidebar-right {
    display: none;
  }
}

@media (max-width: 768px) {
  .workspace {
    grid-template-columns: 0px 1fr 0px;
  }
  
  .sidebar-left {
    display: none;
  }
}
</style>
