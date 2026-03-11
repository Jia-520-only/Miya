import axios from 'axios'
import type { ChatResponse, SystemStatus } from './types'

const API_BASE = 'http://localhost:8000/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

export const chatAPI = {
  // 发送消息
  async sendMessage(message: string, sessionId: string = 'default'): Promise<ChatResponse> {
    const response = await api.post('/chat', {
      message,
      session_id: sessionId,
      platform: 'pc_ui',
    })
    return response.data
  },

  // 获取系统状态
  async getStatus(): Promise<SystemStatus> {
    const response = await api.get('/status')
    return response.data
  },
}

export default api
