<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'

const emit = defineEmits<{
  (e: 'send', message: string): void
}>()

const chatStore = useChatStore()
const inputRef = ref<HTMLTextAreaElement>()
const inputValue = ref('')
const isComposing = ref(false)

const canSend = computed(() => {
  return inputValue.value.trim().length > 0 && !chatStore.isLoading
})

function handleInput() {
  // 自动调整高度
  if (inputRef.value) {
    inputRef.value.style.height = 'auto'
    inputRef.value.style.height = Math.min(inputRef.value.scrollHeight, 120) + 'px'
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    if (event.shiftKey || event.ctrlKey) {
      // Shift+Enter 或 Ctrl+Enter 换行
      event.preventDefault()
      const cursorPosition = inputRef.value?.selectionStart || 0
      const text = inputValue.value
      inputValue.value = text.slice(0, cursorPosition) + '\n' + text.slice(cursorPosition)
      nextTick(() => {
        if (inputRef.value) {
          inputRef.value.selectionStart = inputRef.value.selectionEnd = cursorPosition + 1
          inputRef.value.focus()
        }
      })
    } else if (!isComposing.value) {
      // Enter 发送
      event.preventDefault()
      send()
    }
  }
}

function handleCompositionStart() {
  isComposing.value = true
}

function handleCompositionEnd() {
  isComposing.value = false
}

function send() {
  const message = inputValue.value.trim()
  if (message && canSend.value) {
    emit('send', message)
    inputValue.value = ''
    if (inputRef.value) {
      inputRef.value.style.height = 'auto'
    }
  }
}

function focus() {
  inputRef.value?.focus()
}

// 暴露方法
defineExpose({
  focus
})
</script>

<template>
  <div class="chat-input">
    <textarea
      ref="inputRef"
      v-model="inputValue"
      @input="handleInput"
      @keydown="handleKeydown"
      @compositionstart="handleCompositionStart"
      @compositionend="handleCompositionEnd"
      placeholder="输入消息... (Enter发送, Shift+Enter换行)"
      rows="1"
      :disabled="chatStore.isLoading"
      class="input-textarea"
    />
    <button
      class="send-button"
      @click="send"
      :disabled="!canSend"
      title="发送 (Enter)"
    >
      <i class="pi pi-send"></i>
    </button>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: var(--secondary-bg);
  border-top: 1px solid var(--border);
  align-items: flex-end;
}

.input-textarea {
  flex: 1;
  min-height: 44px;
  max-height: 120px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  outline: none;
  transition: all 0.2s;
  overflow-y: auto;
}

.input-textarea:focus {
  border-color: var(--accent);
  background: rgba(255, 255, 255, 0.06);
  box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.15);
}

.input-textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-textarea::placeholder {
  color: #64748b;
}

.send-button {
  width: 44px;
  height: 44px;
  background: linear-gradient(135deg, #2dd4bf, #0ea5e9);
  border: none;
  border-radius: 10px;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(45, 212, 191, 0.3);
}

.send-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(45, 212, 191, 0.4);
}

.send-button:active:not(:disabled) {
  transform: translateY(0);
}

.send-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  box-shadow: none;
}

.send-button i {
  font-size: 16px;
}

/* 亮色主题 */
:deep(.light-mode .chat-input) {
  background: #f6f8fa;
  border-top-color: rgba(0, 0, 0, 0.1);
}

:deep(.light-mode .input-textarea) {
  background: white;
  border-color: rgba(0, 0, 0, 0.1);
  color: #1a1a2e;
}

:deep(.light-mode .input-textarea:focus) {
  background: white;
  border-color: #e94560;
  box-shadow: 0 0 0 2px rgba(233, 69, 96, 0.1);
}

:deep(.light-mode .input-textarea::placeholder) {
  color: rgba(0, 0, 0, 0.4);
}
</style>
