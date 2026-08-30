<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const router = useRouter()
const route = useRoute()

interface Shortcut {
  id: string
  label: string
  icon: string
  path?: string
  action?: () => void
}

const shortcuts: Shortcut[] = [
  { id: 'home', label: '首页', icon: '⌂', path: '/' },
  { id: 'chat', label: '对话', icon: '◆', path: '/chat' },
  { id: 'hub', label: '中枢', icon: '⬢', path: '/hub' },
  { id: 'float', label: '悬浮', icon: '◈', action: () => {
    window.electronAPI?.floating?.enter()
  } },
  { id: 'config', label: '调谐', icon: '❖', path: '/config' },
]

function handleShortcut(s: Shortcut) {
  if (s.path)
    router.push(s.path)
  else if (s.action)
    s.action()
}
</script>

<template>
  <footer class="bottom-bar">
    <button
      v-for="s in shortcuts"
      :key="s.id"
      class="bottom-item"
      :class="{ active: s.path && route.path === s.path }"
      :title="s.label"
      @click="handleShortcut(s)"
    >
      <span class="bottom-icon">{{ s.icon }}</span>
      <span class="bottom-label">{{ s.label }}</span>
    </button>
  </footer>
</template>

<style scoped>
.bottom-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.1rem;
  height: var(--miya-shell-bottom);
  min-height: var(--miya-shell-bottom);
  padding: 0 1rem;
  background: rgba(7, 11, 18, 0.76);
  border-top: 1px solid var(--miya-line-soft);
  box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.12);
  backdrop-filter: blur(18px);
  z-index: 60;
  user-select: none;
}

.bottom-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.05rem;
  width: 52px;
  height: 34px;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--miya-text-muted);
  border-radius: var(--miya-radius-sm);
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
  position: relative;
}

.bottom-item:hover {
  color: var(--miya-text-strong);
  transform: translateY(-1px);
  background: rgba(120, 207, 209, 0.07);
}

/* Floating command dock: keep the canvas open instead of drawing a full-width bar. */
.bottom-bar {
  gap: 0.22rem;
  background: linear-gradient(90deg, transparent 27%, rgba(5, 11, 18, 0.8) 38%, rgba(5, 11, 18, 0.88) 50%, rgba(5, 11, 18, 0.8) 62%, transparent 73%);
  border-top: 0;
  box-shadow: none;
  backdrop-filter: none;
}

.bottom-item {
  width: 54px;
  border-radius: 0;
  background: rgba(8, 17, 27, 0.5);
  border: 1px solid rgba(162, 245, 238, 0.06);
  clip-path: polygon(6px 0, calc(100% - 6px) 0, 100% 6px, 100% 100%, 0 100%, 0 6px);
}

.bottom-item:hover,
.bottom-item.active {
  background: linear-gradient(180deg, rgba(120, 207, 209, 0.16), rgba(8, 17, 27, 0.72));
  border-color: rgba(162, 245, 238, 0.18);
  box-shadow: 0 -6px 18px rgba(0, 0, 0, 0.18), inset 0 2px rgba(162, 245, 238, 0.32);
}

.bottom-item.active {
  color: var(--miya-accent-bright);
  background: rgba(120, 207, 209, 0.08);
}

.bottom-item::after {
  content: '';
  position: absolute;
  bottom: 2px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 1px;
  background: color-mix(in srgb, var(--miya-chat-ai) 50%, transparent);
  transition: width 0.3s ease;
}

.bottom-item:hover::after {
  width: 50%;
}

.bottom-icon {
  font-size: 0.85rem;
  line-height: 1;
  transition: transform 0.3s ease;
}

.bottom-item:hover .bottom-icon {
  transform: scale(1.1);
}

.bottom-label {
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 0.52rem;
  letter-spacing: 0.05em;
  line-height: 1;
}
</style>
