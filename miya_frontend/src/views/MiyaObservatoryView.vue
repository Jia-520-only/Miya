<script setup lang="ts">
import type { FluxGeometry } from '@/components/MiyaFluxScene.vue'
import type { RuntimeAnchor, RuntimeCategory, RuntimeLog, RuntimeSeverity } from '@/utils/miyaRuntimeLogs'
import { onClickOutside } from '@vueuse/core'
import { computed, nextTick, ref, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import MiyaFluxPortraitSettings from '@/components/MiyaFluxPortraitSettings.vue'
import MiyaFluxScene from '@/components/MiyaFluxScene.vue'
import MiyaRuntimeRings from '@/components/MiyaRuntimeRings.vue'
import { useMiyaFluxPreferences } from '@/composables/useMiyaFluxPreferences'
import { useMiyaPresence } from '@/composables/useMiyaPresence'
import { useMiyaRuntimeLogs } from '@/composables/useMiyaRuntimeLogs'
import { emotionLabel, MEMORY_LAYERS, phaseLabel } from '@/utils/miyaPresence'
import { filterRuntimeLogs, RUNTIME_RINGS, runtimeWarning } from '@/utils/miyaRuntimeLogs'

const router = useRouter()
const { presence, connection, online, updatedAt, streaming, refresh } = useMiyaPresence()
const { mode, composition, paused } = useMiyaFluxPreferences()
const { entries: runtimeEntries, recent: runtimeRecent, connection: logConnection, now: logClock, hidden: logHidden } = useMiyaRuntimeLogs()
const selectedCategory = ref<RuntimeCategory | null>(null)
const categoryLogs = computed(() => runtimeEntries.value.filter(entry => entry.category === selectedCategory.value).slice().reverse())
const logQuery = ref('')
const logSeverity = ref<RuntimeSeverity>('all')
const followingLogs = ref(true)
const retainedLogs = shallowRef<RuntimeLog[]>([])
const logList = ref<HTMLOListElement>()
const readableLogs = computed(() => followingLogs.value ? categoryLogs.value : retainedLogs.value)
const filteredLogs = computed(() => filterRuntimeLogs(readableLogs.value, logQuery.value, logSeverity.value))
const unreadLogs = computed(() => {
  if (followingLogs.value)
    return 0
  const last = retainedLogs.value[0]
  return categoryLogs.value.filter(entry => !last || entry.receivedAt > last.receivedAt || (entry.receivedAt === last.receivedAt && entry.seq > last.seq)).length
})
function holdLogs() {
  if (!followingLogs.value)
    return
  retainedLogs.value = categoryLogs.value.slice()
  followingLogs.value = false
}
async function resumeLogs() {
  followingLogs.value = true
  retainedLogs.value = []
  await nextTick()
  logList.value?.scrollTo({ top: 0 })
}
function onLogScroll() {
  if ((logList.value?.scrollTop ?? 0) > 16)
    holdLogs()
}
const categoryLabel = computed(() => RUNTIME_RINGS.find(ring => ring.id === selectedCategory.value)?.label)
const immersive = ref(false)
const controlsOpen = ref(false)
const controls = ref<HTMLElement>()
const controlsToggle = ref<HTMLButtonElement>()

onClickOutside(controls, () => controlsOpen.value = false, { ignore: ['#miya-portrait-editor', '.portrait-dismiss'] })

function dismissControls(event: KeyboardEvent) {
  if (!controlsOpen.value)
    return
  event.stopPropagation()
  controlsOpen.value = false
  controlsToggle.value?.focus()
}

const geometry = ref<FluxGeometry>()
const runtimeAnchors = ref<RuntimeAnchor[]>([])
const runtimeBridges = computed(() => {
  const g = geometry.value
  if (!g)
    return []
  return runtimeAnchors.value.flatMap((a) => {
    const dx = g.x - a.x
    const dy = g.y - a.y
    const distance = Math.hypot(dx, dy)
    if (distance < g.outerRadius + a.radius + 12)
      return []
    const x1 = a.x + dx / distance * (a.radius + 8)
    const y1 = a.y + dy / distance * (a.radius + 8)
    const x2 = g.x - dx / distance * (g.outerRadius + 6)
    const y2 = g.y - dy / distance * (g.outerRadius + 6)
    const event = logConnection.value === 'online' ? [...runtimeRecent.value].reverse().find(entry => entry.category === a.category && logClock.value - entry.receivedAt < 3500) : undefined
    return [{ category: a.category, x: x2, y: y2, event, path: `M ${x1} ${y1} C ${(x1 + x2) / 2} ${y1 - 24}, ${(x1 + x2) / 2} ${y2 - 24}, ${x2} ${y2}` }]
  })
})
const details = ref<HTMLDialogElement>()
const noteDetails = ref<HTMLDialogElement>()
const selectedLayer = ref<string | null>(null)
const modes = [{ id: 'resonance', label: '共鸣' }, { id: 'surge', label: '洪流' }, { id: 'quiet', label: '静谧' }] as const
const compositions = [{ id: 'complete', label: '完整圆环' }, { id: 'closeup', label: '局部特写' }] as const
const hasSnapshot = computed(() => updatedAt.value !== null)
const stale = computed(() => !online.value && hasSnapshot.value)
const statusLabel = computed(() => {
  if (online.value)
    return streaming.value ? '状态实时同步' : '状态定时同步'
  if (stale.value)
    return '上次状态 · 非实时'
  return connection.value === 'connecting' ? '正在连接状态' : '状态暂未连接'
})
const logStatus = computed(() => logConnection.value === 'connecting' ? '日志连接中' : logConnection.value === 'offline' ? '日志重连中' : '')
const syncedAt = computed(() => updatedAt.value?.toLocaleString('zh-CN', {
  ...(stale.value ? { year: 'numeric', month: '2-digit', day: '2-digit' } as const : {}),
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
}) ?? '尚未同步')
const phase = computed(() => phaseLabel(presence.value.phase))
const summaryPhase = computed(() => hasSnapshot.value
  ? presence.value.phase ? phase.value : '活动状态待同步'
  : connection.value === 'connecting' ? '等候首次状态' : '暂无状态读数')
const emotion = computed(() => emotionLabel(presence.value.emotion))
const intensity = computed(() => presence.value.emotionIntensity)
const emotionReadings = computed(() => [...presence.value.emotions].sort((a, b) => b.intensity - a.intensity))
const note = computed(() => presence.value.note)
const noteDate = computed(() => note.value ? new Date(note.value.createdAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '')
const lifecycleTime = computed(() => presence.value.lifecycleAt ? new Date(presence.value.lifecycleAt).toLocaleTimeString('zh-CN', { hour12: false }) : null)
const selectedMemory = computed(() => MEMORY_LAYERS.find(layer => layer.id === selectedLayer.value))
const identityPosition = computed(() => {
  const g = geometry.value
  if (!g || composition.value === 'closeup')
    return undefined
  return { left: `${g.x}px`, top: `${g.y - g.radius * 0.7}px` }
})
function count(value: number | null | undefined) {
  return value != null ? value.toLocaleString('zh-CN') : '—'
}
function openDetails(layer: string | null = null) {
  selectedCategory.value = null
  selectedLayer.value = layer
  details.value?.showModal()
}
function openRuntime(category: RuntimeCategory, layer?: string) {
  selectedLayer.value = layer ?? null
  selectedCategory.value = category
  logQuery.value = ''
  logSeverity.value = 'all'
  followingLogs.value = true
  retainedLogs.value = []
  details.value?.showModal()
}
function closeDetails() {
  details.value?.close()
  selectedLayer.value = null
  selectedCategory.value = null
}
</script>

<template>
  <main class="observatory-view" :class="[{ 'is-immersive': immersive }, `composition-${composition}`]" @keydown.esc="immersive = false">
    <header class="observatory-header">
      <button class="observatory-back" title="返回首页" aria-label="返回首页" @click="router.push('/')">
        ←
      </button>
      <div class="observatory-title">
        <h1>弥娅观测台</h1><span class="mono">MIYA / LIVING FIELD</span>
      </div>
      <button v-if="!immersive" class="note-preview" aria-haspopup="dialog" @click="noteDetails?.showModal()">
        <span class="note-label">短笺</span>
        <strong class="note-title" :title="note?.title">{{ note?.title || '还没有留下短笺' }}</strong>
        <span class="note-arrow" aria-hidden="true">↗</span>
      </button>
      <div ref="controls" class="header-tools" @keydown.esc="dismissControls">
        <button ref="controlsToggle" class="tools-toggle" :aria-expanded="controlsOpen" aria-controls="observatory-controls" aria-label="观测控件" title="观测控件" @click="controlsOpen = !controlsOpen">
          <span aria-hidden="true">⋯</span>
        </button>
        <div id="observatory-controls" class="header-controls" :class="{ 'controls-open': controlsOpen }" role="group" aria-label="观测控件">
          <div class="composition-modes" role="group" aria-label="圆环构图">
            <button v-for="item in compositions" :key="item.id" :aria-pressed="composition === item.id" @click="composition = item.id">
              {{ item.label }}
            </button>
          </div>
          <div class="field-modes" role="group" aria-label="共鸣场视觉模式">
            <button v-for="item in modes" :key="item.id" :aria-pressed="mode === item.id" @click="mode = item.id">
              {{ item.label }}
            </button>
          </div>
          <MiyaFluxPortraitSettings />
          <button class="motion-toggle" :aria-pressed="paused" :aria-label="paused ? '继续共鸣动画' : '暂停共鸣动画'" @click="paused = !paused">
            {{ paused ? '▷ 继续' : 'Ⅱ 暂停' }}
          </button>
        </div>
      </div>
      <button class="immersion-toggle" :aria-pressed="immersive" aria-label="沉浸观测" :title="immersive ? '退出沉浸' : '沉浸观测'" @click="immersive = !immersive">
        <span class="immersion-label">{{ immersive ? '退出沉浸' : '沉浸观测' }}</span><span aria-hidden="true">⛶</span>
      </button>
    </header>
    <section class="observatory-workspace" :data-composition="composition" aria-label="弥娅灵魂共鸣">
      <div class="field-space" aria-label="弥娅六层记忆与灵魂光场">
        <MiyaFluxScene class="observatory-scene" framed :selected-layer="selectedLayer" :runtime-logs="runtimeEntries" @geometry="geometry = $event" />
        <div class="field-vignette" aria-hidden="true" />
        <span class="field-index mono">BLUE & WHITE / {{ composition === 'complete' ? 'WHOLE / 完整观测' : 'CLOSE / 局部特写' }}</span>
        <div v-if="geometry" class="ring-identity" :class="{ 'closeup-identity': composition === 'closeup' }" :style="identityPosition">
          <span class="persona-name">{{ presence.persona ?? '弥娅' }}</span>
          <button v-if="immersive" class="phase-label" @click="openDetails()">
            {{ summaryPhase }}<span v-if="stale"> · 非实时</span>
          </button>
        </div>
        <div class="field-caption">
          <span class="mono">{{ paused ? 'STILL / RESONANCE' : 'CONTINUOUS / BECOMING' }}</span><p>灵魂主环 · 青花共鸣</p>
        </div>
      </div>
      <svg class="runtime-bridge" :class="{ 'is-still': paused || logHidden }" aria-hidden="true">
        <g v-for="bridge in runtimeBridges" :key="bridge.category" :data-category="bridge.category">
          <path :d="bridge.path" />
          <circle v-if="bridge.event" :key="`${bridge.event.seq}-${bridge.event.receivedAt}`" class="runtime-arrival" :class="{ 'is-warning': runtimeWarning(bridge.event) }" :cx="bridge.x" :cy="bridge.y" r="7" />
        </g>
      </svg>
      <template v-for="bridge in runtimeBridges" :key="bridge.category">
        <span v-if="bridge.event" :key="`${bridge.event.seq}-${bridge.event.receivedAt}`" class="runtime-transfer" :class="{ 'is-warning': runtimeWarning(bridge.event) }" :data-category="bridge.category" :style="{ offsetPath: `path('${bridge.path}')`, animationPlayState: paused || logHidden ? 'paused' : 'running' }" aria-hidden="true" />
      </template>
      <MiyaRuntimeRings class="runtime-station" :presence="presence" :online="online" :entries="runtimeEntries" :recent="runtimeRecent" :connection="logConnection" :paused="paused" :hidden="logHidden" :now="logClock" :composition="composition" :selected-layer="selectedLayer" @select="openRuntime" @anchors="runtimeAnchors = $event" />
    </section>
    <footer class="observatory-footer">
      <div v-if="!immersive" class="now-reading" :data-signal="online ? 'live' : stale ? 'stale' : 'waiting'">
        <button class="now-trigger" aria-haspopup="dialog" @click="openDetails()">
          <span class="now-phase">{{ summaryPhase }}</span><span aria-hidden="true">›</span>
        </button>
        <div class="now-meta">
          <span class="now-signal" role="status"><i aria-hidden="true" />{{ statusLabel }}<span v-if="logStatus" class="now-log"> · {{ logStatus }}</span></span>
          <time v-if="updatedAt && stale" :datetime="updatedAt.toISOString()">采样于 {{ syncedAt }}</time>
        </div>
      </div>
      <nav class="presence-links" aria-label="弥娅功能入口">
        <button class="presence-chat" @click="router.push('/chat')">
          与弥娅对话 ↗
        </button><button class="presence-memory" @click="router.push('/mind')">
          记忆星河 ↗
        </button><button class="details-trigger" @click="openDetails()">
          状态详情 ＋
        </button>
      </nav>
    </footer>
    <Teleport to="body">
      <dialog ref="noteDetails" class="observatory-details observatory-note-dialog" aria-labelledby="observatory-note-title" @click="event => { if (event.target === noteDetails) noteDetails?.close() }">
        <header class="details-header">
          <h2 id="observatory-note-title">
            弥娅的短笺
          </h2><button aria-label="关闭短笺" @click="noteDetails?.close()">
            ×
          </button>
        </header>
        <h3>{{ note?.title || '等一封，弥娅的短笺。' }}</h3>
        <p>{{ note?.body || '弥娅留下的话，会安静地保存在这里。' }}</p>
        <small>{{ note ? `${note.personaName || '弥娅'} · ${noteDate}` : '尚未留下短笺' }}<template v-if="note && stale"> · 上次同步</template></small>
      </dialog>
      <dialog ref="details" class="observatory-details" aria-labelledby="observatory-details-title" @cancel.prevent="closeDetails" @click="event => { if (event.target === details) closeDetails() }">
        <header class="details-header">
          <div>
            <span class="mono">MIYA / LIVE READINGS</span><h2 id="observatory-details-title">
              {{ selectedMemory ? `${selectedMemory.label}记忆` : selectedCategory === 'execution' ? '运行记录' : selectedCategory ? `${categoryLabel}运行轨迹` : '此刻的弥娅' }}
            </h2>
          </div><button aria-label="关闭状态详情" @click="closeDetails">
            ×
          </button>
        </header>
        <p v-if="stale" class="stale-reading">
          状态读数来自上次采样 · {{ syncedAt }} · 非实时
        </p>
        <div v-if="selectedMemory" class="selected-memory">
          <strong>{{ count(presence.memoryLayers[selectedMemory.id]) }}</strong><span>个{{ selectedMemory.label }}记忆节点</span>
        </div>
        <section v-if="selectedCategory" class="runtime-log-details" aria-label="分类运行日志">
          <div class="runtime-log-status">
            <span>{{ logConnection === 'online' ? '日志实时连接' : logConnection === 'connecting' ? '日志连接中' : '日志连接中断 · 保留最近记录' }}</span><small>显示 {{ filteredLogs.length }} / {{ readableLogs.length }} 条 · 最多保留 160 条</small>
          </div>
          <div class="runtime-log-tools">
            <input v-model="logQuery" type="search" aria-label="搜索运行日志" placeholder="搜索模块或日志内容" @input="holdLogs">
            <select v-model="logSeverity" aria-label="日志级别" @change="holdLogs">
              <option value="all">
                全部级别
              </option><option value="warning">
                警告与错误
              </option><option value="error">
                仅错误
              </option>
            </select>
            <button class="log-follow-toggle" :aria-pressed="followingLogs" @click="followingLogs ? holdLogs() : resumeLogs()">
              {{ followingLogs ? '停止跟随' : unreadLogs ? `查看新增 ${unreadLogs} 条` : '跟随最新' }}
            </button>
          </div>
          <p v-if="selectedMemory" class="runtime-log-help">
            上方为{{ selectedMemory.label }}记忆存量；下方为全部记忆模块日志，当前日志未提供分层标记。
          </p>
          <p class="log-reading-status" role="status">
            {{ followingLogs ? '自动跟随最新记录 · 翻阅时自动停止跟随' : '已保留当前阅读位置 · 新记录继续接收' }}
          </p>
          <ol v-if="readableLogs.length" ref="logList" class="runtime-log-list" tabindex="0" aria-label="运行日志列表" @scroll.passive="onLogScroll">
            <li v-for="entry in filteredLogs" :key="`${entry.seq}-${entry.ts}`" :class="{ 'log-warning': runtimeWarning(entry) }">
              <div><time>{{ entry.ts.slice(11, 23) }}</time><b>{{ entry.level }}</b><span>{{ entry.name }}</span><small v-if="entry.historical">历史</small></div>
              <pre>{{ entry.text }}</pre>
            </li>
          </ol>
          <p v-if="!filteredLogs.length" class="runtime-log-empty">
            {{ readableLogs.length ? '没有符合筛选条件的记录。' : '此分类暂未收到运行记录。' }}
          </p>
          <p class="runtime-log-help">
            日志按模块归类，运行记录包含系统维护；近 60 秒按本页接收时间统计，不含历史补发。六层记忆存量来自独立状态接口。
          </p>
        </section>
        <p class="details-persona">
          {{ presence.persona ?? '人格待同步' }}
        </p>
        <section class="observatory-readings" aria-label="弥娅状态读数">
          <article>
            <span class="reading-label"><i />{{ stale ? '上次活动状态' : '活动状态' }} <small class="mono">SOUL</small></span><div class="reading-value">
              <strong class="phase-value">{{ phase }}</strong>
            </div>
            <small class="reading-detail">{{ lifecycleTime ? `心跳采样 ${lifecycleTime}` : '等候生命状态信号' }}</small>
          </article>
          <article>
            <span class="reading-label"><i />记忆条目 <small class="mono">MEMORY</small></span><div class="reading-value">
              <strong>{{ count(presence.memoryCount) }}</strong><span>个记忆节点</span>
            </div>
            <div class="memory-layer-readings" aria-label="六层记忆数量">
              <span v-for="layer in MEMORY_LAYERS" :key="layer.id">{{ layer.label }} <b>{{ count(presence.memoryLayers[layer.id]) }}</b></span>
            </div>
          </article>
          <article>
            <span class="reading-label"><i />已启用平台 <small class="mono">M-LINK</small></span><div class="reading-value">
              <strong>{{ count(presence.platformCount) }}</strong><span>个交流入口</span>
            </div>
            <small class="reading-detail">{{ stale ? '上次在线' : '在线' }} {{ count(presence.onlinePlatforms) }} · 已启用 {{ count(presence.platformCount) }}</small>
          </article>
          <article class="reading-connection">
            <span class="reading-label"><i :class="{ online }" />{{ statusLabel }}<button class="refresh-reading" title="重新同步状态" aria-label="重新同步状态" @click="refresh">↻</button></span>
            <p>{{ updatedAt ? `快照采样 ${syncedAt}` : '等候首次状态同步' }}</p>
            <small>{{ logStatus || '运行日志已连接' }}</small>
          </article>
        </section>
        <div class="emotion-reading">
          <div><span>基础情绪</span><strong>{{ emotion }}<span v-if="intensity !== null"> · {{ intensity }}%</span></strong></div>
          <div class="emotion-spectrum" aria-label="基础情绪强度">
            <div v-for="item in emotionReadings.slice(0, 4)" :key="item.name" class="emotion-meter" :title="`${emotionLabel(item.name)} ${item.intensity}%`">
              <span>{{ emotionLabel(item.name) }}</span><i><b :style="{ width: `${item.intensity}%` }" /></i><small>{{ item.intensity }}%</small>
            </div>
            <span v-if="!emotionReadings.length" class="emotion-empty">{{ intensity === null ? '等候情绪信号' : '当前仅同步主导情绪' }}</span>
          </div>
          <small>这里是情绪引擎的基础读数；对话还会参考当前会话的经历。</small>
        </div>

        <p class="details-help">
          读数来自运行状态；环带光流与旋转为艺术化表达。
        </p>
        <p class="details-credit">
          光场基础视觉基于 <a href="https://github.com/Ryder191/haloflux" target="_blank" rel="noreferrer">HALOFLUX by Ryder191 (RYDER CODE / Ms MAIKEBAIs CAT)</a> 修改。
        </p>
      </dialog>
    </Teleport>
  </main>
</template>

<style>
.observatory-view,.observatory-details,.miya-porcelain-surface {
  color-scheme: light;
  --porcelain-white: var(--miya-observatory-glaze, #f8fbff);
  --porcelain-ink: var(--miya-observatory-ink, #183568);
  --porcelain-blue: var(--miya-observatory-accent, #315da2);
  --porcelain-wash: color-mix(in srgb, var(--porcelain-white) 94%, var(--porcelain-blue));
  --porcelain-muted: color-mix(in srgb, var(--porcelain-ink) 76%, var(--porcelain-white));
  --porcelain-line: color-mix(in srgb, var(--porcelain-blue) 22%, transparent);
  --porcelain-tint: color-mix(in srgb, var(--porcelain-white) 90%, var(--porcelain-blue));
  --porcelain-tint-strong: color-mix(in srgb, var(--porcelain-white) 81%, var(--porcelain-blue));
  --porcelain-warning: #8c4d25;
  --porcelain-shadow: color-mix(in srgb, var(--porcelain-ink) 21%, transparent);
}
</style>

<style scoped>
.observatory-view { --obs-line: var(--porcelain-line); display: flex; flex-direction: column; flex: 1; min-width: 0; min-height: 0; overflow: hidden; container: observatory / inline-size; color: var(--porcelain-ink); background: var(--porcelain-white); border: 1px solid var(--obs-line); border-radius: 6px; }
.mono { font: 9px/1.5 Consolas,monospace; letter-spacing: .13em; }
button { color: inherit; font: inherit; cursor: pointer; }
.observatory-header { position: relative; z-index: 3; background: linear-gradient(110deg,var(--porcelain-white),var(--porcelain-wash)); display: flex; align-items: center; gap: 10px; flex: 0 0 auto; padding: 10px 16px; border-bottom: 1px solid var(--porcelain-line); }
.observatory-back { flex: none; width: 28px; height: 28px; color: var(--porcelain-blue); border: 1px solid var(--obs-line); background: var(--porcelain-tint); }
.observatory-title { display: grid; flex: none; gap: 2px; white-space: nowrap; }
.observatory-title h1 { margin: 0; font-size: 14px; font-weight: 500; letter-spacing: .12em; }
.observatory-title .mono { color: var(--porcelain-muted); font-size: 8px; }
.immersion-toggle { display: inline-flex; align-items: center; justify-content: center; gap: 4px; flex: none; padding: 6px; min-height: 32px; white-space: nowrap; color: var(--porcelain-muted); background: transparent; font-size: 11px; }
.header-tools { flex: none; margin-left: auto; }
.header-controls { display: flex; align-items: center; gap: 8px; }
.tools-toggle { display: none; width: 32px; height: 32px; border: 1px solid var(--porcelain-line); border-radius: 4px; color: var(--porcelain-blue); background: var(--porcelain-tint); font-size: 18px; line-height: 1; }
.composition-modes,.field-modes { display: flex; gap: 2px; padding: 2px; border: 1px solid var(--porcelain-line); border-radius: 4px; }
.composition-modes button,.field-modes button { padding: 4px 8px; min-height: 26px; color: var(--porcelain-muted); background: transparent; font-size: 11px; white-space: nowrap; border-radius: 2px; }
.composition-modes button[aria-pressed=true],.field-modes button[aria-pressed=true] { color: var(--porcelain-ink); background: var(--porcelain-tint-strong); }
.motion-toggle { padding: 6px; min-height: 32px; background: transparent; color: var(--porcelain-muted); font-size: 11px; white-space: nowrap; }
.observatory-header button:where(:hover),.motion-toggle[aria-pressed=true],.immersion-toggle[aria-pressed=true],.tools-toggle[aria-expanded=true] { color: var(--porcelain-ink); background: var(--porcelain-tint); }
.observatory-header button:focus-visible { outline: 1px solid var(--porcelain-blue); outline-offset: 2px; }
.observatory-workspace { position: relative; flex: 1; min-height: 0; isolation: isolate; container-type: size; }
.note-preview { display: flex; align-items: baseline; gap: 7px; min-width: 0; flex: 1; max-width: 380px; margin-left: auto; padding: 5px 8px; background: transparent; text-align: left; }
.note-label { color: var(--porcelain-muted); font-size: 10px; white-space: nowrap; }
.note-title { min-width: 0; overflow: hidden; color: var(--porcelain-ink); font: 500 13px/1.5 'Noto Serif SC',SimSun,serif; text-overflow: ellipsis; white-space: nowrap; }
.note-arrow { color: var(--porcelain-blue); font-size: 11px; }
.note-preview + .header-tools { margin-left: 0; }
.now-reading { display: flex; align-items: center; flex-wrap: wrap; column-gap: 12px; row-gap: 2px; min-width: 0; }
.now-trigger { display: flex; align-items: baseline; gap: 4px; padding: 4px 0; color: var(--porcelain-ink); background: transparent; font-size: 12px; text-align: left; }
.now-trigger > span[aria-hidden] { color: var(--porcelain-blue); }
.now-trigger:hover,.note-preview:hover .note-title { color: var(--porcelain-blue); }
.now-trigger:focus-visible,.note-preview:focus-visible { outline: 1px solid var(--porcelain-blue); outline-offset: 3px; }
.now-meta { display: flex; flex-wrap: wrap; gap: 2px 8px; color: var(--porcelain-muted); font-size: 10px; line-height: 1.5; }
.now-meta time { font-variant-numeric: tabular-nums; }
.now-signal i { display: inline-block; width: 5px; height: 5px; margin-right: 5px; vertical-align: 1px; border-radius: 50%; background: var(--porcelain-muted); }
[data-signal=live] .now-signal i { background: var(--porcelain-blue); box-shadow: 0 0 6px var(--porcelain-line); }
[data-signal=stale] .now-signal,.now-log { color: var(--porcelain-warning); }
[data-signal=stale] .now-signal i { background: var(--porcelain-warning); }
.field-space { position: absolute; inset: 0; overflow: hidden; }
.observatory-scene { width: 100%; height: 100%; border: 0; pointer-events: none; }
.field-vignette { --glaze-fade: color-mix(in srgb, var(--porcelain-white) 70%, transparent); position: absolute; inset: 0; background: linear-gradient(90deg,var(--glaze-fade),transparent 36%),linear-gradient(0deg,var(--porcelain-white),transparent 13%,transparent 93%,var(--glaze-fade)); pointer-events: none; }
.field-index { position: absolute; top: 12px; left: 24px; color: var(--porcelain-muted); font-size: 8px; }
.ring-identity { position: absolute; display: grid; gap: 6px; text-align: center; transform: translate(-50%,-50%); max-width: 260px; }
.persona-name { font: 14px/1.5 'Noto Serif SC',SimSun,serif; color: var(--porcelain-ink); letter-spacing: .12em; text-shadow: 0 0 5px var(--porcelain-white), 0 0 9px var(--porcelain-white); }
.phase-label { padding: 2px 6px; font-size: 10px; line-height: 1.7; color: var(--porcelain-blue); background: color-mix(in srgb, var(--porcelain-white) 86%, transparent); border-radius: 3px; white-space: nowrap; }
.phase-label span { color: var(--porcelain-muted); }
.closeup-identity { top: 56px; right: 30px; left: auto; text-align: right; transform: none; }
.field-caption { position: absolute; bottom: 16px; left: 63%; transform: translateX(-50%); text-align: center; pointer-events: none; }
.field-caption .mono { color: var(--porcelain-muted); font-size: 8px; }
.field-caption p { margin: 5px 0 0; color: var(--porcelain-muted); font-size: 10px; letter-spacing: .15em; }
.composition-closeup .field-vignette { background: linear-gradient(270deg,var(--glaze-fade),transparent 36%),linear-gradient(0deg,var(--porcelain-white),transparent 13%,transparent 93%,var(--glaze-fade)); }
.composition-closeup .field-caption { left: auto; right: 30px; transform: none; text-align: right; }
.observatory-footer { display: flex; align-items: center; flex-wrap: wrap; justify-content: space-between; gap: 12px 18px; flex: 0 0 auto; padding: 12px 20px; border-top: 1px solid var(--porcelain-line); background: var(--porcelain-white); }
.presence-links { display: flex; margin-left: auto; align-items: center; flex-wrap: wrap; gap: 8px; }
.presence-links button { min-height: 32px; padding: 6px 10px; color: var(--porcelain-blue); background: var(--porcelain-tint); border: 1px solid var(--porcelain-line); font-size: 10px; }
.presence-links button:hover { background: var(--porcelain-tint-strong); }
.details-credit { margin: 12px 0 0; color: var(--porcelain-muted); font: 9px/1.8 Consolas,monospace; }
.details-credit a { color: var(--porcelain-blue); text-underline-offset: 3px; }
.is-immersive .field-index { display: none; }
.observatory-details { width: min(540px,calc(100vw - 32px)); max-height: calc(100dvh - 90px); margin: auto; padding: 24px; overflow: auto; color: var(--porcelain-ink); border: 1px solid var(--porcelain-line); border-radius: 8px; background: linear-gradient(145deg,var(--porcelain-white),var(--porcelain-wash)); box-shadow: 0 24px 90px var(--porcelain-shadow); }
.observatory-details::backdrop { background: color-mix(in srgb, var(--miya-observatory-ink, #183568) 33%, transparent); }
.details-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.details-header .mono { font-size: 9px; color: var(--porcelain-muted); }
.details-header h2 { margin: 8px 0 14px; font: 22px SimSun,serif; }
.details-header button { align-self: start; width: 34px; height: 34px; background: transparent; color: var(--porcelain-blue); font-size: 24px; }
.details-persona { color: var(--porcelain-muted); font-size: 12px; }
.selected-memory { display: flex; align-items: baseline; flex-wrap: wrap; gap: 10px; margin: 12px 0 22px; }
.selected-memory strong { font: 32px Consolas,monospace; overflow-wrap: anywhere; }
.selected-memory span { color: var(--porcelain-muted); font-size: 11px; }
.observatory-readings { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 24px 20px; padding-block: 20px; border-block: 1px solid var(--porcelain-line); }
.observatory-readings article { min-width: 0; display: grid; align-content: start; gap: 10px; overflow-wrap: anywhere; }
.reading-label { display: flex; align-items: center; gap: 6px; color: var(--porcelain-muted); font-size: 11px; }
.reading-label small { margin-left: auto; color: var(--porcelain-muted); font-size: 7px; }
.reading-value { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px; }
.reading-value strong { color: var(--porcelain-ink); font: 26px/1.3 Consolas,SimSun,serif; }
.reading-value > span,.reading-detail { color: var(--porcelain-muted); font-size: 10px; line-height: 1.7; }
.memory-layer-readings { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 7px; color: var(--porcelain-muted); font-size: 10px; }
.memory-layer-readings > span { overflow-wrap: anywhere; }
.memory-layer-readings b { font: 10px Consolas,monospace; color: var(--porcelain-ink); }
.refresh-reading { margin-left: auto; min-height: 28px; min-width: 28px; background: transparent; color: var(--porcelain-blue); font-size: 20px; }
.reading-connection p { margin: 0; font-size: 11px; line-height: 1.7; }
.reading-connection > small { color: var(--porcelain-muted); font-size: 10px; line-height: 1.7; }
.emotion-reading { margin-top: 20px; }
.emotion-reading > div:first-child { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; color: var(--porcelain-muted); }
.emotion-reading strong { color: var(--porcelain-blue); }
.emotion-spectrum { display: grid; gap: 10px; margin: 14px 0; }
.emotion-meter { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--porcelain-muted); }
.emotion-meter > span { min-width: 30px; }
.emotion-meter > i { flex: 1; height: 3px; background: var(--porcelain-tint); }
.emotion-meter b { display: block; height: 100%; background: var(--porcelain-blue); }
.emotion-meter > small { min-width: 30px; text-align: right; }
.emotion-empty,.emotion-reading > small,.details-help { color: var(--porcelain-muted); font-size: 10px; line-height: 1.8; }
.details-help { margin: 20px 0 0; }
.stale-reading { margin: 14px 0 4px; color: var(--porcelain-warning); font-size: 11px; line-height: 1.6; }
@container observatory (max-width: 780px) {
  .tools-toggle { display: block; }
  .header-controls { display: none; position: absolute; top: calc(100% + 4px); right: 12px; width: max-content; max-width: calc(100% - 24px); box-sizing: border-box; flex-wrap: wrap; padding: 8px; background: var(--porcelain-white); border: 1px solid var(--porcelain-line); border-radius: 4px; box-shadow: 0 8px 24px var(--porcelain-shadow); }
  .header-controls.controls-open { display: flex; }
}
@container observatory (max-width: 480px) {
  .observatory-header { padding: 8px 10px; gap: 5px; }
  .note-preview { gap: 4px; padding-inline: 3px; }
  .note-arrow { display: none; }
  .note-title { font-size: 12px; }
  .observatory-title h1 { font-size: 12px; }
  .observatory-title .mono { font-size: 7px; letter-spacing: 0; }
  .immersion-toggle { width: 30px; padding-inline: 0; font-size: 16px; }
  .immersion-label { display: none; }
}
@media (max-width: 850px), (max-height: 570px) {
  .observatory-view { overflow-y: auto; overflow-x: hidden; }
  .observatory-footer { flex: 0 0 auto; }
  .observatory-workspace { display: flex; flex-direction: column; flex: 0 0 auto; container-type: inline-size; }
  .field-space { position: relative; flex: 0 0 auto; height: clamp(370px,65vh,560px); }
  .field-index { left: 16px; font-size: 7px; }
  .field-caption { left: 50%; bottom: 28px; white-space: nowrap; }
  .field-caption p { font-size: 9px; }
  .composition-closeup .field-caption { right: 16px; bottom: 35px; }
  .closeup-identity { top: 35px; right: 16px; max-width: 160px; }
  .closeup-identity .persona-name { font-size: 12px; }
  .closeup-identity .phase-label { white-space: normal; }
  .field-vignette { background: linear-gradient(0deg,var(--porcelain-white),transparent 18%); }
  .ring-identity { gap: 3px; }
  .persona-name { font-size: 11px; }
  .phase-label { font-size: 9px; }
  .observatory-footer { padding: 12px; gap: 10px; }
  .presence-links { width: 100%; gap: 6px; }
  .presence-links button { flex: 1; padding-inline: 5px; }
}
@media (max-width: 480px) {
  .observatory-details { padding: 18px; }
  .observatory-readings { grid-template-columns: minmax(0,1fr); }
}
.runtime-station { position: absolute; left: 8px; bottom: 24px; width: min(38cqw,460px,calc((100cqh - 74px) * .98)); z-index: 2; }
.runtime-bridge { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; overflow: visible; }
.runtime-bridge path { fill: none; stroke: var(--porcelain-blue); stroke-width: .6; stroke-dasharray: 2 7; opacity: .24; }
.runtime-transfer { position: absolute; left: 0; top: 0; width: 3px; height: 3px; border-radius: 50%; background: var(--porcelain-blue); box-shadow: 0 0 8px var(--porcelain-blue); pointer-events: none; z-index: 2; animation: runtime-transfer 1.8s linear forwards; }
.runtime-transfer.is-warning { background: var(--porcelain-warning); box-shadow: 0 0 8px #8c4d2566; }
.runtime-arrival { fill: none; stroke: var(--porcelain-blue); stroke-width: .8; opacity: 0; transform-box: fill-box; transform-origin: center; animation: runtime-arrival 1.2s 1.65s ease-out forwards; }
.runtime-arrival.is-warning { stroke: var(--porcelain-warning); }
.runtime-bridge.is-still .runtime-arrival { animation-play-state: paused; }
@keyframes runtime-transfer { from { offset-distance: 0%; opacity: 0; } 20% { opacity: 1; } to { offset-distance: 100%; opacity: 0; } }
@keyframes runtime-arrival { from { transform: scale(.4); opacity: .8; } to { transform: scale(2.5); opacity: 0; } }
.composition-closeup .runtime-station { left: auto; right: 8px; }
.composition-closeup .closeup-identity { top: 32px; left: 24px; right: auto; text-align: left; }
.runtime-log-details { margin: 16px 0 24px; }
.runtime-log-status { display: flex; flex-wrap: wrap; gap: 8px 20px; justify-content: space-between; font-size: 11px; color: var(--porcelain-muted); }
.runtime-log-status small,.runtime-log-help { font-size: 10px; color: var(--porcelain-muted); }
.runtime-log-help { line-height: 1.8; }
.runtime-log-tools { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.runtime-log-tools input,.runtime-log-tools select,.log-follow-toggle { min-height: 34px; padding: 6px 9px; color: var(--porcelain-ink); border: 1px solid var(--porcelain-line); border-radius: 3px; background: var(--porcelain-white); font: 11px 'Microsoft YaHei',sans-serif; }
.runtime-log-tools input { flex: 1 1 170px; min-width: 0; }
.runtime-log-tools input::placeholder { color: var(--porcelain-muted); }
.runtime-log-tools :focus-visible { outline: 1px solid var(--porcelain-blue); outline-offset: 2px; }
.log-follow-toggle { min-width: 110px; cursor: pointer; }
.log-follow-toggle[aria-pressed=false] { color: var(--porcelain-warning); border-color: #8c4d2555; }
.log-reading-status { color: var(--porcelain-muted); font-size: 10px; line-height: 1.6; }
.runtime-log-list { list-style: none; padding: 0; max-height: 42vh; overflow-y: auto; overscroll-behavior: contain; overflow-anchor: none; scrollbar-gutter: stable; }
.runtime-log-list li { border-bottom: 1px solid var(--porcelain-line); padding: 12px 0; }
.runtime-log-list li > div { display: flex; flex-wrap: wrap; gap: 6px 10px; font: 10px/1.6 Consolas,monospace; color: var(--porcelain-muted); }
.runtime-log-list b { color: var(--porcelain-ink); }
.runtime-log-list pre { margin: 6px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; font: 11px/1.8 Consolas,'Microsoft YaHei',monospace; color: var(--porcelain-ink); }
.runtime-log-list .log-warning b { color: var(--porcelain-warning); }
.runtime-log-empty { padding: 20px 0; font-size: 12px; color: var(--porcelain-muted); }
.observatory-note-dialog h3 { font: 24px/1.6 SimSun,serif; white-space: pre-line; }
.observatory-note-dialog p { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; line-height: 2; color: var(--porcelain-muted); }
.observatory-note-dialog small { font-size: 10px; color: var(--porcelain-muted); }
@container (max-height: 540px) {
  .field-caption { display: none; }
}
@media (max-width: 850px), (max-height: 570px) {
  .runtime-bridge,.runtime-transfer { display: none; }
  .runtime-station,.composition-closeup .runtime-station { position: relative; left: auto; right: auto; bottom: auto; width: min(100%,480px); margin: 0 auto 20px; flex: 0 0 auto; }
}
@media (prefers-reduced-motion: reduce) { .runtime-transfer,.runtime-arrival { display: none; } }
</style>
