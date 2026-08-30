<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

interface HubCard {
  id: string
  icon: string
  title: string
  desc: string
  path: string
  color: string
  size?: 'wide' | 'tall'
}

const cards: HubCard[] = [
  { id: 'chat', icon: '◆', title: '弥娅对话', desc: '灵魂共鸣 · AI 深度交流', path: '/chat', color: '#00FFF5' },
  { id: 'inbox', icon: '✉', title: '消息收件箱', desc: '跨平台消息总览', path: '/inbox', color: '#60a5fa' },
  { id: 'mind', icon: '◇', title: '记忆星河', desc: '3D 认知可视化图谱', path: '/mind', color: '#c084fc', size: 'tall' },
  { id: 'artboard', icon: '⬡', title: '弥娅画板', desc: 'AI 绘画创作工具', path: '/artboard', color: '#f472b6' },
  { id: 'terminal', icon: '▷', title: '终端引擎', desc: 'DSH TUI 交互终端', path: '/terminal', color: '#38bdf8' },
  { id: 'dsh-web', icon: '◈', title: 'DSH 工作台', desc: 'DSH 网页智能体界面', path: '/dsh-web', color: '#34d399' },
  { id: 'config', icon: '❖', title: '灵魂调谐', desc: '人格配置 · 模型切换', path: '/config', color: '#a5b4fc' },
  { id: 'community', icon: '✧', title: '弥娅社区', desc: '资源 · 分享 · 社区', path: '/community', color: '#7dd3fc', size: 'wide' },
  { id: 'screen', icon: '⊙', title: '屏幕视觉', desc: '截图 · 视觉分析', path: '/screen', color: '#facc15' },
  { id: 'platforms', icon: '⊡', title: '平台状态', desc: '多平台健康监控', path: '/platforms', color: '#34d399' },
]

function navigate(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="hub-view">
    <div class="hub-header">
      <div class="hub-title-group">
        <h1 class="hub-title">
          弥娅中枢
        </h1>
        <span class="hub-subtitle">COMMAND HUB · 功能聚合</span>
      </div>
      <button class="hub-back" title="返回首页" @click="router.push('/')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>
    </div>

    <div class="hub-grid">
      <button
        v-for="card in cards"
        :key="card.id"
        class="hub-card"
        :class="[card.size]"
        :style="{ '--card-color': card.color }"
        @click="navigate(card.path)"
      >
        <div class="hub-card-inner">
          <span class="hub-card-icon">{{ card.icon }}</span>
          <h2 class="hub-card-title">
            {{ card.title }}
          </h2>
          <p class="hub-card-desc">
            {{ card.desc }}
          </p>
          <div class="hub-card-gloss" />
          <div class="hub-card-corner tl" />
          <div class="hub-card-corner br" />
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.hub-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1rem;
  gap: 1rem;
  overflow-y: auto;
  animation: hub-enter 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes hub-enter {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.hub-view::-webkit-scrollbar { width: 4px; }
.hub-view::-webkit-scrollbar-thumb { background: rgba(0, 173, 181, 0.12); border-radius: 2px; }

/* ── Header ── */
.hub-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.hub-title-group {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.hub-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 1.1rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.1em;
  margin: 0;
  text-shadow: 0 0 8px rgba(0, 255, 245, 0.15);
}

.hub-subtitle {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.55rem;
  color: rgba(0, 255, 245, 0.4);
  letter-spacing: 0.12em;
}

.hub-back {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(0, 173, 181, 0.12);
  background: rgba(0, 173, 181, 0.06);
  color: rgba(0, 173, 181, 0.5);
  cursor: pointer;
  clip-path: polygon(0 4px, 4px 0, 100% 0, 100% calc(100% - 4px), calc(100% - 4px) 100%, 0 100%);
  transition: all 0.3s ease;
}

.hub-back:hover {
  background: rgba(0, 173, 181, 0.16);
  border-color: rgba(0, 255, 245, 0.4);
  color: rgba(0, 255, 245, 0.9);
  box-shadow: 0 0 14px rgba(0, 173, 181, 0.2);
  transform: skewX(-4deg);
}

/* ── Grid ── */
.hub-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: minmax(140px, 1fr);
  gap: 0.6rem;
  align-content: start;
}

/* ── Card — PGR 战双风格 ═─ */
.hub-card {
  position: relative;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(0, 173, 181, 0.08);
  cursor: pointer;
  transition: all 0.45s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
  font-family: inherit;
  color: inherit;
  text-align: left;
  transform: rotateX(2deg) rotateY(-3deg);
  box-shadow:
    4px 4px 12px rgba(0, 60, 70, 0.4),
    -3px -3px 8px rgba(0, 200, 210, 0.06),
    0 1px 0 rgba(0, 173, 181, 0.05);
}

.hub-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--card-color) 12%, transparent), transparent 70%);
  opacity: 0;
  transition: opacity 0.4s ease;
  pointer-events: none;
  z-index: 0;
}

.hub-card:hover {
  background: rgba(0, 173, 181, 0.18);
  transform: rotateX(1deg) rotateY(-6deg) skewX(-3deg) translateY(-4px);
  border-color: color-mix(in srgb, var(--card-color) 35%, rgba(0, 173, 181, 0.2));
  box-shadow:
    6px 6px 18px rgba(0, 60, 70, 0.5),
    -3px -3px 10px rgba(0, 200, 210, 0.12),
    0 0 20px color-mix(in srgb, var(--card-color) 18%, transparent);
}

.hub-card:hover::after {
  opacity: 1;
}

.hub-card:active {
  transform: skewX(-5deg) scale(0.97);
  transition: transform 0.1s ease;
}

/* Wide / Tall variants */
.hub-card.wide {
  grid-column: span 2;
}

.hub-card.tall {
  grid-row: span 2;
}

/* ── Card Inner ═─ */
.hub-card-inner {
  position: relative;
  z-index: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 1rem;
  gap: 0.25rem;
}

.hub-card-icon {
  font-size: 1.4rem;
  color: color-mix(in srgb, var(--card-color) 70%, rgba(0, 255, 245, 0.3));
  line-height: 1;
  transition: all 0.4s ease;
}

.hub-card:hover .hub-card-icon {
  transform: scale(1.25) skewX(-5deg);
  color: color-mix(in srgb, var(--card-color) 95%, white);
  filter: drop-shadow(0 0 8px color-mix(in srgb, var(--card-color) 35%, transparent));
}

.hub-card-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.95rem;
  font-weight: 700;
  color: #ffffff;
  margin: 0;
  transition: color 0.3s, text-shadow 0.3s, letter-spacing 0.4s;
}

.hub-card:hover .hub-card-title {
  text-shadow: 0 0 12px color-mix(in srgb, var(--card-color) 30%, transparent);
  letter-spacing: 0.06em;
}

.hub-card-desc {
  color: rgba(187, 182, 182, 0.55);
  font-size: 0.6rem;
  margin: 0;
  line-height: 1.4;
  transition: color 0.3s;
}

.hub-card:hover .hub-card-desc {
  color: rgba(255, 255, 255, 0.7);
}

/* ── Gloss (扫光) ═─ */
.hub-card-gloss {
  position: absolute;
  top: -15%;
  left: -10%;
  width: 5px;
  height: 130%;
  background: rgba(255, 255, 255, 0.15);
  transform: skewX(-20deg);
  box-shadow: 0 0 20px rgba(255, 255, 255, 0.2);
  z-index: 0;
  filter: blur(4px);
  animation: gloss-sweep 3s ease-in-out infinite;
  opacity: 0;
  transition: opacity 0.4s ease;
  pointer-events: none;
}

.hub-card:hover .hub-card-gloss {
  opacity: 1;
}

@keyframes gloss-sweep {
  0% { left: -10%; }
  50% { left: 130%; }
  100% { left: 130%; }
}

/* ── Corner brackets ═─ */
.hub-card-corner {
  position: absolute;
  pointer-events: none;
  z-index: 2;
  transition: all 0.4s ease;
}

.hub-card-corner.tl {
  top: 4px; left: 4px;
  width: 14px; height: 14px;
  border-top: 2px solid color-mix(in srgb, var(--card-color) 20%, transparent);
  border-left: 2px solid color-mix(in srgb, var(--card-color) 20%, transparent);
}

.hub-card-corner.br {
  bottom: 4px; right: 4px;
  width: 10px; height: 10px;
  border-bottom: 2px solid color-mix(in srgb, var(--card-color) 20%, transparent);
  border-right: 2px solid color-mix(in srgb, var(--card-color) 20%, transparent);
}

.hub-card:hover .hub-card-corner.tl,
.hub-card:hover .hub-card-corner.br {
  border-color: color-mix(in srgb, var(--card-color) 55%, rgba(0, 255, 245, 0.4));
}
</style>
