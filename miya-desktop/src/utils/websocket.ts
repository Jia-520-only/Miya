/**
 * 跨端消息服务
 * 用于接收来自其他终端（QQ、终端、Web）的消息
 * 使用HTTP轮询方式
 */

import { ref } from 'vue'
import apiClient from '../api/index'

export interface CrossTerminalMessage {
  id: string
  source_type: string
  source_id: string
  target_type: string
  target_id: string
  message_type: string
  content: string
  metadata: Record<string, any>
  timestamp: number
}

export interface CrossTerminalNotification {
  id: string
  title: string
  content: string
  timestamp: number
  source: string
}

class CrossTerminalService {
  private pollTimer: number | null = null
  private pollInterval = 2000  // 2秒轮询一次
  private lastMessageId = ''

  // 响应式状态
  public isConnected = ref(false)
  public notifications = ref<CrossTerminalNotification[]>([])
  public messages = ref<CrossTerminalMessage[]>([])
  public lastError = ref<string>('')

  // 回调函数
  private onNotificationCallbacks: ((notification: CrossTerminalNotification) => void)[] = []
  private onMessageCallbacks: ((message: CrossTerminalMessage) => void)[] = []

  /**
   * 启动轮询
   */
  startPolling() {
    if (this.pollTimer) {
      console.log('[CrossTerminal] 轮询已在运行')
      return
    }

    console.log('[CrossTerminal] 启动消息轮询...')
    this.poll()
    this.pollTimer = window.setInterval(() => {
      this.poll()
    }, this.pollInterval)
  }

  /**
   * 停止轮询
   */
  stopPolling() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer)
      this.pollTimer = null
      console.log('[CrossTerminal] 已停止轮询')
    }
    this.isConnected.value = false
  }

  /**
   * 轮询获取消息
   */
  private async poll() {
    try {
      const response = await apiClient.get('/cross-terminal/messages', {
        params: {
          last_id: this.lastMessageId,
          limit: 20
        }
      })

      if (response.success && response.messages && response.messages.length > 0) {
        this.isConnected.value = true
        this.lastError.value = ''

        // 处理新消息
        for (const msg of response.messages) {
          this.handleMessage(msg)
          this.lastMessageId = msg.id
        }
      } else if (!response.success) {
        this.lastError.value = response.error || '获取消息失败'
      }
    } catch (e: any) {
      console.error('[CrossTerminal] 轮询失败:', e)
      this.isConnected.value = false
      this.lastError.value = e.message || '连接失败'
    }
  }

  /**
   * 处理收到的消息
   */
  private handleMessage(data: CrossTerminalMessage) {
    console.log('[CrossTerminal] 收到消息:', data)

    // 添加到消息列表
    this.messages.value.unshift(data)

    // 只保留最近100条消息
    if (this.messages.value.length > 100) {
      this.messages.value = this.messages.value.slice(0, 100)
    }

    // 如果是通知类型，显示通知
    if (data.message_type === 'notification' || data.message_type === 'text') {
      const notification: CrossTerminalNotification = {
        id: data.id,
        title: '来自其他端的消息',
        content: data.content,
        timestamp: data.timestamp,
        source: data.source_type
      }

      this.notifications.value.unshift(notification)

      // 只保留最近50条通知
      if (this.notifications.value.length > 50) {
        this.notifications.value = this.notifications.value.slice(0, 50)
      }

      // 触发通知回调
      this.onNotificationCallbacks.forEach(cb => cb(notification))
    }

    // 触发消息回调
    this.onMessageCallbacks.forEach(cb => cb(data))
  }

  /**
   * 发送跨端消息
   */
  async sendMessage(target: string, content: string, messageType: string = 'text') {
    try {
      const response = await apiClient.post('/cross-terminal/send', null, {
        params: {
          target,
          content,
          message_type: messageType
        }
      })
      return response
    } catch (e: any) {
      console.error('[CrossTerminal] 发送消息失败:', e)
      return { success: false, error: e.message }
    }
  }

  /**
   * 同步状态
   */
  async syncState(key: string, value: string) {
    try {
      const response = await apiClient.post('/cross-terminal/sync-state', null, {
        params: { key, value }
      })
      return response
    } catch (e: any) {
      console.error('[CrossTerminal] 同步状态失败:', e)
      return { success: false, error: e.message }
    }
  }

  /**
   * 获取在线设备
   */
  async getDevices() {
    try {
      const response = await apiClient.get('/cross-terminal/devices')
      return response
    } catch (e: any) {
      console.error('[CrossTerminal] 获取设备失败:', e)
      return { success: false, devices: [], error: e.message }
    }
  }

  /**
   * 注册通知回调
   */
  onNotification(callback: (notification: CrossTerminalNotification) => void) {
    this.onNotificationCallbacks.push(callback)
    return () => {
      const index = this.onNotificationCallbacks.indexOf(callback)
      if (index > -1) {
        this.onNotificationCallbacks.splice(index, 1)
      }
    }
  }

  /**
   * 注册消息回调
   */
  onMessage(callback: (message: CrossTerminalMessage) => void) {
    this.onMessageCallbacks.push(callback)
    return () => {
      const index = this.onMessageCallbacks.indexOf(callback)
      if (index > -1) {
        this.onMessageCallbacks.splice(index, 1)
      }
    }
  }

  /**
   * 清除所有通知
   */
  clearNotifications() {
    this.notifications.value = []
  }
}

// 导出单例
export const crossTerminalService = new CrossTerminalService()
export default crossTerminalService
