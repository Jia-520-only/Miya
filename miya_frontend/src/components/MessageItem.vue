<script setup lang="ts">
import type { Message, ToolEvent } from '@/utils/session'
import { computed, ref } from 'vue'
import { CONFIG } from '@/utils/config'
import { buildEmotionColorMap } from '@/utils/emotionColors'
import { getPlatformColor, getPlatformLabel } from '@/utils/platform'
import Markdown from './Markdown.vue'
import SoulCard from './SoulCard.vue'

const props = defineProps<Message>()

const ROLE_MAP: Record<string, string> = {
  assistant: '弥娅',
  user: CONFIG.value.ui.user_name || '我',
  system: 'SYS',
  error: 'ERR',
}
const ROLE_PREFIX: Record<string, string> = {
  assistant: 'AI',
  user: 'USR',
  system: 'SYS',
  error: 'ERR',
}
const ROLE_COLOR_VAR: Record<string, string> = {
  assistant: '--miya-chat-ai',
  user: '--miya-chat-user',
  system: '--miya-chat-ai',
  error: '#f87171',
}

const reasoningExpanded = ref(true)
const detailOpen = ref(false)

const soulBars = computed(() => {
  const ec = buildEmotionColorMap()
  const emos = props.soulData?.emotions
  if (!emos?.length)
    return []
  const total = emos.reduce((s, e) => s + e.intensity, 1) || 1
  return emos.slice(0, 5).map(e => ({
    name: e.name,
    intensity: e.intensity,
    color: ec[e.name] || '#00ADB5',
    width: Math.round((e.intensity / total) * 100),
  }))
})

const emotionList = computed(() => {
  const ec = buildEmotionColorMap()
  const emos = props.soulData?.emotions
  if (emos?.length)
    return emos.slice(0, 5).map(e => ({ name: e.name, pct: e.intensity, color: ec[e.name] || '#00ADB5' }))
  return []
})

const soulDetail = computed(() => {
  if (props.role !== 'assistant')
    return null
  const savedSoul = props.soulData
  if (savedSoul && (
    savedSoul.emotions?.length
    || savedSoul.innerThought
    || savedSoul.attribution
    || savedSoul.reflection
    || savedSoul.thinking
  ))
    return savedSoul

  const raw = (props as Message & { emotionDataRaw?: unknown, soulRaw?: unknown }).emotionDataRaw
    ?? (props as Message & { soulRaw?: unknown }).soulRaw
  if (!raw || typeof raw !== 'object')
    return null

  const emotionSource = 'current' in raw && raw.current && typeof raw.current === 'object'
    ? raw.current as Record<string, unknown>
    : raw as Record<string, unknown>
  const emotions = Object.entries(emotionSource)
    .filter(([name]) => !['dominant', 'intensity'].includes(name))
    .map(([name, value]) => ({
      name,
      intensity: typeof value === 'number' ? Math.round(value <= 1 ? value * 100 : value) : 50,
    }))

  const textValue = (...keys: string[]) => keys
    .map(key => (raw as Record<string, unknown>)[key])
    .find(value => typeof value === 'string' && value.length > 0) as string | undefined
  const detail = {
    ...(emotions.length ? { emotions } : {}),
    innerThought: textValue('innerThought', 'inner_thought'),
    attribution: textValue('attribution'),
    reflection: textValue('reflection'),
    thinking: textValue('thinking'),
  }
  return Object.values(detail).some(Boolean) ? detail : null
})

const displaySource = computed(() => {
  if (typeof props.content === 'string')
    return props.content
  return JSON.stringify(props.content, null, 2)
})

const platformInfo = computed(() => {
  if (!props.platform) return null
  return {
    id: props.platform,
    label: getPlatformLabel(props.platform, props.platformName),
    color: getPlatformColor(props.platform),
  }
})

function formatToolPayload(value: any): string {
  if (value === null || value === undefined)
    return ''
  if (typeof value === 'string')
    return value
  try { return JSON.stringify(value, null, 2) }
  catch { return String(value) }
}
function toolSummary(event: ToolEvent): string {
  const name = event.name || '工具'
  if (event.type === 'tool_call')
    return `▸ ${name}`
  return `${event.isError ? '✕' : '✓'} ${name}`
}
function toolBody(event: ToolEvent): string {
  if (event.type === 'tool_call')
    return formatToolPayload(event.args)
  return formatToolPayload(event.result)
}

</script>

<template>
  <div v-if="role === 'info'" class="info-divider">
    <span class="info-text">{{ content }}</span>
  </div>
  <div v-else class="msg-shell" :class="{ 'has-soul-card': detailOpen && soulDetail }">
    <div class="msg-card" :class="[role, { generating }]" :style="{ '--role-color': ROLE_COLOR_VAR[role] || 'var(--miya-chat-ai)' }">
    <!-- 四角 bracket -->
    <div class="card-corner tl" />
    <div class="card-corner tr" />
    <div class="card-corner bl" />
    <div class="card-corner br" />

    <!-- PGR 扫光 -->
    <div class="card-gloss" />

    <!-- 顶栏 -->
    <div class="card-bar row-group">
      <span class="bar-id">{{ ROLE_PREFIX[role] }}</span>
      <span class="bar-sender">{{ sender ?? ROLE_MAP[role] }}</span>

      <span
        v-if="platformInfo && platform"
        class="bar-platform"
        :style="{ '--pf-color': platformInfo.color }"
      >
        {{ platformInfo.label }}
      </span>

      <span v-if="direction === 'in'" class="bar-dir-in" title="入站消息">←</span>
      <span v-else-if="direction === 'out'" class="bar-dir-out" title="出站回复">→</span>

      <!-- 情绪光带 (仅 AI) -->
      <div v-if="role === 'assistant' && soulBars.length" class="bar-emotion-strip">
        <div
          v-for="b in soulBars" :key="b.name"
          class="bar-emotion-seg"
          :style="{ background: b.color, width: `${b.width}%` }"
          :title="`${b.name} ${b.intensity}%`"
        />
      </div>

      <span v-if="generating" class="bar-status">
        <span class="bar-pulse" />
        <span>{{ status || 'LINK' }}</span>
      </span>
    </div>

    <!-- 展开/收起按钮（绝对定位，不受裁剪影响） -->
    <button
      v-if="role === 'assistant' && !generating"
      class="bar-expand-btn"
      :title="detailOpen ? '收起灵魂' : '查看灵魂'"
      @click="detailOpen = !detailOpen"
    >
      {{ detailOpen ? '▲' : '▼' }}
    </button>

    <!-- 扫描线 (生成中) -->
    <div v-if="generating" class="card-scan" />

    <!-- 思考过程 -->
    <div v-if="reasoning" class="card-reason">
      <div class="reason-toggle" @click="reasoningExpanded = !reasoningExpanded">
        <span class="reason-dot" :class="{ pulse: generating }" />
        <span class="reason-label">{{ generating ? '◈ PROCESSING' : '◈ COGNITION' }}</span>
        <span v-if="!generating" class="reason-arrow">{{ reasoningExpanded ? '▲' : '▼' }}</span>
      </div>
      <div v-show="reasoningExpanded" class="reason-body">
        <Markdown :source="reasoning" />
      </div>
    </div>

    <!-- 消息内容 -->
    <div class="card-body" :class="{ wait: !content && !reasoning && generating }">
      <div v-if="!content && !reasoning && generating && status" class="card-waiting">
        <span class="wait-cursor">▌</span>
        <span>{{ status }}</span>
      </div>
      <Markdown v-else :source="displaySource" />

      <!-- 工具事件 -->
      <div v-if="toolEvents?.length" class="card-tools">
        <details v-for="(event, idx) in toolEvents" :key="idx" class="tool-block">
          <summary>{{ toolSummary(event) }}</summary>
          <pre v-if="toolBody(event)">{{ toolBody(event) }}</pre>
        </details>
      </div>
    </div>

    <!-- 灵魂内联面板（默认展开，可收起） -->
    <div v-if="role === 'assistant' && detailOpen" class="soul-detail">
      <div v-if="!soulDetail" class="soul-empty">SOUL DATA SYNCING...</div>
      <div v-if="emotionList.length" class="soul-section emotion-section">
        <div class="soul-section-title">
          ♥ 情绪
        </div>
        <div class="soul-emotion-list">
          <div v-for="e in emotionList" :key="e.name" class="soul-emotion-row">
            <span class="soul-em-name">{{ e.name }}</span>
            <div class="soul-em-bar">
              <div class="soul-em-fill" :style="{ width: `${e.pct}%`, background: e.color }" />
            </div>
            <span class="soul-em-val">{{ e.pct }}%</span>
          </div>
        </div>
      </div>
      <div v-if="soulDetail?.innerThought && soulDetail.innerThought !== '正常对话互动'" class="soul-section thought-section">
        <div class="soul-section-title">
          ✦ 内心独白
        </div>
        <div class="soul-section-text thought-text">
          {{ soulDetail.innerThought }}
        </div>
      </div>
      <div v-if="soulDetail?.attribution && soulDetail.attribution !== '正常对话互动'" class="soul-section attrib-section">
        <div class="soul-section-title">
          → 归因
        </div>
        <div class="soul-section-text dim">
          {{ soulDetail.attribution }}
        </div>
      </div>
      <div v-if="soulDetail?.reflection" class="soul-section reflection-section">
        <div class="soul-section-title">
          ↻ 反思
        </div>
        <div class="soul-section-text dim">
          {{ soulDetail.reflection }}
        </div>
      </div>
      <div v-if="soulDetail?.thinking" class="soul-section thinking-section">
        <div class="soul-section-title">
          ◇ 思考
        </div>
        <div class="soul-section-text code">
          {{ soulDetail.thinking }}
        </div>
      </div>

    </div>
      </div>
      <SoulCard
      v-if="role === 'assistant' && detailOpen && soulDetail"
      class="message-soul-card"
      :emotions="soulDetail.emotions"
      :inner-thought="soulDetail.innerThought"
      :attribution="soulDetail.attribution"
      :reflection="soulDetail.reflection"
      :thinking="soulDetail.thinking"
      :generating="generating"
    />
  </div>
</template>

<style scoped>
/* ═══ 组件调色变量 ═══ */
.msg-shell {
  position: relative;
  width: 100%;
}

.msg-shell.has-soul-card {
  padding-right: 188px;
}

.msg-shell.has-soul-card > .message-soul-card {
  right: 0;
}

@media (max-width: 900px) {
  .msg-shell.has-soul-card {
    padding-right: 0;
    padding-bottom: 250px;
  }
}

.msg-card {
  --ai: var(--miya-comp-message-ai, #00ADB5);
  --usr: var(--miya-comp-message-user, #00ADB5);
  --bg: var(--miya-comp-message-bg, #222831);
  --in: var(--miya-comp-message-input, #00ADB5);
  --tx: var(--miya-comp-message-text, #E4ECF0);

  position: relative;
  padding: .85rem 1.2rem .65rem 1rem;
  background: linear-gradient(135deg, rgba(0,0,0,0.55), rgba(0,0,0,0.42));
  border: 1px solid color-mix(in srgb, var(--ai) 6%, rgba(255,255,255,0.03));
  clip-path: polygon(
    0 10px, 6px 0, 100% 0,
    100% calc(100% - 6px), calc(100% - 6px) 100%,
    6px 100%, 0 calc(100% - 6px)
  );
  overflow: hidden;
  transition: all 0.35s cubic-bezier(0.22, 1, 0.36, 1);
  perspective: 600px;
}

.msg-card:hover {
  border-color: color-mix(in srgb, var(--ai) 15%, rgba(255,255,255,0.05));
  transform: rotateX(0.3deg) rotateY(-1.2deg) translateY(-1px);
}

.msg-card.user {
  border-color: color-mix(in srgb, var(--usr) 6%, rgba(255,255,255,0.03));
}

.msg-card.user:hover {
  border-color: color-mix(in srgb, var(--usr) 15%, rgba(255,255,255,0.05));
}

.msg-card.generating {
  border-color: color-mix(in srgb, var(--ai) 22%, rgba(0,255,245,0.08));
  animation: card-glow 2.5s ease-in-out infinite;
}

.msg-card.user.generating {
  border-color: color-mix(in srgb, var(--usr) 22%, rgba(0,255,245,0.08));
  animation: card-glow-u 2.5s ease-in-out infinite;
}

@keyframes card-glow {
  0%,100% { border-color: color-mix(in srgb, var(--ai) 12%, rgba(0,255,245,0.04)); }
  50% { border-color: color-mix(in srgb, var(--ai) 35%, rgba(0,255,245,0.12)); }
}

@keyframes card-glow-u {
  0%,100% { border-color: color-mix(in srgb, var(--usr) 12%, rgba(0,255,245,0.04)); }
  50% { border-color: color-mix(in srgb, var(--usr) 35%, rgba(0,255,245,0.12)); }
}

/* ═══ PGR 扫光 ═══ */
.card-gloss {
  position: absolute;
  top: -25%;
  left: -15%;
  width: 6px;
  height: 160%;
  background: rgba(255,255,255,0.18);
  transform: skewX(-28deg);
  box-shadow: 0 0 50px rgba(255,255,255,0.18), 0 0 8px rgba(129,191,241,0.3);
  z-index: 1;
  filter: blur(5px);
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}

.msg-card:hover .card-gloss,
.msg-card.generating .card-gloss {
  animation: gloss-sweep 2.2s ease-in-out;
}

@keyframes gloss-sweep {
  0% { left: -15%; opacity: 1; }
  70% { left: 120%; opacity: 0.6; }
  71% { left: 120%; opacity: 0; }
  100% { left: 120%; opacity: 0; }
}

/* ═══ 四角 bracket ═══ */
.card-corner {
  position: absolute;
  z-index: 2;
  pointer-events: none;
  transition: all 0.35s ease;
}

.card-corner.tl {
  top: 1px; left: 1px;
  width: 14px; height: 14px;
  border-top: 2px solid color-mix(in srgb, var(--ai) 30%, rgba(0,255,245,0.25));
  border-left: 2px solid color-mix(in srgb, var(--ai) 30%, rgba(0,255,245,0.25));
}

.card-corner.tr {
  top: 1px; right: 1px;
  width: 10px; height: 10px;
  border-top: 1px solid color-mix(in srgb, var(--ai) 15%, transparent);
  border-right: 1px solid color-mix(in srgb, var(--ai) 15%, transparent);
}

.card-corner.bl {
  bottom: 1px; left: 1px;
  width: 14px; height: 14px;
  border-bottom: 2px solid color-mix(in srgb, var(--ai) 20%, transparent);
  border-left: 2px solid color-mix(in srgb, var(--ai) 20%, transparent);
}

.card-corner.br {
  bottom: 1px; right: 1px;
  width: 10px; height: 10px;
  border-bottom: 1px solid color-mix(in srgb, var(--ai) 25%, rgba(0,255,245,0.15));
  border-right: 1px solid color-mix(in srgb, var(--ai) 25%, rgba(0,255,245,0.15));
}

.msg-card.user .card-corner.tl {
  border-color: color-mix(in srgb, var(--usr) 25%, rgba(0,255,245,0.2)) color-mix(in srgb, var(--usr) 25%, rgba(0,255,245,0.2)) transparent transparent;
}

.msg-card.user .card-corner.tr {
  border-color: color-mix(in srgb, var(--usr) 12%, transparent) color-mix(in srgb, var(--usr) 12%, transparent) transparent transparent;
}

.msg-card.user .card-corner.bl {
  border-color: transparent transparent color-mix(in srgb, var(--usr) 16%, transparent) color-mix(in srgb, var(--usr) 16%, transparent);
}

.msg-card.user .card-corner.br {
  border-color: transparent transparent color-mix(in srgb, var(--usr) 20%, rgba(0,255,245,0.12)) color-mix(in srgb, var(--usr) 20%, rgba(0,255,245,0.12));
}

.msg-card:hover .card-corner.tl,
.msg-card:hover .card-corner.br {
  border-color: color-mix(in srgb, var(--ai) 55%, rgba(0,255,245,0.45)) color-mix(in srgb, var(--ai) 55%, rgba(0,255,245,0.45)) transparent transparent;
}

.msg-card.user:hover .card-corner.tl,
.msg-card.user:hover .card-corner.br {
  border-color: color-mix(in srgb, var(--usr) 55%, rgba(0,255,245,0.45));
}

/* ═══ 顶栏 ═══ */
.card-bar {
  display: flex;
  align-items: center;
  gap: .5rem;
  padding-bottom: .45rem;
  margin-bottom: .5rem;
  border-bottom: 1px solid color-mix(in srgb, var(--ai) 5%, rgba(255,255,255,0.02));
  font-family: 'JetBrains Mono', monospace;
  font-size: .65rem;
  position: relative;
  z-index: 2;
}

.msg-card.user .card-bar {
  border-color: color-mix(in srgb, var(--usr) 5%, rgba(255,255,255,0.02));
}

.bar-id {
  color: color-mix(in srgb, var(--ai) 55%, rgba(0,255,245,0.35));
  font-weight: 700;
  letter-spacing: .1em;
  border-right: 1px solid color-mix(in srgb, var(--ai) 10%, transparent);
  padding-right: .5rem;
}

.msg-card.user .bar-id {
  color: color-mix(in srgb, var(--usr) 55%, rgba(0,255,245,0.35));
  border-color: color-mix(in srgb, var(--usr) 10%, transparent);
}

.bar-sender {
  color: color-mix(in srgb, var(--ai) 80%, rgba(255,255,255,0.7));
  letter-spacing: .05em;
  font-weight: 600;
}

.msg-card.user .bar-sender {
  color: color-mix(in srgb, var(--usr) 80%, rgba(255,255,255,0.7));
}

.bar-platform {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  padding: 0 4px;
  height: 14px;
  line-height: 14px;
  border-radius: 2px;
  color: color-mix(in srgb, var(--pf-color, #6B7280) 85%, #e4ecf0);
  background: color-mix(in srgb, var(--pf-color, #6B7280) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--pf-color, #6B7280) 18%, transparent);
  margin-left: 6px;
  letter-spacing: 0.04em;
}

.bar-dir-in {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: #22c55e;
  margin-left: 4px;
  opacity: 0.6;
}

.bar-dir-out {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: #3b82f6;
  margin-left: 4px;
  opacity: 0.6;
}

.bar-status {
  display: flex;
  align-items: center;
  gap: .3rem;
  margin-left: auto;
  color: color-mix(in srgb, var(--ai) 35%, rgba(0,255,245,0.3));
  font-size: .6rem;
}

.bar-pulse {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--ai) 55%, rgba(0,255,245,0.5));
  animation: dot-pulse 1.2s ease-in-out infinite;
}

@keyframes dot-pulse {
  0%,100% { opacity: .2; box-shadow: none; }
  50% { opacity: 1; box-shadow: 0 0 8px color-mix(in srgb, var(--ai) 60%, rgba(0,255,245,0.6)); }
}

/* ═══ 扫描线 ═══ */
.card-scan {
  position: absolute;
  left: 2%;
  width: 96%;
  height: 1px;
  background: linear-gradient(90deg, transparent 5%, color-mix(in srgb, var(--ai) 18%, rgba(0,255,245,0.08)) 30%, color-mix(in srgb, var(--ai) 18%, rgba(0,255,245,0.08)) 70%, transparent 95%);
  top: 0;
  opacity: 1;
  pointer-events: none;
  z-index: 0;
  animation: card-scan 1.2s ease-in-out infinite;
}

@keyframes card-scan {
  0%, 100% { top: 0; opacity: 0; }
  50% { top: 70%; opacity: 1; }
}

/* ═══ 思考过程 ═══ */
.card-reason {
  margin: 0 0 .6rem;
  border: 1px solid color-mix(in srgb, var(--ai) 6%, transparent);
  background: rgba(0,0,0,0.3);
  clip-path: polygon(0 4px, 4px 0, 100% 0, 100% 100%, 0 100%);
  position: relative;
  z-index: 2;
}

.reason-toggle {
  display: flex;
  align-items: center;
  gap: .4rem;
  padding: .35rem .6rem;
  cursor: pointer;
  user-select: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: .65rem;
  color: color-mix(in srgb, var(--ai) 30%, rgba(0,255,245,0.25));
  transition: color .2s;
}

.reason-toggle:hover {
  color: color-mix(in srgb, var(--ai) 65%, rgba(0,255,245,0.55));
}

.reason-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--ai) 30%, rgba(0,255,245,0.25));
}

.reason-dot.pulse {
  animation: dot-pulse 1.2s ease-in-out infinite;
}

.reason-arrow {
  margin-left: auto;
  font-size: .55rem;
}

.reason-body {
  padding: .2rem .6rem .5rem;
  border-top: 1px solid color-mix(in srgb, var(--ai) 4%, transparent);
  font-size: .75rem;
  color: color-mix(in srgb, var(--tx) 60%, rgba(200,200,200,0.55));
  line-height: 1.5;
}

/* ═══ 消息主体 ═══ */
.card-body {
  font-size: .88rem;
  line-height: 1.7;
  color: color-mix(in srgb, var(--tx) 88%, rgba(228,236,240,0.85));
  overflow-wrap: break-word;
  word-break: break-word;
  min-width: 0;
  position: relative;
  z-index: 2;
}

.card-body :deep(pre) {
  background: rgba(0,0,0,0.45);
  border: 1px solid color-mix(in srgb, var(--ai) 8%, transparent);
  border-left: 2px solid color-mix(in srgb, var(--ai) 28%, rgba(0,255,245,0.2));
  padding: .6rem .8rem;
  overflow-x: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: .75rem;
  color: color-mix(in srgb, var(--ai) 80%, rgba(200,230,255,0.75));
}

.msg-card.user .card-body :deep(pre) {
  border-color: color-mix(in srgb, var(--usr) 8%, transparent);
  border-left-color: color-mix(in srgb, var(--usr) 28%, rgba(0,255,245,0.2));
}

.card-body :deep(code) {
  background: color-mix(in srgb, var(--ai) 4%, transparent);
  color: color-mix(in srgb, var(--ai) 75%, rgba(0,255,245,0.7));
  padding: .12em .35em;
  font-size: .85em;
}

.card-body :deep(pre code) {
  background: none;
  color: inherit;
  padding: 0;
}

.msg-card.user .card-body :deep(code) {
  background: color-mix(in srgb, var(--usr) 4%, transparent);
  color: color-mix(in srgb, var(--usr) 75%, rgba(0,255,245,0.7));
}

.card-body :deep(blockquote) {
  border-left: 2px solid color-mix(in srgb, var(--ai) 25%, rgba(0,255,245,0.2));
  background: color-mix(in srgb, var(--ai) 3%, rgba(0,255,245,0.02));
  padding: .35rem .7rem;
  margin: .4rem 0;
}

.msg-card.user .card-body :deep(blockquote) {
  border-left-color: color-mix(in srgb, var(--usr) 25%, rgba(0,255,245,0.2));
}

/* ═══ 等待状态 ═══ */
.card-waiting {
  display: flex;
  align-items: center;
  gap: .4rem;
  color: color-mix(in srgb, var(--ai) 35%, rgba(0,255,245,0.3));
  font-family: 'JetBrains Mono', monospace;
  font-size: .75rem;
}

.wait-cursor {
  animation: blinker .7s step-end infinite;
  color: color-mix(in srgb, var(--ai) 55%, rgba(0,255,245,0.5));
}

@keyframes blinker {
  0%,100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ═══ 工具事件 ═══ */
.card-tools {
  margin-top: .5rem;
  padding-top: .3rem;
  border-top: 1px solid color-mix(in srgb, var(--ai) 5%, transparent);
}

.tool-block {
  margin: .15rem 0;
  font-size: .7rem;
  color: color-mix(in srgb, var(--ai) 30%, rgba(0,255,245,0.25));
}

.tool-block summary {
  cursor: pointer;
  padding: .15rem 0;
}

.tool-block summary:hover {
  color: color-mix(in srgb, var(--ai) 60%, rgba(0,255,245,0.5));
}

.tool-block pre {
  background: rgba(0,0,0,0.7);
  border: 1px solid color-mix(in srgb, var(--ai) 5%, transparent);
  padding: .4rem;
  font-size: .65rem;
  color: color-mix(in srgb, var(--ai) 55%, rgba(200,200,200,0.5));
  overflow-x: auto;
  white-space: pre-wrap;
  font-family: 'JetBrains Mono', monospace;
}

/* ═══ 分隔条 ═══ */
.info-divider {
  display: flex;
  align-items: center;
  gap: .6rem;
  padding: .3rem 0;
}

.info-divider::before,
.info-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--ai) 10%, transparent), transparent);
}

.info-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: .6rem;
  color: color-mix(in srgb, var(--ai) 22%, rgba(0,255,245,0.2));
  white-space: nowrap;
}

/* ═══ 情绪光带 ═══ */
.bar-emotion-strip {
  display: flex;
  flex: 1;
  min-width: 60px;
  height: 4px;
  border-radius: 2px;
  overflow: hidden;
  gap: 2px;
  opacity: .85;
  margin: 0 .25rem;
}

.bar-emotion-seg {
  height: 100%;
  border-radius: 1px;
  transition: width .5s ease;
  box-shadow: 0 0 4px currentColor;
}

/* ═══ 展开按钮 ═══ */
.bar-expand-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 5;
  padding: 1px 6px;
  border: 1px solid color-mix(in srgb, var(--ai) 18%, transparent);
  border-radius: 3px;
  background: color-mix(in srgb, var(--ai) 8%, rgba(0,0,0,0.5));
  color: color-mix(in srgb, var(--ai) 50%, rgba(0,255,245,0.45));
  cursor: pointer;
  font-size: .55rem;
  line-height: 1.4;
  transition: all .2s ease;
  min-width: 20px;
  text-align: center;
  backdrop-filter: blur(4px);
}

.bar-expand-btn:hover {
  border-color: color-mix(in srgb, var(--ai) 45%, rgba(0,255,245,0.4));
  color: color-mix(in srgb, var(--ai) 80%, rgba(0,255,245,0.75));
  background: rgba(129,191,241,0.15);
  transform: skewX(-5deg);
}

/* ═══ 灵魂内联面板（始终展开） ═══ */
.soul-detail {
  --sp: var(--miya-comp-soul-primary, #00ADB5);
  --spo: var(--miya-comp-soul-positive, #ff6b9d);
  --sth: var(--miya-comp-soul-thought, #00ADB5);
  --stk: var(--miya-comp-soul-think, #4ade80);
  position: relative;
  z-index: 2;
  margin: 0.6rem 0 0;
  border-top: 1px solid color-mix(in srgb, var(--ai) 6%, transparent);
  padding: 0.5rem 0 0;
  font-size: 0.65rem;
  animation: detail-in 0.35s ease;
}

.soul-empty {
  color: color-mix(in srgb, var(--sp) 45%, transparent);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.58rem;
  letter-spacing: 0.04em;
  line-height: 1.5;
  padding: 0.25rem 0;
}

@keyframes detail-in {
  from { opacity: 0; max-height: 0; }
  to { opacity: 1; max-height: 400px; }
}

.soul-section {
  margin-bottom: 0.35rem;
  padding-left: 0.4rem;
  border-left: 2px solid color-mix(in srgb, var(--sp) 10%, transparent);
}

.soul-section:last-child { margin-bottom: 0; }

.soul-section.emotion-section { border-left-color: color-mix(in srgb, var(--spo) 25%, transparent); }
.soul-section.thought-section { border-left-color: color-mix(in srgb, var(--sth) 25%, transparent); }
.soul-section.attrib-section { border-left-color: color-mix(in srgb, var(--sp) 25%, transparent); }
.soul-section.reflection-section { border-left-color: color-mix(in srgb, var(--usr) 25%, transparent); }
.soul-section.thinking-section { border-left-color: color-mix(in srgb, var(--stk) 25%, transparent); }

.soul-section-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: color-mix(in srgb, var(--sp) 40%, transparent);
  letter-spacing: 0.06em;
  margin-bottom: 0.2rem;
}

.soul-section-text {
  color: color-mix(in srgb, var(--tx) 65%, transparent);
  line-height: 1.45;
  font-size: 0.68rem;
}

.soul-section-text.dim {
  color: color-mix(in srgb, var(--sp) 30%, transparent);
  font-size: 0.62rem;
}

.soul-section-text.code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: color-mix(in srgb, var(--stk) 50%, transparent);
  background: color-mix(in srgb, var(--bg) 25%, #0004);
  border: 1px solid color-mix(in srgb, var(--sp) 5%, transparent);
  border-radius: 3px;
  padding: 0.35rem 0.45rem;
  max-height: 140px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.45;
}

.thought-text {
  font-family: 'Noto Serif SC', serif;
  font-style: italic;
  color: color-mix(in srgb, var(--tx) 70%, transparent);
  padding: 0.2rem 0.3rem;
  background: color-mix(in srgb, var(--sth) 3%, transparent);
  border-radius: 2px;
  font-size: 0.63rem;
}

/* ═══ 情绪可视化条 ═══ */
.soul-emotion-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.soul-emotion-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.soul-em-name {
  font-size: 0.6rem;
  color: color-mix(in srgb, var(--tx) 55%, transparent);
  width: 2.5rem;
  text-align: right;
  flex-shrink: 0;
}

.soul-em-bar {
  flex: 1;
  height: 5px;
  background: color-mix(in srgb, var(--sp) 6%, transparent);
  border-radius: 3px;
  overflow: hidden;
}

.soul-em-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.soul-em-val {
  font-size: 0.55rem;
  color: color-mix(in srgb, var(--sp) 30%, transparent);
  width: 2rem;
  text-align: right;
  font-family: 'JetBrains Mono', monospace;
  flex-shrink: 0;
}

@media (prefers-reduced-motion: reduce) {
  .msg-card,
  .msg-card::before,
  .msg-card::after,
  .msg-card * {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
  }
}
</style>
