<script setup lang="ts">
import { computed, nextTick, ref, watch, onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import MarkdownRenderer from './MarkdownRenderer.vue'
import { copyToClipboard, formatTimestamp } from '../utils'
import { ttsApi, playAudioFromBase64, stopAudio, isPlaying } from '../api/tts'
import type { ChatMessage } from '../stores/chat'

interface Props {
  message: ChatMessage
  showActions?: boolean
  isNew?: boolean  // 是否是新消息，用于自动播放
}

const props = withDefaults(defineProps<Props>(), {
  showActions: true,
  isNew: false
})

const emit = defineEmits<{
  (e: 'regenerate', message: ChatMessage): void
  (e: 'copy', content: string): void
  (e: 'delete', message: ChatMessage): void
  (e: 'played'): void  // 播放完成事件
}>()

const settings = useSettingsStore()
const showActionsMenu = ref(false)
const copied = ref(false)
const isSpeaking = ref(false)

const isUser = computed(() => props.message.role === 'user')
const isAssistant = computed(() => props.message.role === 'assistant')

// 检测是否为系统日志/代码类型内容（不需要TTS播放）
function isSystemLogContent(content: string): boolean {
  if (!content) return false
  
  // 检查是否包含代码块（多个```）
  const codeBlockCount = (content.match(/```/g) || []).length
  if (codeBlockCount >= 2) return true
  
  // 检查是否包含堆栈跟踪特征
  if (/Traceback \(most recent call last\)|Error:|Exception:|at\s+\w+\(|Stack trace:/.test(content)) {
    return true
  }
  
  // 检查是否包含日志级别标识
  if (/^\[INFO\]|\[DEBUG\]|\[ERROR\]|\[WARN\]|\[WARNING\]|\[FATAL\]/m.test(content)) {
    return true
  }
  
  // 检查是否主要是JSON输出
  if (/^\s*\{[\s\S]*\}\s*$/.test(content) && content.includes('"')) {
    const tryParse = content.trim()
    try {
      JSON.parse(tryParse)
      return true // JSON输出不需要朗读
    } catch {}
  }
  
  // 检查是否包含文件路径模式
  const pathPattern = /(\/[\w\-./]+\.[\w]+|\w:\\[\w\-\\.]+|~\/[\w\-./]+)/
  if (pathPattern.test(content) && content.length > 200) {
    return true
  }
  
  // 检查是否包含命令输出特征
  if (/^\$|^\s*>\s+/m.test(content) && content.includes('\n')) {
    return true
  }
  
  return false
}

// 自动播放功能
watch(() => props.isNew, (newVal) => {
  if (newVal && isAssistant.value && settings.settings.ttsEnabled && settings.settings.ttsAutoPlay) {
    // 检查是否是系统日志/代码类型内容，如果是则跳过TTS
    if (isSystemLogContent(props.message.content)) {
      console.log('跳过系统日志内容的TTS播放')
      return
    }
    // 延迟一下确保消息已渲染
    setTimeout(() => {
      handleSpeak(true)
    }, 500)
  }
}, { immediate: true })

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

async function handleSpeak(isAutoPlay: boolean = false) {
  if (isSpeaking.value) {
    stopAudio()
    isSpeaking.value = false
    return
  }

  // 检查 TTS 设置
  if (!settings.settings.ttsEnabled) {
    console.log('TTS未启用')
    return
  }

  // 检查是否是系统日志内容（手动点击也检查）
  if (isSystemLogContent(props.message.content)) {
    console.log('系统日志/代码内容不适宜TTS播放')
    return
  }

  isSpeaking.value = true
  try {
    const result = await ttsApi.speak({
      text: props.message.content,
      engine: 'gpt_sovits'
    })

    if (result.success && result.audio_data) {
      playAudioFromBase64(result.audio_data, result.format)

      // 监听播放结束
      const audio = new Audio()
      audio.src = `data:audio/${result.format || 'mpeg'};base64,${result.audio_data}`
      audio.onended = () => {
        isSpeaking.value = false
        if (isAutoPlay) {
          emit('played')
        }
      }
      audio.onerror = () => {
        isSpeaking.value = false
        if (isAutoPlay) {
          emit('played')
        }
      }
    } else {
      console.error('TTS生成失败:', result.error)
      isSpeaking.value = false
      if (isAutoPlay) {
        emit('played')
      }
    }
  } catch (error) {
    console.error('TTS错误:', error)
    isSpeaking.value = false
    if (isAutoPlay) {
      emit('played')
    }
  }
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
          v-if="isAssistant"
          class="action-button speak"
          :class="{ speaking: isSpeaking }"
          @click="handleSpeak"
          :title="isSpeaking ? '停止播放' : '语音朗读'"
        >
          <i :class="isSpeaking ? 'pi pi-stop-circle' : 'pi pi-volume-up'"></i>
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

.action-button.speak:hover {
  background: rgba(168, 85, 247, 0.15);
  border-color: rgba(168, 85, 247, 0.3);
  color: #a855f7;
}

.action-button.speaking {
  background: rgba(168, 85, 247, 0.2);
  border-color: rgba(168, 85, 247, 0.4);
  color: #a855f7;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
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
  background: rgba(240, 253, 250, 0.9);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-color: rgba(45, 212, 191, 0.3);
  color: #0f172a;
}

:deep(.light-mode .message-bubble.user .bubble-content) {
  background: linear-gradient(135deg, #2dd4bf, #0ea5e9);
  color: white;
  box-shadow: 0 4px 12px rgba(45, 212, 191, 0.3);
}

:deep(.light-mode .meta-item) {
  background: rgba(0, 0, 0, 0.05);
}
</style>
