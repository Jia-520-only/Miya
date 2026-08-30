<script lang="ts">
import type { Message, SoulData } from '@/utils/session'
import { useEventListener, useStorage } from '@vueuse/core'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import API from '@/api/core'
import MessageItem from '@/components/MessageItem.vue'
import { CONFIG } from '@/utils/config'
import { proxySetSoulEmotion, proxySetState } from '@/utils/live2dProxy'
import { CURRENT_SESSION_ID, formatRelativeTime, getActiveTab, latestEmotion, loadCurrentSession, MESSAGES, newSession, saveMessages, switchSession } from '@/utils/session'
import { buildEmotionColorMap } from '@/utils/emotionColors'
import { isPlaying, stop as stopTTS } from '@/utils/tts'
import { setMessageViewExpanded } from '@/utils/uiState'
import { apiUrl } from '@/utils/api-url'

const isSending = ref(false)
const messageQueue: Array<{ content: string, options?: any }> = []
const ttsEnabled = ref(localStorage.getItem('ttsEnabled') !== 'false')
let lastAppliedMemoryHash = ''

function parseEmotionValue(value: unknown): Record<string, unknown> | null {
  if (typeof value !== 'string') {
    return value && typeof value === 'object' ? value as Record<string, unknown> : null
  }
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : null
  }
  catch {
    return null
  }
}

async function processQueue() {
  if (messageQueue.length === 0 || isSending.value) return
  const { content, options } = messageQueue.shift()!
  await chatStreamInternal(content, options)
}

export function chatStream(content: string, options?: { skill?: string, images?: string[], voiceInput?: boolean }) {
  stopTTS()
  MESSAGES.value.push({ role: 'user', content: options?.images?.length ? `[截图x${options.images.length}] ${content}` : content })
  saveMessages()
  messageQueue.push({ content, options })
  processQueue()
}

function normalizeIntensity(value: unknown): number {
  const parsed = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(parsed)) return 50
  return Math.min(100, Math.max(0, Math.round(parsed <= 1 ? parsed * 100 : parsed)))
}

function normalizeSoulPayload(input: any): SoulData | undefined {
  if (!input || typeof input !== 'object') return undefined
  const source = input.soul || input.soul_data || input.data?.soul || input.data?.soul_data || input
  if (!source || typeof source !== 'object') return undefined
  const result: SoulData = {}
  const emotions = source.emotions || source.current?.emotions
  if (Array.isArray(emotions)) {
    result.emotions = emotions
      .filter((emotion: any) => emotion && typeof emotion.name === 'string')
      .map((emotion: any) => ({ name: emotion.name, intensity: normalizeIntensity(emotion.intensity) }))
  } else if (emotions && typeof emotions === 'object') {
    result.emotions = Object.entries(emotions)
      .filter(([name]) => !['dominant', 'intensity'].includes(name))
      .map(([name, value]) => ({ name, intensity: normalizeIntensity(value) }))
  }
  const textValue = (...keys: string[]) => keys
    .map(key => source[key])
    .find(value => typeof value === 'string' && value.trim().length > 0) as string | undefined
  result.innerThought = textValue('innerThought', 'inner_thought')
  result.attribution = textValue('attribution')
  result.reflection = textValue('reflection')
  result.thinking = textValue('thinking')
  for (const key of ['innerThought', 'attribution', 'reflection', 'thinking'] as const) {
    if (!result[key]) delete result[key]
  }
  return result.emotions?.length || Object.keys(result).some(key => key !== 'emotions') ? result : undefined
}

function applySoulToMessage(soul: any, target?: Message) {
  const normalized = normalizeSoulPayload(soul)
  if (!normalized) return
  const msgs = MESSAGES.value
  const targetIndex = target ? msgs.indexOf(target) : -1
  let index = targetIndex
  if (index < 0) {
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i]!.role === 'assistant') {
        index = i
        break
      }
    }
  }
  if (index < 0) return

  const existing = (msgs[index]! as any).soulData || {}
  if (normalized.emotions?.length) existing.emotions = normalized.emotions
  if (!existing.innerThought && normalized.innerThought) existing.innerThought = normalized.innerThought
  if (!existing.attribution && normalized.attribution) existing.attribution = normalized.attribution
  if (!existing.reflection && normalized.reflection) existing.reflection = normalized.reflection
  if (!existing.thinking && normalized.thinking) existing.thinking = normalized.thinking
  ;(msgs[index]! as any).soulData = existing
  if (existing.emotions?.length) {
    latestEmotion.value = { ...latestEmotion.value, emotions: existing.emotions }
    proxySetSoulEmotion(existing.emotions)
  }
}

async function fetchSoulData(retryCount = 0, target?: Message) {
  try {
    const soulRes = await fetch(apiUrl('/api/soul/current'))
    const directSoul = await soulRes.json()
    applySoulToMessage(directSoul, target)
    const res = await fetch(apiUrl('/api/desktop/files/read?path=data%2Fmemory%2Fcognitive_memories.json'))
    const data = await res.json()
    if (data?.lines) {
      const items = JSON.parse(data.lines.join(''))
      if (!Array.isArray(items) || items.length === 0) {
        if (retryCount < 2) { setTimeout(() => fetchSoulData(retryCount + 1, target), 1500) }
        return
      }
      const memoryHash = JSON.stringify(items[items.length - 1])
      if (memoryHash === lastAppliedMemoryHash) {
        if (retryCount < 2) { setTimeout(() => fetchSoulData(retryCount + 1, target), 1500) }
        return
      }
      lastAppliedMemoryHash = memoryHash
      const merged: any = {}
      for (let i = items.length - 1; i >= Math.max(0, items.length - 5); i--) {
        const entry = items[i]
        if (!entry || String(entry.user_id) !== '1523878699') continue
        let emo = entry.emotions
        emo = parseEmotionValue(emo)
        if (!merged.emotions && emo && typeof emo === 'object') {
          merged.emotions = Object.entries(emo).map(([name, val]) => ({ name, intensity: normalizeIntensity(val) }))
        }
        if (!merged.innerThought && entry.inner_thought) merged.innerThought = entry.inner_thought
        if (!merged.attribution && entry.attribution) merged.attribution = entry.attribution
        if (!merged.reflection && entry.reflection) merged.reflection = entry.reflection
        if (!merged.thinking && entry.thinking) merged.thinking = entry.thinking
      }
      if (merged.emotions) merged.emotions = merged.emotions.slice(0, 6)
      if (!merged.emotions?.length && !merged.innerThought && !merged.attribution && !merged.reflection && !merged.thinking && retryCount < 2) {
        setTimeout(() => fetchSoulData(retryCount + 1, target), 1500)
        return
      }
      applySoulToMessage(merged, target)
    } else if (retryCount < 2) {
      setTimeout(() => fetchSoulData(retryCount + 1, target), 1500)
    }
  } catch {}
}

async function chatStreamInternal(content: string, options?: { skill?: string, images?: string[], voiceInput?: boolean }) {
  isSending.value = true
  MESSAGES.value.push({ role: 'assistant', content: '', reasoning: '', generating: true, status: options?.voiceInput ? '理解话语中' : undefined })
  const message = MESSAGES.value[MESSAGES.value.length - 1]!

  proxySetState('thinking')
  let contentBuf = ''
  const pushContent = (text: string) => {
    contentBuf += text
    message.content = contentBuf
    try { localStorage.setItem('miya-messages', JSON.stringify(MESSAGES.value.slice(-200))) } catch {}
  }

  return API.chatSend({
    message: content,
    session_id: CURRENT_SESSION_ID.value ?? 'default',
    platform: 'desktop',
    user_id: CONFIG.value.ui?.owner_id || '1523878699',
    usg_id: CONFIG.value.ui?.desktop_usg_id || 'desktop_user',
    image_data: (options?.images?.length ?? 0) > 0 ? options!.images![0] : undefined,
  } as any).then((res: any) => {
    let responseText = ''
    const soulRaw: any = {}
    if (typeof res === 'string' && res.startsWith('data:')) {
      const lines = res.split('\n')
      for (const line of lines) {
        const dataPrefix = 'data: '
        if (!line.startsWith(dataPrefix)) continue
        const jsonStr = line.slice(dataPrefix.length).trim()
        if (!jsonStr || jsonStr === '[DONE]') continue
        try {
          const chunk = JSON.parse(jsonStr)
          if (chunk.type === 'plain' && chunk.data) responseText = chunk.data
          else if (chunk.type === 'reasoning') message.reasoning = (message.reasoning || '') + (chunk.data || chunk.text || '')
          else if (chunk.type === 'soul' && chunk.data) Object.assign(soulRaw, chunk.data)
          else if (chunk.type === 'done' && chunk.data?.response && !responseText) responseText = chunk.data.response
        } catch {}
      }
    } else {
      responseText = res?.response || res?.data?.response || JSON.stringify(res)
      const responseSoul = res?.soul || res?.soul_data || res?.data?.soul || res?.data?.soul_data
      if (responseSoul && typeof responseSoul === 'object') Object.assign(soulRaw, responseSoul)
    }

    pushContent(responseText || res?.response || JSON.stringify(res))
    message.generating = false
    message.status = undefined
    proxySetState('idle')

    if (Object.keys(soulRaw).length > 0) {
      applySoulToMessage(soulRaw, message)
      saveMessages()
    }
    // The cognitive record can be written just after the response is returned.
    // Always refresh, even when chat/send did not include an inline soul payload.
    fetchSoulData(0, message)

    // @ts-expect-error msgListRef declared in <script setup>, merged at runtime
    nextTick(() => { const el = msgListRef.value; if (el) el.scrollTop = el.scrollHeight })
    isSending.value = false
    saveMessages()
    processQueue()
  }).catch((err: any) => {
    message.content = `[连接失败: ${err?.message || '后端未响应'}]`
    message.generating = false
    isSending.value = false
    saveMessages()
    processQueue()
  })
}
</script>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
const input = defineModel<string>()
const composerRef = ref<HTMLTextAreaElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const inputDockRef = ref<HTMLElement | null>(null)
const isExpanded = ref(false)
const expandedStyle = ref<Record<string, string>>({})
const expandedInputStyle = ref<Record<string, string>>({})
const expandedAnchorLeft = ref(8)
const msgListRef = ref<HTMLDivElement | null>(null)
const showMoreActions = ref(false)

function isImeComposing(event: KeyboardEvent) {
  return event.isComposing || (event as any).keyCode === 229
}

function resizeComposer() {
  if (!composerRef.value) return
  composerRef.value.style.height = '0px'
  const nextHeight = Math.min(Math.max(composerRef.value.scrollHeight, 44), 160)
  composerRef.value.style.height = `${nextHeight}px`
}

function handleComposerEnter(event: KeyboardEvent) {
  if (isImeComposing(event) || event.shiftKey) return
  event.preventDefault()
  sendMessage()
}

function toggleTTS() {
  ttsEnabled.value = !ttsEnabled.value
  localStorage.setItem('ttsEnabled', String(ttsEnabled.value))
  if (!ttsEnabled.value) stopTTS()
}

watch(isPlaying, (playing) => { proxySetState(playing ? 'talking' : 'idle') })
watch(input, () => { nextTick(() => { resizeComposer() }) })
watch(isExpanded, (value) => { setMessageViewExpanded(value) })

function scrollToBottom() {
  const el = msgListRef.value
  if (el) el.scrollTop = el.scrollHeight
}

const activeMessages = computed(() => getActiveTab().messages)

function sendMessage() {
  if (!input.value?.trim()) return
  chatStream(input.value)
  nextTick().then(scrollToBottom)
  input.value = ''
}

function pushSystemMessage(content: string): Message {
  const message: Message = { role: 'system', content }
  MESSAGES.value.push(message)
  nextTick().then(scrollToBottom)
  return message
}

function dispatchToActiveTab(content: string, options?: { skill?: string, images?: string[], voiceInput?: boolean }) {
  chatStream(content, options)
  nextTick().then(scrollToBottom)
}

onMounted(async () => {
  await loadCurrentSession()
  // 历史会话打开时也要回填灵魂状态，不能只在发送新消息后请求。
  fetchSoulData()
  scrollToBottom()
  nextTick(resizeComposer)
})

onBeforeUnmount(() => { setMessageViewExpanded(false) })

useEventListener('token', scrollToBottom)

// ── Session history ──
const showHistory = ref(false)
const sessions = ref<Array<{ sessionId: string, createdAt: string, lastActiveAt: string, conversationRounds: number, temporary: boolean }>>([])
const loadingSessions = ref(false)

async function fetchSessions() {
  loadingSessions.value = true
  try { const res = await API.getSessions(); sessions.value = res.sessions ?? [] }
  catch { sessions.value = [] }
  loadingSessions.value = false
}

function toggleHistory() {
  showHistory.value = !showHistory.value
  if (showHistory.value) fetchSessions()
}

async function handleSwitchSession(id: string) {
  await switchSession(id)
  showHistory.value = false
  nextTick().then(scrollToBottom)
}

async function handleDeleteSession(id: string) {
  try {
    await API.deleteSession(id)
    sessions.value = sessions.value.filter(s => s.sessionId !== id)
    if (CURRENT_SESSION_ID.value === id) newSession()
  } catch {}
}

function handleNewSession() {
  newSession()
  showHistory.value = false
}

function triggerUpload() { fileInput.value?.click() }

async function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  const ext = file.name.split('.').pop()?.toLowerCase()
  const parseable = ['docx', 'xlsx', 'txt', 'csv', 'md']
  if (ext && parseable.includes(ext)) {
    const msg = pushSystemMessage(`正在解析文件: ${file.name}...`)
    try {
      const result = await API.parseDocument(file)
      msg.content = `文件解析完成: ${file.name}${result.truncated ? '（内容过长，已截断）' : ''}`
      dispatchToActiveTab(`以下是文件「${file.name}」的内容：\n\n${result.content}\n\n请分析这个文件的内容。`)
    } catch (err: any) { msg.content = `文件解析失败: ${err?.response?.data?.detail || err.message}` }
  } else {
    const msg = pushSystemMessage(`正在上传文件: ${file.name}...`)
    try {
      const result = await API.uploadDocument(file)
      msg.content = `文件上传成功: ${file.name}`
      if (result.filePath) dispatchToActiveTab(`请分析我刚上传的文件「${file.name}」，文件完整路径: ${result.filePath}`)
    } catch (err: any) { msg.content = `文件上传失败: ${err.message}` }
  }
  target.value = ''
}

// ── Voice ──
const isRecording = ref(false)
let mediaRecorder: MediaRecorder | null = null
let audioChunks: Blob[] = []

async function toggleVoiceInput() {
  if (!CONFIG.value.voice_realtime.enabled) return
  if (isRecording.value) { stopVoiceInput(); return }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioChunks = []
    mediaRecorder = new MediaRecorder(stream, { mimeType: getSupportedMimeType() })
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data) }
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop())
      if (audioChunks.length === 0) return
      const audioBlob = new Blob(audioChunks, { type: mediaRecorder?.mimeType || 'audio/webm' })
      try {
        const { text } = await API.transcribeAudio(audioBlob, { language: 'zh' })
        if (text && typeof text === 'string' && text.trim()) dispatchToActiveTab(`以下是用户的语音输入：【${text.trim()}】`, { voiceInput: true })
      } catch (err: any) {
        const status = err?.response?.status
        if (status === 401) pushSystemMessage('语音识别需要登录后使用')
        else if (status === 402) pushSystemMessage('余额不足，无法使用语音识别')
        else pushSystemMessage(`语音识别失败: ${err.message || err}`)
      }
    }
    mediaRecorder.start()
    isRecording.value = true
  } catch (err: any) {
    if (err.name === 'NotAllowedError') pushSystemMessage('麦克风权限被拒绝，请在系统设置中允许麦克风访问')
    else pushSystemMessage(`无法启动录音: ${err.message || err}`)
  }
}

function stopVoiceInput() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop()
  mediaRecorder = null; isRecording.value = false
}

function getSupportedMimeType(): string {
  const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
  for (const t of types) { if (MediaRecorder.isTypeSupported(t)) return t }
  return ''
}

// ── 对话工作区视角：左右两栏始终同步 ──
const tiltEnabled = useStorage('miya-chat-perspective', false)

// ── 灵魂状态卡片数据 ──
const showSoulThinking = ref(false)

const latestSoulData = computed(() => {
  const msgs = MESSAGES.value
  for (let i = msgs.length - 1; i >= 0; i--) {
    const msg = msgs[i]
    if (msg?.role === 'assistant' && (msg as any).soulData) {
      return (msg as any).soulData
    }
  }
  return null
})

function getEmotionColorMap() { return buildEmotionColorMap() }
</script>

<template>
  <div class="pgr-chat" :class="{ perspective: tiltEnabled }">
    <!-- ═══ 左面板 30% ═══ -->
    <div class="pgr-left">
      <!-- Profile -->
      <div class="left-profile">
        <div class="left-avatar">
          <div class="avatar-hex">
            <span class="avatar-text">弥</span>
          </div>
          <div class="avatar-scan" />
        </div>
        <div class="left-name-group">
          <span class="left-name">弥娅</span>
          <span class="left-id">ID: MIYA-CORE</span>
        </div>
        <div class="left-lv">
          <span class="lv-label">等级/</span>
          <span class="lv-value">∞</span>
          <div class="lv-bar" />
        </div>
      </div>

      <!-- Nav blocks -->
      <div class="left-nav">
        <button class="nav-block active" title="弥娅对话">
          <span class="nav-block-title">对话</span>
          <span class="nav-block-tip">灵魂共鸣</span>
        </button>
        <button class="nav-block" title="记忆星河" @click="router.push('/mind')">
          <span class="nav-block-title">记忆</span>
          <span class="nav-block-tip">认知图谱</span>
        </button>
        <button class="nav-block" title="弥娅画板" @click="router.push('/artboard')">
          <span class="nav-block-title">画板</span>
          <span class="nav-block-tip">创作工具</span>
        </button>
        <button class="nav-block" title="终端引擎" @click="router.push('/terminal')">
          <span class="nav-block-title">终端</span>
          <span class="nav-block-tip">DSH 执行</span>
        </button>
      </div>

      <!-- Banner -->
      <div class="left-banner" @click="handleNewSession">
        <div class="banner-inner">
          <div class="banner-shine" />
          <span class="banner-text">◆ 新对话</span>
          <span class="banner-tip">开启一段新的灵魂交流</span>
        </div>
      </div>

      <!-- ♥ 灵魂共鸣卡片 -->
      <div v-if="latestSoulData?.emotions?.length || latestSoulData?.innerThought || latestSoulData?.attribution || latestSoulData?.reflection || latestSoulData?.thinking" class="left-soul">
        <div class="soul-header">
          <span class="soul-header-dot" />
          <span class="soul-header-text">灵魂共鸣</span>
          <span class="soul-header-subtitle">SOUL RESONANCE</span>
        </div>

        <!-- 情绪条 -->
        <div v-if="latestSoulData.emotions?.length" class="soul-emotions">
          <div v-for="e in latestSoulData.emotions.slice(0, 5)" :key="e.name" class="soul-em-row">
            <span class="soul-em-name">{{ e.name }}</span>
            <div class="soul-em-bar">
              <div
                class="soul-em-fill"
                :style="{
                  width: `${Math.min(e.intensity, 100)}%`,
                  background: getEmotionColorMap()[e.name] || '#00ADB5',
                }"
              />
            </div>
            <span class="soul-em-val">{{ e.intensity }}%</span>
          </div>
        </div>

        <!-- 内心独白 -->
        <div v-if="latestSoulData.innerThought" class="soul-thought">
          <span class="soul-quote">"</span>
          {{ latestSoulData.innerThought }}
          <span class="soul-quote">"</span>
        </div>

        <!-- 归因 + 反思 -->
        <div v-if="latestSoulData.attribution || latestSoulData.reflection" class="soul-meta">
          <div v-if="latestSoulData.attribution" class="soul-line">
            <span class="soul-line-icon">→</span>
            <span>{{ latestSoulData.attribution }}</span>
          </div>
          <div v-if="latestSoulData.reflection" class="soul-line">
            <span class="soul-line-icon">↻</span>
            <span>{{ latestSoulData.reflection }}</span>
          </div>
        </div>

        <!-- 思考过程 -->
        <div v-if="latestSoulData.thinking" class="soul-thinking">
          <div class="thinking-toggle" @click="showSoulThinking = !showSoulThinking">
            <span class="thinking-icon">◇</span>
            <span>{{ showSoulThinking ? '收起思考' : '展开思考' }}</span>
            <span class="thinking-len">{{ latestSoulData.thinking.length }}ch</span>
          </div>
          <div v-if="showSoulThinking" class="thinking-body">{{ latestSoulData.thinking }}</div>
        </div>

        <!-- 空状态 -->
        <div v-if="!latestSoulData.emotions?.length && !latestSoulData.innerThought && !latestSoulData.attribution && !latestSoulData.reflection && !latestSoulData.thinking" class="soul-empty">
          ◇ 等待弥娅的回应...
        </div>
      </div>

      <!-- History preview -->
      <div class="left-history">
        <div class="history-bar">
          <span class="history-icon">◇</span>
          <span class="history-label">对话历史</span>
          <button class="history-toggle" @click="toggleHistory">{{ showHistory ? '收起' : '展开' }}</button>
        </div>

        <!-- 展开的历史列表 -->
        <Transition name="history-expand">
          <div v-if="showHistory" class="history-dropdown">
            <div v-if="loadingSessions" class="history-status">加载中...</div>
            <div v-else-if="sessions.length === 0" class="history-status">暂无历史</div>
            <div v-else class="history-list">
              <div
                v-for="s in sessions" :key="s.sessionId"
                class="history-row"
                :class="{ active: s.sessionId === CURRENT_SESSION_ID }"
                @click="handleSwitchSession(s.sessionId)"
              >
                <span class="history-sid">{{ s.sessionId.slice(0, 8) }}</span>
                <span class="history-meta">{{ formatRelativeTime(s.lastActiveAt) }} · {{ s.conversationRounds }}轮</span>
                <button class="history-del" @click.stop="handleDeleteSession(s.sessionId)">✕</button>
              </div>
            </div>
            <button class="history-new-btn" @click="handleNewSession">+ 新建对话</button>
          </div>
        </Transition>
      </div>
    </div>

    <!-- ═══ 右面板 70% ═══ -->
    <div class="pgr-right">
      <!-- 顶部状态条 -->
      <div class="right-status">
        <div class="status-item">
          <span class="status-dot on" />
          <span class="status-label">SOUL.OK</span>
          <span class="status-val">v2.1.0</span>
        </div>
        <div class="status-item">
          <span class="status-dot on" />
          <span class="status-label">{{ latestEmotion?.emotions?.[0]?.name || '情绪' }}</span>
          <span class="status-val">{{ latestEmotion?.emotions?.[0]?.intensity || '--' }}%</span>
        </div>
        <div class="status-item">
          <span class="status-dot" />
          <span class="status-label">会话轮数</span>
          <span class="status-val">{{ getActiveTab().conversationRounds || 0 }}</span>
        </div>
      </div>

      <div class="tilt-toggle-wrap" role="group" aria-label="对话页面视角">
        <button class="tilt-toggle" :class="{ active: !tiltEnabled }" @click="tiltEnabled = false">
          平视
        </button>
        <button class="tilt-toggle" :class="{ active: tiltEnabled }" @click="tiltEnabled = true">
          透视
        </button>
      </div>

      <!-- 消息列表 -->
      <div ref="msgListRef" class="right-messages">
        <div class="msg-list">
          <TransitionGroup name="msg-in">
            <MessageItem
              v-for="item, index in activeMessages" :key="index"
              :role="item.role" :content="item.content"
              :reasoning="item.reasoning" :sender="item.sender"
              :generating="item.generating" :status="item.status"
              :tool-events="item.toolEvents"
              :soul-data="item.soulData"
              :style="{ '--msg-index': index }"
            />
          </TransitionGroup>
        </div>
      </div>

      <!-- 输入栏 -->
      <div ref="inputDockRef" class="right-input">
        <div class="input-box">
          <div class="input-main">
            <span class="input-cursor">&gt;</span>
            <textarea
              ref="composerRef"
              v-model="input"
              rows="1"
              class="input-textarea"
              placeholder="与弥娅对话..."
              @keydown.enter.exact="handleComposerEnter"
              @input="resizeComposer"
            />

            <div class="input-actions">
              <button class="input-btn" :class="{ active: showHistory }" title="对话历史" @click="toggleHistory">H</button>
              <button
                v-if="CONFIG.voice_realtime.enabled"
                class="input-btn" :class="{ recording: isRecording }"
                :title="isRecording ? '停止录音' : '语音输入'"
                @click="toggleVoiceInput"
              >
                <svg v-if="!isRecording" xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" x2="12" y1="19" y2="22" /></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
              </button>

              <div class="input-more-wrap">
                <button class="input-btn" title="更多" @click="showMoreActions = !showMoreActions">···</button>
              </div>
            </div>

            <button class="send-btn" :disabled="!input?.trim()" title="发送" @click="sendMessage">
              <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 2 11 13" />
                <path d="m22 2-7 20-4-9-9-4Z" />
              </svg>
            </button>
          </div>
        </div>

        <!-- 更多菜单 -->
        <Transition name="more-pop">
          <div v-if="showMoreActions" class="input-more-menu">
            <button v-if="CONFIG.system.voice_enabled" class="more-item" @click="toggleTTS">
              {{ ttsEnabled ? '♪ 关闭语音播报' : '♪ 开启语音播报' }}
            </button>
            <button class="more-item" @click="triggerUpload">⇧ 上传文件</button>
          </div>
        </Transition>
        <input ref="fileInput" type="file" accept=".docx,.xlsx,.txt,.csv,.md,.pdf,.png,.jpg,.jpeg" class="hidden" @change="handleFileUpload">
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ═══════════════════════════════════════════
   PGR 战双帕弥什 左右分栏布局
   ═══════════════════════════════════════════ */
.pgr-chat {
  display: flex;
  height: 100%;
  width: 100%;
  justify-content: space-between;
  align-items: center;
  perspective: 800px;
  -webkit-perspective: 800px;
  perspective-origin: center;
  -webkit-perspective-origin: center;
  overflow: hidden;
  padding: 0.8rem 1.2rem;
  gap: 1.2rem;
  min-width: 0;
}

/* ═══ 左面板 30% ═══ */
.pgr-left {
  width: 28%;
  height: 92%;
  padding: 1rem 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  transform: rotateY(12deg);
  transition: transform 0.5s ease;
}

.pgr-left:hover {
  transform: rotateY(9deg);
}

/* Profile */
.left-profile {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.4rem 0.5rem;
  font-weight: bold;
}

.left-avatar {
  position: relative;
  width: 48px;
  height: 48px;
  margin-bottom: 0.2rem;
}

.avatar-hex {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, rgba(0, 173, 181, 0.2), rgba(57, 164, 252, 0.15));
  border: 1px solid rgba(0, 255, 245, 0.25);
  clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-text {
  font-family: 'Noto Serif SC', serif;
  font-size: 1.4rem;
  font-weight: 900;
  color: rgba(0, 255, 245, 0.8);
  text-shadow: 0 0 10px rgba(0, 255, 245, 0.3);
}

.avatar-scan {
  position: absolute;
  top: -10%;
  left: -5%;
  width: 3px;
  height: 120%;
  background: rgba(255, 255, 255, 0.25);
  transform: skewX(-20deg);
  box-shadow: 0 0 15px rgba(255, 255, 255, 0.3);
  filter: blur(3px);
  animation: avatar-scan 3.5s ease-in-out infinite;
}

@keyframes avatar-scan {
  0%, 100% { left: -5%; opacity: 0; }
  30% { left: 110%; opacity: 0.8; }
  60% { left: 110%; opacity: 0; }
}

.left-name-group {
  display: flex;
  flex-direction: column;
  gap: 0.05rem;
}

.left-name {
  color: white;
  font-size: 1.2em;
  letter-spacing: 0.05em;
  font-weight: 700;
  text-shadow: 0 0 6px rgba(0, 255, 245, 0.1);
}

.left-id {
  color: #c8c8c8;
  font-size: 0.6em;
}

.left-lv {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.7em;
}

.lv-label { color: #c8c8c8; }
.lv-value { color: white; font-size: 1.5em; font-weight: 900; }

.lv-bar {
  width: 28%;
  height: 3px;
  background: linear-gradient(70deg, #27c0fe 50%, #505050 50%);
  border-radius: 2px;
}

/* Nav blocks */
.left-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  padding: 0 0.2rem;
}

.nav-block {
  height: 68px;
  width: calc(50% - 0.2rem);
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(0, 173, 181, 0.06);
  box-shadow: 3px 3px 8px rgba(0, 40, 50, 0.3), -2px -2px 6px rgba(0, 180, 200, 0.04);
  padding: 0.4rem;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: inherit;
  color: inherit;
}

.nav-block-title {
  color: white;
  font-size: 0.85em;
  font-weight: 700;
  margin-bottom: 20%;
}

.nav-block-tip {
  color: #c8c8c8;
  font-size: 0.4em;
}

.nav-block:hover {
  background: rgba(129, 191, 241, 0.15);
  border-color: rgba(0, 255, 245, 0.2);
  transform: skewX(-6deg);
}

.nav-block.active {
  background: rgba(0, 173, 181, 0.12);
  border-color: rgba(0, 255, 245, 0.3);
  box-shadow: 0 0 12px rgba(0, 173, 181, 0.1);
}

/* Banner */
.left-banner {
  width: 100%;
  cursor: pointer;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.banner-inner {
  position: relative;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(0, 173, 181, 0.08);
  padding: 0.5rem;
  clip-path: polygon(0 6px, 4px 0, calc(100% - 4px) 0, 100% 4px, 100% 100%, 0 100%);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.banner-shine {
  position: absolute;
  top: -20%;
  left: -10%;
  width: 4px;
  height: 140%;
  background: rgba(255, 255, 255, 0.12);
  transform: skewX(-25deg);
  box-shadow: 0 0 20px rgba(255, 255, 255, 0.1);
  filter: blur(3px);
  animation: banner-shine 3s ease-in-out infinite;
}

@keyframes banner-shine {
  0%, 100% { left: -10%; opacity: 0; }
  40% { left: 120%; opacity: 0.6; }
  60% { left: 120%; opacity: 0; }
}

.banner-text {
  color: white;
  font-size: 0.7em;
  font-weight: 600;
  position: relative;
  z-index: 1;
}

.banner-tip {
  color: #bbb6b6;
  font-size: 0.5em;
  position: relative;
  z-index: 1;
}

.left-banner:hover .banner-inner {
  background: rgba(129, 191, 241, 0.12);
  border-color: rgba(0, 255, 245, 0.2);
}

/* ═══ 灵魂共鸣卡片 ═══ */
.left-soul {
  margin-top: 0.3rem;
  background: rgba(0, 0, 0, 0.55);
  border: 1px solid rgba(0, 173, 181, 0.08);
  padding: 0.5rem;
  overflow: hidden;
  position: relative;
  box-shadow:
    2px 2px 8px rgba(0, 30, 40, 0.3),
    -1px -1px 4px rgba(0, 180, 200, 0.04);
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
  flex-shrink: 0;
  max-height: 260px;
  overflow-y: auto;
}

.left-soul::-webkit-scrollbar { width: 3px; }
.left-soul::-webkit-scrollbar-thumb { background: rgba(0, 173, 181, 0.1); border-radius: 2px; }

.left-soul:hover {
  border-color: rgba(0, 255, 245, 0.15);
  box-shadow:
    2px 3px 12px rgba(0, 30, 40, 0.4),
    0 0 16px rgba(0, 173, 181, 0.06);
}

/* Header */
.soul-header {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.4rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid rgba(0, 173, 181, 0.06);
}

.soul-header-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: rgba(0, 255, 245, 0.6);
  box-shadow: 0 0 6px rgba(0, 255, 245, 0.4);
  animation: dot-breath 2s ease-in-out infinite;
  flex-shrink: 0;
}

.soul-header-text {
  color: white;
  font-size: 0.65em;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.soul-header-subtitle {
  margin-left: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.45em;
  color: rgba(0, 173, 181, 0.3);
  letter-spacing: 0.1em;
}

/* Emotions */
.soul-emotions {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.4rem;
}

.soul-em-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.soul-em-name {
  font-size: 0.55em;
  color: #bbb6b6;
  width: 2rem;
  text-align: right;
  flex-shrink: 0;
}

.soul-em-bar {
  flex: 1;
  height: 4px;
  background: rgba(0, 173, 181, 0.06);
  border-radius: 2px;
  overflow: hidden;
}

.soul-em-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 0 4px currentColor;
}

.soul-em-val {
  font-size: 0.5em;
  color: rgba(0, 173, 181, 0.3);
  width: 1.8rem;
  text-align: right;
  font-family: 'JetBrains Mono', monospace;
  flex-shrink: 0;
}

/* Inner thought */
.soul-thought {
  font-family: 'Noto Serif SC', serif;
  font-style: italic;
  font-size: 0.6em;
  color: rgba(200, 210, 230, 0.7);
  line-height: 1.5;
  padding: 0.3rem 0.35rem;
  margin-bottom: 0.35rem;
  background: rgba(0, 173, 181, 0.03);
  border-left: 2px solid rgba(0, 173, 181, 0.15);
  border-radius: 0 3px 3px 0;
}

.soul-quote {
  color: rgba(0, 173, 181, 0.25);
  font-size: 0.8em;
}

/* Meta lines */
.soul-meta {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin-bottom: 0.35rem;
}

.soul-line {
  display: flex;
  gap: 0.25rem;
  font-size: 0.5em;
  color: rgba(180, 190, 210, 0.45);
  line-height: 1.4;
}

.soul-line-icon {
  color: rgba(0, 173, 181, 0.3);
  flex-shrink: 0;
  font-size: 0.55em;
  margin-top: 0.1em;
}

/* Thinking */
.soul-thinking {
  border-top: 1px solid rgba(0, 173, 181, 0.05);
  padding-top: 0.3rem;
}

.thinking-toggle {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
  color: rgba(0, 173, 181, 0.3);
  font-size: 0.55em;
  transition: color 0.2s;
  user-select: none;
}

.thinking-toggle:hover { color: rgba(0, 173, 181, 0.55); }

.thinking-icon { font-size: 0.6em; }

.thinking-len {
  margin-left: auto;
  font-size: 0.45em;
  opacity: 0.4;
  font-family: 'JetBrains Mono', monospace;
}

.thinking-body {
  margin-top: 0.3rem;
  padding: 0.3rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 173, 181, 0.05);
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5em;
  color: rgba(160, 190, 220, 0.5);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 100px;
  overflow-y: auto;
}

.thinking-body::-webkit-scrollbar { width: 2px; }
.thinking-body::-webkit-scrollbar-thumb { background: rgba(0, 173, 181, 0.1); border-radius: 1px; }

/* Empty */
.soul-empty {
  text-align: center;
  padding: 0.5rem;
  color: rgba(0, 173, 181, 0.15);
  font-size: 0.55em;
}

/* History preview */
.left-history {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.history-bar {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.4rem;
  background: rgba(255, 252, 252, 0.08);
  border: 1px solid rgba(0, 173, 181, 0.05);
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.history-bar:hover {
  background: rgba(129, 191, 241, 0.12);
}

.history-icon {
  color: rgba(0, 255, 245, 0.4);
  font-size: 0.65rem;
}

.history-label {
  color: white;
  font-size: 0.65em;
  font-weight: 600;
}

.history-toggle {
  margin-left: auto;
  background: none;
  border: none;
  color: #c8c8c8;
  font-size: 0.55em;
  cursor: pointer;
  transition: color 0.2s;
}

.history-toggle:hover { color: rgba(0, 255, 245, 0.8); }

.history-dropdown {
  margin-top: 0.3rem;
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid rgba(0, 173, 181, 0.08);
  overflow: hidden;
  backdrop-filter: blur(12px);
}

.history-status {
  text-align: center;
  padding: 0.8rem;
  color: rgba(0, 173, 181, 0.3);
  font-size: 0.6rem;
}

.history-list {
  max-height: 180px;
  overflow-y: auto;
}

.history-list::-webkit-scrollbar { width: 3px; }
.history-list::-webkit-scrollbar-thumb { background: rgba(0, 173, 181, 0.1); border-radius: 2px; }

.history-row {
  display: flex;
  align-items: center;
  padding: 0.35rem 0.5rem;
  cursor: pointer;
  transition: all 0.15s ease;
  border-bottom: 1px solid rgba(0, 173, 181, 0.03);
}

.history-row:hover,
.history-row.active {
  background: rgba(129, 191, 241, 0.1);
}

.history-row.active {
  border-left: 2px solid rgba(0, 255, 245, 0.4);
}

.history-sid {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  color: rgba(228, 236, 240, 0.6);
}

.history-meta {
  margin-left: auto;
  font-size: 0.5rem;
  color: rgba(0, 173, 181, 0.3);
}

.history-del {
  background: none; border: none;
  color: rgba(0, 173, 181, 0.15);
  cursor: pointer; font-size: 0.5rem;
  padding: 2px;
}

.history-del:hover { color: rgba(255, 100, 100, 0.6); }

.history-new-btn {
  display: block;
  width: 100%;
  padding: 0.35rem;
  background: rgba(0, 173, 181, 0.06);
  border: none;
  border-top: 1px solid rgba(0, 173, 181, 0.06);
  color: rgba(0, 255, 245, 0.4);
  font-size: 0.6rem;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}

.history-new-btn:hover {
  background: rgba(0, 173, 181, 0.12);
  color: rgba(0, 255, 245, 0.7);
}

.history-expand-enter-active { transition: all 0.25s ease; }
.history-expand-leave-active { transition: all 0.15s ease; }
.history-expand-enter-from,
.history-expand-leave-to { opacity: 0; max-height: 0; }

/* ═══ 右面板 70% ═══ */
.pgr-right {
  width: 72%;
  height: 94%;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.4rem 0.6rem;
  background:
    linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0) 30%),
    linear-gradient(0deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0) 20%);
  border: 1px solid rgba(0, 173, 181, 0.04);
  border-radius: 2px;
  transition: transform 0.5s ease;
}

.pgr-right.tilted {
  transform: rotateY(-12deg);
}

.pgr-right.tilted:hover {
  transform: rotateY(-9deg);
}

/* Tilt toggle */
.tilt-toggle-wrap {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0.2rem;
}

.tilt-toggle {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 173, 181, 0.08);
  color: rgba(0, 173, 181, 0.35);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  padding: 2px 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  letter-spacing: 0.05em;
}

.tilt-toggle:hover {
  background: rgba(0, 173, 181, 0.1);
  border-color: rgba(0, 255, 245, 0.25);
  color: rgba(0, 255, 245, 0.7);
}

.right-status {
  display: flex;
  justify-content: space-between;
  gap: 0.4rem;
  flex-shrink: 0;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: 1;
  height: 36px;
  background: rgba(0, 0, 0, 0.55);
  border: 1px solid rgba(0, 173, 181, 0.07);
  padding: 0 0.7rem;
  cursor: pointer;
  transition: all 0.25s ease;
}

.status-item:hover {
  background: rgba(129, 191, 241, 0.12);
  border-color: rgba(0, 173, 181, 0.2);
}

.status-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: rgba(0, 173, 181, 0.15);
  flex-shrink: 0;
}

.status-dot.on {
  background: rgba(0, 255, 245, 0.6);
  box-shadow: 0 0 6px rgba(0, 255, 245, 0.4);
  animation: dot-breath 2s ease-in-out infinite;
}

@keyframes dot-breath {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.status-label {
  color: white;
  font-size: 0.65em;
  font-weight: 600;
}

.status-val {
  margin-left: auto;
  color: #bbb6b6;
  font-size: 0.6em;
  font-family: 'JetBrains Mono', monospace;
}

/* Messages */
.right-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0.4rem 0.4rem 0.4rem 0.2rem;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
}

.right-messages::-webkit-scrollbar { width: 4px; }
.right-messages::-webkit-scrollbar-track { background: transparent; }
.right-messages::-webkit-scrollbar-thumb { background: rgba(0, 173, 181, 0.12); border-radius: 2px; }

.msg-list {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  padding-bottom: 0.3rem;
}

/* 消息入场 */
.msg-in-enter-active {
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  transition-delay: calc(var(--msg-index, 0) * 30ms);
}
.msg-in-leave-active { transition: all 0.2s ease-in; }
.msg-in-enter-from { opacity: 0; transform: translateY(16px) scale(0.97); }
.msg-in-leave-to { opacity: 0; }

/* ═══ 输入栏 ═══ */
.right-input {
  position: relative;
  flex-shrink: 0;
}

.input-box {
  background: rgba(0, 0, 0, 0.55);
  border: 1px solid rgba(0, 173, 181, 0.07);
  padding: 0.45rem 0.55rem;
  backdrop-filter: blur(16px);
  transition: border-color 0.3s, box-shadow 0.3s;
}

.input-box:focus-within {
  border-color: rgba(0, 173, 181, 0.3);
}

.input-main {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.input-cursor {
  color: rgba(0, 255, 245, 0.35);
  font-size: 0.85rem;
  font-family: 'JetBrains Mono', monospace;
  flex-shrink: 0;
  user-select: none;
}

.input-textarea {
  flex: 1;
  min-width: 0;
  min-height: 36px;
  max-height: 140px;
  padding: 6px 0;
  line-height: 22px;
  resize: none;
  overflow-y: auto;
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 0.85rem;
  background: transparent;
  border: none;
  outline: none;
  color: rgba(228, 236, 240, 0.9);
}

.input-textarea::placeholder { color: rgba(0, 173, 181, 0.12); }

.input-actions {
  display: flex;
  align-items: center;
  gap: 0.2rem;
}

.input-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px; height: 30px;
  background: transparent;
  border: 1px solid rgba(0, 173, 181, 0.06);
  color: rgba(200, 200, 200, 0.4);
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  transition: all 0.25s cubic-bezier(0.22, 1, 0.36, 1);
  flex-shrink: 0;
}

.input-btn:hover {
  color: rgba(255, 255, 255, 0.85);
  background: rgba(129, 191, 241, 0.12);
  border-color: rgba(0, 173, 181, 0.2);
  transform: skewX(-5deg);
}

.input-btn.active {
  color: rgba(0, 255, 245, 0.75);
  background: rgba(0, 173, 181, 0.14);
  border-color: rgba(0, 255, 245, 0.25);
}

.input-btn.recording {
  color: #f87171;
  animation: rec-pulse 1.2s ease-in-out infinite;
}

@keyframes rec-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(248, 113, 113, 0.3); }
  50% { box-shadow: 0 0 0 5px rgba(248, 113, 113, 0); }
}

.send-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px; height: 34px;
  border: 1px solid rgba(0, 173, 181, 0.12);
  background: rgba(57, 164, 252, 0.08);
  color: rgba(0, 173, 181, 0.45);
  cursor: pointer;
  clip-path: polygon(0 3px, 3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%);
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: rgba(57, 164, 252, 0.2);
  border-color: rgba(0, 255, 245, 0.5);
  color: rgba(0, 255, 245, 0.95);
  transform: skewX(-3deg);
}

.send-btn:disabled { opacity: 0.12; cursor: default; }

.input-more-wrap { flex-shrink: 0; }

.input-more-menu {
  position: absolute;
  bottom: calc(100% - 2px);
  right: 1rem;
  min-width: 130px;
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid rgba(0, 173, 181, 0.12);
  backdrop-filter: blur(16px);
  box-shadow: 3px 3px 12px rgba(0, 40, 50, 0.45);
  overflow: hidden;
  z-index: 100;
}

.more-item {
  display: block;
  width: 100%;
  padding: 0.4rem 0.7rem;
  background: none;
  border: none;
  border-bottom: 1px solid rgba(0, 173, 181, 0.04);
  color: rgba(200, 200, 200, 0.5);
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 0.7rem;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.more-item:hover {
  background: rgba(129, 191, 241, 0.12);
  color: #ffffff;
  transform: skewX(-4deg);
}

.more-item:last-child { border-bottom: none; }

.more-pop-enter-active { transition: all 0.15s ease; }
.more-pop-leave-active { transition: all 0.1s ease; }
.more-pop-enter-from,
.more-pop-leave-to { opacity: 0; transform: translateY(4px); }

/* Miya OS: 对话是日常核心体验，优先保证平静、清晰与长时间可读。 */
.pgr-chat {
  align-items: stretch;
  padding: var(--miya-space-3);
  gap: var(--miya-space-3);
  perspective: none;
}

.pgr-left {
  width: clamp(220px, 25%, 300px);
  height: 100%;
  padding: var(--miya-space-4);
  transform: none;
  background: var(--miya-surface-1);
  border: 1px solid var(--miya-line-soft);
  border-radius: var(--miya-radius-lg);
  box-shadow: var(--miya-shadow-panel);
  backdrop-filter: blur(16px);
}

.pgr-left:hover { transform: none; }

.pgr-right {
  width: auto;
  flex: 1;
  height: 100%;
  padding: var(--miya-space-3);
  gap: var(--miya-space-3);
  transform: none;
  background: rgba(8, 14, 22, 0.52);
  border: 1px solid var(--miya-line-soft);
  border-radius: var(--miya-radius-lg);
  box-shadow: var(--miya-shadow-panel);
  backdrop-filter: blur(14px);
}

.pgr-chat.perspective { perspective: 1100px; }
.pgr-chat.perspective .pgr-left {
  transform: rotateY(9deg) translateX(4px);
  transform-origin: center left;
}
.pgr-chat.perspective .pgr-right {
  transform: rotateY(-9deg) translateX(-4px);
  transform-origin: center right;
}
.pgr-chat.perspective .pgr-left:hover { transform: rotateY(7deg) translateX(4px); }
.pgr-chat.perspective .pgr-right:hover { transform: rotateY(-7deg) translateX(-4px); }

.pgr-left,
.pgr-right {
  transition: transform var(--miya-duration-slow) var(--miya-ease-out), border-color var(--miya-duration-base) ease;
}

.right-status { gap: var(--miya-space-2); }
.status-item {
  height: 34px;
  background: rgba(16, 25, 37, 0.68);
  border-color: var(--miya-line-soft);
  border-radius: var(--miya-radius-sm);
}
.status-item:hover {
  background: rgba(120, 207, 209, 0.07);
  border-color: var(--miya-line);
}

.tilt-toggle-wrap {
  align-self: flex-end;
  gap: 2px;
  padding: 2px;
  margin: -2px 0 0;
  background: rgba(7, 11, 18, 0.52);
  border: 1px solid var(--miya-line-soft);
  border-radius: var(--miya-radius-sm);
}
.tilt-toggle {
  min-width: 48px;
  padding: 4px 10px;
  color: var(--miya-text-muted);
  background: transparent;
  border: 0;
  border-radius: var(--miya-radius-xs);
}
.tilt-toggle:hover { color: var(--miya-text-strong); background: rgba(120, 207, 209, 0.06); }
.tilt-toggle.active {
  color: var(--miya-accent-bright);
  background: rgba(120, 207, 209, 0.12);
  box-shadow: inset 0 0 0 1px var(--miya-line);
}

.right-messages {
  padding: var(--miya-space-3);
  background: rgba(7, 11, 18, 0.32);
  border-radius: var(--miya-radius-md);
}

.input-box {
  padding: var(--miya-space-2) var(--miya-space-3);
  background: var(--miya-surface-2);
  border-color: var(--miya-line);
  border-radius: var(--miya-radius-md);
  box-shadow: 0 10px 34px rgba(0, 0, 0, 0.22);
}
.input-box:focus-within {
  border-color: var(--miya-line-strong);
  box-shadow: var(--miya-shadow-focus), 0 14px 38px rgba(0, 0, 0, 0.24);
}

.nav-block:hover,
.more-item:hover { transform: none; }

@media (max-width: 900px) {
  .pgr-left { width: 210px; }
}
</style>
