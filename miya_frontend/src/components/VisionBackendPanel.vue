<script setup lang="ts">
/**
 * Miya's camera console: what she sees, whether she is healthy, and the few
 * things worth controlling.
 *
 * This is a *monitor*, not a log. An earlier version listed every observation
 * round as a feed, which answered "what happened" but not the question Jia
 * actually has: is she looking at me right now, and is anything broken. The
 * health row comes first for that reason; the history is below it.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import API from '@/api/core'
import { useCameraVision } from '@/utils/cameraVision'

const camera = useCameraVision()
const expanded = ref<string>('')
const details = ref<Record<string, Record<string, any>>>({})
const loadingDetail = ref(false)
const thumbBusy = ref(false)
const voiceBusy = ref(false)
const previewNonce = ref(0)
let previewTimer: ReturnType<typeof setInterval> | null = null

const events = computed<Array<Record<string, any>>>(() => camera.visionEvents.value.slice(0, 8))
const streamStatus = computed<Record<string, any>>(() => camera.visionStreamStatus.value)
const cadence = computed<Record<string, any>>(() => camera.visionCadence.value)
const agent = computed<Record<string, any>>(() => camera.agentState.value || {})
const health = computed<Record<string, any>>(() => camera.cameraHealth.value || {})
const thumbsOn = computed(() => camera.thumbnailsEnabled.value)
const sources = computed<Record<string, any>>(() => camera.visionSources.value || {})
const voice = computed<Record<string, any> | null>(() => camera.agentVoice.value)
const pendingVoice = computed<Array<Record<string, any>>>(() => camera.agentVoiceQueue.value || [])
const intents = computed<Array<Record<string, any>>>(() => camera.agentAgency.value?.intents || [])
const bridge = computed<Record<string, any> | null>(() => camera.visionBridge.value)
/** null = not yet known; true = Miya's own proactive path is available. */
const bridgeReady = computed<boolean | null>(() => {
  const value = bridge.value
  if (!value || typeof value.running !== 'boolean') return null
  return value.running
})

/** The one-line answer to "is she okay". */
const healthView = computed(() => {
  const running = Boolean(agent.value.running)
  const usable = Number(health.value.usableCount || 0)
  const total = Number(health.value.count || 0)
  const sleeping = Number(health.value.sleepingCount || 0)
  const blocked = Number(health.value.unopenableCount || 0)
  const unknown = Math.max(0, total - usable - sleeping - blocked)
  if (!running) {
    return { tone: 'off', label: '观察已停止', detail: '她现在没有在看。' }
  }
  if (usable === 0) {
    if (unknown === total && total > 0) {
      return { tone: 'warn', label: '等待摄像头探测', detail: `已发现 ${total} 台，正在等待第一帧。` }
    }
    return { tone: 'bad', label: '看不到你', detail: `${total - unknown} 台已探测设备现在都没画面。${unknown ? `另有 ${unknown} 台等待探测。` : ''}` }
  }
  const interval = Number(cadence.value.current_interval || agent.value.interval_seconds || 0)
  const watching = Number(cadence.value.unchanged_streak || 0) < Number(cadence.value.slow_after || 3)
  return {
    tone: sleeping + blocked > 0 ? 'warn' : 'good',
    label: watching ? '正在看着你' : '画面没什么变化，放慢了',
    detail: `${usable}/${total} 台有画面${sleeping ? ` · ${sleeping} 台无画面` : ''}${blocked ? ` · ${blocked} 台打不开` : ''}${unknown ? ` · ${unknown} 台待探测` : ''} · 每 ${Math.round(interval)} 秒看一次`,
  }
})

const lastLookText = computed(() => {
  const at = Number(agent.value.last_tick || 0)
  if (!at) return '还没有看过'
  const seconds = Math.max(0, Date.now() / 1000 - at)
  if (seconds < 60) return `${Math.round(seconds)} 秒前看过`
  return `${Math.round(seconds / 60)} 分钟前看过`
})

const latestEvent = computed<Record<string, any> | null>(() => camera.visionEvents.value[0] || null)

function clock(at: number): string {
  if (!at) return '--:--:--'
  return new Date(at * 1000).toLocaleTimeString('zh-CN', { hour12: false })
}

function seconds(value: unknown): string {
  const num = Number(value || 0)
  if (!num) return '—'
  return num < 1 ? `${Math.round(num * 1000)}ms` : `${num.toFixed(2)}s`
}

function deviceLabel(index: unknown): string {
  if (index === -1 || index === null || index === undefined) return '浏览器那一路'
  // The backend reports DirectShow names per index. A bare "#2" told nobody
  // whether that was the laptop, the phone, or the 4K camera.
  const name = camera.backendNames?.value?.[String(index)]
    || camera.cameraHealth?.value?.names?.[String(index)]
  return name ? `${name}` : `#${index}`
}

function backendFrameUrl(index: number): string {
  // Absolute, on the discovered API port: an <img> gets no axios baseURL.
  return API.cameraPreviewUrl(index, previewNonce.value)
}

async function toggle(eventId: string) {
  if (expanded.value === eventId) {
    expanded.value = ''
    return
  }
  expanded.value = eventId
  if (details.value[eventId]) return
  loadingDetail.value = true
  try {
    const detail = await camera.loadVisionEvent(eventId)
    if (detail) details.value = { ...details.value, [eventId]: detail }
  } finally {
    loadingDetail.value = false
  }
}

function eventThumbs(eventId: string): Array<Record<string, any>> {
  return details.value[eventId]?.thumbnails || []
}

async function toggleThumbnails() {
  if (thumbBusy.value) return
  thumbBusy.value = true
  try {
    await camera.setThumbnailStorage(!thumbsOn.value)
  } finally {
    thumbBusy.value = false
  }
}

async function toggleWatching() {
  // The backend reads the verb `start` / `stop`; passing `!running` sent the
  // literal `true`, which matched neither branch and silently did nothing - so
  // the button that is supposed to stop her watching never stopped anything.
  await camera.setWatching(agent.value.running ? 'stop' : 'start')
}

async function speakNext() {
  if (voiceBusy.value) return
  voiceBusy.value = true
  try {
    await camera.takeAgentVoice()
  } finally {
    voiceBusy.value = false
  }
}

onMounted(() => {
  void camera.refreshCameraHealth()
  previewTimer = setInterval(() => {
    previewNonce.value = Date.now()
  }, 3000)
})
onBeforeUnmount(() => {
  if (previewTimer) clearInterval(previewTimer)
  previewTimer = null
})
</script>

<template>
  <section class="cap-panel">
    <!-- Health first: the question is "is she looking at me", not "what happened". -->
    <header class="cap-health" :class="healthView.tone">
      <span class="cap-health-dot" />
      <div class="cap-health-text">
        <strong>{{ healthView.label }}</strong>
        <small>{{ healthView.detail }}</small>
      </div>
      <div class="cap-health-meta">
        <span>{{ lastLookText }}</span>
        <span>已看 {{ agent.ticks || 0 }} 次</span>
      </div>
      <button class="cap-btn" :class="{ stop: agent.running }" @click="toggleWatching">
        {{ agent.running ? '让她停下' : '让她开始看' }}
      </button>
    </header>

    <p v-if="agent.last_error" class="cap-health-error">最近一次出错：{{ agent.last_error }}</p>

    <!-- Can what she sees actually reach her voice? Invisible when broken. -->
    <div class="cap-bridge" :class="{ broken: bridgeReady === false }">
      <span class="cap-label">能不能开口</span>
      <span v-if="bridgeReady === null" class="cap-bridge-text">状态未知</span>
      <span v-else-if="bridgeReady" class="cap-bridge-text">
        由弥娅主动链路决定是否开口
        <em v-if="bridge?.owner_target_id"> · 对象 {{ bridge.owner_target_id }}</em>
      </span>
      <span v-else class="cap-bridge-text">
        主动链路状态不可用
      </span>
    </div>

    <!-- Every camera, including the ones that cannot currently see. -->
    <div v-if="health.devices?.length" class="cap-devices">
      <span class="cap-label">摄像头</span>
      <ul class="cap-device-list">
        <li v-for="device in health.devices" :key="device.index" class="cap-device" :class="{ bad: !device.usable }">
          <span class="cap-device-name">{{ deviceLabel(device.index) }}</span>
          <span class="cap-device-state">
            <template v-if="!device.checked">
              已发现 · 等待首次画面探测
            </template>
            <template v-else-if="device.usable">
              可用 · 亮度 {{ Math.round(device.luminance || 0) }}
              <template v-if="device.sees_people"> · 看到人</template>
            </template>
            <template v-else>
              {{ device.reason || '暂时没有画面' }}
              <small v-if="device.retryInSeconds > 0"> · {{ Math.ceil(device.retryInSeconds) }} 秒后重试</small>
            </template>
            <small v-if="device.lastReadingText" class="cap-device-reading">
              · 最近识别：{{ device.lastReadingText }}
            </small>
          </span>
          <span v-if="sources.sources?.[device.index]" class="cap-device-owner">
            {{ sources.sources[device.index].owner === 'browser' ? '预览持有' : '弥娅持有' }}
          </span>
        </li>
      </ul>
    </div>

    <!-- The angles the backend holds. The browser-held one is the big preview above. -->
    <div v-if="sources.backendOwned?.length" class="cap-sources">
      <span class="cap-label">弥娅自己看到的画面</span>
      <div class="cap-sources-strip">
        <figure v-for="index in sources.backendOwned" :key="index" class="cap-source">
          <img :src="backendFrameUrl(index)" alt="" class="cap-source-media">
          <figcaption>{{ deviceLabel(index) }} · 约 1 帧/3 秒</figcaption>
        </figure>
      </div>
    </div>

    <!-- What she concluded most recently, in her own words. -->
    <div v-if="latestEvent" class="cap-latest">
      <span class="cap-label">她最近看到的</span>
      <p class="cap-latest-text">{{ latestEvent.summary || latestEvent.reading_text || '（没有判断）' }}</p>
      <p class="cap-latest-meta">
        {{ clock(latestEvent.at) }}
        <template v-if="latestEvent.expression_text"> · 脸：{{ latestEvent.expression_text }}</template>
        <template v-if="latestEvent.interpreter"> · 由 {{ latestEvent.interpreter }} 解读</template>
        <template v-else-if="!latestEvent.interpreted"> · 仅本地线索，没有模型解读</template>
      </p>
    </div>

    <!-- What she has been wanting to say. Without this she watches all evening and never speaks. -->
    <div v-if="voice || pendingVoice.length" class="cap-voice">
      <span class="cap-label">她想对你说</span>
      <div class="cap-voice-body">
        <p class="cap-voice-text">「{{ voice?.message || pendingVoice[0]?.message || '' }}」</p>
        <button class="cap-btn" :disabled="voiceBusy" @click="speakNext">
          {{ pendingVoice.length > 1 ? `说出来（还有 ${pendingVoice.length - 1} 条）` : '说出来' }}
        </button>
      </div>
    </div>

    <!-- Her own reasons for watching. -->
    <div v-if="intents.length" class="cap-intents">
      <span class="cap-label">她在留意</span>
      <ul>
        <li v-for="intent in intents" :key="intent.id">{{ intent.text }}</li>
      </ul>
    </div>

    <!-- History, deliberately short: this is context, not the point of the page. -->
    <div class="cap-history">
      <div class="cap-history-head">
        <span class="cap-label">最近几次观察</span>
        <label class="cap-thumb-toggle" :title="thumbsOn ? '关闭会一并清空已存的' : '默认不保存任何画面'">
          <input type="checkbox" :checked="thumbsOn" :disabled="thumbBusy" @change="toggleThumbnails">
          <span>保存缩略图{{ thumbsOn ? '（已开启）' : '（默认关闭）' }}</span>
        </label>
      </div>

      <p v-if="thumbsOn" class="cap-privacy-warn">
        正在保存缩略图：每个观察点留一张 160px 小图，只在本机、只保留最近
        {{ streamStatus.thumbnail_max_events || 80 }} 个。关闭会立刻清空。
      </p>

      <div v-if="!events.length" class="cap-empty">还没有观察记录。她开始看之后这里会逐条显示。</div>

      <ol v-else class="cap-list">
        <li v-for="event in events" :key="event.id" class="cap-row" :class="{ open: expanded === event.id }">
          <button class="cap-row-head" @click="toggle(event.id)">
            <span class="cap-dot" :class="{ miss: !event.interpreted }" />
            <span class="cap-time">{{ clock(event.at) }}</span>
            <span class="cap-headline">{{ event.summary || event.reading_text || '看了一眼' }}</span>
            <span class="cap-tags">
              <em v-if="event.said" class="cap-tag said">说了话</em>
              <em v-else-if="event.notable" class="cap-tag notable">觉得值得说</em>
              <em v-if="!event.interpreted" class="cap-tag degraded">仅本地</em>
              <em class="cap-tag">{{ seconds(event.timing?.total) }}</em>
            </span>
          </button>

          <div v-if="expanded === event.id" class="cap-detail">
            <div class="cap-chain">
              <div class="cap-step">
                <span class="cap-step-label">摄像头</span>
                <span class="cap-step-value">
                  <template v-if="event.cameras_used?.length">
                    {{ event.cameras_used.map(deviceLabel).join('、') }}
                    <em v-if="event.cameras_used.length > 1">（多路一起看）</em>
                  </template>
                  <template v-else>没有任何一路出画面</template>
                </span>
              </div>
              <div v-if="event.cameras_failed?.length" class="cap-step">
                <span class="cap-step-label">没用上的</span>
                <span class="cap-step-value warn">
                  <span v-for="fail in event.cameras_failed" :key="fail.index">
                    {{ deviceLabel(fail.index) }}：{{ fail.message }}
                  </span>
                </span>
              </div>
              <div class="cap-step">
                <span class="cap-step-label">量到的</span>
                <span class="cap-step-value">
                  {{ event.reading_text || '没有可用线索' }}
                  <em v-if="event.expression_text"> · 脸：{{ event.expression_text }}</em>
                </span>
              </div>
              <div class="cap-step">
                <span class="cap-step-label">解读</span>
                <span class="cap-step-value">
                  <template v-if="event.interpreted">
                    {{ event.interpreter || '她自己的模型' }} · {{ seconds(event.timing?.interpret) }}
                  </template>
                  <template v-else>
                    没有解读<em v-if="event.degraded_reason">（{{ event.degraded_reason }}）</em>
                  </template>
                </span>
              </div>
              <div class="cap-step">
                <span class="cap-step-label">要不要说</span>
                <span class="cap-step-value">
                  <template v-if="event.said">说了：「{{ event.said }}」</template>
                  <template v-else>这次没说</template>
                </span>
              </div>
              <div class="cap-step">
                <span class="cap-step-label">耗时</span>
                <span class="cap-step-value minor">
                  抓帧 {{ seconds(event.timing?.capture) }} ·
                  本地分析 {{ seconds(event.timing?.local) }} ·
                  模型 {{ seconds(event.timing?.interpret) }} ·
                  合计 {{ seconds(event.timing?.total) }}
                </span>
              </div>
            </div>

            <div v-if="thumbsOn" class="cap-thumbs">
              <div v-if="loadingDetail && !details[event.id]" class="cap-thumb-loading">正在取画面…</div>
              <template v-else-if="eventThumbs(event.id).length">
                <figure v-for="thumb in eventThumbs(event.id)" :key="thumb.index" class="cap-thumb">
                  <img :src="thumb.data_url" :alt="`摄像头 ${thumb.index}`">
                  <figcaption>
                    {{ deviceLabel(thumb.index) }}
                    <em v-if="thumb.owner === 'browser'">· 来自预览</em>
                  </figcaption>
                </figure>
              </template>
              <div v-else class="cap-thumb-loading">这一轮没有留下画面。</div>
            </div>
          </div>
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.cap-panel { margin-top: .7rem; padding: .7rem; border: 1px solid rgba(0,173,181,.12); border-radius: 4px; background: rgba(0,0,0,.32); display: flex; flex-direction: column; gap: .55rem; }
.cap-label { color: rgba(0,255,245,.48); font: .5rem 'JetBrains Mono', monospace; letter-spacing: .08em; }

/* health row */
.cap-health { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; padding: .5rem .6rem; border-radius: 3px; background: rgba(0,173,181,.07); border: 1px solid rgba(0,173,181,.16); }
.cap-health.good { background: rgba(110,231,168,.07); border-color: rgba(110,231,168,.3); }
.cap-health.warn { background: rgba(255,190,120,.07); border-color: rgba(255,190,120,.3); }
.cap-health.bad { background: rgba(255,120,120,.08); border-color: rgba(255,120,120,.32); }
.cap-health.off { background: rgba(160,170,175,.06); border-color: rgba(160,170,175,.2); }
.cap-health-dot { flex: none; width: 8px; height: 8px; border-radius: 50%; background: #6ee7a8; box-shadow: 0 0 10px rgba(110,231,168,.7); }
.cap-health.warn .cap-health-dot { background: #ffbe78; box-shadow: 0 0 10px rgba(255,190,120,.7); }
.cap-health.bad .cap-health-dot { background: #ff7878; box-shadow: 0 0 10px rgba(255,120,120,.7); }
.cap-health.off .cap-health-dot { background: rgba(180,190,195,.5); box-shadow: none; }
.cap-health-text { flex: 1; min-width: 8rem; display: flex; flex-direction: column; }
.cap-health-text strong { color: #eaffff; font: 700 .74rem 'Noto Serif SC', serif; }
.cap-health-text small { color: rgba(210,222,226,.5); font-size: .55rem; }
.cap-health-meta { display: flex; gap: .5rem; color: rgba(200,215,220,.42); font: .5rem 'JetBrains Mono', monospace; }
.cap-health-error { margin: 0; color: rgba(255,180,150,.85); font-size: .55rem; }
.cap-bridge { display: flex; align-items: baseline; gap: .5rem; padding: .3rem .5rem; border-radius: 3px; background: rgba(110,231,168,.05); }
.cap-bridge.broken { background: rgba(255,120,120,.08); }
.cap-bridge-text { color: rgba(210,222,226,.7); font-size: .56rem; }
.cap-bridge.broken .cap-bridge-text { color: rgba(255,170,170,.9); }
.cap-bridge-text em { color: rgba(200,215,220,.45); font-style: normal; }
.cap-btn { padding: .25rem .55rem; border: 1px solid rgba(0,255,245,.3); border-radius: 3px; background: rgba(0,173,181,.12); color: #c8f4f2; font-size: .58rem; cursor: pointer; }
.cap-btn:hover:not(:disabled) { background: rgba(0,173,181,.22); }
.cap-btn:disabled { opacity: .45; cursor: default; }
.cap-btn.stop { border-color: rgba(255,140,140,.35); background: rgba(255,120,120,.12); color: #ffd0d0; }

/* devices */
.cap-devices { display: flex; flex-direction: column; gap: .25rem; }
.cap-device-list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: .2rem; }
.cap-device { display: flex; align-items: baseline; gap: .5rem; padding: .28rem .45rem; border-radius: 3px; background: rgba(0,173,181,.04); font-size: .58rem; }
.cap-device.bad { background: rgba(255,190,120,.05); }
.cap-device-name { flex: none; width: 4.5rem; color: rgba(0,255,245,.7); font: .54rem 'JetBrains Mono', monospace; }
.cap-device-state { flex: 1; min-width: 0; color: rgba(222,232,235,.78); }
.cap-device-reading { display: block; margin-top: .12rem; color: rgba(200,215,220,.48); }
.cap-device.bad .cap-device-state { color: rgba(255,205,150,.8); }
.cap-device-owner { flex: none; color: rgba(200,215,220,.4); font: .48rem 'JetBrains Mono', monospace; }

/* previews */
.cap-sources { display: flex; flex-direction: column; gap: .3rem; }
.cap-sources-strip { display: flex; flex-wrap: wrap; gap: .45rem; }
.cap-source { margin: 0; display: flex; flex-direction: column; gap: .2rem; }
.cap-source-media { width: 176px; height: auto; border: 1px solid rgba(0,173,181,.2); border-radius: 3px; background: #000; }
.cap-source figcaption { color: rgba(200,215,220,.42); font: .48rem 'JetBrains Mono', monospace; }

/* latest reading */
.cap-latest { display: flex; flex-direction: column; gap: .22rem; }
.cap-latest-text { margin: 0; color: rgba(232,240,242,.9); font-size: .68rem; line-height: 1.6; }
.cap-latest-meta { margin: 0; color: rgba(200,215,220,.42); font: .52rem 'JetBrains Mono', monospace; }

/* her voice */
.cap-voice { display: flex; flex-direction: column; gap: .3rem; padding: .45rem .5rem; border-radius: 3px; background: rgba(110,231,168,.06); border: 1px solid rgba(110,231,168,.2); }
.cap-voice-body { display: flex; align-items: center; gap: .5rem; }
.cap-voice-text { flex: 1; margin: 0; color: #d6fff0; font-size: .66rem; line-height: 1.6; }

/* intents */
.cap-intents { display: flex; flex-direction: column; gap: .22rem; }
.cap-intents ul { margin: 0; padding-left: 1rem; color: rgba(210,222,226,.6); font-size: .56rem; line-height: 1.7; }

/* history */
.cap-history { display: flex; flex-direction: column; gap: .35rem; padding-top: .45rem; border-top: 1px solid rgba(0,173,181,.1); }
.cap-history-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: .4rem; }
.cap-thumb-toggle { display: flex; align-items: center; gap: .3rem; color: rgba(220,230,235,.5); font-size: .55rem; cursor: pointer; }
.cap-privacy-warn { margin: 0; padding: .35rem .45rem; border-radius: 3px; background: rgba(255,180,120,.08); color: rgba(255,205,150,.85); font-size: .54rem; line-height: 1.6; }
.cap-empty { color: rgba(200,210,215,.3); font-size: .58rem; }
.cap-list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: .22rem; }
.cap-row { border: 1px solid rgba(0,173,181,.08); border-radius: 3px; background: rgba(0,173,181,.03); }
.cap-row.open { border-color: rgba(0,255,245,.22); background: rgba(0,173,181,.06); }
.cap-row-head { display: flex; align-items: center; gap: .45rem; width: 100%; padding: .35rem .5rem; border: 0; background: transparent; color: inherit; text-align: left; cursor: pointer; }
.cap-dot { flex: none; width: 6px; height: 6px; border-radius: 50%; background: #6ee7a8; box-shadow: 0 0 8px rgba(110,231,168,.6); }
.cap-dot.miss { background: rgba(180,190,195,.4); box-shadow: none; }
.cap-time { flex: none; color: rgba(0,255,245,.5); font: .52rem 'JetBrains Mono', monospace; }
.cap-headline { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: rgba(232,240,242,.86); font-size: .64rem; }
.cap-tags { flex: none; display: flex; gap: .25rem; }
.cap-tag { padding: .1rem .3rem; border-radius: 2px; background: rgba(0,173,181,.1); color: rgba(200,215,220,.6); font: .46rem 'JetBrains Mono', monospace; font-style: normal; }
.cap-tag.said { background: rgba(110,231,168,.16); color: #8ef5c8; }
.cap-tag.notable { background: rgba(255,180,120,.16); color: rgba(255,205,150,.9); }
.cap-tag.degraded { background: rgba(255,255,255,.06); color: rgba(200,210,215,.45); }
.cap-detail { padding: .1rem .55rem .5rem; }
.cap-chain { display: flex; flex-direction: column; gap: .28rem; border-left: 1px solid rgba(0,255,245,.14); padding-left: .55rem; }
.cap-step { display: flex; gap: .5rem; font-size: .58rem; line-height: 1.6; }
.cap-step-label { flex: none; width: 4.2rem; color: rgba(0,255,245,.42); font: .5rem 'JetBrains Mono', monospace; }
.cap-step-value { flex: 1; min-width: 0; color: rgba(226,235,238,.8); word-break: break-word; }
.cap-step-value.warn { color: rgba(255,190,150,.85); }
.cap-step-value.minor { color: rgba(200,215,220,.42); font-size: .52rem; }
.cap-step-value em { color: rgba(200,215,220,.5); font-style: normal; }
.cap-thumbs { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .45rem; }
.cap-thumb { margin: 0; display: flex; flex-direction: column; gap: .2rem; }
.cap-thumb img { width: 148px; height: auto; border: 1px solid rgba(0,173,181,.2); border-radius: 3px; background: #000; }
.cap-thumb figcaption { color: rgba(200,215,220,.45); font: .46rem 'JetBrains Mono', monospace; }
.cap-thumb-loading { color: rgba(200,210,215,.35); font-size: .54rem; }
</style>
