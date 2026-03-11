import apiClient from './index'
import type { SystemStatus, SystemInfo } from '../stores/system'

export const systemApi = {
  /**
   * 获取系统状态
   */
  async getStatus(): Promise<SystemStatus> {
    return apiClient.get('/status')
  },

  /**
   * 获取系统信息
   */
  async getInfo(): Promise<SystemInfo> {
    return apiClient.get('/desktop/system/info')
  },

  /**
   * 执行终端命令
   */
  async executeCommand(command: string): Promise<string> {
    return apiClient.post(`/desktop/terminal/execute?command=${encodeURIComponent(command)}`)
  },

  /**
   * 健康检查
   */
  async healthCheck(): Promise<{ status: string }> {
    return apiClient.get('/health')
  }
}
