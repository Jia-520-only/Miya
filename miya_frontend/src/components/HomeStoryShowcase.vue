<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import { computed, ref, watch } from 'vue'
import EarthAPI from '@/api/earth'
import { pX, pY } from '@/utils/parallax'
import { isLegacyBackground } from '@/utils/backgroundAssets'

const images = useStorage<string[]>('miya-home-gallery-images', [])
images.value = images.value.filter(image => !isLegacyBackground(image))
const captions = useStorage<Record<string, { title: string, description: string }>>('miya-home-gallery-captions', {})
// 展示框自定义样式/文案: 不硬编码，全部可在右上角 ✧ 面板里改
const showcaseStyle = useStorage('miya-home-gallery-style', {
  accent: '',          // 主色 (空 = 跟随主题)
  heading: '美图',     // 标题
  kicker: 'MIYA VISUAL ARCHIVE', // 眉题 (默认隐藏，可开启)
  showKicker: false,
  showCounter: false,  // 右上页码 1/3
  tagText: 'MIYA ART', // 主卡片左上角小角标
})
const panelOpen = ref(false)
const index = ref(0)
watch(() => images.value.length, (length) => {
  if (!length)
    index.value = 0
  else if (index.value >= length)
    index.value = length - 1
})

const current = computed(() => images.value[index.value] || null)
const previous = computed(() => {
  if (!images.value.length)
    return null
  return images.value[(index.value - 1 + images.value.length) % images.value.length] || null
})
const next = computed(() => {
  if (!images.value.length)
    return null
  return images.value[(index.value + 1) % images.value.length] || null
})

const galleryTransform = computed(() => {
  const rotateX = pY.value * -1.4
  const rotateY = pX.value * 3.2
  return `rotateX(${rotateX.toFixed(1)}deg) rotateY(${rotateY.toFixed(1)}deg)`
})
const currentCaption = computed(() => current.value ? captions.value[current.value] : undefined)
const accentStyle = computed(() => (showcaseStyle.value.accent ? { '--hs-accent': showcaseStyle.value.accent } : {}))
// 面板打开/切图时先落一个空配字对象，v-model 才能写进响应式存储
watch([current, panelOpen], () => {
  if (panelOpen.value && current.value && !captions.value[current.value])
    captions.value[current.value] = { title: '', description: '' }
})

function imageUrl(image: string | null): string {
  if (!image)
    return ''
  return image.startsWith('/api/') ? EarthAPI.imageUrl(image) : image
}

function cardStyle(image: string | null, preserveFullImage = false): Record<string, string> {
  if (preserveFullImage) {
    return {
      '--hs-image': `url(${imageUrl(image)})`,
      backgroundImage: 'none',
      backgroundColor: 'rgba(5, 9, 15, 0.82)',
    }
  }
  const style: Record<string, string> = {
    backgroundImage: `linear-gradient(180deg, rgba(7,8,12,0.08), rgba(7,8,12,0.78)), url(${imageUrl(image)})`,
  }
  return style
}

function step(delta: number) {
  if (!images.value.length)
    return
  index.value = (index.value + delta + images.value.length) % images.value.length
}

function pick(image: string | null) {
  if (!image)
    return
  const found = images.value.indexOf(image)
  if (found >= 0)
    index.value = found
}

function resetStyle() {
  showcaseStyle.value = { accent: '', heading: '美图', kicker: 'MIYA VISUAL ARCHIVE', showKicker: false, showCounter: false, tagText: 'MIYA ART' }
}
</script>

<template>
  <aside class="home-story-showcase" :style="{ transform: galleryTransform, ...accentStyle }" aria-label="弥娅美图展示">
    <div v-if="showcaseStyle.showKicker && showcaseStyle.kicker" class="home-story-kicker">{{ showcaseStyle.kicker }}</div>
    <div class="home-story-heading">
      <span class="home-story-heading-text">
        {{ showcaseStyle.heading || '美图' }}
        <button class="home-story-tune" title="自定义文字与配色" @click="panelOpen = !panelOpen">✧</button>
      </span>
      <small v-if="showcaseStyle.showCounter">{{ images.length ? `${index + 1} / ${images.length}` : '' }}</small>
    </div>

    <!-- 自定义面板: 主色 / 文案 / 页码开关 / 当前图配字 -->
    <div v-if="panelOpen" class="home-story-panel">
      <label class="home-story-panel-row">
        <span>主色</span>
        <input v-model="showcaseStyle.accent" type="color" class="home-story-color" :style="{ background: showcaseStyle.accent || '#78cfd1' }">
        <button class="home-story-panel-btn" @click="showcaseStyle.accent = ''">跟随主题</button>
      </label>
      <label class="home-story-panel-row"><span>标题</span><input v-model="showcaseStyle.heading" type="text" maxlength="12" placeholder="美图"></label>
      <label class="home-story-panel-row"><span>角标</span><input v-model="showcaseStyle.tagText" type="text" maxlength="16" placeholder="MIYA ART"></label>
      <label class="home-story-panel-row">
        <span>眉题</span>
        <input v-model="showcaseStyle.kicker" type="text" maxlength="24" placeholder="MIYA VISUAL ARCHIVE">
        <button class="home-story-panel-btn" :class="{ on: showcaseStyle.showKicker }" @click="showcaseStyle.showKicker = !showcaseStyle.showKicker">{{ showcaseStyle.showKicker ? '显示中' : '已隐藏' }}</button>
      </label>
      <label class="home-story-panel-row">
        <span>页码</span>
        <button class="home-story-panel-btn" :class="{ on: showcaseStyle.showCounter }" @click="showcaseStyle.showCounter = !showcaseStyle.showCounter">{{ showcaseStyle.showCounter ? '显示中' : '已隐藏' }}</button>
      </label>
      <template v-if="current && currentCaption">
        <label class="home-story-panel-row"><span>配字标题</span><input v-model="currentCaption.title" type="text" maxlength="24" placeholder="这张图的名字"></label>
        <label class="home-story-panel-row"><span>配字描述</span><input v-model="currentCaption.description" type="text" maxlength="60" placeholder="想为这一刻留下的话"></label>
      </template>
      <div class="home-story-panel-foot">
        <button class="home-story-panel-btn" @click="resetStyle">恢复默认</button>
        <button class="home-story-panel-btn" @click="panelOpen = false">收起 ✧</button>
      </div>
    </div>

    <div v-if="!current" class="home-story-empty">
      <span class="home-story-empty-mark">≋</span>
      <p>还没有弥娅美图</p>
      <small>去画廊生成或保存一张图片，再回来让它成为首页的主视觉。</small>
    </div>
    <div v-else class="home-story-stage">
      <button class="home-story-side home-story-side-prev" :style="cardStyle(previous)" title="上一张美图" @click="pick(previous)">
        <span>PREV</span>
      </button>
      <article class="home-story-main" :style="cardStyle(current, true)">
        <div class="home-story-main-image" aria-hidden="true" />
        <div class="home-story-main-top">
          <span v-if="showcaseStyle.tagText">{{ showcaseStyle.tagText }}</span>
          <span>{{ String(index + 1).padStart(2, '0') }}</span>
        </div>
        <div v-if="currentCaption?.title || currentCaption?.description" class="home-story-main-copy">
          <strong v-if="currentCaption?.title">{{ currentCaption.title }}</strong>
          <p v-if="currentCaption?.description">{{ currentCaption.description }}</p>
        </div>
        <div class="home-story-main-line" />
      </article>
      <button class="home-story-side home-story-side-next" :style="cardStyle(next)" title="下一张美图" @click="pick(next)">
        <span>NEXT</span>
      </button>
    </div>

    <div v-if="current" class="home-story-controls-row">
      <div class="home-story-controls">
        <button class="home-story-arrow" title="上一张美图" @click="step(-1)">‹</button>
        <div class="home-story-dots" aria-label="美图页码">
          <button v-for="(image, imageIndex) in images" :key="`${image}-${imageIndex}`" class="home-story-dot" :class="{ active: imageIndex === index }" title="切换弥娅美图" @click="index = imageIndex" />
        </div>
        <button class="home-story-arrow" title="下一张美图" @click="step(1)">›</button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.home-story-showcase {
  --hs-accent: var(--pv-gold, #78cfd1);
  width: clamp(330px, 29vw, 390px);
  color: #f0e6cf;
  pointer-events: auto;
  user-select: none;
  transform-origin: center;
  transition: transform 0.16s ease-out;
  will-change: transform;
  transform-style: preserve-3d;
}
.home-story-kicker {
  color: color-mix(in srgb, var(--hs-accent) 78%, white 8%);
  font-family: 'mc-gamefont', serif;
  font-size: 0.58rem;
  letter-spacing: 0.34em;
  text-align: right;
}
.home-story-heading {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin: 0.28rem 0 0.65rem;
  border-bottom: 1px solid color-mix(in srgb, var(--hs-accent) 32%, transparent);
  padding-bottom: 0.48rem;
}
.home-story-heading-text { display: inline-flex; align-items: center; gap: 0.5rem; font-size: 1rem; letter-spacing: 0.22em; }
.home-story-heading small { color: rgba(255, 255, 255, 0.44); font-size: 0.56rem; letter-spacing: 0.14em; }
.home-story-tune {
  padding: 0 0.4rem;
  border: 1px solid color-mix(in srgb, var(--hs-accent) 40%, transparent);
  background: transparent;
  color: var(--hs-accent);
  font-size: 0.62rem;
  cursor: pointer;
  transition: background 0.2s;
}
.home-story-tune:hover { background: color-mix(in srgb, var(--hs-accent) 16%, transparent); }
.home-story-panel {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin: 0 0 0.7rem;
  padding: 0.7rem 0.8rem;
  border: 1px solid color-mix(in srgb, var(--hs-accent) 38%, transparent);
  background: rgba(7, 8, 12, 0.72);
  font-size: 0.62rem;
}
.home-story-panel-row { display: flex; align-items: center; gap: 0.5rem; color: rgba(255, 255, 255, 0.62); }
.home-story-panel-row > span { flex: 0 0 3.4em; letter-spacing: 0.08em; }
.home-story-panel-row input[type='text'] {
  flex: 1;
  min-width: 0;
  padding: 0.25rem 0.45rem;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(0, 0, 0, 0.35);
  color: #f0e6cf;
  font-size: 0.62rem;
}
.home-story-panel-row input[type='text']:focus { outline: none; border-color: var(--hs-accent); }
.home-story-color { width: 30px; height: 22px; padding: 0; border: 1px solid rgba(255, 255, 255, 0.2); cursor: pointer; }
.home-story-panel-btn {
  flex-shrink: 0;
  padding: 0.18rem 0.5rem;
  border: 1px solid color-mix(in srgb, var(--hs-accent) 42%, transparent);
  background: transparent;
  color: rgba(255, 255, 255, 0.66);
  font-size: 0.58rem;
  cursor: pointer;
}
.home-story-panel-btn.on, .home-story-panel-btn:hover { color: var(--hs-accent); background: color-mix(in srgb, var(--hs-accent) 14%, transparent); }
.home-story-panel-foot { display: flex; justify-content: flex-end; gap: 0.45rem; margin-top: 0.15rem; }
.home-story-stage { display: flex; align-items: stretch; gap: 7px; height: clamp(340px, 51vh, 430px); perspective: 1000px; transform-style: preserve-3d; }
.home-story-main,
.home-story-side {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--hs-accent) 44%, transparent);
  background-position: center;
  background-size: cover;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.42), inset 0 1px 0 rgba(255, 255, 255, 0.16);
}
.home-story-main::after,
.home-story-side::after { content: ''; position: absolute; inset: 0; border: 1px solid rgba(255,255,255,0.08); pointer-events: none; }
.home-story-main { flex: 1 1 auto; padding: 0.8rem 1rem 0.9rem; min-width: 0; transform: translateZ(16px); }
.home-story-main { box-shadow: 0 22px 64px rgba(0, 0, 0, 0.52), inset 0 0 44px rgba(0, 0, 0, 0.28); }
.home-story-main::before {
  content: '';
  position: absolute;
  inset: -8%;
  z-index: 0;
  background: linear-gradient(180deg, rgba(4, 8, 13, 0.18), rgba(4, 8, 13, 0.76)), var(--hs-image) center / cover no-repeat;
  filter: blur(12px) saturate(0.72);
  opacity: 0.56;
  transform: scale(1.06);
}
.home-story-main-image {
  position: absolute;
  inset: 0;
  z-index: 1;
  background: linear-gradient(180deg, rgba(4, 8, 13, 0.02), rgba(4, 8, 13, 0.28)), var(--hs-image) center / contain no-repeat;
  pointer-events: none;
}
.home-story-side { flex: 0 0 clamp(34px, 3.6vw, 50px); min-width: 0; padding: 0.42rem; opacity: 0.32; cursor: pointer; transition: opacity 0.25s, transform 0.25s, flex-basis 0.25s; }
.home-story-side-prev { transform-origin: right center; transform: rotateY(-12deg) scale(0.96); clip-path: polygon(8% 0, 100% 3%, 100% 97%, 0 100%); }
.home-story-side-prev:hover { flex-basis: clamp(46px, 4.5vw, 64px); opacity: 0.82; transform: translateY(-3px) rotateY(-8deg) scale(0.98); }
.home-story-side-next { transform-origin: left center; transform: rotateY(12deg) scale(0.96); clip-path: polygon(0 3%, 92% 0, 100% 100%, 0 97%); }
.home-story-side-next:hover { flex-basis: clamp(46px, 4.5vw, 64px); opacity: 0.82; transform: translateY(-3px) rotateY(8deg) scale(0.98); }
.home-story-side span { position: relative; z-index: 1; margin-top: auto; color: rgba(255, 255, 255, 0.74); font-size: 0.65rem; line-height: 1.45; }
.home-story-main-top { position: relative; z-index: 2; display: flex; justify-content: space-between; color: var(--hs-accent); font-size: 0.56rem; letter-spacing: 0.1em; }
.home-story-main-copy { position: relative; z-index: 2; max-width: 90%; margin-top: auto; }
.home-story-main-copy strong { display: block; font-size: clamp(1rem, 1.6vw, 1.45rem); line-height: 1.35; }
.home-story-main-copy p { display: -webkit-box; overflow: hidden; margin: 0.45rem 0 0; color: rgba(255,255,255,0.66); font-size: 0.7rem; line-height: 1.6; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.home-story-main-line { position: relative; z-index: 2; width: 42%; height: 2px; margin-top: 0.8rem; background: var(--hs-accent); }
.home-story-controls-row { display: flex; justify-content: center; margin-top: 0.55rem; }
.home-story-controls { display: flex; align-items: center; justify-content: center; gap: 0.55rem; min-width: 0; }
.home-story-arrow { width: 30px; height: 30px; padding: 0; border: 1px solid color-mix(in srgb, var(--hs-accent) 44%, transparent); background: rgba(0,0,0,0.28); color: var(--hs-accent); font-size: 1.2rem; cursor: pointer; }
.home-story-arrow:hover { background: color-mix(in srgb, var(--hs-accent) 18%, transparent); }
.home-story-dots { display: flex; gap: 0.28rem; max-width: min(280px, 48vw); padding: 3px 0; overflow-x: auto; scrollbar-width: thin; }
.home-story-dots::-webkit-scrollbar { height: 2px; }
.home-story-dots::-webkit-scrollbar-thumb { background: rgba(201,172,103,0.35); }
.home-story-dot { width: 17px; height: 3px; padding: 0; border: 0; background: rgba(255,255,255,0.22); cursor: pointer; }
.home-story-dot.active { background: var(--hs-accent); }
.home-story-empty { display: grid; min-height: 300px; place-items: center; border: 1px dashed rgba(201,172,103,0.3); color: rgba(255,255,255,0.58); text-align: center; }
.home-story-empty { padding: 1.4rem; }
.home-story-empty-mark { color: var(--hs-accent); font-size: 1.8rem; }
.home-story-empty p { margin: 0.45rem 0 0.2rem; }
.home-story-empty small { max-width: 250px; color: rgba(255,255,255,0.42); font-size: 0.63rem; line-height: 1.55; }
@media (max-width: 1100px) {
  .home-story-showcase { width: clamp(310px, 30vw, 360px); }
  .home-story-stage { height: clamp(315px, 48vh, 390px); gap: 6px; }
  .home-story-controls-row { gap: 6px; }
}
@media (max-width: 760px) {
  .home-story-showcase { width: min(88vw, 520px); transform: none; }
  .home-story-stage { height: 220px; }
}
</style>
