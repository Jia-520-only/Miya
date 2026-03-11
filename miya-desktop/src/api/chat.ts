import apiClient from './index'
import type { ChatMessage, EmotionState, PersonalityProfile } from '../stores/chat'

export interface ChatRequest {
  message: string
  session_id: string
  platform: string
}

export interface ChatResponse {
  response: string
  emotion?: EmotionState
  personality?: PersonalityProfile
  tools_used?: string[]
  memory_retrieved?: boolean
  timestamp: string
}

export const chatApi = {
  /**
   * 发送消息
   */
  async sendMessage(data: ChatRequest): Promise<ChatResponse> {
    return apiClient.post('/chat', data)
  },

  /**
   * 获取会话历史
   */
  async getHistory(sessionId: string): Promise<ChatMessage[]> {
    return apiClient.get(`/history/${sessionId}`)
  },

  /**
   * 删除会话历史
   */
  async deleteHistory(sessionId: string): Promise<void> {
    return apiClient.delete(`/history/${sessionId}`)
  }
}
