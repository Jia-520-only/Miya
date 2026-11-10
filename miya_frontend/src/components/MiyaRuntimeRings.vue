<script setup lang="ts">
import type { MiyaPresence } from '@/utils/miyaPresence'
import type { RuntimeAnchor, RuntimeCategory, RuntimeLog } from '@/utils/miyaRuntimeLogs'
import { computed, nextTick, onMounted, onUnmounted, ref, useId, watch } from 'vue'
import { MEMORY_LAYERS } from '@/utils/miyaPresence'
import { RUNTIME_RINGS, runtimeExcerpt, runtimeWarning } from '@/utils/miyaRuntimeLogs'

const props = defineProps<{
  presence: MiyaPresence
  online: boolean
  entries: RuntimeLog[]
  recent: RuntimeLog[]
  connection: string
  paused: boolean
  hidden: boolean
  now: number
  composition: string
  selectedLayer?: string | null
}>()
const emit = defineEmits<{ select: [category: RuntimeCategory, layer?: string], anchors: [value: RuntimeAnchor[]] }>()
const orbit = ref<SVGSVGElement>()
const pointer = ref<{ category: RuntimeCategory, layer?: string } | null>(null)
const focused = ref<{ category: RuntimeCategory, layer?: string } | null>(null)
const active = computed(() => pointer.value ?? focused.value)
const hovered = computed(() => active.value?.category)
const activeLayer = computed(() => MEMORY_LAYERS.find(layer => layer.id === active.value?.layer))
const activeRing = computed(() => RUNTIME_RINGS.find(ring => ring.id === hovered.value))
const inspector = ref<HTMLElement>()
const inspectorPosition = ref({ left: '-9999px', top: '0px' })
let observer: ResizeObserver | undefined
function positionInspector() {
  const svg = orbit.value?.getBoundingClientRect()
  const box = inspector.value?.getBoundingClientRect()
  const ring = activeRing.value
  if (!svg || !box || !ring)
    return
  const scale = svg.width / 440
  const x = svg.left + ring.x * scale
  const y = svg.top + ring.y * scale
  const radius = ring.radius * scale
  const rightSpace = window.innerWidth - svg.right - 24
  const leftSpace = svg.left - 24
  const placeRight = props.composition === 'closeup' ? leftSpace < box.width && rightSpace > leftSpace : rightSpace >= box.width || rightSpace > leftSpace
  let left = placeRight ? svg.right + 12 : svg.left - box.width - 12
  let top = y - box.height / 2
  if (Math.max(leftSpace, rightSpace) < box.width) {
    left = x - box.width / 2
    top = y - radius - box.height - 12
  }
  inspectorPosition.value = {
    left: `${Math.max(12, Math.min(window.innerWidth - box.width - 12, left))}px`,
    top: `${Math.max(12, Math.min(window.innerHeight - box.height - 12, top))}px`,
  }
}
function measureAnchor() {
  const element = orbit.value
  const workspace = element?.closest('.observatory-workspace')
  if (!element || !workspace)
    return
  const svg = element.getBoundingClientRect()
  const parent = workspace.getBoundingClientRect()
  const scale = svg.width / 440
  emit('anchors', RUNTIME_RINGS.map(ring => ({ category: ring.id, x: svg.left - parent.left + ring.x * scale, y: svg.top - parent.top + ring.y * scale, radius: ring.radius * scale })))
  positionInspector()
}
onMounted(() => {
  observer = new ResizeObserver(measureAnchor)
  if (orbit.value)
    observer.observe(orbit.value)
  window.addEventListener('scroll', positionInspector, true)
})
onUnmounted(() => {
  observer?.disconnect()
  window.removeEventListener('scroll', positionInspector, true)
})
watch(() => props.composition, async () => {
  await nextTick()
  measureAnchor()
})
const uid = useId().replace(/[^a-z\d]/gi, '')
const preview = ref<RuntimeLog>()
function setHovered(category: RuntimeCategory | null, layer?: string) {
  pointer.value = category ? { category, layer } : null
}
function setFocused(category: RuntimeCategory | null, layer?: string) {
  focused.value = category ? { category, layer } : null
}
watch([hovered, activeLayer], async () => {
  preview.value = [...props.entries].reverse().find(entry => entry.category === hovered.value)
  await nextTick()
  positionInspector()
})
const layerChanges = ref<Record<string, number>>({})
watch(() => ({ online: props.online, layers: { ...props.presence.memoryLayers } }), (next, previous) => {
  if (!next.online || !previous?.online)
    return
  for (const layer of MEMORY_LAYERS) {
    if (next.layers[layer.id] != null && previous.layers[layer.id] != null && next.layers[layer.id] !== previous.layers[layer.id])
      layerChanges.value[layer.id] = props.now
  }
})
const rings = computed(() => RUNTIME_RINGS.map(ring => ({
  ...ring,
  entries: props.entries.filter(entry => entry.category === ring.id).slice(-8).reverse(),
  recent: props.recent.filter(entry => entry.category === ring.id),
})))
const labels = MEMORY_LAYERS.map((layer, i) => {
  const a = -Math.PI / 2 + (i + 0.5) * Math.PI / 3
  return { ...layer, x: 224 + Math.cos(a) * 77, y: 145 + Math.sin(a) * 77 }
})
const focusEntry = computed(() => {
  return hovered.value ? preview.value : props.entries.at(-1)
})
function reading(value: number | null | undefined) {
  return props.online && value != null ? value.toLocaleString('zh-CN') : '—'
}
</script>

<template>
  <section class="runtime-rings" :class="{ 'is-still': paused || hidden, 'is-offline': connection !== 'online' }" aria-label="弥娅运行数据圆环">
    <div class="runtime-heading">
      <span>RUNTIME / 运行轨迹</span><small :data-status="connection">{{ connection === 'online' ? '● 日志实时连接' : connection === 'connecting' ? '◌ 日志连接中' : '◌ 日志连接中断' }}</small>
    </div>
    <svg ref="orbit" viewBox="0 0 440 405" class="runtime-orrery" aria-label="记忆、运行记录、感知与连接三个副环">
      <defs>
        <radialGradient :id="`${uid}-glaze`"><stop offset="0" stop-color="#0a1529" stop-opacity=".94" /><stop offset=".72" stop-color="#0a1529" stop-opacity=".8" /><stop offset="1" stop-color="#0a1529" stop-opacity=".1" /></radialGradient>
        <path v-for="ring in rings" :id="`${uid}-${ring.id}`" :key="ring.id" :d="`M ${ring.radius - 4},0 a ${ring.radius - 4},${ring.radius - 4} 0 1,1 ${-2 * (ring.radius - 4)},0 a ${ring.radius - 4},${ring.radius - 4} 0 1,1 ${2 * (ring.radius - 4)},0`" />
      </defs>
      <path class="orbital-link" d="M149 236 L155 244 M284 231 L291 239" />
      <g v-for="(ring, index) in rings" :key="ring.id" :transform="`translate(${ring.x} ${ring.y})`" class="runtime-ring" :data-category="ring.id" :class="[{ 'is-active': hovered === ring.id }]" @mouseenter="setHovered(ring.id)" @mouseleave="setHovered(null)" @focusin="setFocused(ring.id)" @focusout="setFocused(null)">
        <circle :r="ring.radius + 5" :fill="`url(#${uid}-glaze)`" />
        <circle class="hairline" :r="ring.radius + 3" />
        <circle class="hairline inner-line" :r="ring.radius - 22" />
        <g class="ring-turn" :class="{ reverse: index === 1 }" :style="{ '--turn-duration': `${100 + index * 24}s` }" aria-hidden="true">
          <path v-for="tick in 90" :key="tick" class="instrument-tick" :d="`M0 ${-ring.radius} v${tick % 5 ? 3 : 7}`" :transform="`rotate(${tick * 4})`" :opacity="tick % 5 ? .32 : .8" />
          <path class="sweep-line" :d="`M ${ring.radius - 15} 0 A ${ring.radius - 15} ${ring.radius - 15} 0 0 1 0 ${ring.radius - 15}`" />
          <g v-for="(entry, panel) in ring.entries.slice(0, 6)" :key="`panel-${entry.seq}`" :transform="`rotate(${panel * 51 + 20}) translate(0 ${-ring.radius + 13})`" class="runtime-micro-panel">
            <path d="M-15 -4 h30 M-15 6 h12" />
            <text text-anchor="middle" y="0">{{ entry.name.slice(-16) }}</text>
            <text text-anchor="middle" y="5">{{ entry.ts.slice(11, 19) }} / {{ entry.seq }}</text>
          </g>
          <text v-for="(entry, line) in ring.entries.slice(0, ring.id === 'memory' ? 3 : 2)" :key="entry.seq" class="log-ribbon" :class="{ 'is-warning': runtimeWarning(entry) }" :font-size="ring.id === 'memory' ? 5.5 : 4.8">
            <textPath :href="`#${uid}-${ring.id}`" :startOffset="`${line * 33}%`">{{ runtimeExcerpt(entry, ring.id === 'memory' ? 34 : 24) }}</textPath>
          </text>
        </g>
        <g v-if="connection === 'online'" class="event-traces" aria-hidden="true">
          <path v-for="(entry, trace) in ring.recent.slice(-10)" :key="entry.seq" class="event-trace" :class="{ 'is-warning': runtimeWarning(entry) }" :d="`M ${ring.radius + 7} 0 h${8 + trace % 4 * 3}`" :transform="`rotate(${entry.seq * 137.508 % 360})`" :opacity="Math.max(.15, 1 - (now - entry.receivedAt) / 60000)" />
        </g>
        <g v-if="ring.id !== 'memory'" class="ring-core" role="button" tabindex="0" :aria-label="`查看${ring.label}日志`" @click="emit('select', ring.id)" @keydown.enter.prevent="emit('select', ring.id)" @keydown.space.prevent="emit('select', ring.id)">
          <circle class="core-hit" :r="ring.radius - 26" />
          <text class="core-name" text-anchor="middle" y="-14">{{ ring.label }}</text>
          <text class="core-value" text-anchor="middle" y="8">{{ ring.id === 'connection' ? `${reading(presence.onlinePlatforms)} / ${reading(presence.platformCount)}` : connection === 'online' ? `${ring.recent.length}${ring.recent.length >= 160 ? '+' : ''}` : '—' }}</text>
          <text class="core-caption" text-anchor="middle" y="23">{{ ring.id === 'connection' ? '在线 / 启用平台' : '近 60 秒 / 日志条数' }}</text>
        </g>
      </g>
      <g class="memory-core" role="button" tabindex="0" aria-label="查看记忆日志" @mouseenter="setHovered('memory')" @mouseleave="setHovered(null)" @focusin="setFocused('memory')" @focusout="setFocused(null)" @click="emit('select', 'memory')" @keydown.enter.prevent="emit('select', 'memory')" @keydown.space.prevent="emit('select', 'memory')">
        <circle cx="224" cy="145" r="44" class="core-hit" />
        <text x="224" y="131" text-anchor="middle" class="core-name">六层记忆</text>
        <text v-if="reading(presence.memoryCount).length > 8" x="224" y="154" text-anchor="middle" class="core-value" textLength="84" lengthAdjust="spacingAndGlyphs">{{ reading(presence.memoryCount) }}</text>
        <text v-else x="224" y="154" text-anchor="middle" class="core-value">{{ reading(presence.memoryCount) }}</text>
        <text x="224" y="170" text-anchor="middle" class="core-caption">MEMORY / 实时存量</text>
      </g>
      <g v-for="layer in labels" :key="layer.id" class="ring-label" :class="{ 'layer-changed': online && now - (layerChanges[layer.id] ?? -Infinity) < 4000 }" :data-selected="selectedLayer === layer.id || activeLayer?.id === layer.id" role="button" tabindex="0" :aria-label="`${layer.label}记忆 ${reading(presence.memoryLayers[layer.id])}，查看详情`" @mouseenter="setHovered('memory', layer.id)" @mouseleave="setHovered(null)" @focusin="setFocused('memory', layer.id)" @focusout="setFocused(null)" @click="emit('select', 'memory', layer.id)" @keydown.enter.prevent="emit('select', 'memory', layer.id)" @keydown.space.prevent="emit('select', 'memory', layer.id)">
        <circle class="layer-hit" :cx="layer.x" :cy="layer.y" r="22" />
        <text :x="layer.x" :y="layer.y - 3" text-anchor="middle" class="layer-name">{{ layer.label }}</text>
        <text v-if="reading(presence.memoryLayers[layer.id]).length > 8" :x="layer.x" :y="layer.y + 11" text-anchor="middle" class="layer-value" textLength="54" lengthAdjust="spacingAndGlyphs">{{ reading(presence.memoryLayers[layer.id]) }}</text>
        <text v-else :x="layer.x" :y="layer.y + 11" text-anchor="middle" class="layer-value">{{ reading(presence.memoryLayers[layer.id]) }}</text>
      </g>
    </svg>
    <Teleport to="body">
      <div v-if="activeRing" ref="inspector" class="runtime-inspector" :style="inspectorPosition" aria-live="off">
        <div><strong>{{ activeLayer ? `${activeLayer.label}记忆` : activeRing.label }}</strong><b v-if="activeLayer">{{ reading(presence.memoryLayers[activeLayer.id]) }} <small>个节点</small></b><b v-else-if="activeRing.id === 'memory'">{{ reading(presence.memoryCount) }} <small>个节点</small></b><b v-else-if="activeRing.id === 'connection'">{{ reading(presence.onlinePlatforms) }} / {{ reading(presence.platformCount) }} <small>在线 / 启用</small></b></div>
        <p>{{ preview ? runtimeExcerpt(preview, 76) : '此分类暂未收到运行记录' }}</p>
        <small>{{ activeLayer ? '最近记忆模块日志 · 点选查看存量与完整记录' : activeRing.id === 'execution' ? '中心数字为近 60 秒接收的日志条数 · 点选查看' : '点选查看完整记录' }}</small>
      </div>
    </Teleport>
    <p class="runtime-caption" aria-live="off">
      <span>{{ focusEntry ? focusEntry.ts.slice(11, 19) : '—' }}</span>{{ focusEntry ? runtimeExcerpt(focusEntry, 64) : '等候运行事件' }}
    </p>
    <small class="runtime-footnote">{{ focusEntry?.historical ? '最近记录 · 历史补发' : '点选副环查看日志' }} · 光流为艺术化表达</small>
  </section>
</template>

<style scoped>
.runtime-rings { position: relative; color: #b1c9e9; min-width: 0; }
.runtime-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 16px; color: #7d9bc2; font: 8px/1.6 Consolas,monospace; letter-spacing: .12em; }
.runtime-heading small { font: 9px/1.5 sans-serif; letter-spacing: 0; white-space: nowrap; }
.runtime-heading small[data-status=online] { color: #b1d4dc; }
.runtime-orrery { display: block; width: 100%; overflow: visible; }
.orbital-link { fill: none; stroke: #8fbbef; stroke-width: .6; opacity: .4; stroke-dasharray: 2 5; }
.hairline { fill: none; stroke: #9cc1ed; stroke-width: .65; opacity: .55; }
.inner-line { opacity: .3; }
.instrument-tick { stroke: #c2d7ee; stroke-width: .7; fill: none; }
.sweep-line { fill: none; stroke: #bfdfff; stroke-width: 1; opacity: .65; }
.ring-turn { animation: runtime-turn var(--turn-duration) linear infinite; }
.ring-turn.reverse { animation-direction: reverse; }
.is-still .ring-turn,.runtime-ring.is-active .ring-turn { animation-play-state: paused; }
.log-ribbon { fill: #aac9e9; font-family: Consolas,'Microsoft YaHei',monospace; letter-spacing: .3px; opacity: .85; }
.log-ribbon.is-warning { stroke: none; }
.runtime-micro-panel path { fill: none; stroke: #adccec; stroke-width: .4; opacity: .35; }
.runtime-micro-panel text { fill: #92b4d7; font: 3.3px Consolas,'Microsoft YaHei',monospace; }
.is-warning { fill: #e8c89f; stroke: #e8c89f; }
.event-trace { stroke: #d9efff; stroke-width: 1; fill: none; }
.event-trace.is-warning { stroke: #e8c89f; }
.ring-core,.memory-core,.ring-label { cursor: pointer; outline: none; }
.core-hit,.layer-hit { fill: transparent; stroke: transparent; }
.core-name,.layer-name { fill: #b4cce7; font: 10px 'Microsoft YaHei',sans-serif; pointer-events: none; }
.core-value { fill: #e0ecf8; font: 18px Consolas,monospace; pointer-events: none; }
.core-caption { fill: #7395ba; font: 6px Consolas,'Microsoft YaHei',sans-serif; pointer-events: none; }
.layer-name { font-size: 10px; }
.layer-value { fill: #d2e5fb; font: 12px Consolas,monospace; pointer-events: none; }
.layer-changed .layer-hit { stroke: #cae6ff; stroke-width: .8; }
.layer-changed .layer-value { fill: #fff; }
.ring-core:hover .core-hit,.ring-core:focus-visible .core-hit,.memory-core:hover .core-hit,.memory-core:focus-visible .core-hit,.ring-label:hover .layer-hit,.ring-label:focus-visible .layer-hit { stroke: #b9d9ff; stroke-width: .8; stroke-dasharray: 2 4; }
.ring-label[data-selected=true] .layer-hit { stroke: #c9e1fb; stroke-width: .8; }
.is-active .hairline { opacity: .9; }
.is-offline .log-ribbon { opacity: .4; }
.runtime-caption { margin: -13px 16px 0; color: #9bb7d8; font: 10px/1.8 'Microsoft YaHei',sans-serif; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; min-height: 18px; }
.runtime-caption span { font: 9px Consolas,monospace; color: #6e8cb3; margin-right: 9px; }
.runtime-footnote { display: block; padding: 3px 16px 0; color: #6e88ac; font-size: 8px; }
.runtime-inspector { position: fixed; z-index: 60; width: min(240px,calc(100vw - 24px)); box-sizing: border-box; padding: 10px 12px; background: #0a1429f5; border: 1px solid #a8c9ee44; border-radius: 4px; box-shadow: 0 8px 28px #02071266; pointer-events: none; }
.runtime-inspector > div { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px; }
.runtime-inspector strong { font-size: 12px; font-weight: 500; color: #deebfa; }
.runtime-inspector b { font: 16px Consolas,monospace; color: #e5f0ff; overflow-wrap: anywhere; }
.runtime-inspector p { margin: 8px 0; color: #b9cde5; font-size: 11px; line-height: 1.7; overflow-wrap: anywhere; }
.runtime-inspector small { color: #8faaca; font: 10px/1.6 'Microsoft YaHei',sans-serif; }
@keyframes runtime-turn { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .ring-turn { animation: none; } }
</style>
