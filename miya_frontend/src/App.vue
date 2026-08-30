<script setup lang="ts">
import type { FloatingState } from '@/electron.d'
import { useStorage } from '@vueuse/core'
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import EarthAPI from '@/api/earth'
import BottomBar from '@/components/BottomBar.vue'
import HomeStoryShowcase from '@/components/HomeStoryShowcase.vue'
import SciFiOverlay from '@/components/SciFiOverlay.vue'
import SideNav from '@/components/SideNav.vue'
import TitleBar from '@/components/TitleBar.vue'
import TopStatusBar from '@/components/TopStatusBar.vue'
import { useElectron } from '@/composables/useElectron'
import { useMIYARealtime } from '@/composables/useMIYARealtime'
import { destroyParallax, initParallax } from '@/utils/parallax'
import { isLegacyBackground } from '@/utils/backgroundAssets'

const FloatingView = defineAsyncComponent(() => import('@/views/FloatingView.vue'))

const route = useRoute()
const isElectron = !!window.electronAPI
const { connect: connectWS, disconnect: disconnectWS } = useMIYARealtime()
useElectron()

const floatingState = ref<FloatingState>('classic')
let cleanupFloatingState: (() => void) | undefined
const isFloatingMode = computed(() => floatingState.value !== 'classic')
const isHome = computed(() => route.path === '/')

const customBg = useStorage('miya-bg-image', '')
if (isLegacyBackground(customBg.value))
  customBg.value = ''
const customBgOpacity = useStorage('miya-bg-opacity', 0.35)
const hudVisible = useStorage('miya-hud-visible', true)
const hudOpacity = useStorage('miya-hud-opacity', 1.0)
const homeGalleryVisible = useStorage('miya-home-gallery-visible', true)

const frameStyle = computed(() => {
  if (!customBg.value) {
    return `
      radial-gradient(circle at 18% 22%, rgba(0, 173, 181, 0.16), transparent 34%),
      radial-gradient(circle at 78% 70%, rgba(40, 82, 120, 0.16), transparent 38%),
      linear-gradient(145deg, #101923 0%, #071018 52%, #03070c 100%)
    `
  }
  const overlay = `rgba(13, 17, 23, ${1 - customBgOpacity.value})`
  const rawSource = customBg.value
  const source = rawSource.startsWith('/api/') ? EarthAPI.imageUrl(rawSource) : rawSource
  const escaped = source.replace(/"/g, '\\"')
  return `linear-gradient(${overlay}, ${overlay}), url("${escaped}") center / cover no-repeat fixed`
})

function applyBg() {
  document.body.style.background = 'var(--miya-bg-void)'
}
watch([customBg, customBgOpacity], applyBg, { immediate: true })
watch([isHome, homeGalleryVisible], ([home, visible]) => {
  if (home && visible)
    initParallax()
  else
    destroyParallax()
})

onMounted(() => {
  if (isHome.value && homeGalleryVisible.value)
    initParallax()
  connectWS()
  if (isElectron) {
    window.electronAPI?.floating.getState().then((s: FloatingState) => {
      floatingState.value = s
    })
    cleanupFloatingState = window.electronAPI?.floating.onStateChange((s: FloatingState) => {
      floatingState.value = s
    })
  }
})

onUnmounted(() => {
  disconnectWS()
  destroyParallax()
  cleanupFloatingState?.()
})
</script>

<template>
  <template v-if="isFloatingMode">
    <FloatingView />
  </template>
  <template v-else>
    <div class="miya-shell" :class="{ 'is-electron': isElectron }" :style="{ background: frameStyle }">
      <div class="shell-atmosphere" aria-hidden="true" />
      <SciFiOverlay v-if="hudVisible" :style="{ opacity: hudOpacity }" />
      <TitleBar />
      <TopStatusBar />
      <div class="miya-body">
        <div v-if="isHome && homeGalleryVisible" class="home-story-dock">
          <HomeStoryShowcase />
        </div>
        <SideNav />
        <main class="content-main" :class="{ 'content-home': isHome }">
          <RouterView v-slot="{ Component, route: r }">
            <Transition :name="r.path === '/' ? 'page-fade' : 'page-slide'" mode="out-in">
              <component :is="Component" :key="r.fullPath" />
            </Transition>
          </RouterView>
        </main>
      </div>
      <BottomBar />
    </div>
  </template>
</template>

<style scoped>
.miya-shell {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  color: var(--miya-text-body);
  background:
    linear-gradient(115deg, rgba(7, 11, 18, 0.72), rgba(7, 11, 18, 0.3) 48%, rgba(7, 11, 18, 0.68)),
    var(--miya-bg-void);
  overflow: hidden;
}

.miya-shell.is-electron {
  padding-top: var(--miya-shell-title);
}

.shell-atmosphere {
  position: absolute;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background:
    radial-gradient(circle at 78% 14%, rgba(120, 207, 209, 0.08), transparent 30%),
    radial-gradient(circle at 22% 88%, rgba(216, 189, 130, 0.055), transparent 32%),
    repeating-linear-gradient(90deg, transparent 0 79px, rgba(173, 218, 226, 0.018) 80px);
}

.miya-body {
  position: relative;
  perspective: 600px;
  perspective-origin: center;
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.content-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: var(--miya-space-3) var(--miya-space-4);
  overflow: hidden;
}

.content-home {
  padding: 0;
}

.page-slide-enter-active,
.page-slide-leave-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.page-slide-enter-from { opacity: 0; transform: translateX(24px); }
.page-slide-leave-to { opacity: 0; transform: translateX(-24px); }

.page-fade-enter-active,
.page-fade-leave-active {
  transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}
.page-fade-enter-from,
.page-fade-leave-to { opacity: 0; }

.home-story-dock {
  position: absolute;
  top: 49%;
  left: 50%;
  z-index: 1;
  transform: translate(-50%, -46%);
  pointer-events: none;
}
@media (max-width: 760px) {
  .content-main {
    padding: var(--miya-space-2) var(--miya-space-2) var(--miya-space-3);
  }
}
@media (max-width: 900px) {
  .home-story-dock { top: 52%; }
}
@media (max-width: 760px) {
  .home-story-dock {
    top: auto;
    right: 50%;
    bottom: 5.2rem;
    transform: translateX(50%);
  }
}
</style>
  // BGM is started by the home music control after the library loads.
