<script setup lang="ts">
import { ref, nextTick, onMounted, watch, onUnmounted, computed } from 'vue'
import { useChatStore } from '../stores/chat'
import { useSystemStore } from '../stores/system'
import { useSettingsStore } from '../stores/settings'
import { chatApi } from '../api/chat'
import { systemApi } from '../api/system'
import MiyaAvatar from '../components/MiyaAvatar.vue'
import MessageBubble from '../components/MessageBubble.vue'
import ChatInput from '../components/ChatInput.vue'
import ThemeToggle from '../components/ThemeToggle.vue'
import SessionSidebar from '../components/SessionSidebar.vue'
import MiyaPersona from '../components/MiyaPersona.vue'
import NavigationTabs from '../components/NavigationTabs.vue'
import { downloadFile } from '../utils'
import { LIVE2D_MODELS } from '../config/live2dModels'

const chatStore = useChatStore()
const systemStore = useSystemStore()
const settingsStore = useSettingsStore()

const messageContainer = ref<HTMLElement>()
const showPersona = ref(false)
const personaPanelRef = ref<HTMLElement>()
const uiOpacity = ref(0.92) // UI 透明度控制
const latestMessageId = ref<string | null>(null) // 用于追踪最新消息（用于TTS自动播放）

// 桌宠模式状态
const live2DWindowOpen = ref(false)

// 可用模型列表
const availableModels = ref(Object.values(LIVE2D_MODELS))

// 表情列表
const expressions = [
  { name: '开心', index: 0 },
  { name: '害羞', index: 1 },
  { name: '生气', index: 2 },
  { name: '悲伤', index: 3 },
  { name: '平静', index: 4 },
  { name: '兴奋', index: 5 },
  { name: '调皮', index: 6 },
  { name: '嘘声', index: 7 }
]

// 当前选中的模型ID
const selectedModelId = ref('ht')

// 当前表情
const live2dEmotion = ref('平静')

// 切换桌宠模式
async function toggleDesktopPet() {
  try {
    if (!window.electronAPI?.live2d) {
      console.error('[ChatView] electronAPI不可用，无法切换桌宠模式')
      return
    }

    if (live2DWindowOpen.value) {
      // 关闭桌宠
      await window.electronAPI.live2d.close()
      live2DWindowOpen.value = false

      // 恢复主窗口的 Live2D 显示
      window.electronAPI.sendShowMainLive2D?.()
      console.log('[ChatView] 桌宠已关闭，主窗口 Live2D 已恢复')
    } else {
      // 打开桌宠前，先隐藏主窗口的 Live2D（避免 WebGL 冲突）
      window.electronAPI.sendHideMainLive2D?.()
      console.log('[ChatView] 已隐藏主窗口 Live2D')

      // 延迟一点再打开桌宠，确保主窗口 Live2D 已隐藏
      await new Promise(resolve => setTimeout(resolve, 200))

      // 打开桌宠
      await window.electronAPI.live2d.create()
      live2DWindowOpen.value = true

      // 同步当前选择的模型到桌宠
      if (window.electronAPI?.live2d?.sendModelChange) {
        window.electronAPI.live2d.sendModelChange(selectedModelId.value)
        console.log('[ChatView] 同步模型到桌宠:', selectedModelId.value)
      }

      // 同步当前表情到桌宠
      if (window.electronAPI?.live2d?.sendExpression) {
        const emotionIndex = expressions.findIndex(e => e.name === live2dEmotion.value)
        if (emotionIndex >= 0) {
          window.electronAPI.live2d.sendExpression(emotionIndex)
          console.log('[ChatView] 同步表情到桌宠:', live2dEmotion.value)
        }
      }

      console.log('[ChatView] 桌宠已打开')
    }
  } catch (error) {
    console.error('[ChatView] 切换桌宠模式失败:', error)
  }
}

// 设置表情并同步到桌宠
function setLive2DEmotion(emotionName: string) {
  live2dEmotion.value = emotionName

  // 同步到桌宠窗口
  if (window.electronAPI?.live2d?.sendExpression) {
    const emotionIndex = expressions.findIndex(e => e.name === emotionName)
    if (emotionIndex >= 0) {
      window.electronAPI.live2d.sendExpression(emotionIndex)
    }
  }
}





// 计算当前情绪
const currentEmotion = computed(() => {
  try {
    return systemStore?.status?.emotion?.dominant || '平静'
  } catch {
    return '平静'
  }
})

// 点击外部关闭面板
const handleClickOutside = (event: MouseEvent) => {
  const target = event.target as HTMLElement

  // 忽略左侧栏按钮的点击
  if (target.closest('.left-sidebar')) {
    return
  }

  if (showPersona.value && personaPanelRef.value) {
    if (!target.closest('.persona-panel') && !target.closest('.left-sidebar')) {
      showPersona.value = false
    }
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)

  // 监听桌宠窗口关闭事件（用户直接关闭窗口时同步状态）
  if (window.electronAPI?.live2d?.onClosed) {
    window.electronAPI.live2d.onClosed(() => {
      console.log('[ChatView] 桌宠窗口已关闭')
      live2DWindowOpen.value = false
    })
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)

  // 移除桌宠关闭事件监听
  if (window.electronAPI?.live2d?.removeAllListeners) {
    window.electronAPI.live2d.removeAllListeners()
  }
})

onMounted(() => {
  chatStore.initialize()
  settingsStore.initialize()
  loadSystemStatus()
})

// 监听消息变化,自动滚动
watch(() => chatStore.currentMessages, () => {
  nextTick(() => {
    scrollToBottom()
  })
}, { deep: true })

async function loadSystemStatus() {
  try {
    const status = await systemApi.getStatus()
    if (status) {
      systemStore.setStatus(status)
    }
  } catch (error) {
    console.error('Failed to load system status:', error)
  }
}

async function sendMessage(content: string) {
  chatStore.isLoading = true
  chatStore.isTyping = true
  latestMessageId.value = null // 清除之前的最新消息标记

  // 添加用户消息
  chatStore.addMessage({
    role: 'user',
    content,
    sessionId: chatStore.currentSessionId
  })

  nextTick(() => {
    scrollToBottom()
  })

  try {
    const response = await chatApi.sendMessage({
      message: content,
      session_id: chatStore.currentSessionId,
      platform: 'desktop'
    })

    // 添加助手消息
    const assistantMsg = chatStore.addMessage({
      role: 'assistant',
      content: response.response || '抱歉,我遇到了一些问题。',
      emotion: response.emotion,
      personality: response.personality,
      toolsUsed: response.tools_used,
      memoryRetrieved: response.memory_retrieved,
      sessionId: chatStore.currentSessionId
    })
    // 设置最新消息ID用于TTS自动播放
    latestMessageId.value = assistantMsg.id

    // 更新系统状态
    if (response.emotion || response.personality) {
      systemStore.setStatus({
        version: '1.0.0',
        personality: response.personality?.vectors || {
          warmth: 0.5,
          logic: 0.5,
          creativity: 0.5,
          empathy: 0.5,
          resilience: 0.5
        },
        emotion: response.emotion || {
          dominant: '平静',
          intensity: 0.5
        }
      })
    }
  } catch (error: any) {
    console.error('发送消息失败:', error)
    chatStore.addMessage({
      role: 'assistant',
      content: '抱歉,连接服务器失败。请确保后端服务已启动。',
      sessionId: chatStore.currentSessionId
    })
  } finally {
    chatStore.isLoading = false
    chatStore.isTyping = false
  }
}

function scrollToBottom() {
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight
  }
}

function handleRegenerate(message: any) {
  // 找到之前的用户消息
  const messages = chatStore.currentMessages
  const index = messages.findIndex(m => m.id === message.id)
  if (index > 0) {
    const userMessage = messages[index - 1]
    if (userMessage.role === 'user') {
      sendMessage(userMessage.content)
    }
  }
}

function handleDelete(message: any) {
  chatStore.deleteMessage(message.id)
}

function handleCopy() {
  // 复制逻辑在组件内部处理
}

function exportCurrentSession(format: 'json' | 'markdown' | 'txt') {
  const content = chatStore.exportSession(format)
  const filename = `miya_session_${chatStore.currentSessionId}_${format}`
  downloadFile(content, `${filename}.${format}`)
}
</script>

<template>
  <div class="chat-view">
    <!-- 左侧功能栏 -->
    <div class="left-sidebar" :style="{ opacity: uiOpacity }">
      <SessionSidebar
        @create-session="() => chatStore.createSession()"
        @select-session="(id) => chatStore.switchSession(id)"
        @export-session="(format) => exportCurrentSession(format)"
        @delete-session="(id) => chatStore.deleteSession(id)"
      />
      <div class="sidebar-divider"></div>
      <button class="icon-button" title="主题切换">
        <ThemeToggle />
      </button>
      <button class="icon-button persona-toggle" @click="showPersona = !showPersona" :class="{ active: showPersona }" title="人格面板">
        <i class="pi pi-user"></i>
      </button>
      <button class="icon-button desktop-pet-toggle" @click="toggleDesktopPet" :class="{ active: live2DWindowOpen }" title="桌宠模式">
        <i class="pi pi-paw"></i>
        <span class="btn-label">桌宠</span>
      </button>
    </div>

    <!-- 主对话区域 -->
    <div class="chat-main" :style="{ opacity: uiOpacity }">
  <!-- 导航标签 -->
  <div class="navigation-wrapper">
    <NavigationTabs />
  </div>

  <!-- 头部 -->
  <div class="chat-header">
    <div class="header-content">
      <h2>{{ chatStore.currentSession?.title || '对话' }}</h2>
      <span class="message-count">{{ chatStore.currentMessages.length }} 条消息</span>
    </div>
    <!-- UI 透明度控制 -->
    <div class="opacity-control">
      <i class="pi pi-sun"></i>
      <input 
        type="range" 
        v-model.number="uiOpacity" 
        min="0.5" 
        max="1" 
        step="0.05"
        class="opacity-slider"
        title="调整UI透明度"
      />
    </div>
  </div>

    <!-- 主内容区域：仅消息列表 -->
    <div class="chat-content-wrapper">
      <div class="chat-content">
        <div class="chat-messages" ref="messageContainer">
          <div
            v-for="message in chatStore.currentMessages"
            :key="message.id"
            class="message-row"
            :class="message.role"
          >
            <MiyaAvatar
              v-if="message.role === 'assistant'"
              :emotion="message.emotion"
              :is-typing="chatStore.isTyping"
              size="md"
            />
            <div class="message-content-wrapper">
              <MessageBubble
                :message="message"
                :is-new="message.id === latestMessageId"
                @regenerate="handleRegenerate"
                @delete="handleDelete"
                @copy="handleCopy"
                @played="latestMessageId = null"
              />
            </div>
          </div>

          <!-- 正在输入指示器 -->
          <div v-if="chatStore.isTyping" class="message-row assistant">
            <MiyaAvatar is-typing size="md" />
            <div class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="chat-input-area">
      <ChatInput @send="sendMessage" />
    </div>
  </div>
  </div>

  <!-- 人格面板（独立面板） -->
  <div v-if="showPersona" class="persona-panel show" ref="personaPanelRef">
    <div class="persona-header">
      <h3>人格面板</h3>
      <button class="persona-close" @click="showPersona = false">
        <i class="pi pi-times"></i>
      </button>
    </div>
    <MiyaPersona />
  </div>
</template>

<style>
.chat-view {
  display: flex;
  height: 100%;
  background: transparent;
  overflow: hidden;
  padding: 8px;
  box-sizing: border-box;
  position: relative;
}

.chat-view::before {
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

.left-sidebar {
  width: 64px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 0;
  background: linear-gradient(180deg, rgba(6, 78, 59, 0.6) 0%, rgba(5, 46, 41, 0.8) 100%);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-right: 1px solid rgba(45, 212, 191, 0.15);
  flex-shrink: 0;
  gap: 10px;
  box-shadow: 4px 0 24px rgba(0, 0, 0, 0.3);
}

.sidebar-divider {
  width: 36px;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(45, 212, 191, 0.4) 50%, transparent 100%);
  margin: 12px 0;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  max-width: 1600px;
  width: 100%;
  margin: 0 auto;
  z-index: 1;
  transition: opacity 0.3s ease;
  background: rgba(0, 0, 0, 0.35);
  border-radius: 12px;
  border: 1px solid rgba(45, 212, 191, 0.2);
  overflow: hidden;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.navigation-wrapper {
  z-index: 100;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 28px;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(45, 212, 191, 0.2);
  min-height: 64px;
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.opacity-control {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 20px;
}

.opacity-control i {
  color: rgba(45, 212, 191, 0.6);
  font-size: 14px;
}

.opacity-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100px;
  height: 4px;
  background: rgba(45, 212, 191, 0.2);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}

.opacity-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2dd4bf 0%, #0ea5e9 100%);
  cursor: pointer;
  box-shadow: 0 0 8px rgba(45, 212, 191, 0.5);
  transition: transform 0.2s ease;
}

.opacity-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.opacity-slider::-moz-range-thumb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2dd4bf 0%, #0ea5e9 100%);
  cursor: pointer;
  border: none;
  box-shadow: 0 0 8px rgba(45, 212, 191, 0.5);
  transition: transform 0.2s ease;
}

.opacity-slider::-moz-range-thumb:hover {
  transform: scale(1.2);
}

.header-content h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #e0f2fe;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.icon-button {
  width: 48px;
  height: 48px;
  min-height: 48px;
  border-radius: 12px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  padding: 8px 4px;
  gap: 4px;
}

.icon-button i {
  font-size: 20px;
  line-height: 1;
}

.icon-button .btn-label {
  font-size: 10px;
  line-height: 1;
  opacity: 0.85;
  font-weight: 500;
  letter-spacing: 0.2px;
}

.icon-button:hover .btn-label {
  opacity: 1;
}

.icon-button:hover {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.2) 0%, rgba(13, 148, 136, 0.2) 100%);
  color: #e0f2fe;
  transform: scale(1.06);
  border-color: rgba(45, 212, 191, 0.5);
  box-shadow: 0 6px 20px rgba(45, 212, 191, 0.25);
}

.icon-button:active {
  transform: scale(0.96);
}

.sidebar-toggle {
  flex-shrink: 0;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.message-count {
  font-size: 12px;
  color: #5eead4;
  font-weight: 500;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.persona-panel {
  position: fixed;
  right: 0;
  top: 64px;
  bottom: 0;
  width: 420px;
  background: linear-gradient(180deg, rgba(6, 78, 59, 0.95) 0%, rgba(5, 46, 41, 0.98) 100%);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-left: 1px solid rgba(45, 212, 191, 0.25);
  overflow-y: auto;
  z-index: 200;
  box-shadow: -12px 0 48px rgba(0, 0, 0, 0.5);
  transform: translateX(100%);
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.persona-panel.show {
  transform: translateX(0);
}

.persona-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  border-bottom: 1px solid rgba(45, 212, 191, 0.25);
  background: rgba(0, 0, 0, 0.3);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.25);
}

.persona-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #e0f2fe;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.persona-close {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: transparent;
  border: none;
  color: #5eead4;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  font-size: 20px;
}

.persona-close:hover {
  background: rgba(45, 212, 191, 0.2);
  color: #e0f2fe;
  transform: rotate(90deg);
  box-shadow: 0 6px 20px rgba(45, 212, 191, 0.3);
}

.chat-content-wrapper {
  display: flex;
  flex: 1;
  min-height: 0;
  padding: 16px 20px;
  padding-right: 280px;
  overflow: hidden;
}

.chat-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  max-width: 100%;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
  padding-right: 12px;
}



/* Live2D 浮动面板 - 右侧固定位置 */
.live2d-float-panel {
  position: fixed;
  right: 24px;
  top: 50%;
  transform: translateY(-50%);
  width: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  z-index: 100;
}

.live2d-float-panel.collapsed {
  top: auto;
  bottom: 100px;
  transform: none;
}

.live2d-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  background: rgba(45, 212, 191, 0.2);
  border: 1px solid rgba(45, 212, 191, 0.4);
  border-radius: 20px;
  color: #2dd4bf;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
  backdrop-filter: blur(8px);
}

.live2d-toggle-btn:hover {
  background: rgba(45, 212, 191, 0.3);
  border-color: rgba(45, 212, 191, 0.6);
  transform: scale(1.05);
}

.live2d-toggle-btn.active {
  background: rgba(45, 212, 191, 0.4);
  box-shadow: 0 0 20px rgba(45, 212, 191, 0.3);
}

.live2d-panel-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 20px;
  backdrop-filter: blur(16px);
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.live2d-mini-info {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

.model-tag,
.emotion-tag {
  padding: 4px 12px;
  background: rgba(45, 212, 191, 0.15);
  border: 1px solid rgba(45, 212, 191, 0.3);
  border-radius: 12px;
  font-size: 11px;
  color: #2dd4bf;
}

.emotion-tag {
  background: rgba(244, 114, 182, 0.15);
  border-color: rgba(244, 114, 182, 0.3);
  color: #f472b6;
}

.live2d-quick-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(45, 212, 191, 0.1);
  border: 1px solid rgba(45, 212, 191, 0.3);
  border-radius: 50%;
  color: #2dd4bf;
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-btn:hover {
  background: rgba(45, 212, 191, 0.25);
  border-color: rgba(45, 212, 191, 0.5);
  transform: scale(1.1);
}

.action-btn.active {
  background: rgba(167, 139, 250, 0.25);
  border-color: rgba(167, 139, 250, 0.5);
  color: #c4b5fd;
  box-shadow: 0 0 12px rgba(167, 139, 250, 0.3);
}

.action-btn i {
  font-size: 16px;
}

/* 信息卡片通用样式 */
.live2d-info-card,
.system-info-card,
.quick-actions-card {
  width: 100%;
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

.model-name {
  font-size: 15px;
  font-weight: 600;
  color: #e0f2fe;
}

.model-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #22c55e;
}

.status-dot {
  width: 8px;
  height: 8px;
  background: #22c55e;
  border-radius: 50%;
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.9); }
}

.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(45, 212, 191, 0.08);
  border-radius: 8px;
}

.status-label {
  font-size: 12px;
  color: #94a3b8;
}

.status-value {
  font-size: 13px;
  font-weight: 600;
  color: #e0f2fe;
}

.status-value.emotion-value {
  color: #f472b6;
}

.status-value.connected {
  color: #22c55e;
}

/* 快捷操作卡片 */
.quick-actions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.quick-action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 8px;
  background: rgba(45, 212, 191, 0.1);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 8px;
  color: #e0f2fe;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.quick-action-btn:hover {
  background: rgba(45, 212, 191, 0.2);
  border-color: rgba(45, 212, 191, 0.4);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(45, 212, 191, 0.2);
}

.quick-action-btn:active {
  transform: translateY(0);
}

.quick-action-btn.active {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.25) 0%, rgba(13, 148, 136, 0.2) 100%);
  border-color: #2dd4bf;
  box-shadow: 0 0 16px rgba(45, 212, 191, 0.3);
}

.quick-action-btn i {
  font-size: 18px;
  opacity: 0.9;
}

/* 亮色主题适配 */
:deep(.light-mode .live2d-float-panel) {
  background: rgba(13, 148, 136, 0.05);
}

:deep(.light-mode .live2d-panel-content) {
  background: rgba(255, 255, 255, 0.6);
  border-color: rgba(13, 148, 136, 0.2);
}

:deep(.light-mode .live2d-info-card),
:deep(.light-mode .system-info-card),
:deep(.light-mode .quick-actions-card) {
  background: rgba(255, 255, 255, 0.6);
  border-color: rgba(13, 148, 136, 0.2);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

:deep(.light-mode .info-card-header) {
  color: #0d9488;
}

:deep(.light-mode .model-name) {
  color: #0f766e;
}

:deep(.light-mode .status-value) {
  color: #0f766e;
}

:deep(.light-mode .status-row) {
  background: rgba(13, 148, 136, 0.08);
}

:deep(.light-mode .quick-action-btn) {
  background: rgba(13, 148, 136, 0.1);
  border-color: rgba(13, 148, 136, 0.2);
  color: #0f766e;
}

:deep(.light-mode .quick-action-btn:hover) {
  background: rgba(13, 148, 136, 0.15);
  border-color: rgba(13, 148, 136, 0.3);
}

.message-row {
  display: flex;
  gap: 14px;
  max-width: 85%;
  animation: message-in 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.message-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

@keyframes message-in {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-content-wrapper {
  flex: 1;
  min-width: 0;
}

.typing-indicator {
  display: flex;
  gap: 6px;
  padding: 14px 18px;
  background: linear-gradient(135deg, rgba(6, 78, 59, 0.7) 0%, rgba(5, 46, 41, 0.8) 100%);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 14px;
  border-bottom-left-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2dd4bf 0%, #0ea5e9 100%);
  animation: typing 1.5s ease-in-out infinite;
  box-shadow: 0 0 12px rgba(45, 212, 191, 0.4);
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    opacity: 0.4;
    transform: scale(0.7);
  }
  30% {
    opacity: 1;
    transform: scale(1.1);
  }
}

.chat-input-area {
  padding: 0;
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-top: 1px solid rgba(45, 212, 191, 0.2);
}

/* 过渡动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(-100%);
}

/* 移除过渡样式,因为SessionSidebar现在是独立的 */

.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.3s ease;
}

.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
}

/* 滚动条样式 */
.chat-messages::-webkit-scrollbar {
  width: 10px;
}

.chat-messages::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.25);
  border-radius: 6px;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.5) 0%, rgba(13, 148, 136, 0.5) 100%);
  border-radius: 6px;
  transition: all 0.3s ease;
  border: 1px solid rgba(45, 212, 191, 0.2);
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.7) 0%, rgba(13, 148, 136, 0.7) 100%);
  box-shadow: 0 0 16px rgba(45, 212, 191, 0.4);
}

/* 控制面板滚动条 */
.live2d-control-panel-wrapper::-webkit-scrollbar {
  width: 8px;
}

.live2d-control-panel-wrapper::-webkit-scrollbar-track {
  background: transparent;
}

.live2d-control-panel-wrapper::-webkit-scrollbar-thumb {
  background: rgba(45, 212, 191, 0.35);
  border-radius: 4px;
  transition: all 0.3s ease;
}

.live2d-control-panel-wrapper::-webkit-scrollbar-thumb:hover {
  background: rgba(45, 212, 191, 0.55);
}

/* Live2D 控制面板按钮 */
.live2d-toggle {
  color: #94a3b8;
}

.live2d-toggle:hover {
  color: #2dd4bf;
  background: rgba(45, 212, 191, 0.2);
}

.live2d-toggle.active {
  color: #2dd4bf;
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.3) 0%, rgba(13, 148, 136, 0.2) 100%);
  border-color: rgba(45, 212, 191, 0.5);
  box-shadow: 0 0 24px rgba(45, 212, 191, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.desktop-pet-toggle {
  color: #a78bfa;
  border-color: rgba(167, 139, 250, 0.3);
}

.desktop-pet-toggle:hover {
  color: #c4b5fd;
  background: rgba(167, 139, 250, 0.2);
  border-color: rgba(167, 139, 250, 0.5);
}

.desktop-pet-toggle.active {
  color: #c4b5fd;
  background: linear-gradient(135deg, rgba(167, 139, 250, 0.35) 0%, rgba(139, 92, 246, 0.2) 100%);
  border-color: rgba(167, 139, 250, 0.65);
  box-shadow: 0 0 28px rgba(167, 139, 250, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.desktop-pet-toggle.active .btn-label {
  font-weight: 600;
}

/* Live2D 控制面板 */
.live2d-control-panel-wrapper {
  position: fixed;
  right: 0;
  top: 64px;
  bottom: 0;
  width: 400px;
  background: linear-gradient(180deg, rgba(6, 78, 59, 0.98) 0%, rgba(5, 46, 41, 0.99) 100%);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-left: 1px solid rgba(45, 212, 191, 0.25);
  overflow-y: auto;
  z-index: 1000;
  transform: translateX(100%);
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  box-shadow: -12px 0 48px rgba(0, 0, 0, 0.5);
}

.live2d-control-panel-wrapper.show {
  transform: translateX(0);
}

.live2d-control-panel-wrapper:not(.show) {
  display: none;
}

.live2d-control-panel-wrapper .panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  border-bottom: 1px solid rgba(45, 212, 191, 0.25);
  background: rgba(0, 0, 0, 0.35);
  position: sticky;
  top: 0;
  z-index: 10;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.3);
}

.live2d-control-panel-wrapper .panel-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #2dd4bf;
  letter-spacing: 0.6px;
  text-transform: uppercase;
}

.live2d-control-panel-wrapper .panel-close {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 20px;
  cursor: pointer;
  padding: 8px;
  border-radius: 10px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.live2d-control-panel-wrapper .panel-close:hover {
  color: #f87171;
  background: rgba(248, 113, 113, 0.18);
  transform: rotate(90deg);
  box-shadow: 0 6px 20px rgba(248, 113, 113, 0.25);
}

/* Live2D 状态 */
.live2d-status {
  padding: 24px;
  border-bottom: 1px solid rgba(45, 212, 191, 0.2);
  background: linear-gradient(135deg, rgba(6, 78, 59, 0.7) 0%, rgba(45, 212, 191, 0.08) 100%);
}

.live2d-status .status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}

.live2d-status .status-title {
  font-size: 15px;
  font-weight: 700;
  color: #2dd4bf;
  letter-spacing: 0.4px;
}

.live2d-status .status-indicator {
  font-size: 11px;
  color: #2dd4bf;
  display: flex;
  align-items: center;
  gap: 8px;
}

.live2d-status .status-indicator::before {
  content: '●';
  animation: pulse 2.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.live2d-status .status-details {
  background: rgba(45, 212, 191, 0.1);
  padding: 18px;
  border-radius: 14px;
  border: 1px solid rgba(45, 212, 191, 0.2);
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

.live2d-status .status-details p {
  margin: 0;
  font-size: 14px;
  color: #e2e8f0;
  line-height: 1.9;
}

/* 表情选择器 */
.expression-selector {
  padding: 24px;
}

.expression-selector h4 {
  margin: 0 0 18px 0;
  font-size: 14px;
  font-weight: 700;
  color: #e0f2fe;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}

.expression-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.expression-btn {
  padding: 16px 18px;
  font-size: 13px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  color: #e0f2fe;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  text-align: center;
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.expression-btn:hover {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.22) 0%, rgba(13, 148, 136, 0.18) 100%);
  border-color: rgba(45, 212, 191, 0.5);
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(45, 212, 191, 0.25);
}

.expression-btn:active {
  transform: translateY(0);
}

.expression-btn.active {
  background: linear-gradient(135deg, rgba(45, 212, 191, 0.3) 0%, rgba(13, 148, 136, 0.25) 100%);
  border-color: #2dd4bf;
  color: #2dd4bf;
  font-weight: 600;
  box-shadow: 0 0 24px rgba(45, 212, 191, 0.4);
}

/* 模型选择器 */
.model-selector {
  width: 100%;
}

.model-select {
  width: 100%;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #e0f2fe;
  padding: 16px 18px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.model-select:hover {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(45, 212, 191, 0.45);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
}

.model-select:focus {
  border-color: #2dd4bf;
  box-shadow: 0 0 0 4px rgba(45, 212, 191, 0.15), 0 6px 20px rgba(0, 0, 0, 0.2);
}

.model-select option {
  background: rgba(6, 78, 59, 0.98);
  color: #e0f2fe;
  padding: 14px 18px;
  font-size: 14px;
}

/* 人格按钮 */
.persona-toggle {
  color: #94a3b8;
}

.persona-toggle:hover {
  color: #f472b6;
  background: rgba(244, 114, 182, 0.18);
  border-color: rgba(244, 114, 182, 0.4);
}

.persona-toggle.active {
  color: #f472b6;
  background: linear-gradient(135deg, rgba(244, 114, 182, 0.3) 0%, rgba(219, 39, 119, 0.2) 100%);
  border-color: rgba(244, 114, 182, 0.6);
  box-shadow: 0 0 24px rgba(244, 114, 182, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

/* 响应式设计 */
@media (max-width: 1600px) {
  .chat-main {
    max-width: 1300px;
  }
}

@media (max-width: 1400px) {
  .chat-main {
    max-width: 1200px;
  }

  .chat-content {
    max-width: 100%;
  }

  .chat-content-wrapper {
    padding-right: 260px;
  }

  .live2d-float-panel {
    width: 240px;
    right: 16px;
  }
}

@media (max-width: 1200px) {
  .chat-view {
    padding: 12px;
  }

  .chat-main {
    max-width: 100%;
  }

  .chat-content-wrapper {
    flex-direction: column;
    padding: 20px;
    padding-right: 20px;
    gap: 20px;
  }

  .chat-content {
    max-width: 100%;
  }

  .live2d-float-panel {
    position: relative;
    right: auto;
    top: auto;
    transform: none;
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
    justify-content: center;
    padding: 12px;
    background: rgba(45, 212, 191, 0.05);
    border-radius: 12px;
  }

  .live2d-toggle-btn {
    display: none;
  }

  .live2d-panel-content {
    flex-direction: row;
    width: 100%;
    justify-content: center;
    padding: 12px;
  }

  .live2d-mini-info {
    display: none;
  }
}

@media (max-width: 768px) {
  .chat-view {
    padding: 8px;
  }

  .chat-content-wrapper {
    padding: 16px;
    padding-right: 16px;
    gap: 16px;
  }
  
  .chat-header {
    padding: 12px 16px;
  }
  
  .opacity-control {
    display: none;
  }
}

/* 移除动画效果，保持简约 */
.live2d-float-panel {
  animation: none;
}

/* 简化滚动条 */
.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: rgba(45, 212, 191, 0.3);
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: rgba(45, 212, 191, 0.5);
}
</style>