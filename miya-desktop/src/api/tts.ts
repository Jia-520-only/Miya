import apiClient from './index'

export interface TTSRequest {
  text: string
  engine?: string
}

export interface TTSResponse {
  success: boolean
  audio_data?: string
  format?: string
  error?: string
}

export const ttsApi = {
  /**
   * 文本转语音
   */
  async speak(data: TTSRequest): Promise<TTSResponse> {
    return apiClient.post('/tts/speak', data)
  },

  /**
   * 获取可用的TTS引擎
   */
  async getEngines(): Promise<{ success: boolean; engines?: string[]; error?: string }> {
    return apiClient.get('/tts/engines')
  }
}

// 音频播放工具
let currentAudio: HTMLAudioElement | null = null

export function playAudioFromBase64(base64Data: string, format: string = 'mp3') {
  // 停止当前播放
  stopAudio()
  
  // 将base64转换为blob URL
  const mimeType = format === 'mp3' ? 'audio/mpeg' : 'audio/wav'
  const audioSrc = `data:${mimeType};base64,${base64Data}`
  
  currentAudio = new Audio(audioSrc)
  currentAudio.play().catch(err => {
    console.error('播放音频失败:', err)
  })
}

export function stopAudio() {
  if (currentAudio) {
    currentAudio.pause()
    currentAudio = null
  }
}

export function isPlaying(): boolean {
  return currentAudio !== null && !currentAudio.paused
}
