<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useMiyaFluxPreferences } from '@/composables/useMiyaFluxPreferences'
import { useMiyaPresence } from '@/composables/useMiyaPresence'
import { porcelainEmotionColor } from '@/utils/miyaFluxTheme'

const props = withDefaults(defineProps<{ ambient?: boolean }>(), { ambient: false })
const frame = ref<HTMLIFrameElement>()
const { presence, online } = useMiyaPresence()
const { mode, paused, portrait, avatarSource } = useMiyaFluxPreferences()
const sceneUrl = `${import.meta.env.BASE_URL}haloflux/lab.html?ambient=1&miya=1`
const origin = window.location.origin
const fileOrigin = window.location.protocol === 'file:'
const targetOrigin = fileOrigin || origin === 'null' ? '*' : origin
const payload = computed(() => ({
  type: 'miya:presence',
  online: online.value,
  activity: online.value ? presence.value.activity : null,
  memoryCount: online.value ? presence.value.memoryCount : null,
  platformCount: online.value ? presence.value.platformCount : null,
  color: porcelainEmotionColor(online.value ? presence.value.emotion ?? 'calm' : 'neutral'),
  mode: mode.value,
  paused: paused.value || document.hidden,
  ambient: props.ambient,
}))
const portraitPayload = computed(() => ({
  type: 'miya:portrait',
  source: avatarSource.value,
  zoom: portrait.value.zoom,
  x: portrait.value.x,
  y: portrait.value.y,
  flow: portrait.value.flow,
}))

function syncPortrait() {
  frame.value?.contentWindow?.postMessage({ ...portraitPayload.value }, targetOrigin)
}

function syncScene() {
  frame.value?.contentWindow?.postMessage({ ...payload.value, paused: paused.value || document.hidden }, targetOrigin)
}

function syncAll() {
  syncScene()
  syncPortrait()
}

function receiveReady(event: MessageEvent) {
  const trustedOrigin = event.origin === origin || (fileOrigin && event.origin === 'null')
  if (event.source === frame.value?.contentWindow && trustedOrigin && event.data?.type === 'miya:ready')
    syncAll()
}

watch(payload, syncScene)
watch(portraitPayload, syncPortrait)
onMounted(() => {
  window.addEventListener('message', receiveReady)
  document.addEventListener('visibilitychange', syncScene)
})
onUnmounted(() => {
  window.removeEventListener('message', receiveReady)
  document.removeEventListener('visibilitychange', syncScene)
})
</script>

<template>
  <iframe
    ref="frame"
    :src="sceneUrl"
    title="弥娅灵魂共鸣场"
    tabindex="-1"
    aria-hidden="true"
    @load="syncAll"
  />
</template>
