import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface EmotionState {
  dominant: string
  intensity: number
}

export interface PersonalityProfile {
  warmth: number
  logic: number
  creativity: number
  empathy: number
  resilience: number
}

export interface SystemStatus {
  version: string
  personality: PersonalityProfile
  emotion: EmotionState
}

export interface SystemInfo {
  system: {
    os: string
    os_version: string
    machine: string
    processor: string
    python_version: string
  }
  cpu: {
    count: number
    percent: number
  }
  memory: {
    total: number
    available: number
    percent: number
  }
  disk: {
    total: number
    used: number
    free: number
  }
}

export const useSystemStore = defineStore('system', () => {
  // State
  const status = ref<SystemStatus | null>(null)
  const info = ref<SystemInfo | null>(null)
  const isConnected = ref(false)
  const isLoading = ref(false)

  // Computed
  const currentEmotion = computed(() => status.value?.emotion)

  const emotionEmoji = computed(() => {
    const emojiMap: Record<string, string> = {
      '快乐': '😊',
      '悲伤': '😢',
      '愤怒': '😠',
      '焦虑': '😰',
      '平静': '😌',
      '兴奋': '🤩',
      '困惑': '😕',
      '专注': '🧐',
      '疲惫': '😴',
      '惊讶': '😲'
    }
    return emojiMap[currentEmotion.value?.dominant || '快乐'] || '😊'
  })

  const emotionColor = computed(() => {
    if (!currentEmotion.value) return '#4caf50'
    const intensity = currentEmotion.value.intensity
    if (intensity < 0.3) return '#4caf50'
    if (intensity < 0.6) return '#ff9800'
    return '#e94560'
  })

  const personalityDominant = computed(() => {
    if (!status.value?.personality) return '平衡'
    const vectors = status.value.personality
    const maxKey = Object.keys(vectors).reduce((a, b) =>
      vectors[a as keyof PersonalityProfile] > vectors[b as keyof PersonalityProfile] ? a : b
    )
    const stateMap: Record<string, string> = {
      'warmth': '温暖',
      'logic': '理性',
      'creativity': '创造',
      'empathy': '共情',
      'resilience': '韧性'
    }
    return stateMap[maxKey] || '平衡'
  })

  const memoryUsagePercent = computed(() => info.value?.memory.percent || 0)
  const cpuUsagePercent = computed(() => info.value?.cpu.percent || 0)
  const diskUsagePercent = computed(() => {
    if (!info.value?.disk.total) return 0
    return (info.value.disk.used / info.value.disk.total) * 100
  })

  // Actions
  function setStatus(newStatus: SystemStatus) {
    status.value = newStatus
  }

  function setInfo(newInfo: SystemInfo) {
    info.value = newInfo
  }

  function setConnected(connected: boolean) {
    isConnected.value = connected
  }

  function setLoading(loading: boolean) {
    isLoading.value = loading
  }

  function formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
  }

  return {
    // State
    status,
    info,
    isConnected,
    isLoading,

    // Computed
    currentEmotion,
    emotionEmoji,
    emotionColor,
    personalityDominant,
    memoryUsagePercent,
    cpuUsagePercent,
    diskUsagePercent,

    // Actions
    setStatus,
    setInfo,
    setConnected,
    setLoading,
    formatBytes
  }
})
