<script setup lang="ts">
import type { FluxGeometry } from '@/components/MiyaFluxScene.vue'
import type { RuntimeAnchor, RuntimeCategory, RuntimeLog, RuntimeSeverity } from '@/utils/miyaRuntimeLogs'
import { computed, nextTick, ref, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import MiyaFluxPortraitSettings from '@/components/MiyaFluxPortraitSettings.vue'
import MiyaFluxScene from '@/components/MiyaFluxScene.vue'
import MiyaRuntimeRings from '@/components/MiyaRuntimeRings.vue'
import { useMiyaFluxPreferences } from '@/composables/useMiyaFluxPreferences'
import { useMiyaPresence } from '@/composables/useMiyaPresence'
import { useMiyaRuntimeLogs } from '@/composables/useMiyaRuntimeLogs'
import { porcelainEmotionColor } from '@/utils/miyaFluxTheme'
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
const noteExpanded = ref(false)
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
const incomplete = computed(() => [presence.value.persona, presence.value.emotion, presence.value.phase, presence.value.memoryCount, presence.value.platformCount].includes(null))
const statusLabel = computed(() => online.value ? incomplete.value ? '部分状态待同步' : '共鸣已连接' : connection.value === 'connecting' ? '正在感知弥娅' : '等待重新连接')
const emotionAccent = computed(() => porcelainEmotionColor(online.value ? presence.value.emotion ?? 'calm' : 'neutral'))
const syncedAt = computed(() => updatedAt.value?.toLocaleTimeString('zh-CN', { hour12: false }) ?? '尚未同步')
const phase = computed(() => phaseLabel(online.value ? presence.value.phase : null))
const emotion = computed(() => emotionLabel(online.value ? presence.value.emotion : null))
const intensity = computed(() => online.value ? presence.value.emotionIntensity : null)
const emotionReadings = computed(() => online.value ? [...presence.value.emotions].sort((a, b) => b.intensity - a.intensity) : [])
const note = computed(() => presence.value.note)
const noteDate = computed(() => note.value ? new Date(note.value.createdAt).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '')
const lifecycleTime = computed(() => online.value && presence.value.lifecycleAt ? new Date(presence.value.lifecycleAt).toLocaleTimeString('zh-CN', { hour12: false }) : null)
const memory = computed(() => online.value && presence.value.memoryCount !== null ? presence.value.memoryCount.toLocaleString('zh-CN') : '—')
const platforms = computed(() => online.value ? presence.value.platformCount ?? '—' : '—')
const selectedMemory = computed(() => MEMORY_LAYERS.find(layer => layer.id === selectedLayer.value))
const identityPosition = computed(() => {
  const g = geometry.value
  if (!g || composition.value === 'closeup')
    return undefined
  return { left: `${g.x}px`, top: `${g.y - g.radius * 0.7}px` }
})
function count(value: number | null | undefined) {
  return online.value && value != null ? value.toLocaleString('zh-CN') : '—'
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
  <main class="observatory-view" :class="[{ 'is-immersive': immersive }, `composition-${composition}`]" :style="{ '--soul-accent': emotionAccent }" @keydown.esc="immersive = false">
    <header class="observatory-header">
      <button class="observatory-back" title="返回首页" aria-label="返回首页" @click="router.push('/')">
        ←
      </button>
      <div class="observatory-title">
        <h1>弥娅观测台</h1><span class="mono">MIYA / LIVING FIELD</span>
      </div>
      <button class="immersion-toggle" :aria-pressed="immersive" @click="immersive = !immersive">
        {{ immersive ? '退出沉浸' : '沉浸观测' }} ⛶
      </button>
    </header>
    <div class="observatory-toolbar">
      <div class="composition-modes" role="group" aria-label="圆环构图">
        <button v-for="item in compositions" :key="item.id" :aria-pressed="composition === item.id" @click="composition = item.id">
          {{ item.label }}
        </button>
      </div>
      <div class="field-controls">
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
    <section class="observatory-workspace" :data-composition="composition" aria-label="弥娅灵魂共鸣">
      <div class="field-space" aria-label="弥娅六层记忆与灵魂光场">
        <MiyaFluxScene class="observatory-scene" framed :selected-layer="selectedLayer" :runtime-logs="runtimeEntries" @geometry="geometry = $event" />
        <div class="field-vignette" aria-hidden="true" />
        <span class="field-index mono">BLUE & WHITE / {{ composition === 'complete' ? 'WHOLE / 完整观测' : 'CLOSE / 局部特写' }}</span>
        <div v-if="geometry" class="ring-identity" :class="{ 'closeup-identity': composition === 'closeup' }" :style="identityPosition">
          <span class="persona-name">{{ online ? presence.persona ?? '人格待同步' : '等待弥娅的信号' }}</span>
          <button class="phase-label" @click="openDetails()">
            {{ phase }}<span> · {{ emotion }}<template v-if="intensity !== null"> {{ intensity }}%</template></span>
          </button>
        </div>
        <div class="field-caption">
          <span class="mono">{{ paused ? 'STILL / RESONANCE' : 'CONTINUOUS / BECOMING' }}</span><p>灵魂主环 · 青花共鸣</p>
        </div>
        <span class="field-art-note">光场为艺术化表达 · 点选副环读取运行轨迹</span>
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
      <button v-show="!immersive" class="compact-note-trigger" @click="noteDetails?.showModal()">
        弥娅的短笺 ↗
      </button>
      <MiyaRuntimeRings class="runtime-station" :presence="presence" :online="online" :entries="runtimeEntries" :recent="runtimeRecent" :connection="logConnection" :paused="paused" :hidden="logHidden" :now="logClock" :composition="composition" :selected-layer="selectedLayer" @select="openRuntime" @anchors="runtimeAnchors = $event" />
      <aside v-show="!immersive" class="presence-panel" :class="{ 'note-expanded': noteExpanded }" aria-label="弥娅的短笺">
        <span class="presence-eyebrow mono">A NOTE FROM MIYA</span>
        <Transition name="note" mode="out-in">
          <div :key="note?.id || 'empty'" class="presence-note">
            <h2>{{ note?.title || '等一封，\n弥娅的短笺。' }}</h2>
            <p id="observatory-note-body" class="presence-intro">
              {{ note?.body || '弥娅留下的话，会安静地保存在这里。' }}
            </p>
            <p class="note-meta">
              {{ note ? `${note.personaName || '弥娅'} · ${noteDate}` : '尚未留下短笺' }}<span v-if="note && !online"> · 已保存</span>
            </p>
          </div>
        </Transition>
        <button class="note-toggle" aria-controls="observatory-note-body" :aria-expanded="noteExpanded" @click="noteExpanded = !noteExpanded">
          {{ noteExpanded ? '收起短笺 ↑' : '展开短笺 ↓' }}
        </button>
      </aside>
    </section>
    <footer class="observatory-footer">
      <button class="connection-summary" :title="updatedAt ? `快照采样 ${syncedAt}` : '尚未同步'" @click="openDetails()">
        <i :class="{ online }" />{{ statusLabel }}<span>{{ online ? streaming ? '实时同步' : '定时同步' : '等候信号' }}</span>
      </button>
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
        <small>{{ note ? `${note.personaName || '弥娅'} · ${noteDate}` : '尚未留下短笺' }}</small>
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
          {{ online ? presence.persona ?? '人格待同步' : '等待弥娅的信号' }}
        </p>
        <section class="observatory-readings" aria-label="弥娅实时状态">
          <article>
            <span class="reading-label"><i />此刻状态 <small class="mono">SOUL</small></span><div class="reading-value">
              <strong class="phase-value">{{ phase }}</strong>
            </div>
            <small class="reading-detail">{{ lifecycleTime ? `心跳采样 ${lifecycleTime}` : '等候生命状态信号' }}</small>
          </article>
          <article>
            <span class="reading-label"><i />记忆条目 <small class="mono">MEMORY</small></span><div class="reading-value">
              <strong>{{ memory }}</strong><span>个记忆节点</span>
            </div>
            <div class="memory-layer-readings" aria-label="六层记忆数量">
              <span v-for="layer in MEMORY_LAYERS" :key="layer.id">{{ layer.label }} <b>{{ online ? presence.memoryLayers[layer.id] ?? '—' : '—' }}</b></span>
            </div>
          </article>
          <article>
            <span class="reading-label"><i />已启用平台 <small class="mono">M-LINK</small></span><div class="reading-value">
              <strong>{{ platforms }}</strong><span>个交流入口</span>
            </div>
            <small class="reading-detail">在线 {{ online ? presence.onlinePlatforms ?? '—' : '—' }} · 已启用 {{ platforms }}</small>
          </article>
          <article class="reading-connection">
            <span class="reading-label"><i :class="{ online }" />{{ statusLabel }}<button class="refresh-reading" title="重新同步状态" aria-label="重新同步状态" @click="refresh">↻</button></span>
            <p>{{ updatedAt ? `快照采样 ${syncedAt}` : '等候首次状态同步' }}</p>
            <small>{{ online ? streaming ? '实时同步中' : '定时同步 · 正在恢复实时连接' : updatedAt ? '信号已中断，等候新的状态' : '连接后呈现真实状态' }}</small>
          </article>
        </section>
        <div class="emotion-reading">
          <div><span>此刻的情绪</span><strong>{{ emotion }}<span v-if="intensity !== null"> · {{ intensity }}%</span></strong></div>
          <div class="emotion-spectrum" aria-label="当前情绪强度">
            <div v-for="item in emotionReadings.slice(0, 4)" :key="item.name" class="emotion-meter" :title="`${emotionLabel(item.name)} ${item.intensity}%`">
              <span>{{ emotionLabel(item.name) }}</span><i><b :style="{ width: `${item.intensity}%` }" /></i><small>{{ item.intensity }}%</small>
            </div>
            <span v-if="!emotionReadings.length" class="emotion-empty">{{ intensity === null ? '等候情绪信号' : '当前仅同步主导情绪' }}</span>
          </div>
          <small>情绪晕染青花，生命节律牵动光场。</small>
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

<style scoped>
.observatory-view { --obs-line: #94b1e42e; display: flex; flex-direction: column; flex: 1; min-width: 0; min-height: 0; overflow: hidden; color: #ecf1f9; background: #080f20; border: 1px solid var(--obs-line); border-radius: 6px; }
.mono { font: 9px/1.5 Consolas,monospace; letter-spacing: .13em; }
button { color: inherit; font: inherit; cursor: pointer; }
.observatory-header { display: flex; align-items: center; gap: 12px; flex: 0 0 auto; padding: 13px 20px; border-bottom: 1px solid #94b1e417; }
.observatory-back { width: 28px; height: 28px; color: #b5ccea; border: 1px solid var(--obs-line); background: #719de60a; }
.observatory-title { display: flex; align-items: baseline; flex-wrap: wrap; gap: 14px; }
.observatory-title h1 { margin: 0; font-size: 14px; font-weight: 500; letter-spacing: .12em; }
.observatory-title .mono { color: #7895bd; font-size: 8px; }
.immersion-toggle { margin-left: auto; padding: 6px; white-space: nowrap; color: #b1c4e1; background: transparent; font-size: 11px; }
.observatory-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex: 0 0 auto; padding: 10px 20px; }
.composition-modes,.field-modes { display: flex; gap: 3px; padding: 3px; border: 1px solid #94b1e425; border-radius: 4px; }
.composition-modes button,.field-modes button { padding: 6px 12px; min-height: 28px; color: #94acce; background: transparent; font-size: 11px; white-space: nowrap; border-radius: 2px; }
.composition-modes button[aria-pressed=true],.field-modes button[aria-pressed=true] { color: #d8e8ff; background: #87ace820; }
.field-controls { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.motion-toggle { padding: 6px; min-height: 32px; background: transparent; color: #abc0df; font-size: 11px; white-space: nowrap; }
.observatory-workspace { position: relative; flex: 1; min-height: 0; isolation: isolate; container-type: size; }
.field-space { position: absolute; inset: 0; overflow: hidden; }
.observatory-scene { width: 100%; height: 100%; border: 0; pointer-events: none; }
.field-vignette { position: absolute; inset: 0; background: linear-gradient(90deg,#080f20e8,transparent 37%,transparent 85%),linear-gradient(0deg,#080f20,transparent 17%,transparent 90%,#080f20); pointer-events: none; }
.field-index { position: absolute; top: 12px; left: 24px; color: #7593be; font-size: 8px; }
.ring-identity { position: absolute; display: grid; gap: 6px; text-align: center; transform: translate(-50%,-50%); max-width: 260px; }
.persona-name { font: 14px/1.5 'Noto Serif SC',SimSun,serif; color: #d7e5f9; letter-spacing: .12em; }
.phase-label { padding: 2px 6px; font-size: 10px; line-height: 1.7; color: #a8c5ed; background: #081021aa; border-radius: 3px; white-space: nowrap; }
.phase-label span { color: #99b3d5; }
.closeup-identity { top: 56px; right: 30px; left: auto; text-align: right; transform: none; }
.field-caption { position: absolute; bottom: 16px; left: 63%; transform: translateX(-50%); text-align: center; pointer-events: none; }
.field-caption .mono { color: #92add3; font-size: 8px; }
.field-caption p { margin: 5px 0 0; color: #a8bfdf; font-size: 10px; letter-spacing: .15em; }
.field-art-note { position: absolute; bottom: 17px; left: 24px; color: #647fa7; font-size: 8px; }
.presence-panel { position: absolute; top: 50%; left: 26px; width: clamp(160px,22%,265px); max-height: calc(100% - 100px); overflow: auto; transform: translateY(-50%); padding: 10px 10px 12px 0; scrollbar-gutter: stable; }
.presence-eyebrow { color: #7f9ecb; font-size: 8px; }
.presence-note h2 { margin: 18px 0 15px; color: #e0eaf9; font: 400 clamp(22px,2vw,32px)/1.65 'Noto Serif SC',SimSun,serif; letter-spacing: .07em; white-space: pre-line; overflow-wrap: anywhere; }
.presence-intro { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; margin: 0; color: #9bb1d2; font-size: 11px; line-height: 2; overflow-wrap: anywhere; white-space: pre-line; }
.note-expanded .presence-intro { display: block; }
.note-meta { margin: 14px 0; color: #7e99c0; font-size: 9px; line-height: 1.9; }
.note-toggle { padding: 6px 0; background: transparent; color: #8eacd4; font-size: 10px; }
.note-enter-active,.note-leave-active { transition: opacity .3s; }
.note-enter-from,.note-leave-to { opacity: 0; }
.composition-closeup .presence-panel { left: auto; right: 28px; width: clamp(170px,24%,290px); }
.composition-closeup .field-vignette { background: linear-gradient(270deg,#080f20f2,transparent 42%),linear-gradient(0deg,#080f20,transparent 15%,transparent 90%,#080f20); }
.composition-closeup .field-caption { left: auto; right: 30px; transform: none; text-align: right; }
.observatory-footer { display: flex; align-items: center; flex-wrap: wrap; justify-content: space-between; gap: 12px 18px; flex: 0 0 auto; padding: 12px 20px; border-top: 1px solid #94b1e419; background: #080f20; }
.connection-summary { display: flex; align-items: center; gap: 7px; background: transparent; font-size: 10px; color: #afc6e6; text-align: left; }
.connection-summary i { width: 5px; height: 5px; flex-shrink: 0; border-radius: 50%; background: #677c9c; }
.connection-summary i.online { background: #b4d5ff; box-shadow: 0 0 8px #a7caff77; }
.connection-summary span { font-size: 9px; color: #7c98bf; }
.presence-links { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.presence-links button { min-height: 32px; padding: 6px 10px; color: #b4cdec; background: #719de60c; border: 1px solid #719de628; font-size: 10px; }
.presence-links button:hover { background: #719de627; }
.details-credit { margin: 12px 0 0; color: #6984ab; font: 9px/1.8 Consolas,monospace; }
.details-credit a { color: #93b1d8; text-underline-offset: 3px; }
.is-immersive .field-index,.is-immersive .field-art-note { display: none; }
.observatory-details { width: min(540px,calc(100vw - 32px)); max-height: calc(100dvh - 90px); margin: auto; padding: 24px; overflow: auto; color: #d6e4f9; border: 1px solid #9dbce752; border-radius: 8px; background: linear-gradient(145deg,#12213b,#080f20); box-shadow: 0 24px 90px #020510bb; }
.observatory-details::backdrop { background: #020510a6; }
.details-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.details-header .mono { font-size: 9px; color: #8caad3; }
.details-header h2 { margin: 8px 0 14px; font: 22px SimSun,serif; }
.details-header button { align-self: start; width: 34px; height: 34px; background: transparent; color: #b8cfec; font-size: 24px; }
.details-persona { color: #a2bcdf; font-size: 12px; }
.selected-memory { display: flex; align-items: baseline; flex-wrap: wrap; gap: 10px; margin: 12px 0 22px; }
.selected-memory strong { font: 32px Consolas,monospace; overflow-wrap: anywhere; }
.selected-memory span { color: #8eabd2; font-size: 11px; }
.observatory-readings { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 24px 20px; padding-block: 20px; border-block: 1px solid #94b1e42e; }
.observatory-readings article { min-width: 0; display: grid; align-content: start; gap: 10px; overflow-wrap: anywhere; }
.reading-label { display: flex; align-items: center; gap: 6px; color: #9eb8dc; font-size: 11px; }
.reading-label small { margin-left: auto; color: #617fa8; font-size: 7px; }
.reading-value { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px; }
.reading-value strong { color: #dbe7f9; font: 26px/1.3 Consolas,SimSun,serif; }
.reading-value > span,.reading-detail { color: #8ea8cc; font-size: 10px; line-height: 1.7; }
.memory-layer-readings { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 7px; color: #8ea8cc; font-size: 10px; }
.memory-layer-readings > span { overflow-wrap: anywhere; }
.memory-layer-readings b { font: 10px Consolas,monospace; color: #c4d8f3; }
.refresh-reading { margin-left: auto; min-height: 28px; min-width: 28px; background: transparent; color: #b4ceee; font-size: 20px; }
.reading-connection p { margin: 0; font-size: 11px; line-height: 1.7; }
.reading-connection > small { color: #8ea8cc; font-size: 10px; line-height: 1.7; }
.emotion-reading { margin-top: 20px; }
.emotion-reading > div:first-child { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; color: #a8c0e1; }
.emotion-reading strong { color: var(--soul-accent,#b4ceee); }
.emotion-spectrum { display: grid; gap: 10px; margin: 14px 0; }
.emotion-meter { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #9cb5d8; }
.emotion-meter > span { min-width: 30px; }
.emotion-meter > i { flex: 1; height: 3px; background: #243858; }
.emotion-meter b { display: block; height: 100%; background: #aacbf6; }
.emotion-meter > small { min-width: 30px; text-align: right; }
.emotion-empty,.emotion-reading > small,.details-help { color: #839fc4; font-size: 10px; line-height: 1.8; }
.details-help { margin: 20px 0 0; }
@media (max-width: 1100px) { .connection-summary span { display: none; } }
@media (max-width: 800px) {
  .observatory-toolbar { flex-wrap: wrap; padding-inline: 12px; }
  .field-controls { margin-left: auto; gap: 6px; }
  .field-modes button { padding-inline: 8px; }
  .observatory-title .mono { display: none; }
  .presence-note h2 { font-size: 22px; }
  .presence-panel { width: 24%; left: 16px; }
  .composition-closeup .presence-panel { right: 16px; }
}
@media (max-width: 850px), (max-height: 570px) {
  .observatory-view { overflow-y: auto; overflow-x: hidden; }
  .observatory-header,.observatory-toolbar,.observatory-footer { flex: 0 0 auto; }
  .observatory-workspace { display: flex; flex-direction: column; flex: 0 0 auto; container-type: inline-size; }
  .field-space { position: relative; flex: 0 0 auto; height: clamp(370px,65vh,560px); }
  .presence-panel,.composition-closeup .presence-panel { position: relative; top: auto; left: auto; right: auto; transform: none; width: auto; max-height: none; margin: 0 20px; padding: 20px 0; border-top: 1px solid #94b1e426; overflow: visible; }
  .presence-note h2 { margin: 12px 0; font-size: 24px; }
  .presence-intro { -webkit-line-clamp: 2; }
  .note-meta { margin-bottom: 4px; }
  .field-index { left: 16px; font-size: 7px; }
  .field-art-note { left: 16px; bottom: 8px; font-size: 7px; }
  .field-caption { left: 50%; bottom: 28px; white-space: nowrap; }
  .field-caption p { font-size: 9px; }
  .composition-closeup .field-caption { right: 16px; bottom: 35px; }
  .closeup-identity { top: 35px; right: 16px; max-width: 160px; }
  .closeup-identity .persona-name { font-size: 12px; }
  .closeup-identity .phase-label { white-space: normal; }
  .field-vignette { background: linear-gradient(0deg,#080f20,transparent 18%); }
  .ring-identity { gap: 3px; }
  .persona-name { font-size: 11px; }
  .phase-label { font-size: 9px; }
  .observatory-footer { padding: 12px; gap: 10px; }
  .presence-links { width: 100%; gap: 6px; }
  .presence-links button { flex: 1; padding-inline: 5px; }
}
@media (max-width: 480px) {
  .observatory-header { padding: 12px; gap: 8px; }
  .observatory-title h1 { font-size: 12px; }
  .immersion-toggle { font-size: 10px; }
  .observatory-toolbar { gap: 10px; }
  .composition-modes { width: 100%; }
  .composition-modes button { flex: 1; }
  .field-controls { width: 100%; justify-content: space-between; gap: 4px; }
  .field-modes button { padding-inline: 6px; }
  .motion-toggle { font-size: 10px; }
  .observatory-details { padding: 18px; }
  .observatory-readings { grid-template-columns: minmax(0,1fr); }
}
.runtime-station { position: absolute; left: 8px; bottom: 24px; width: min(38cqw,460px,calc((100cqh - 180px) * .98)); z-index: 2; }
.runtime-bridge { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; overflow: visible; }
.runtime-bridge path { fill: none; stroke: #a8cbed; stroke-width: .6; stroke-dasharray: 2 7; opacity: .24; }
.runtime-transfer { position: absolute; left: 0; top: 0; width: 3px; height: 3px; border-radius: 50%; background: #cfe9ff; box-shadow: 0 0 8px #adcfff; pointer-events: none; z-index: 2; animation: runtime-transfer 1.8s linear forwards; }
.runtime-transfer.is-warning { background: #e8c89f; box-shadow: 0 0 8px #e8c89f99; }
.runtime-arrival { fill: none; stroke: #cfe9ff; stroke-width: .8; opacity: 0; transform-box: fill-box; transform-origin: center; animation: runtime-arrival 1.2s 1.65s ease-out forwards; }
.runtime-arrival.is-warning { stroke: #e8c89f; }
.runtime-bridge.is-still .runtime-arrival { animation-play-state: paused; }
@keyframes runtime-transfer { from { offset-distance: 0%; opacity: 0; } 20% { opacity: 1; } to { offset-distance: 100%; opacity: 0; } }
@keyframes runtime-arrival { from { transform: scale(.4); opacity: .8; } to { transform: scale(2.5); opacity: 0; } }
.presence-panel { top: 5px; left: 26px; transform: none; width: 31%; max-height: 24%; }
.presence-note h2 { margin: 8px 0; font-size: clamp(18px,1.6vw,24px); line-height: 1.4; }
.presence-intro { -webkit-line-clamp: 1; }
.note-meta { display: none; }
.note-expanded { z-index: 4; max-height: 24%; padding: 14px; background: #081021f5; border: 1px solid #94b1e42e; }
.note-expanded .note-meta { display: block; }
.composition-closeup .runtime-station { left: auto; right: 8px; }
.composition-closeup .presence-panel { top: 5px; width: 31%; max-height: min(24%,150px); }
.composition-closeup .closeup-identity { top: 32px; left: 24px; right: auto; text-align: left; }
.runtime-log-details { margin: 16px 0 24px; }
.runtime-log-status { display: flex; flex-wrap: wrap; gap: 8px 20px; justify-content: space-between; font-size: 11px; color: #b4ccea; }
.runtime-log-status small,.runtime-log-help { font-size: 10px; color: #819ec4; }
.runtime-log-help { line-height: 1.8; }
.runtime-log-tools { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.runtime-log-tools input,.runtime-log-tools select,.log-follow-toggle { min-height: 34px; padding: 6px 9px; color: #c9dbf1; border: 1px solid #92b5e13d; border-radius: 3px; background: #0b162b; font: 11px 'Microsoft YaHei',sans-serif; }
.runtime-log-tools input { flex: 1 1 170px; min-width: 0; }
.runtime-log-tools input::placeholder { color: #7895b9; }
.runtime-log-tools :focus-visible { outline: 1px solid #a8c9ed; outline-offset: 2px; }
.log-follow-toggle { min-width: 110px; cursor: pointer; }
.log-follow-toggle[aria-pressed=false] { color: #e8d4b7; border-color: #e8c89f55; }
.log-reading-status { color: #a2bddd; font-size: 10px; line-height: 1.6; }
.runtime-log-list { list-style: none; padding: 0; max-height: 42vh; overflow-y: auto; overscroll-behavior: contain; overflow-anchor: none; scrollbar-gutter: stable; }
.runtime-log-list li { border-bottom: 1px solid #91b3e220; padding: 12px 0; }
.runtime-log-list li > div { display: flex; flex-wrap: wrap; gap: 6px 10px; font: 10px/1.6 Consolas,monospace; color: #83a3ca; }
.runtime-log-list b { color: #b7cee8; }
.runtime-log-list pre { margin: 6px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; font: 11px/1.8 Consolas,'Microsoft YaHei',monospace; color: #bfcee2; }
.runtime-log-list .log-warning b { color: #e8c89f; }
.runtime-log-empty { padding: 20px 0; font-size: 12px; color: #8da9cb; }
.compact-note-trigger { display: none; position: absolute; top: 8px; left: 24px; padding: 3px 0; background: transparent; color: #a6c1e1; font-size: 10px; z-index: 3; }
.composition-closeup .compact-note-trigger { left: auto; right: 24px; }
.observatory-note-dialog h3 { font: 24px/1.6 SimSun,serif; white-space: pre-line; }
.observatory-note-dialog p { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; line-height: 2; color: #aec5df; }
.observatory-note-dialog small { font-size: 10px; color: #8da9cb; }
@container (max-height: 540px) {
  .presence-panel { display: none; }
  .compact-note-trigger { display: block; }
  .runtime-station { width: min(38cqw,460px,calc((100cqh - 90px) * .98)); }
  .field-caption { display: none; }
  .field-index { top: 32px; }
  .composition-closeup .field-index { top: 12px; }
  .field-art-note { bottom: 6px; }
}
@media (max-width: 850px), (max-height: 570px) {
  .runtime-bridge,.runtime-transfer { display: none; }
  .runtime-station,.composition-closeup .runtime-station { position: relative; left: auto; right: auto; bottom: auto; width: min(100%,480px); margin: 0 auto 20px; flex: 0 0 auto; }
  .presence-panel,.composition-closeup .presence-panel { top: auto; left: auto; right: auto; transform: none; width: auto; max-height: none; background: transparent; }
  .presence-note h2 { font-size: 24px; }
  .presence-intro { -webkit-line-clamp: 2; }
  .note-meta { display: block; }
  .note-expanded { border: 0; }
}
@media (prefers-reduced-motion: reduce) { .runtime-transfer,.runtime-arrival { display: none; } .note-enter-active,.note-leave-active { transition: none; } }
</style>
