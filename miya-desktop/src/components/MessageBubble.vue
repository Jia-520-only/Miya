<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useSettingsStore } from '../stores/settings'
import MarkdownRenderer from './MarkdownRenderer.vue'
import { copyToClipboard, formatTimestamp } from '../utils'
import type { ChatMessage } from '../stores/chat'

interface Props {
  message: ChatMessage
  showActions?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showActions: true
})

const emit = defineEmits<{
  (e: 'regenerate', message: ChatMessage): void
  (e: 'copy', content: string): void
  (e: 'delete', message: ChatMessage): void
}>()

const settings = useSettingsStore()
const showActionsMenu = ref(false)
const copied = ref(false)

const isUser = computed(() => props.message.role === 'user')
const isAssistant = computed(() => props.message.role === 'assistant')

async function handleCopy() {
  const success = await copyToClipboard(props.message.content)
  if (success) {
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
    emit('copy', props.message.content)
  }
}

function handleRegenerate() {
  emit('regenerate', props.message)
}

function handleDelete() {
  emit('delete', props.message)
}
</script>

<template>
  <div class="message-bubble" :class="{ user: isUser, assistant: isAssistant }">
    <div class="bubble-header" v-if="showActions">
      <div class="bubble-actions" :class="{ visible: showActionsMenu }">
        <button
          v-if="isAssistant"
          class="action-button"
          @click="handleRegenerate"
          title="重新生成"
        >
          <i class="pi pi-refresh"></i>
        </button>
        <button
          class="action-button"
          @click="handleCopy"
          title="复制"
          :class="{ copied }"
        >
          <i :class="copied ? 'pi pi-check' : 'pi pi-copy'"></i>
        </button>
        <button
          class="action-button delete"
          @click="handleDelete"
          title="删除"
        >
          <i class="pi pi-trash"></i>
        </button>
      </div>
      <div
        class="bubble-time"
        v-if="settings.settings.showTimestamp"
        @click="showActionsMenu = !showActionsMenu"
      >
        {{ formatTimestamp(message.timestamp) }}
      </div>
    </div>

    <div class="bubble-content">
      <MarkdownRenderer
        :content="message.content"
        :enable-code-highlight="settings.settings.codeHighlight"
      />
    </div>

    <div v-if="isAssistant && (message.emotion || message.personality)" class="bubble-meta">
      <span v-if="message.emotion" class="meta-item emotion">
        <i class="pi pi-heart"></i>
        {{ message.emotion.dominant }}
      </span>
      <span v-if="message.toolsUsed?.length" class="meta-item tools">
        <i class="pi pi-cog"></i>
        {{ message.toolsUsed.length }} 工具
      </span>
      <span v-if="message.memoryRetrieved" class="meta-item memory">
        <i class="pi pi-database"></i>
        已检索记忆
      </span>
    </div>
  </div>
</template>

<style scoped>
.message-bubble {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 100%;
  animation: bubble-in 0.3s ease-out;
}

@keyframes bubble-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.bubble-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  font-size: 11px;
}

.bubble-actions {
  display: flex;
  gap: 6px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message-bubble:hover .bubble-actions {
  opacity: 1;
}

.action-button {
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-button:hover {
  background: rgba(45, 212, 191, 0.15);
  border-color: rgba(45, 212, 191, 0.3);
  color: #2dd4bf;
  transform: translateY(-1px);
}

.action-button.copied {
  background: rgba(34, 197, 94, 0.15);
  border-color: rgba(34, 197, 94, 0.3);
  color: #22c55e;
}

.action-button.delete:hover {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.3);
  color: #ef4444;
}

.bubble-time {
  color: #64748b;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: all 0.2s;
}

.bubble-time:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #94a3b8;
}

.bubble-content {
  padding: 14px 18px;
  border-radius: 14px;
  font-size: var(--message-font-size, 14px);
  line-height: 1.7;
  overflow-wrap: break-word;
}

.message-bubble.assistant .bubble-content {
  background: rgba(4, 47, 46, 0.5);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(45, 212, 191, 0.15);
  color: var(--text-primary);
  border-bottom-left-radius: 6px;
}

.message-bubble.user .bubble-content {
  background: linear-gradient(135deg, #2dd4bf, #0ea5e9);
  border: none;
  color: white;
  border-bottom-right-radius: 6px;
  box-shadow: 0 4px 16px rgba(45, 212, 191, 0.25);
}

.bubble-meta {
  display: flex;
  gap: 10px;
  font-size: 11px;
  color: #64748b;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 14px;
}

.meta-item.emotion {
  color: #2dd4bf;
  background: rgba(45, 212, 191, 0.08);
}

.meta-item.tools {
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.08);
}

.meta-item.memory {
  color: #22c55e;
  background: rgba(34, 197, 94, 0.08);
}

/* 亮色主题 */
:deep(.light-mode .message-bubble.assistant .bubble-content) {
  background: rgba(240, 253, 250, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-color: rgba(45, 212, 191, 0.3);
  color: #042f2e;
}

:deep(.light-mode .message-bubble.user .bubble-content) {
  background: linear-gradient(135deg, #0d9488, #0ea5e9);
  color: white;
  box-shadow: 0 4px 12px rgba(45, 212, 191, 0.4);
}

:deep(.light-mode .meta-item) {
  background: rgba(0, 0, 0, 0.05);
}
</style>
