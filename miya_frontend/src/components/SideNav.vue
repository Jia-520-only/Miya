<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

interface NavItem {
  id: string
  label: string
  icon: string
  path?: string
  action?: () => void
}

const router = useRouter()
const route = useRoute()
const showMore = ref(false)

const mainItems: NavItem[] = [
  { id: 'chat', label: '弥娅对话', icon: '◆', path: '/chat' },
  { id: 'platforms', label: '平台状态', icon: '⊡', path: '/platforms' },
  { id: 'console', label: '后台终端', icon: '▤', path: '/console' },
  { id: 'inbox', label: '消息收件箱', icon: '✉', path: '/inbox' },
  { id: 'mind', label: '记忆星河', icon: '◇', path: '/mind' },
  { id: 'artboard', label: '弥娅画板', icon: '⬗', path: '/artboard' },
  { id: 'terminal', label: '终端引擎', icon: '⬡', path: '/terminal' },
  { id: 'dsh-web', label: 'DSH 工作台', icon: '◈', path: '/dsh-web' },
  { id: 'earth', label: '地球online', icon: '◎', path: '/earth' },
]

const moreItems: NavItem[] = [
  { id: 'config', label: '灵魂调谐', icon: '❖', path: '/config' },
  { id: 'community', label: '弥娅社区', icon: '✧', path: '/community' },
  { id: 'hub', label: '弥娅中枢', icon: '⬡', path: '/hub' },
  { id: 'screen', label: '屏幕视觉', icon: '⊙', path: '/screen' },
]

function isActive(item: NavItem) {
  if (item.path === '/chat' && (route.path === '/chat' || route.path === '/'))
    return true
  return route.path.startsWith(item.path || '')
}

const homeActive = computed(() => route.path === '/' || route.path === '')

function navigateTo(item: NavItem) {
  if (item.action) {
    item.action()
    return
  }
  if (item.path)
    router.push(item.path)
  showMore.value = false
}
</script>

<template>
  <nav class="side-nav" @keydown.esc="showMore = false">
    <!-- Logo / Home -->
    <button
      class="nav-logo"
      :class="{ active: homeActive }"
      title="弥娅 · 首页"
      @click="router.push('/')"
    >
      <span class="nav-logo-icon">弥</span>
      <span class="nav-logo-label">MIYA</span>
    </button>

    <div class="nav-divider" />

    <!-- 主菜单 -->
    <button
      v-for="item in mainItems"
      :key="item.id"
      class="nav-item"
      :class="{ active: isActive(item) }"
      :title="item.label"
      @click="navigateTo(item)"
    >
      <span class="nav-icon">{{ item.icon }}</span>
      <span class="nav-label">{{ item.label }}</span>
      <div class="nav-active-bar" />
    </button>

    <!-- 更多按钮 -->
    <button
      class="nav-item nav-more-btn"
      :class="{ active: showMore }"
      :aria-expanded="showMore"
      title="更多功能"
      @click="showMore = !showMore"
    >
      <span class="nav-icon">{{ showMore ? '▼' : '▶' }}</span>
      <span class="nav-label">更多</span>
    </button>

    <!-- 展开更多项 -->
    <Transition name="more-slide">
      <div v-if="showMore" class="nav-more-section">
        <button
          v-for="item in moreItems"
          :key="item.id"
          class="nav-item nav-item-sm"
          :class="{ active: isActive(item) }"
          :title="item.label"
          @click="navigateTo(item)"
        >
          <span class="nav-icon-sm">{{ item.icon }}</span>
          <span class="nav-label-sm">{{ item.label }}</span>
        </button>
      </div>
    </Transition>

    <!-- 底部 -->
    <div class="nav-spacer" />
    <div class="nav-divider" />
    <button
      class="nav-item"
      title="回到首页"
      @click="router.push('/')"
    >
      <span class="nav-icon">⌂</span>
      <span class="nav-label">首页</span>
    </button>
  </nav>
</template>

<style scoped>
.side-nav {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: var(--miya-shell-nav);
  min-width: var(--miya-shell-nav);
  height: 100%;
  padding: var(--miya-space-2) 0;
  background: linear-gradient(180deg, rgba(8, 14, 22, 0.9), rgba(8, 14, 22, 0.72));
  border-right: 1px solid var(--miya-line-soft);
  box-shadow: 12px 0 40px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(18px);
  perspective: 400px;
  -webkit-perspective: 400px;
  z-index: 50;
  user-select: none;
}

/* Logo */
.nav-logo {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1rem;
  padding: 0.4rem 0;
  width: 56px;
  margin: 0.3rem 0;
  background: rgba(120, 207, 209, 0.035);
  border: 1px solid var(--miya-line-soft);
  border-radius: var(--miya-radius-sm);
  cursor: pointer;
  transition: all 0.35s cubic-bezier(0.22, 1, 0.36, 1);
  box-shadow:
    2px 2px 6px rgba(0, 0, 0, 0.3),
    -1px -1px 4px color-mix(in srgb, var(--miya-border) 6%, transparent);
}

.nav-logo:hover,
.nav-logo.active {
  border-color: var(--miya-line-strong);
  box-shadow: inset 0 0 20px rgba(120, 207, 209, 0.06);
}

/* The navigation is a HUD rail, not a continuous glass panel. */
.side-nav {
  width: 70px;
  min-width: 70px;
  padding: 0.45rem 0 0.35rem;
  background: linear-gradient(90deg, rgba(5, 10, 17, 0.5), rgba(5, 10, 17, 0.12) 72%, transparent);
  border-right: 0;
  box-shadow: none;
  backdrop-filter: none;
}

.nav-logo,
.nav-item {
  border-radius: 0;
  clip-path: polygon(0 0, calc(100% - 7px) 0, 100% 7px, 100% 100%, 0 100%);
}

.nav-logo {
  width: 54px;
  background: rgba(6, 14, 23, 0.62);
  border-color: rgba(162, 245, 238, 0.12);
}

.nav-item {
  width: 56px;
  min-height: 41px;
  margin-block: 0.04rem;
}

.nav-item:hover,
.nav-item.active {
  background: linear-gradient(90deg, rgba(120, 207, 209, 0.16), rgba(6, 14, 23, 0.62));
  box-shadow: inset 2px 0 rgba(162, 245, 238, 0.5), 0 5px 16px rgba(0, 0, 0, 0.18);
}

.nav-divider { width: 34px; margin-block: 0.18rem; }
.nav-spacer { min-height: 0.25rem; }

.nav-logo.active {
  background: rgba(120, 207, 209, 0.1);
}

.nav-logo-icon {
  font-family: 'Noto Serif SC', serif;
  font-size: 1.2rem;
  font-weight: 700;
  color: color-mix(in srgb, var(--miya-home, #00ADB5) 85%, transparent);
  line-height: 1;
  transition: all 0.3s ease;
}

.nav-logo:hover .nav-logo-icon {
  text-shadow: 0 0 12px color-mix(in srgb, var(--miya-home, #00ADB5) 30%, transparent);
}

.nav-logo-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.5rem;
  color: var(--miya-text-muted);
  letter-spacing: 0.2em;
}

/* Divider */
.nav-divider {
  width: 40px;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, var(--miya-border) 15%, transparent),
    transparent
  );
  margin: 0.25rem 0;
}

/* Nav items */
.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  width: 60px;
  min-height: 43px;
  padding: 0.38rem 0;
  margin: 0.08rem 0;
  border-radius: var(--miya-radius-sm);
  background: none;
  border: none;
  cursor: pointer;
  position: relative;
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
  color: var(--miya-text-muted);
}

.nav-item:hover {
  color: var(--miya-text-strong);
  transform: translateX(2px);
  background: rgba(120, 207, 209, 0.07);
  box-shadow: none;
}

.nav-item.active {
  color: var(--miya-accent-bright);
  background: linear-gradient(90deg, rgba(120, 207, 209, 0.14), rgba(120, 207, 209, 0.035));
  font-weight: 600;
}

.nav-icon {
  font-size: 1rem;
  line-height: 1;
  transition: transform 0.3s ease, filter 0.3s ease;
}

.nav-item:hover .nav-icon {
  transform: scale(1.15);
}

.nav-item.active .nav-icon {
  filter: drop-shadow(0 0 8px color-mix(in srgb, var(--miya-chat-ai) 50%, transparent));
}

.nav-label {
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 0.58rem;
  letter-spacing: 0.06em;
  line-height: 1;
  white-space: nowrap;
}

/* Active bar */
.nav-active-bar {
  position: absolute;
  left: 0;
  top: 15%;
  height: 70%;
  width: 2px;
  background: linear-gradient(
    180deg,
    transparent,
    color-mix(in srgb, var(--miya-chat-ai) 70%, transparent),
    transparent
  );
  opacity: 0;
  transition: opacity 0.3s ease;
  box-shadow: 0 0 4px color-mix(in srgb, var(--miya-chat-ai) 30%, transparent);
}

.nav-item.active .nav-active-bar {
  opacity: 1;
}

/* More button */
.nav-more-btn {
  margin-top: 0.2rem;
}

.nav-more-btn .nav-icon {
  font-size: 0.6rem;
  transition: transform 0.3s ease;
}

/* More section */
.nav-more-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: hidden;
}

.nav-item-sm {
  padding: 0.35rem 0;
  width: 44px;
  margin: 0.08rem 0;
}

.nav-icon-sm {
  font-size: 0.9rem;
}

.nav-label-sm {
  font-size: 0.42rem;
}

/* Transitions */
.more-slide-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.more-slide-leave-active {
  transition: all 0.2s ease-in;
}
.more-slide-enter-from,
.more-slide-leave-to {
  opacity: 0;
  max-height: 0;
}

/* Spacer */
.nav-spacer {
  flex: 1;
}

/* More opens beside the rail so every secondary destination stays visible. */
.side-nav {
  position: relative;
  overflow: visible;
}

.nav-more-section {
  position: absolute;
  left: 64px;
  bottom: 52px;
  z-index: 90;
  display: grid;
  grid-template-columns: repeat(2, 72px);
  gap: 5px;
  width: max-content;
  padding: 8px;
  overflow: visible;
  background: linear-gradient(135deg, rgba(7, 15, 24, 0.96), rgba(11, 22, 34, 0.9));
  border: 1px solid rgba(162, 245, 238, 0.18);
  border-left: 2px solid rgba(162, 245, 238, 0.48);
  box-shadow: 14px 18px 42px rgba(0, 0, 0, 0.42);
  backdrop-filter: blur(16px);
  clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 0 100%);
}

.nav-more-section::before {
  content: 'EXTENDED ACCESS';
  grid-column: 1 / -1;
  padding: 2px 3px 5px;
  color: rgba(162, 245, 238, 0.46);
  border-bottom: 1px solid rgba(162, 245, 238, 0.1);
  font: 0.38rem/1 'JetBrains Mono', monospace;
  letter-spacing: 0.16em;
}

.nav-more-section .nav-item-sm {
  width: 72px;
  min-height: 48px;
  margin: 0;
  padding: 0.38rem 0.25rem;
  background: rgba(120, 207, 209, 0.035);
  border: 1px solid rgba(162, 245, 238, 0.08);
}

.nav-more-section .nav-item-sm:hover,
.nav-more-section .nav-item-sm.active {
  transform: translateY(-1px);
  background: rgba(120, 207, 209, 0.12);
  border-color: rgba(162, 245, 238, 0.22);
}

.nav-more-section .nav-label-sm {
  color: var(--miya-text-body);
  font-size: 0.48rem;
  white-space: nowrap;
}

.more-slide-enter-from,
.more-slide-leave-to {
  max-height: none;
  opacity: 0;
  transform: translateX(-8px) scale(0.96);
}

/* 手机端保留 HUD 轨道，释放更多空间给具体模块内容。 */
@media (max-width: 760px) {
  .side-nav {
    width: 54px;
    min-width: 54px;
    padding-top: .3rem;
  }
  .nav-logo { width: 44px; margin-block: .15rem .35rem; }
  .nav-item { width: 44px; min-height: 38px; padding-block: .32rem; }
  .nav-label { display: none; }
  .nav-icon { font-size: .92rem; }
  .nav-divider { width: 28px; margin-block: .12rem; }
  .nav-more-section { left: 48px; bottom: 48px; }
}
</style>
