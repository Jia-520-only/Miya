<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { emotionColor, emotionGradient } from '@/utils/emotionColors'

const props = defineProps<{
  emotions?: Array<{ name: string, intensity: number }>
  innerThought?: string
  attribution?: string
  reflection?: string
  thinking?: string
  generating?: boolean
}>()

const thinkingExpanded = ref(false)
const visible = ref(false)

onMounted(() => {
  requestAnimationFrame(() => { visible.value = true })
})

const dominantColor = computed(() => {
  const top = props.emotions?.[0]
  if (!top)
    return '#00ADB5'
  return emotionColor(top.name, '#00ADB5')
})

const accentGlow = computed(() => `0 0 18px ${dominantColor.value}22, 0 0 4px ${dominantColor.value}11`)
</script>

<template>
  <Transition name="soul-slide">
    <div
      v-if="emotions?.length || innerThought || attribution || reflection || thinking || generating"
      class="soul-card"
      :class="{ loading: generating, visible }"
      :style="{ '--card-glow': accentGlow }"
    >
      <!-- 标题 -->
      <div class="soul-header">
        <span class="soul-header-dot" :style="{ background: dominantColor }" />
        <span class="soul-header-text">灵魂共鸣</span>
      </div>

      <!-- 情绪条 -->
      <div v-if="emotions?.length" class="soul-emotions">
        <div v-for="e in emotions.slice(0, 5)" :key="e.name" class="soul-emotion-item">
          <span class="soul-em-name">{{ e.name }}</span>
          <div class="soul-emotion-bar">
            <div
              class="soul-emotion-fill"
              :style="{
                width: `${e.intensity}%`,
                background: emotionGradient(e.name) || `linear-gradient(90deg, ${dominantColor}, ${dominantColor}88)`,
              }"
            />
          </div>
          <span class="soul-em-val">{{ e.intensity }}%</span>
        </div>
      </div>

      <!-- 加载占位 -->
      <div v-if="generating && !emotions?.length" class="soul-loading">
        <span class="soul-loading-dot" />
        <span class="soul-loading-dot" style="animation-delay:0.2s" />
        <span class="soul-loading-dot" style="animation-delay:0.4s" />
      </div>

      <!-- 内心独白 -->
      <div v-if="innerThought" class="soul-thought">
        <span class="soul-quote">"</span>{{ innerThought }}<span class="soul-quote">"</span>
      </div>

      <!-- 归因+反思 -->
      <div v-if="attribution || reflection" class="soul-meta">
        <div v-if="attribution" class="soul-attribution">
          <span class="soul-meta-icon">→</span> {{ attribution }}
        </div>
        <div v-if="reflection" class="soul-reflection">
          <span class="soul-meta-icon">↻</span> {{ reflection }}
        </div>
      </div>

      <!-- 思考过程 -->
      <div v-if="thinking" class="soul-thinking">
        <div class="thinking-toggle" @click="thinkingExpanded = !thinkingExpanded">
          <span class="thinking-icon">◇</span>
          <span>{{ thinkingExpanded ? '收起思考' : '展开思考' }}</span>
          <span class="thinking-len">{{ thinking.length }}ch</span>
        </div>
        <div v-if="thinkingExpanded" class="thinking-body">
          {{ thinking }}
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* ── 组件调色变量 ── */
.soul-card {
  --sp: var(--miya-comp-soul-primary, #00ADB5);
  --spo: var(--miya-comp-soul-positive, #ff6b9d);
  --sne: var(--miya-comp-soul-negative, #7dd3fc);
  --ssu: var(--miya-comp-soul-surprise, #facc15);
  --sth: var(--miya-comp-soul-thought, #00ADB5);
  --stk: var(--miya-comp-soul-think, #4ade80);
  --bg: var(--miya-comp-message-bg, #222831);
  --tx: var(--miya-comp-message-text, #E4ECF0);

  position: absolute;
  right: -188px;
  top: 0;
  width: 172px;
  max-height: 240px;
  overflow-y: auto;
  background: linear-gradient(135deg, color-mix(in srgb, var(--bg) 90%, #000), color-mix(in srgb, var(--bg) 70%, #000));
  border: 1px solid color-mix(in srgb, var(--sp) 12%, transparent);
  border-radius: 6px;
  padding: 0.7rem;
  font-size: 0.65rem;
  z-index: 5;
  pointer-events: auto;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3), var(--card-glow, none);
  transition: border-color 0.4s, box-shadow 0.4s, transform 0.25s ease;
  opacity: 0;
  transform: translateX(12px);
}

.soul-card.visible {
  opacity: 1;
  transform: translateX(0);
}

.soul-card:hover {
  border-color: rgba(0, 173, 181, 0.3);
  box-shadow: 0 6px 32px rgba(0, 0, 0, 0.35), var(--card-glow, none);
  transform: translateX(-2px);
}

@media (max-width: 900px) {
  .soul-card {
    top: calc(100% + 0.4rem);
    right: 0;
    width: min(172px, calc(100vw - 2rem));
  }
}

.soul-card.loading {
  border-color: color-mix(in srgb, var(--sp) 20%, transparent);
  animation: card-pulse 2s ease-in-out infinite;
}

@keyframes card-pulse {
  0%, 100% { border-color: color-mix(in srgb, var(--sp) 12%, transparent); }
  50% { border-color: color-mix(in srgb, var(--sp) 30%, transparent); }
}

/* 滚动条 */
.soul-card::-webkit-scrollbar { width: 3px; }
.soul-card::-webkit-scrollbar-track { background: transparent; }
.soul-card::-webkit-scrollbar-thumb { background: rgba(0, 173, 181, 0.12); border-radius: 3px; }

/* 标题 */
.soul-header {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.5rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid rgba(0, 173, 181, 0.06);
}
.soul-header-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  box-shadow: 0 0 6px currentColor;
}
.soul-header-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: rgba(0, 173, 181, 0.35);
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

/* 情绪条 */
.soul-emotions {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.5rem;
}
.soul-emotion-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.soul-em-name {
  font-size: 0.55rem;
  color: rgba(180, 200, 220, 0.6);
  width: 2.2rem;
  text-align: right;
  flex-shrink: 0;
}
.soul-emotion-bar {
  flex: 1;
  height: 5px;
  background: rgba(0, 173, 181, 0.05);
  border-radius: 3px;
  overflow: hidden;
}
.soul-emotion-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.soul-em-val {
  font-size: 0.5rem;
  color: rgba(0, 173, 181, 0.3);
  width: 1.8rem;
  text-align: right;
  font-family: 'JetBrains Mono', monospace;
  flex-shrink: 0;
}

/* 加载 */
.soul-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  padding: 1rem 0;
}
.soul-loading-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: rgba(0, 173, 181, 0.5);
  animation: ld-bounce 0.6s ease-in-out infinite;
}
@keyframes ld-bounce {
  0%, 100% { transform: translateY(0); opacity: 0.4; }
  50% { transform: translateY(-6px); opacity: 1; }
}

/* 内心独白 */
.soul-thought {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.65rem;
  color: rgba(200, 210, 230, 0.75);
  line-height: 1.6;
  margin-bottom: 0.4rem;
  padding: 0.3rem 0.4rem;
  background: rgba(0, 173, 181, 0.03);
  border-left: 2px solid rgba(0, 173, 181, 0.12);
  border-radius: 0 3px 3px 0;
  font-style: italic;
}
.soul-quote {
  color: rgba(0, 173, 181, 0.25);
  font-size: 0.75rem;
}

/* meta */
.soul-meta {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  margin-bottom: 0.3rem;
}
.soul-meta-icon {
  font-size: 0.5rem;
  opacity: 0.5;
  margin-right: 0.15rem;
}
.soul-attribution {
  color: rgba(0, 173, 181, 0.4);
  font-size: 0.55rem;
  line-height: 1.35;
}
.soul-reflection {
  color: rgba(180, 77, 255, 0.35);
  font-size: 0.55rem;
  line-height: 1.35;
}

/* 思考 */
.soul-thinking {
  margin-top: 0.3rem;
  border-top: 1px solid rgba(0, 173, 181, 0.06);
  padding-top: 0.35rem;
}
.thinking-toggle {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  cursor: pointer;
  color: rgba(0, 173, 181, 0.3);
  font-size: 0.55rem;
  transition: color 0.2s;
  user-select: none;
}
.thinking-toggle:hover { color: rgba(0, 173, 181, 0.6); }
.thinking-icon { font-size: 0.6rem; }
.thinking-len {
  margin-left: auto;
  font-size: 0.5rem;
  opacity: 0.4;
  font-family: 'JetBrains Mono', monospace;
}
.thinking-body {
  margin-top: 0.35rem;
  padding: 0.3rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: rgba(160, 190, 220, 0.55);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow-y: auto;
}

/* 过渡 */
.soul-slide-enter-active { transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1); }
.soul-slide-leave-active { transition: all 0.2s ease-in; }
.soul-slide-enter-from { opacity: 0; transform: translateX(16px); }
.soul-slide-leave-to { opacity: 0; transform: translateX(8px); }
</style>
