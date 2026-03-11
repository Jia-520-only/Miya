<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '../stores/chat'
import { formatTimestamp } from '../utils'

const emit = defineEmits<{
  (e: 'create-session'): void
  (e: 'export-session', format: 'json' | 'markdown' | 'txt'): void
  (e: 'delete-session', id: string): void
  (e: 'select-session', id: string): void
  (e: 'close'): void
}>()

const chatStore = useChatStore()

const showMenu = ref<string | null>(null)
const searchQuery = ref('')
const showSidebar = ref(false)

// 过滤会话
const filteredSessions = computed(() => {
  if (!searchQuery.value) return chatStore.sessions
  return chatStore.sessions.filter(session =>
    session.title.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
    session.lastMessage?.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

function toggleMenu(sessionId: string) {
  showMenu.value = showMenu.value === sessionId ? null : sessionId
}

function selectSession(sessionId: string) {
  chatStore.switchSession(sessionId)
  emit('select-session', sessionId)
  showMenu.value = null
  showSidebar.value = false
}

function createSession() {
  chatStore.createSession()
  emit('create-session')
  showSidebar.value = false
}

function exportSession(sessionId: string, format: 'json' | 'markdown' | 'txt') {
  chatStore.switchSession(sessionId)
  const content = chatStore.exportSession(format)
  const filename = `miya_session_${sessionId}_${format}`
  downloadFile(content, `${filename}.${format}`)
  emit('export-session', format)
  showMenu.value = null
}

function deleteSession(sessionId: string) {
  chatStore.deleteSession(sessionId)
  emit('delete-session', sessionId)
  showMenu.value = null
}

function downloadFile(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

// 关闭侧边栏
function closeSidebar() {
  showSidebar.value = false
  emit('close')
}
</script>

<template>
  <div class="session-sidebar-container">
    <!-- 触发按钮 -->
    <button class="trigger-button" @click="showSidebar = !showSidebar" :class="{ active: showSidebar }" title="会话列表">
      <i class="pi pi-list"></i>
      <span v-if="chatStore.currentSession" class="current-session-badge">{{ chatStore.currentSession.title.substring(0, 8) }}...</span>
    </button>

    <!-- 侧边栏弹出层 -->
    <transition name="sidebar-slide">
      <div v-if="showSidebar" class="sidebar-overlay" @click="closeSidebar">
        <div class="session-sidebar" @click.stop>
          <div class="sidebar-header">
            <h3>会话</h3>
            <button class="close-btn" @click="closeSidebar">
              <i class="pi pi-times"></i>
            </button>
          </div>

          <div class="search-box">
            <i class="pi pi-search"></i>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索会话..."
              class="search-input"
            />
          </div>

          <div class="sessions-list">
            <div
              v-for="session in filteredSessions"
              :key="session.id"
              class="session-item"
              :class="{ active: session.id === chatStore.currentSessionId }"
              @click="selectSession(session.id)"
            >
              <div class="session-info">
                <div class="session-title">{{ session.title }}</div>
                <div class="session-meta">
                  <span class="message-count">{{ session.messageCount }} 条</span>
                  <span class="session-time">{{ formatTimestamp(session.updatedAt, 'date') }}</span>
                </div>
                <div v-if="session.lastMessage" class="session-last-message">
                  {{ session.lastMessage }}
                </div>
              </div>

              <div class="session-menu" @click.stop>
                <button class="menu-button" @click="toggleMenu(session.id)">
                  <i class="pi pi-ellipsis-v"></i>
                </button>
                <div v-if="showMenu === session.id" class="menu-dropdown">
                  <button @click="exportSession(session.id, 'json')">导出 JSON</button>
                  <button @click="exportSession(session.id, 'markdown')">导出 Markdown</button>
                  <button @click="exportSession(session.id, 'txt')">导出 TXT</button>
                  <button class="delete" @click="deleteSession(session.id)">删除</button>
                </div>
              </div>
            </div>

            <div v-if="filteredSessions.length === 0" class="empty-state">
              <i class="pi pi-comments"></i>
              <p>没有会话</p>
            </div>
          </div>

          <div class="sidebar-footer">
            <button class="new-session-btn" @click="createSession">
              <i class="pi pi-plus"></i>
              <span>新建会话</span>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.session-sidebar-container {
  position: relative;
}

.trigger-button {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(4, 47, 46, 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(45, 212, 191, 0.2);
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  padding: 4px;
}

.trigger-button:hover {
  background: rgba(45, 212, 191, 0.15);
  border-color: rgba(45, 212, 191, 0.4);
  color: #2dd4bf;
  transform: scale(1.05);
}

.trigger-button.active {
  background: linear-gradient(135deg, #2dd4bf, #0ea5e9);
  color: white;
  border-color: transparent;
}

.trigger-button i {
  font-size: 16px;
  margin-bottom: 2px;
}

.current-session-badge {
  font-size: 9px;
  color: inherit;
  opacity: 0.8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 32px;
}

.sidebar-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding: 20px;
}

.session-sidebar {
  width: 380px;
  max-height: calc(100vh - 40px);
  background: rgba(4, 47, 46, 0.95);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid rgba(45, 212, 191, 0.15);
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #f0fdfa;
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: transparent;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.search-box {
  position: relative;
  padding: 16px 20px;
}

.search-box i {
  position: absolute;
  left: 36px;
  top: 50%;
  transform: translateY(-50%);
  color: #64748b;
}

.search-input {
  width: 100%;
  padding: 12px 16px 12px 44px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(45, 212, 191, 0.15);
  border-radius: 10px;
  color: #f0fdfa;
  font-size: 14px;
  outline: none;
  transition: all 0.2s;
}

.search-input:focus {
  border-color: #2dd4bf;
  background: rgba(255, 255, 255, 0.06);
  box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.15);
}

.search-input::placeholder {
  color: #64748b;
}

.sessions-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.session-item {
  position: relative;
  padding: 16px;
  margin-bottom: 8px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  gap: 12px;
}

.session-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.session-item.active {
  background: linear-gradient(135deg, #2dd4bf, #0ea5e9);
  box-shadow: 0 4px 12px rgba(45, 212, 191, 0.3);
}

.session-item.active .session-title,
.session-item.active .session-meta,
.session-item.active .session-last-message {
  color: white;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 15px;
  font-weight: 500;
  color: #f0fdfa;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}

.session-last-message {
  font-size: 13px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-menu {
  position: relative;
}

.menu-button {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: transparent;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.menu-button:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #f0fdfa;
}

.menu-dropdown {
  position: absolute;
  right: 0;
  top: 100%;
  z-index: 100;
  background: rgba(4, 47, 46, 0.98);
  border: 1px solid rgba(45, 212, 191, 0.2);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  min-width: 140px;
  overflow: hidden;
}

.menu-dropdown button {
  width: 100%;
  padding: 10px 14px;
  background: transparent;
  border: none;
  color: #f0fdfa;
  text-align: left;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}

.menu-dropdown button:hover {
  background: rgba(255, 255, 255, 0.05);
}

.menu-dropdown button.delete {
  color: #ef4444;
}

.menu-dropdown button.delete:hover {
  background: rgba(239, 68, 68, 0.1);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #64748b;
}

.empty-state i {
  font-size: 40px;
  margin-bottom: 16px;
  opacity: 0.4;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(45, 212, 191, 0.15);
}

.new-session-btn {
  width: 100%;
  padding: 14px;
  border-radius: 10px;
  background: linear-gradient(135deg, #2dd4bf, #0ea5e9);
  border: none;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(45, 212, 191, 0.3);
}

.new-session-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(45, 212, 191, 0.4);
}

.new-session-btn:active {
  transform: translateY(0);
}

/* 过渡动画 */
.sidebar-slide-enter-active,
.sidebar-slide-leave-active {
  transition: all 0.3s ease;
}

.sidebar-slide-enter-from,
.sidebar-slide-leave-to {
  opacity: 0;
}

.sidebar-slide-enter-from .session-sidebar,
.sidebar-slide-leave-to .session-sidebar {
  transform: translateX(-30px);
}
</style>
