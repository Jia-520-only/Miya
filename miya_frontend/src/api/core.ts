import type { StreamChunk } from '@/utils/encoding'
import { aiter } from 'iterator-helper'
import { decodeStreamChunk, readerToMessageStream } from '@/utils/encoding'
import { apiPort, startApiPortPolling } from '@/utils/api-port'
import { ApiClient } from './index'

// Start polling for dynamic port from Electron
startApiPortPolling()

export interface MemoryStats {
  nodeCount: number
  edgeCount: number
  memorySize?: string
}

export interface EmotionState {
  dominant: string
  intensity: number
  emotions: Array<{ name: string, intensity: number }>
  inner_thought?: string
}

export interface SessionInfo {
  id: string
  name: string
  created_at?: string
  updated_at?: string
  message_count?: number
}

export class CoreApiClient extends ApiClient {
  // ── 系统 ──
  async health(): Promise<{ status: string }> {
    return this.instance.get('/health')
  }

  async systemStatus(): Promise<any> {
    return this.instance.get('/api/status')
  }

  // ── 对话 ──
  async chatSend(data: {
    message: string
    session_id?: string
    platform?: string
    user_id?: string
    usg_id?: string
  }): Promise<any> {
    return this.instance.post('/api/chat/send', data, {
      transformResponse: [(d: string) => d],  // 跳过 axios JSON 解析
    }).then((raw: any) => {
      try { return JSON.parse(raw) } catch { return raw }
    })
  }

  async chatStream(data: {
    message: string
    session_id?: string
    platform?: string
    user_id?: string
  }): Promise<AsyncIterableIterator<StreamChunk>> {
    return this.instance.post('/api/chat', data, {
      responseType: 'stream',
      timeout: 0,
      headers: { Accept: 'text/event-stream' },
    }).then(res => {
      const reader = (res as any).data?.getReader?.()
      if (!reader) return aiter((async function* () { /* empty */ })())
      const msgStream = readerToMessageStream(reader)
      return aiter((async function* () {
        for await (const data of msgStream) {
          yield decodeStreamChunk(data)
        }
      })())
    })
  }

  async listSessions(): Promise<SessionInfo[]> {
    return this.instance.get('/api/chat/sessions')
  }

  async getSession(sessionId: string): Promise<any> {
    return this.instance.get(`/api/chat/get_session?session_id=${sessionId}`)
  }

  async newSession(): Promise<{ id: string }> {
    return this.instance.get('/api/chat/new_session')
  }

  async deleteSession(sessionId: string): Promise<void> {
    return this.instance.get(`/api/chat/delete_session?session_id=${sessionId}`)
  }

  async updateSessionName(sessionId: string, name: string): Promise<void> {
    return this.instance.post('/api/chat/update_session_display_name', {
      session_id: sessionId,
      display_name: name,
    })
  }

  // ── 记忆 ──
  async getMemoryStats(): Promise<MemoryStats> {
    return this.instance.get('/api/memory/stats')
  }

  async getMemoryList(limit?: number): Promise<any[]> {
    return this.instance.get(`/api/memory/list${limit ? `?limit=${limit}` : ''}`)
  }

  async searchMemory(query: string, limit?: number): Promise<any[]> {
    return this.instance.get(`/api/memory/search?query=${query}${limit ? `&limit=${limit}` : ''}`)
  }

  // ── 人格 ──
  async getPersonaList(): Promise<any[]> {
    return this.instance.get('/api/persona/list')
  }

  async getCurrentPersona(): Promise<any> {
    return this.instance.get('/api/persona/current')
  }

  async switchPersona(personaId: string): Promise<void> {
    return this.instance.post('/api/persona/switch', { persona_id: personaId })
  }

  // ── 知识图谱 (记忆可视化) ──
  async getQuintuples(filter?: string): Promise<any> {
    const res = await this.instance.get('/api/plug/alkaid/ltm/graph')
    return res?.data || res || { nodes: [], edges: [] }
  }

  async searchQuintuples(query: string): Promise<any> {
    const res = await this.instance.get(`/api/plug/alkaid/ltm/graph/search?query=${encodeURIComponent(query)}`)
    return res?.data || res || { nodes: [], edges: [] }
  }

  async addMemoryEntry(data: { subject: string, predicate: string, obj: string }): Promise<any> {
    return this.instance.post('/api/memory/add', {
      subject: data.subject,
      predicate: data.predicate,
      object: data.obj,
      type: 'memory',
    })
  }

  // ── 模型池 ──
  async listModels(): Promise<{ models: Array<{ id: string; name: string; type: string; provider: string; enabled: boolean; priority: number }>; count: number }> {
    return this.instance.get('/api/models/list')
  }

  async getModelsStatus(): Promise<{ total: number; enabled: number; disabled: number; by_type: Record<string, { enabled: number; total: number }> }> {
    return this.instance.get('/api/models/status')
  }

  async getModelsRouting(taskType?: string): Promise<any> {
    const params = taskType ? `?task_type=${encodeURIComponent(taskType)}` : ''
    return this.instance.get(`/api/models/routing${params}`)
  }
  async getConfig(): Promise<any> {
    return this.instance.get('/api/config/get')
  }

  // ── MCP 工具调用 ──
  async mcpCall(service: string, tool: string, params: Record<string, any> = {}): Promise<any> {
    return this.instance.post('/api/mcp/call', { service, tool, ...params }, {
      transformRequest: [(d: any) => JSON.stringify(d)],
      transformResponse: [(d: string) => {
        try { return JSON.parse(d) } catch { return d }
      }],
    })
  }

  async getCameraControl(): Promise<{ success: boolean, state: Record<string, any> }> {
    return this.instance.get('/api/camera/control')
  }

  async setCameraControl(data: {
    mode: 'off' | 'companion' | 'snapshot'
    local_only?: boolean
    action_recognition?: boolean
    autonomous?: boolean
  }): Promise<{ success: boolean, state: Record<string, any> }> {
    return this.instance.post('/api/camera/control', data)
  }

  async getCameraRequest(): Promise<{ success: boolean, request: Record<string, any> | null }> {
    return this.instance.get('/api/camera/request')
  }

  async publishCameraResult(
    requestId: string,
    result: Record<string, any>,
    extra: { query?: string, mode?: string, localOnly?: boolean } = {},
  ): Promise<any> {
    // `query` and the mode are what let the stored observation keep the question
    // it answered; they used to be omitted, so every record lost them.
    return this.instance.post('/api/camera/result', {
      request_id: requestId,
      result,
      ...(extra.query !== undefined ? { query: extra.query } : {}),
      ...(extra.mode !== undefined ? { mode: extra.mode } : {}),
      ...(extra.localOnly !== undefined ? { local_only: extra.localOnly } : {}),
    })
  }

  async getVisionPresence(): Promise<{ success: boolean, presence: Record<string, any> | null }> {
    return this.instance.get('/api/vision/presence')
  }

  async getCameraDevices(probe = true): Promise<{ success: boolean, devices: Array<Record<string, any>>, message?: string }> {
    return this.instance.get('/api/camera/devices', { params: { probe } })
  }

  /**
   * The backend's camera inventory.
   *
   * Field names arrive camelCased: `api/index.ts` runs every response through
   * `camelcaseKeys`, so `usable_indices` is `usableIndices` by the time any
   * caller sees it. Reading the snake_case name silently yields `undefined`.
   */
  async getCameraSources(): Promise<{
    success: boolean
    devices: Array<Record<string, any>>
    names?: Record<string, string>
    message?: string
    usableIndices?: number[]
    sleepingIndices?: number[]
    unopenableIndices?: number[]
  }> {
    return this.instance.get('/api/camera/sources')
  }

  async getVisionActivity(): Promise<{ success: boolean, activity: Record<string, any> | null, message?: string }> {
    return this.instance.get('/api/vision/activity')
  }

  async getVisionAgent(): Promise<{ success: boolean, agent: Record<string, any> | null, agency?: Record<string, any> }> {
    return this.instance.get('/api/vision/agent')
  }

  async setVisionAgent(action: 'start' | 'stop' | 'tick' | 'status', extra: Record<string, any> = {}): Promise<any> {
    return this.instance.post('/api/vision/agent', { action, ...extra })
  }

  /** What Miya has been wanting to say while watching. */
  async getVisionVoice(): Promise<{ success: boolean, next: Record<string, any> | null, pending: Array<Record<string, any>>, count: number }> {
    return this.instance.get('/api/vision/voice')
  }

  /** Take (and remove) the next thing she wanted to say, or clear them all. */
  async takeVisionVoice(action: 'take' | 'clear' = 'take'): Promise<any> {
    return this.instance.post('/api/vision/voice', { action })
  }

  /** Miya's observation rounds: what she saw, how she read it, what she decided. */
  async getVisionStream(): Promise<{
    success: boolean
    status: Record<string, any>
    events: Array<Record<string, any>>
    cadence: Record<string, any>
  }> {
    return this.instance.get('/api/vision/stream')
  }

  /** One round in full, including thumbnails when they are enabled. */
  async getVisionEvent(eventId: string): Promise<{ success: boolean, event: Record<string, any> | null }> {
    return this.instance.get(`/api/vision/stream/${encodeURIComponent(eventId)}`)
  }

  /** Turn thumbnail storage on or off (off also forgets what was kept). */
  async setVisionThumbnails(enabled: boolean): Promise<{ success: boolean, status: Record<string, any> | null }> {
    return this.instance.post('/api/vision/thumbnails', { enabled })
  }

  /**
   * Whether what she sees can reach her voice.
   *
   * Exists because this failure is invisible: the observation loop and trackers
   * all look healthy while nothing is ever submitted to the proactive chain.
   */
  async getVisionBridge(): Promise<{ success: boolean, bridge: Record<string, any> | null }> {
    return this.instance.get('/api/vision/bridge')
  }

  /** Which side owns which camera, and whether a frame is currently held. */
  async getVisionSources(): Promise<{
    success: boolean
    sources: Record<string, any>
    names?: Record<string, string>
    browserOwned: number[]
    backendOwned: number[]
    readersRunning: number[]
  }> {
    return this.instance.get('/api/vision/sources')
  }

  /**
   * Absolute URL for one camera's still frame.
   *
   * An `<img src>` does not go through axios, so it gets no `baseURL` fallback: a
   * relative path resolves against the page origin instead - the Vite dev server
   * on :5173, or `file://` in a packaged build - and the picture never loads. The
   * discovered API port is the only correct origin.
   */
  cameraPreviewUrl(index: number, nonce: number | string = ''): string {
    const query = new URLSearchParams({ max_age: '10' })
    if (nonce) query.set('_', String(nonce))
    return `${this.endpoint}/api/vision/preview/${index}?${query.toString()}`
  }

  // ── 会话 ──
  async getSessions(): Promise<{ sessions: any[] }> {
    const res: any = await this.instance.get('/api/chat/sessions')
    return { sessions: res?.data ?? [] }
  }

  // ── 画板 ──
  async getGallery(options: { limit: number }): Promise<{ images: any[] }> {
    return this.instance.get(`/api/art/gallery?limit=${options.limit}`)
  }

  async generate(params: {
    prompt: string; provider: string; negativePrompt: string
    width: number; height: number; steps: number; cfgScale: number
    seed: number | null; numImages: number; style: string
  }): Promise<{ success: boolean; images?: any[]; error?: string }> {
    return this.instance.post('/api/art/generate', params)
  }

  async deleteImage(id: string): Promise<void> {
    return this.instance.post('/api/art/delete', { id })
  }

  async clearGallery(): Promise<void> {
    return this.instance.post('/api/art/clear')
  }

  getImageUrl(filename: string): string {
    return `${this.endpoint}/api/art/image/${encodeURIComponent(filename)}`
  }

  async getProviders(): Promise<{ providers: Array<{ name: string; available: boolean }> }> {
    return this.instance.get('/api/art/providers')
  }

  // ── 系统提示词 ──
  async getSystemPrompt(): Promise<{ prompt: string }> {
    return this.instance.get('/api/system/prompt')
  }

  async setSystemPrompt(content: string): Promise<void> {
    return this.instance.post('/api/system/prompt', { prompt: content })
  }

  async setSystemConfig(payload: Record<string, any>): Promise<void> {
    return this.instance.post('/api/config/set', payload)
  }

  // ── 文件 ──
  async parseDocument(file: File): Promise<{ content: string; truncated?: boolean }> {
    const form = new FormData()
    form.append('file', file)
    return this.instance.post('/api/document/parse', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  }

  async uploadDocument(file: File): Promise<{ filePath?: string }> {
    const form = new FormData()
    form.append('file', file)
    return this.instance.post('/api/document/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  }

  // ── 语音 ──
  async transcribeAudio(audioBlob: Blob, options: { language: string }): Promise<{ text: string }> {
    const form = new FormData()
    form.append('audio', audioBlob, 'recording.wav')
    form.append('language', options.language)
    return this.instance.post('/api/audio/transcribe', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  }

  // ── 调试 / 诊断 ──
  async systemInfo(): Promise<any> {
    return this.instance.get('/api/system/info')
  }
}

export default new CoreApiClient(apiPort)
