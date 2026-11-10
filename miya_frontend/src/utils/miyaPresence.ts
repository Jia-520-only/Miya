export const MEMORY_LAYERS = [
  { id: 'dialogue', label: '对话' },
  { id: 'shortTerm', label: '短期' },
  { id: 'longTerm', label: '长期' },
  { id: 'semantic', label: '语义' },
  { id: 'knowledge', label: '知识' },
  { id: 'pinned', label: '置顶' },
] as const

const UPPERCASE = /[A-Z]/g

export interface ObservatoryNote {
  id: string
  title: string
  body: string
  createdAt: string
  personaName: string | null
}

export interface MiyaPresence {
  persona: string | null
  emotion: string | null
  emotionIntensity: number | null
  emotions: Array<{ name: string, intensity: number }>
  phase: string | null
  lifecycleAt: string | null
  messageCount: number | null
  memoryCount: number | null
  memoryLayers: Record<string, number | null>
  platformCount: number | null
  onlinePlatforms: number | null
  sampledAt: string | null
  note: ObservatoryNote | null
}

function record(value: unknown): Record<string, any> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function count(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? Math.round(value) : null
}

function timestamp(value: unknown): string | null {
  return typeof value === 'string' && Number.isFinite(Date.parse(value)) ? value : null
}

const PHASES: Record<string, string> = {
  INIT: '初始化',
  BOOT: '启动中',
  RUNNING: '运行中',
  IDLE: '安静陪伴',
  DROWSY: '半休眠',
  SLEEP: '休眠中',
  WAKE: '唤醒中',
  SHUTDOWN: '已关闭',
}

const EMOTIONS: Record<string, string> = {
  joy: '喜悦',
  sadness: '忧伤',
  anger: '生气',
  fear: '担忧',
  love: '爱',
  surprise: '惊讶',
  neutral: '平静',
  calm: '安心',
  warm: '温暖',
  curious: '好奇',
  shy: '害羞',
  anticipation: '期待',
  attachment: '依恋',
}

export function phaseLabel(phase: string | null): string {
  return phase ? PHASES[phase] ?? '待感知' : '待感知'
}

export function emotionLabel(emotion: string | null): string {
  return emotion ? EMOTIONS[emotion] ?? emotion : '待感知'
}

// SSE sends native keys; ApiClient converts REST responses to camelCase.
// Legacy status defaults are intentionally not accepted as telemetry.
export function normalizeMiyaPresence(value: unknown): MiyaPresence {
  const status = record(value)
  const persona = record(status.persona)
  const emotion = record(status.emotion)
  const memory = record(status.memory)
  const layers = record(memory.layers)
  const platforms = record(status.platforms)
  const lifecycle = record(status.lifecycle)
  const note = record(status.note)
  const emotionIntensity = count(emotion.intensity)
  return {
    persona: text(persona.name) ?? text(persona.id),
    emotion: text(emotion.name),
    emotionIntensity: emotionIntensity !== null && emotionIntensity <= 100 ? emotionIntensity : null,
    emotions: (Array.isArray(emotion.emotions) ? emotion.emotions : []).map(record).filter(item => text(item.name) && count(item.intensity) !== null && item.intensity <= 100).map(item => ({ name: item.name, intensity: Math.round(item.intensity) })),
    phase: typeof lifecycle.phase === 'string' && Object.hasOwn(PHASES, lifecycle.phase) ? lifecycle.phase : null,
    lifecycleAt: timestamp(lifecycle.observedAt ?? lifecycle.observed_at),
    messageCount: count(lifecycle.messageCount ?? lifecycle.message_count),
    memoryCount: count(memory.total),
    memoryLayers: Object.fromEntries(MEMORY_LAYERS.map(({ id }) => {
      const nativeId = id.replace(UPPERCASE, letter => `_${letter.toLowerCase()}`)
      return [id, count(layers[id] ?? layers[nativeId])]
    })),
    platformCount: count(platforms.enabledCount ?? platforms.enabled_count),
    onlinePlatforms: count(platforms.onlineCount ?? platforms.online_count),
    sampledAt: timestamp(status.sampledAt ?? status.sampled_at),
    note: text(note.title) && text(note.body) && timestamp(note.createdAt ?? note.created_at)
      ? { id: text(note.id) ?? '', title: note.title.trim(), body: note.body.trim(), createdAt: note.createdAt ?? note.created_at, personaName: text(note.personaName ?? note.persona_name) }
      : null,
  }
}
