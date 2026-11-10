<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useMiyaFluxPreferences } from '@/composables/useMiyaFluxPreferences'

const { portrait, avatarSource, savePortrait } = useMiyaFluxPreferences()
const expanded = ref(false)
const busy = ref(false)
const feedback = ref('')
const failed = ref(false)
const picker = ref<HTMLInputElement>()
const trigger = ref<HTMLButtonElement>()
const closeButton = ref<HTMLButtonElement>()

async function toggle() {
  expanded.value = !expanded.value
  if (expanded.value) {
    await nextTick()
    closeButton.value?.focus()
  }
}

function close() {
  expanded.value = false
  trigger.value?.focus()
}

async function chooseImage(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file)
    return
  feedback.value = ''
  failed.value = false
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 15 * 1024 * 1024) {
    failed.value = true
    feedback.value = '请选择 15 MB 以内的 PNG、JPG 或 WebP 图片。'
    return
  }
  busy.value = true
  const url = URL.createObjectURL(file)
  try {
    const image = new Image()
    image.src = url
    await image.decode()
    const scale = Math.min(1, 1024 / Math.max(image.naturalWidth, image.naturalHeight))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale))
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
    const context = canvas.getContext('2d')
    if (!context)
      throw new Error('图片处理暂不可用')
    context.fillStyle = '#eff4fa'
    context.fillRect(0, 0, canvas.width, canvas.height)
    context.drawImage(image, 0, 0, canvas.width, canvas.height)
    savePortrait(canvas.toDataURL('image/jpeg', 0.9))
    feedback.value = '头像已保存，首页与观测台同步生效。'
  }
  catch (error) {
    failed.value = true
    feedback.value = error instanceof DOMException && error.name === 'QuotaExceededError'
      ? '本地存储空间不足，请换一张较小的图片。'
      : '这张图片暂时无法读取或保存，请尝试另一张。'
  }
  finally {
    busy.value = false
    URL.revokeObjectURL(url)
  }
}

function restore() {
  try {
    savePortrait('')
    failed.value = false
    feedback.value = '已恢复默认的青花瓷弥娅。'
  }
  catch {
    failed.value = true
    feedback.value = '暂时无法保存，请稍后重试。'
  }
}
</script>

<template>
  <div class="portrait-settings" @keydown.esc.stop="close">
    <button ref="trigger" class="portrait-trigger" :aria-expanded="expanded" aria-controls="miya-portrait-editor" @click="toggle">
      <img :src="avatarSource" alt="" aria-hidden="true">头像设置
    </button>
    <Teleport to="body">
      <div v-if="expanded" class="portrait-dismiss" aria-hidden="true" @click="close" />
      <section v-if="expanded" id="miya-portrait-editor" class="portrait-editor" role="dialog" aria-label="自定义弥娅头像" @keydown.esc.stop="close">
        <header>
          <div><span>青花 · 映像</span><small>PORCELAIN / PORTRAIT</small></div><button ref="closeButton" aria-label="关闭头像设置" @click="close">
            ×
          </button>
        </header>
        <div class="portrait-preview-row">
          <div class="portrait-preview">
            <img :src="avatarSource" :style="{ objectPosition: `${portrait.x}% ${portrait.y}%`, transform: `scale(${portrait.zoom})`, transformOrigin: `${portrait.x}% ${portrait.y}%` }" alt="弥娅头像裁切预览">
          </div>
          <div><p>你的弥娅，你的映像。</p><small>圆形裁切 · 本地保存<br>首页与观测台共用</small></div>
        </div>
        <input ref="picker" class="portrait-file" type="file" accept="image/png,image/jpeg,image/webp" aria-label="选择弥娅头像图片" @change="chooseImage">
        <div class="portrait-buttons">
          <button :disabled="busy" @click="picker?.click()">
            {{ busy ? '正在保存…' : '选择图片' }}
          </button><button :disabled="busy" @click="restore">
            恢复默认
          </button>
        </div>
        <label>头像缩放 <span>{{ Number(portrait.zoom).toFixed(2) }}×</span><input v-model.number="portrait.zoom" aria-label="头像缩放" type="range" min="1" max="2.5" step="0.05"></label>
        <label>左右位置 <input v-model.number="portrait.x" aria-label="头像左右位置" type="range" min="0" max="100" step="1"></label>
        <label>上下位置 <input v-model.number="portrait.y" aria-label="头像上下位置" type="range" min="0" max="100" step="1"></label>
        <label>数据流强度 <span>{{ portrait.flow }}%</span><input v-model.number="portrait.flow" aria-label="头像数据流强度" type="range" min="0" max="75" step="1"></label>
        <p class="portrait-help">
          PNG / JPG / WebP，最大 15 MB。调整后自动保存。
        </p>
        <p v-if="feedback" class="portrait-feedback" :class="{ failed }" role="status">
          {{ feedback }}
        </p>
      </section>
    </Teleport>
  </div>
</template>

<style scoped>
.portrait-settings { position: relative; }
.portrait-trigger { display: flex; align-items: center; gap: 7px; padding: 5px 8px; min-height: 32px; border: 1px solid rgba(148,184,239,.23); border-radius: 4px; color: #c4d8f2; background: rgba(19,38,70,.64); font-size: 11px; cursor: pointer; white-space: nowrap; }
.portrait-trigger:hover,.portrait-trigger[aria-expanded=true] { background: rgba(76,116,185,.22); border-color: rgba(177,205,245,.5); }
.portrait-trigger > img { width: 20px; height: 20px; border-radius: 50%; object-fit: cover; }
.portrait-dismiss { position: fixed; inset: 0; z-index: 1000; background: #02051099; }
.portrait-editor { position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%); z-index: 1001; width: min(340px,calc(100vw - 32px)); max-height: min(640px,calc(100dvh - 80px)); overflow: auto; overscroll-behavior: contain; padding: 20px; border: 1px solid rgba(148,184,239,.38); border-radius: 8px; color: #dce6f4; background: linear-gradient(145deg,#12213b,#080f1f 85%); box-shadow: 0 18px 60px #020510b3; }
.portrait-editor > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding-bottom: 15px; border-bottom: 1px solid #a0c1ee24; }
.portrait-editor > header > div { display: grid; gap: 6px; }
.portrait-editor > header span { font: 16px SimSun,serif; letter-spacing: .16em; color: #e4ecf7; }
.portrait-editor > header small { color: #7897c2; font: 8px Consolas,monospace; letter-spacing: .1em; }
.portrait-editor > header > button { width: 28px; height: 28px; background: transparent; color: #aec6e8; cursor: pointer; font-size: 20px; }
.portrait-preview-row { display: flex; align-items: center; gap: 15px; margin: 18px 0; }
.portrait-preview { width: 80px; height: 80px; flex-shrink: 0; overflow: hidden; border: 2px solid #b6cfec; border-radius: 50%; box-shadow: 0 0 0 4px #5582c91f; }
.portrait-preview img { width: 100%; height: 100%; object-fit: cover; }
.portrait-preview-row p { margin: 0 0 7px; font-size: 11px; }
.portrait-preview-row small { color: #8ea5c6; font-size: 10px; line-height: 1.8; }
.portrait-file { display: none; }
.portrait-buttons { display: flex; gap: 8px; margin-bottom: 18px; }
.portrait-buttons button { flex: 1; min-height: 32px; border: 1px solid #94b8ef38; border-radius: 3px; background: #648fdb18; color: #c6d8f3; cursor: pointer; font-size: 11px; }
.portrait-buttons button:hover { background: #648fdb30; }
.portrait-buttons button:disabled { cursor: wait; opacity: .5; }
.portrait-editor > label { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; margin-top: 13px; color: #adc1dc; font-size: 10px; }
.portrait-editor > label > span { color: #e1ebf8; font-family: Consolas,monospace; }
.portrait-editor input[type=range] { width: 100%; height: 14px; margin: 0; accent-color: #8cafe6; cursor: pointer; }
.portrait-help { margin: 16px 0 0; color: #6d86aa; font-size: 9px; line-height: 1.8; }
.portrait-feedback { margin: 10px 0 0; color: #b5d7f7; font-size: 10px; line-height: 1.8; }
.portrait-feedback.failed { color: #f1b0b8; }
@media (max-width: 480px) { .portrait-trigger { gap: 4px; padding-inline: 5px; font-size: 10px; } .portrait-trigger > img { width: 17px; height: 17px; } }
</style>
