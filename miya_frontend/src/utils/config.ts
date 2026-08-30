import { ref, watch } from 'vue'
import API from '@/api/core'
import { apiPort, discoverApiPort } from '@/utils/api-port'

export const DEFAULT_CONFIG = {
  system: {
    version: '8.0.0',
    ai_name: '弥娅',
    active_character: '弥娅',
    voice_enabled: true,
    stream_mode: true,
    debug: false,
    log_level: 'INFO',
    save_prompts: true,
  },
  api: {
    api_key: 'your-api-key-here',
    base_url: 'https://api.deepseek.com/v1',
    model: 'deepseek-v4-flash',
    temperature: 0.7,
    max_tokens: 8192,
    max_history_rounds: 10,
    persistent_context: true,
    context_load_days: 3,
    context_parse_logs: true,
    applied_proxy: false,
  },
  api_server: {
    enabled: true,
    host: '127.0.0.1',
    port: (typeof window !== 'undefined' && (window as any).__MIYA_API_PORT__) || Number(import.meta.env.VITE_API_PORT) || 9800,
    auto_start: true,
    docs_enabled: true,
  },
  agentserver: {
    enabled: true,
    host: '127.0.0.1',
    port: 8001,
    auto_start: true,
  },
  mcpserver: {
    enabled: true,
    host: '127.0.0.1',
    port: 8003,
    auto_start: true,
    agent_discovery: true,
  },
  grag: {
    enabled: true,
    auto_extract: true,
    context_length: 5,
    similarity_threshold: 0.6,
    neo4j_uri: 'neo4j://127.0.0.1:7687',
    neo4j_user: 'neo4j',
    neo4j_password: 'your-neo4j-password',
    neo4j_database: 'neo4j',
    extraction_timeout: 12,
    extraction_retries: 2,
    base_timeout: 15,
  },
  browser: {
    playwright_headless: false,
  },
  tts: {
    api_key: '',
    port: 5048,
    default_voice: 'zh-CN-XiaoxiaoNeural',
    default_format: 'mp3',
    default_speed: 1.0,
    default_language: 'zh-CN',
    remove_filter: false,
    expand_api: true,
    require_api_key: false,
  },
  voice_realtime: {
    enabled: false,
    provider: 'qwen',
    api_key: 'your-dashscope-api-key-here',
    model: 'qwen3-asr-realtime',
    tts_model: 'qwen-tts-realtime',
    asr_model: 'qwen3-asr-realtime',
    voice: 'Cherry',
    voice_mode: 'auto',
    tts_voice: 'zh-CN-XiaoyiNeural',
    input_sample_rate: 16000,
    output_sample_rate: 24000,
    chunk_size_ms: 200,
    vad_threshold: 0.02,
    echo_suppression: true,
    min_user_interval: 2.0,
    cooldown_duration: 1.0,
    max_user_speech: 30.0,
    debug: false,
    integrate_with_memory: true,
    show_in_chat: true,
    use_api_server: true,
  },
  weather: {
    api_key: 'your-weather-api-key-or-leave-empty',
  },
  mqtt: {
    enabled: false,
    broker: 'mqtt-broker-address',
    port: 1883,
    topic: 'naga/agent/topic',
    client_id: 'naga-agent-client',
    username: 'mqtt-username',
    password: 'mqtt-password',
    keepalive: 60,
    qos: 1,
  },
  ui: {
    user_name: '用户',
    owner_id: '1523878699',
    desktop_usg_id: 'desktop_user',
    bg_alpha: 0.81,
    window_bg_alpha: 128,
    mac_btn_size: 36,
    mac_btn_margin: 16,
    mac_btn_gap: 12,
    animation_duration: 600,
  },
  live2d: {
    enabled: false,
    model_path: '',
    fallback_image: 'ui/img/standby.png',
    auto_switch: true,
    animation_enabled: true,
    touch_interaction: true,
  },
  floating: {
    enabled: false,
  },
  memory_server: {
    url: 'http://localhost:8004',
    token: null as string | null,
  },
  embedding: {
    model: 'BAAI/bge-large-zh-v1.5',
    api_base: '',
    api_key: '',
  },
  web_live2d: {
    ssaa: 2,
    model: {
      source: '',
      x: 0.3,
      y: 1.0,
      size: 6800,
    },
    face_y_ratio: 0.13,
    tracking_hold_delay_ms: 100,
  },
  system_check: {
    passed: false,
    timestamp: '',
    python_version: '',
    project_path: '',
  },
  online_search: {
    searxng_url: 'https://searxng.pylindex.top',
    engines: [
      'google',
    ],
    num_results: 5,
  },
  computer_control: {
    enabled: true,
    model: 'gemini-2.5-flash',
    model_url: 'https://open.bigmodel.cn/api/paas/v4',
    api_key: '',
    grounding_model: 'gemini-2.5-flash',
    grounding_url: 'https://open.bigmodel.cn/api/paas/v4',
    grounding_api_key: '',
    screen_width: 1920,
    screen_height: 1080,
    max_dim_size: 1920,
    dpi_awareness: true,
    safe_mode: true,
  },
  crawl4ai: {
    headless: true,
    timeout: 30000,
    user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    viewport_width: 1280,
    viewport_height: 720,
  },
  notifications: {},
}

export const SYSTEM_PROMPT = ref('')

let promptWatchStop: (() => void) | null = null
const CONFIG_SYNC_DELAY_MS = 400

function loadSystemPrompt() {
  API.getSystemPrompt().then((res) => {
    SYSTEM_PROMPT.value = res.prompt
    if (!promptWatchStop) {
      promptWatchStop = watch(SYSTEM_PROMPT, (content) => {
        API.setSystemPrompt(content)
      })
    }
  }).catch(() => {
    setTimeout(loadSystemPrompt, 3000)
  })
}

export type Config = typeof DEFAULT_CONFIG

export const CONFIG = ref<Config>(JSON.parse(JSON.stringify(DEFAULT_CONFIG)))
export const backendConnected = ref(false)

function deepMerge<T extends Record<string, any>>(target: T, source: Record<string, any>): T {
  const result = { ...target }
  for (const key of Object.keys(source)) {
    const tVal = result[key as keyof T]
    const sVal = source[key]
    if (
      tVal && sVal
      && typeof tVal === 'object' && !Array.isArray(tVal)
      && typeof sVal === 'object' && !Array.isArray(sVal)
    ) {
      ;(result as any)[key] = deepMerge(tVal, sVal)
    }
    else {
      ;(result as any)[key] = sVal
    }
  }
  return result
}

let configWatchStop: (() => void) | null = null
let configSyncTimer: ReturnType<typeof setTimeout> | null = null

function scheduleConfigSync(config: Config) {
  if (configSyncTimer) {
    clearTimeout(configSyncTimer)
  }

  const payload: Config = JSON.parse(JSON.stringify(config))
  configSyncTimer = setTimeout(() => {
    API.setSystemConfig(payload).catch(() => {
    })
  }, CONFIG_SYNC_DELAY_MS)
}

let connectRetryDelay = 300
let connectRetries = 0
const MAX_RETRIES = 5

function connectBackend() {
  const tryConnect = async () => {
    let port = apiPort.value
    let healthOk = false
    const doHealthCheck = async (p: number) => {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 2000)
      try {
        const r = await fetch(`http://localhost:${p}/health`, { signal: controller.signal })
        clearTimeout(timer)
        const res = await r.json()
        return res.status === 'healthy'
      }
      catch {
        clearTimeout(timer)
        return false
      }
    }
    healthOk = await doHealthCheck(port)
    if (!healthOk) {
      port = await discoverApiPort()
      if (port !== apiPort.value) {
        healthOk = await doHealthCheck(port)
      }
    }
    if (healthOk) {
      backendConnected.value = true
      connectRetryDelay = 300
      console.log('[MIYA] 后端已连接')
      if (!configWatchStop) {
        configWatchStop = watch(CONFIG, (nextConfig) => {
          if (!backendConnected.value) return
          scheduleConfigSync(nextConfig)
        }, { deep: true })
      }
    }
    else {
      connectRetries++
      if (connectRetries <= MAX_RETRIES) {
        setTimeout(connectBackend, connectRetryDelay)
        connectRetryDelay = Math.min(connectRetryDelay * 2, 5000)
      }
      else {
        console.log('[MIYA] 后端未检测到，进入离线模式')
      }
    }
  }
  tryConnect()
}

connectBackend()
