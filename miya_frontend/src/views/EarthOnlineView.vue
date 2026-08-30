<script setup lang="ts">
import type { EarthTheme } from '@/api/earth'
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import EarthAPI from '@/api/earth'

const PlayerView = defineAsyncComponent(() => import('./earth/PlayerView.vue'))
const AdminView = defineAsyncComponent(() => import('./earth/AdminView.vue'))

// ── 地球online 壳: 前台展示 (玩家视角) / 后台管理 (数据录入) 双界面 ──

const view = ref<'player' | 'admin'>('player')
const theme = ref<EarthTheme>({ accent: '#78cfd1', accent_light: '#a2f5ee', accent_deep: '#4f9fa5', background: '', background_opacity: 0.25, glass: true })
const shellThemeVars = computed(() => ({
  '--earth-accent': theme.value.accent,
  '--earth-accent-light': theme.value.accent_light,
  '--earth-accent-deep': theme.value.accent_deep,
}))

onMounted(async () => {
  try {
    theme.value = await EarthAPI.getTheme()
  }
  catch { /* 后端不可用时保留默认 Miya OS 配色 */ }
})

const VIEW_LABELS = {
  player: '玩家视角 · 展示面板 / 接取任务',
  admin: '管理视角 · 录入与编辑数据',
} as const
</script>

<template>
  <div class="earth-shell" :class="view === 'admin' ? 'is-admin' : 'is-player'" :style="shellThemeVars">
    <div class="view-switch">
      <div class="view-buttons">
        <button class="view-btn" :class="{ active: view === 'player' }" @click="view = 'player'">
          ◈ 前台展示
        </button>
        <button class="view-btn" :class="{ active: view === 'admin' }" @click="view = 'admin'">
          ⚙ 后台管理
        </button>
      </div>
      <span class="view-hint">{{ VIEW_LABELS[view] }}</span>
    </div>
    <PlayerView v-if="view === 'player'" />
    <AdminView v-else />
  </div>
</template>

<style scoped>
.earth-shell {
  --earth-accent: var(--miya-accent-soft);
  --earth-accent-light: var(--miya-accent-bright);
  --earth-accent-deep: #4f9fa5;
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background: transparent;
  border: 0;
  box-shadow: none;
}
.view-switch {
  position: relative;
  z-index: 60;
  flex: 0 0 32px;
  min-height: 32px;
  display: flex;
  align-items: center;
  gap: .9rem;
  padding: 0 .6rem;
  background: linear-gradient(90deg, rgba(5, 10, 16, .92), rgba(8, 18, 28, .7) 62%, rgba(5, 10, 16, .52));
  border-bottom: 1px solid rgba(162, 245, 238, .16);
  box-shadow: inset 0 -1px rgba(120, 207, 209, .04);
  backdrop-filter: blur(14px);
}
.view-switch::after { content: ''; position: absolute; right: 0; bottom: -1px; width: 34%; height: 1px; background: linear-gradient(90deg, transparent, var(--earth-accent-light)); }
.view-buttons { display: flex; gap: 0; border-left: 1px solid rgba(162, 245, 238, .12); }
.view-btn { height: 31px; padding: 0 .78rem; color: var(--miya-text-faint); font-size: .62rem; letter-spacing: .08em; background: transparent; border: 0; cursor: pointer; }
.view-btn:hover { color: var(--earth-accent-light); border-color: transparent; background: rgba(120, 207, 209, .06); }
.view-btn.active { color: var(--earth-accent-light); background: rgba(120, 207, 209, .1); box-shadow: inset 0 -2px var(--earth-accent-light); }
.view-hint { margin-left: auto; color: var(--miya-text-faint); font-size: .5rem; letter-spacing: .12em; text-transform: uppercase; }
@media (max-width: 700px) {
  .view-switch { flex-basis: 30px; min-height: 30px; gap: .35rem; padding-inline: .35rem; }
  .view-btn { height: 29px; padding-inline: .55rem; font-size: .58rem; letter-spacing: .04em; }
  .view-hint { display: none; }
}
</style>
