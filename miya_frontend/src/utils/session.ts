import type { StreamChunk } from '@/utils/encoding'
import { useStorage } from '@vueuse/core'
import { ref, watch } from 'vue'
import API from '@/api/core'
import { apiPort } from '@/utils/api-port'

export const proactiveNotifier = ref<null | ((source: string, content: string) => void)>(null)

export interface Message {
  role: 'system' | 'user' | 'assistant' | 'info'
  content: string
  reasoning?: string
  generating?: boolean
  status?: string
  sender?: string
  platform?: string
  platformName?: string
  messageId?: string
  direction?: 'in' | 'out'
  replyToMessageId?: string
  timestamp?: string
  toolEvents?: ToolEvent[]
  soulData?: SoulData
}

export interface SoulData {
  emotions?: Array<{ name: string, intensity: number }>
  innerThought?: string
  attribution?: string
  reflection?: string
  thinking?: string
}

export interface ToolEvent {
  type: 'tool_call' | 'tool_result'
  name?: string
  toolCallId?: string
  args?: any
  result?: any
  isError?: boolean
}

// ── Tab 状态管理 ──

export interface ChatTab {
  id: string
  name: string
  messages: Message[]
  unread: number
  conversationRounds?: number
}

export const tabs = ref<ChatTab[]>(
  (() => {
    try {
      const saved = localStorage.getItem('miya-chat-tabs')
      return saved ? JSON.parse(saved) : [{ id: 'default', name: '弥娅', messages: [], unread: 0 }]
    } catch { return [{ id: 'default', name: '弥娅', messages: [], unread: 0 }] }
  })()
)

// 监听保存
watch(tabs, (t) => {
  try { localStorage.setItem('miya-chat-tabs', JSON.stringify(t)) } catch {}
}, { deep: true })

// 全局最新情绪（跨组件共享）
export const latestEmotion = ref<SoulData>({ emotions: [] })

export const activeTabId = useStorage('miya-active-tab', 'default')

export function getActiveTab(): ChatTab {
  return tabs.value.find(t => t.id === activeTabId.value) || tabs.value[0]!
}

export function getDefaultTab(): ChatTab {
  return tabs.value[0]!
}

export function appendDefaultMessage(message: Message) {
  MESSAGES.value.push(message)
  syncDefaultMessages()
}

export async function reloadCurrentSessionMessages() {
  if (!CURRENT_SESSION_ID.value)
    return
  const detail = await API.getSession(CURRENT_SESSION_ID.value)
  MESSAGES.value = normalizeMessages(detail.messages)
  syncDefaultMessages()
}

function normalizeToolEvent(input: any): ToolEvent | null {
  if (!input || typeof input !== 'object')
    return null
  const type = input.type === 'tool_result' ? 'tool_result' : input.type === 'tool_call' ? 'tool_call' : null
  if (!type)
    return null
  return {
    type,
    name: typeof input.name === 'string' ? input.name : undefined,
    toolCallId: typeof input.toolCallId === 'string'
      ? input.toolCallId
      : typeof input.tool_call_id === 'string'
        ? input.tool_call_id
        : undefined,
    args: input.args,
    result: input.result,
    isError: Boolean(input.isError ?? input.is_error),
  }
}

function extractStructuredToolBlocks(content: string): { content: string, toolEvents: ToolEvent[] } {
  if (!content.includes('```tool-'))
    return { content, toolEvents: [] }

  const toolEvents: ToolEvent[] = []
  let remaining = content
  let cleaned = ''

  while (remaining.length > 0) {
    const startCall = remaining.indexOf('```tool-call')
    const startResult = remaining.indexOf('```tool-result')
    const start = startCall === -1
      ? startResult
      : startResult === -1
        ? startCall
        : Math.min(startCall, startResult)
    if (start === -1) {
      cleaned += remaining
      break
    }

    cleaned += remaining.slice(0, start)
    const isToolCall = remaining.startsWith('```tool-call', start)
    const afterHeader = remaining.indexOf('\n', start)
    if (afterHeader === -1) {
      cleaned += remaining.slice(start)
      break
    }

    const end = remaining.indexOf('```', afterHeader + 1)
    if (end === -1) {
      cleaned += remaining.slice(start)
      break
    }

    const block = remaining.slice(afterHeader + 1, end).trim()
    if (block) {
      const lines = block.split('\n')
      const summary = (lines[0] || '').trim()
      const body = lines.slice(1).join('\n').trim()
      const isError = summary.startsWith('❌ ')
      const isSuccess = summary.startsWith('✅ ')
      const name = (isError || isSuccess) ? summary.slice(2).trim() : summary
      toolEvents.push({
        type: isToolCall ? 'tool_call' : 'tool_result',
        name: name || '工具',
        isError: isToolCall ? undefined : isError,
        args: isToolCall ? body : undefined,
        result: isToolCall ? undefined : body,
      })
    }

    remaining = remaining.slice(end + 3)
  }

  return {
    content: cleaned.replace(/\n{3,}/g, '\n\n').trim(),
    toolEvents,
  }
}

function buildMessageQueueKey(role: Message['role'], content: string): string {
  return `${role}\u0000${extractStructuredToolBlocks(content).content}`
}

function normalizeSoulData(input: any): SoulData | undefined {
  if (!input || typeof input !== 'object') return undefined
  const sd: SoulData = {}
  if (Array.isArray(input.emotions) && input.emotions.length) {
    sd.emotions = input.emotions.filter((emotion: any) => emotion && typeof emotion.name === 'string')
  } else if (input.emotions && typeof input.emotions === 'object') {
    sd.emotions = Object.entries(input.emotions)
      .filter(([name]) => !['dominant', 'intensity'].includes(name))
      .map(([name, value]) => ({
        name,
        intensity: typeof value === 'number' && value <= 1 ? Math.round(value * 100) : Number(value) || 50,
      }))
  }
  const textValue = (...keys: string[]) => keys
    .map(key => input[key])
    .find(value => typeof value === 'string' && value.trim().length > 0) as string | undefined
  sd.innerThought = textValue('innerThought', 'inner_thought')
  sd.attribution = textValue('attribution')
  sd.reflection = textValue('reflection')
  sd.thinking = textValue('thinking')
  for (const key of ['innerThought', 'attribution', 'reflection', 'thinking'] as const) {
    if (!sd[key]) delete sd[key]
  }
  return Object.keys(sd).length ? sd : undefined
}

function normalizeMessage(input: any, assistantName?: string): Message | null {
  if (!input || typeof input !== 'object')
    return null

  const role = input.role
  if (role !== 'system' && role !== 'user' && role !== 'assistant' && role !== 'info')
    return null

  const initialContent = typeof input.content === 'string' ? input.content : ''
  const extracted = extractStructuredToolBlocks(initialContent)
  const rawEvents = Array.isArray(input.toolEvents)
    ? input.toolEvents
    : Array.isArray(input.tool_events)
      ? input.tool_events
      : []
  const toolEvents = [
    ...((rawEvents.map(normalizeToolEvent).filter(Boolean)) as ToolEvent[]),
    ...extracted.toolEvents,
  ]

  return {
    role,
    content: extracted.content,
    reasoning: typeof input.reasoning === 'string' ? input.reasoning : undefined,
    generating: Boolean(input.generating),
    status: typeof input.status === 'string' ? input.status : undefined,
    sender: typeof input.sender === 'string' ? input.sender : role === 'assistant' ? assistantName : undefined,
    platform: typeof input.platform === 'string' ? input.platform : undefined,
    platformName: typeof input.platform_name === 'string' ? input.platform_name : typeof input.platformName === 'string' ? input.platformName : undefined,
    messageId: typeof input.message_id === 'string' ? input.message_id : typeof input.messageId === 'string' ? input.messageId : undefined,
    direction: typeof input.direction === 'string' ? input.direction : undefined,
    replyToMessageId: typeof input.reply_to_message_id === 'string' ? input.reply_to_message_id : typeof input.replyToMessageId === 'string' ? input.replyToMessageId : undefined,
    timestamp: typeof input.timestamp === 'string' ? input.timestamp : undefined,
    toolEvents: toolEvents.length ? toolEvents : undefined,
    // 兼容旧会话：灵魂字段有时直接挂在消息对象上，而不是 soulData 内。
    soulData: normalizeSoulData(input.soulData || input.soul_data || input),
  }
}

function mergeAssistantMessages(base: Message, extra: Message) {
  if (extra.content) {
    base.content = base.content
      ? `${base.content}\n\n${extra.content}`.trim()
      : extra.content
  }
  if (extra.reasoning) {
    base.reasoning = base.reasoning
      ? `${base.reasoning}\n\n${extra.reasoning}`.trim()
      : extra.reasoning
  }
  if (extra.toolEvents?.length) {
    base.toolEvents = [...(base.toolEvents || []), ...extra.toolEvents]
  }
  if (!base.status && extra.status)
    base.status = extra.status
  if (!base.sender && extra.sender)
    base.sender = extra.sender
  if (!base.platform && extra.platform)
    base.platform = extra.platform
  if (!base.platformName && extra.platformName)
    base.platformName = extra.platformName
  if (!base.messageId && extra.messageId)
    base.messageId = extra.messageId
  if (!base.direction && extra.direction)
    base.direction = extra.direction
  if (!base.timestamp && extra.timestamp)
    base.timestamp = extra.timestamp
  if (extra.soulData) {
    const soul = base.soulData || {}
    if (!soul.emotions?.length && extra.soulData.emotions?.length)
      soul.emotions = extra.soulData.emotions
    if (!soul.innerThought && extra.soulData.innerThought)
      soul.innerThought = extra.soulData.innerThought
    if (!soul.attribution && extra.soulData.attribution)
      soul.attribution = extra.soulData.attribution
    if (!soul.reflection && extra.soulData.reflection)
      soul.reflection = extra.soulData.reflection
    if (!soul.thinking && extra.soulData.thinking)
      soul.thinking = extra.soulData.thinking
    base.soulData = soul
  }
  base.generating = base.generating || extra.generating
}

export function normalizeMessages(messages: unknown, assistantName?: string): Message[] {
  if (!Array.isArray(messages))
    return []

  const normalized: Message[] = []
  for (const item of messages) {
    const message = normalizeMessage(item, assistantName)
    if (!message)
      continue

    const previous = normalized[normalized.length - 1]
    if (message.role === 'assistant' && previous?.role === 'assistant') {
      mergeAssistantMessages(previous, message)
      continue
    }
    normalized.push(message)
  }
  return normalized
}

// ── 默认 tab 会话管理 ──

export const CURRENT_SESSION_ID = useStorage<string | null>('miya-session', null)
// 从 localStorage 恢复消息（优先 miya-messages，fallback 到 miya-chat-tabs）
function loadSavedMessages(): Message[] {
  const tryLoad = (key: string, path?: (data: any) => any): Message[] | null => {
    try {
      const saved = localStorage.getItem(key)
      if (saved) {
        const parsed = JSON.parse(saved)
        const arr = path ? path(parsed) : parsed
        if (Array.isArray(arr) && arr.length > 0)
          return arr as Message[]
      }
    }
    catch (e) {
      console.warn(`[MIYA] 无法从 localStorage 加载 ${key}:`, e)
    }
    return null
  }

  const primary = tryLoad('miya-messages')
  if (primary)
    return primary

  const fallback = tryLoad('miya-chat-tabs', (data) => data?.[0]?.messages)
  if (fallback) {
    console.warn('[MIYA] miya-messages 为空，已从 tabs 恢复消息')
    return fallback
  }

  return []
}
export const MESSAGES = ref<Message[]>(loadSavedMessages())

export function saveMessages() {
  try {
    const toSave = MESSAGES.value.slice(-200)
    localStorage.setItem('miya-messages', JSON.stringify(toSave))
  } catch (e) {
    console.warn('[MIYA] 保存消息到 localStorage 失败:', e)
  }
}

export const IS_TEMPORARY_SESSION = ref(false)

tabs.value[0]!.messages = MESSAGES.value

function syncDefaultMessages() {
  tabs.value[0]!.messages = MESSAGES.value
}

export async function loadCurrentSession() {
  if (CURRENT_SESSION_ID.value) {
    try {
      const detail = await API.getSession(CURRENT_SESSION_ID.value)
      const normalized = normalizeMessages(detail.messages)
      // 只有后端有数据时才替换，否则保留本地消息
      if (normalized.length > 0) {
        MESSAGES.value = normalized
        syncDefaultMessages()
        // 异步回填灵魂数据（从认知记忆 / soul API）
        backfillSoulDataForSession()
        return
      }
    }
    catch {
      CURRENT_SESSION_ID.value = null
    }
  }
  // 保留现有消息
  syncDefaultMessages()
}

async function backfillSoulDataForSession() {
  const msgs = MESSAGES.value
  const lastAi = msgs
    .filter(m => m.role === 'assistant')
    .slice(-1)[0]
  if (!lastAi || (lastAi as any).soulData?.emotions?.length || (lastAi as any).soulData?.innerThought || (lastAi as any).soulData?.attribution || (lastAi as any).soulData?.reflection || (lastAi as any).soulData?.thinking) return

  try {
    const res = await fetch(`http://localhost:${apiPort.value}/api/soul/current`)
    const soul = await res.json()
    if (soul && ((soul.emotions && (Array.isArray(soul.emotions) ? soul.emotions.length : Object.keys(soul.emotions).length)) || soul.inner_thought || soul.attribution || soul.reflection || soul.thinking)) {
      const existing = (lastAi as any).soulData || {}
      if (soul.emotions && typeof soul.emotions === 'object' && !Array.isArray(soul.emotions)) {
        existing.emotions = Object.entries(soul.emotions).map(([name, val]: any) => ({
          name,
          intensity: typeof val === 'number' ? Math.round(val <= 1 ? val * 100 : val) : 50,
        }))
      } else if (Array.isArray(soul.emotions)) {
        existing.emotions = soul.emotions
      }
      if (!existing.innerThought && soul.inner_thought) existing.innerThought = soul.inner_thought
      if (!existing.attribution && soul.attribution) existing.attribution = soul.attribution
      if (!existing.reflection && soul.reflection) existing.reflection = soul.reflection
      if (!existing.thinking && soul.thinking) existing.thinking = soul.thinking
      ;(lastAi as any).soulData = existing
      saveMessages()
    }
  } catch {}
}

export function newSession() {
  CURRENT_SESSION_ID.value = null
  MESSAGES.value = []
  saveMessages()
  syncDefaultMessages()
  IS_TEMPORARY_SESSION.value = false
}

export function newTemporarySession() {
  CURRENT_SESSION_ID.value = null
  MESSAGES.value = []
  saveMessages()
  syncDefaultMessages()
  IS_TEMPORARY_SESSION.value = true
}

export async function switchSession(id: string) {
  CURRENT_SESSION_ID.value = id
  IS_TEMPORARY_SESSION.value = false
  await loadCurrentSession()
}

export function formatRelativeTime(iso: string) {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1)
    return '刚刚'
  if (diffMin < 60)
    return `${diffMin}分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24)
    return `${diffHour}小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7)
    return `${diffDay}天前`
  return d.toLocaleDateString()
}

declare global {
  interface WindowEventMap {
    token: CustomEvent<StreamChunk>
  }
}
