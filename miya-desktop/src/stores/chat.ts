import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface EmotionState {
  dominant: string
  intensity: number
}

export interface PersonalityProfile {
  state: string
  vectors: {
    warmth: number
    logic: number
    creativity: number
    empathy: number
    resilience: number
  }
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  emotion?: EmotionState
  personality?: PersonalityProfile
  toolsUsed?: string[]
  memoryRetrieved?: boolean
  timestamp: string
  sessionId: string
}

export interface ChatSession {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messageCount: number
  lastMessage?: string
}

export const useChatStore = defineStore('chat', () => {
  // 状态
  const messages = ref<ChatMessage[]>([])
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string>('default')
  const isLoading = ref(false)
  const isTyping = ref(false)
  const inputText = ref('')

  // 计算属性
  const currentMessages = computed(() => {
    return messages.value.filter(m => m.sessionId === currentSessionId.value)
  })

  const currentSession = computed(() => {
    return sessions.value.find(s => s.id === currentSessionId.value)
  })

  const lastAiMessage = computed(() => {
    return currentMessages.value.filter(m => m.role === 'assistant').pop()
  })

  const currentEmotion = computed(() => {
    return lastAiMessage.value?.emotion
  })

  const currentPersonality = computed(() => {
    return lastAiMessage.value?.personality
  })

  // Actions
  function addMessage(message: Omit<ChatMessage, 'id' | 'timestamp'>) {
    const newMessage: ChatMessage = {
      ...message,
      id: generateId(),
      timestamp: new Date().toISOString(),
      sessionId: currentSessionId.value
    }
    messages.value.push(newMessage)
    updateSessionLastMessage()
    return newMessage
  }

  function updateMessage(id: string, updates: Partial<ChatMessage>) {
    const index = messages.value.findIndex(m => m.id === id)
    if (index !== -1) {
      messages.value[index] = { ...messages.value[index], ...updates }
      updateSessionLastMessage()
    }
  }

  function deleteMessage(id: string) {
    const index = messages.value.findIndex(m => m.id === id)
    if (index !== -1) {
      messages.value.splice(index, 1)
      updateSessionLastMessage()
    }
  }

  function clearCurrentMessages() {
    messages.value = messages.value.filter(m => m.sessionId !== currentSessionId.value)
    updateSessionLastMessage()
  }

  function createSession(title?: string) {
    const session: ChatSession = {
      id: generateId(),
      title: title || `对话 ${sessions.value.length + 1}`,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messageCount: 0
    }
    sessions.value.unshift(session)
    currentSessionId.value = session.id
    return session
  }

  function updateSession(id: string, updates: Partial<ChatSession>) {
    const index = sessions.value.findIndex(s => s.id === id)
    if (index !== -1) {
      sessions.value[index] = {
        ...sessions.value[index],
        ...updates,
        updatedAt: new Date().toISOString()
      }
    }
  }

  function deleteSession(id: string) {
    const index = sessions.value.findIndex(s => s.id === id)
    if (index !== -1) {
      sessions.value.splice(index, 1)
      // 删除会话的所有消息
      messages.value = messages.value.filter(m => m.sessionId !== id)
      // 如果删除的是当前会话，切换到第一个会话
      if (currentSessionId.value === id && sessions.value.length > 0) {
        currentSessionId.value = sessions.value[0].id
      } else if (sessions.value.length === 0) {
        createSession()
      }
    }
  }

  function switchSession(id: string) {
    currentSessionId.value = id
  }

  function exportSession(format: 'json' | 'markdown' | 'txt') {
    const session = currentSession.value
    if (!session) return ''

    const sessionMessages = currentMessages.value

    switch (format) {
      case 'json':
        return JSON.stringify({
          session,
          messages: sessionMessages
        }, null, 2)

      case 'markdown':
        let md = `# ${session.title}\n\n`
        md += `创建时间: ${new Date(session.createdAt).toLocaleString()}\n\n---\n\n`
        sessionMessages.forEach(msg => {
          const role = msg.role === 'assistant' ? '弥娅' : '你'
          md += `## ${role}\n\n`
          md += `${msg.content}\n\n`
          if (msg.emotion) {
            md += `*情绪: ${msg.emotion.dominant} (${(msg.emotion.intensity * 100).toFixed(0)}%)*\n\n`
          }
        })
        return md

      case 'txt':
        let txt = `${session.title}\n`
        txt += `${'='.repeat(50)}\n\n`
        sessionMessages.forEach(msg => {
          const role = msg.role === 'assistant' ? '弥娅' : '你'
          txt += `[${role}] ${new Date(msg.timestamp).toLocaleTimeString()}\n`
          txt += `${msg.content}\n\n`
        })
        return txt

      default:
        return ''
    }
  }

  function updateSessionLastMessage() {
    const session = currentSession.value
    if (!session) return

    const lastMsg = currentMessages.value[currentMessages.value.length - 1]
    updateSession(session.id, {
      lastMessage: lastMsg?.content?.substring(0, 50) || '',
      messageCount: currentMessages.value.length
    })
  }

  function generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }

  // 初始化默认会话
  function initialize() {
    if (sessions.value.length === 0) {
      const defaultSession = createSession('默认对话')
      addMessage({
        role: 'assistant',
        content: '你好!我是弥娅,你的数字生命伴侣。有什么可以帮助你的吗?',
        sessionId: defaultSession.id
      })
    }
  }

  return {
    // State
    messages,
    sessions,
    currentSessionId,
    isLoading,
    isTyping,
    inputText,

    // Computed
    currentMessages,
    currentSession,
    lastAiMessage,
    currentEmotion,
    currentPersonality,

    // Actions
    addMessage,
    updateMessage,
    deleteMessage,
    clearCurrentMessages,
    createSession,
    updateSession,
    deleteSession,
    switchSession,
    exportSession,
    initialize
  }
})
