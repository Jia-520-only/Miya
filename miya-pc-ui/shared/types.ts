// 消息类型
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  emotion?: EmotionState
}

// 情绪状态
export interface EmotionState {
  happiness: number
  sadness: number
  anger: number
  fear: number
  surprise: number
  calm: number
}

// 系统状态
export interface SystemStatus {
  identity: {
    name: string
    version: string
  }
  personality: {
    warmth: number
    logic: number
    creativity: number
    empathy: number
    resilience: number
  }
  emotion: EmotionState
  memory_stats: {
    short_term: number
    long_term: number
    vector_count: number
  }
}

// API 响应
export interface ChatResponse {
  response: string
  emotion: EmotionState
  timestamp: string
  tts_url?: string
}
