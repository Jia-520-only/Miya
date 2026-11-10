<script setup lang="ts">
import type { RuntimeLog } from '@/utils/miyaRuntimeLogs'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useMiyaFluxPreferences } from '@/composables/useMiyaFluxPreferences'
import { useMiyaPresence } from '@/composables/useMiyaPresence'
import { porcelainEmotionColor } from '@/utils/miyaFluxTheme'
import { runtimeTelemetry } from '@/utils/miyaRuntimeLogs'

export interface FluxGeometry {
  width: number
  height: number
  x: number
  y: number
  radius: number
  outerRadius: number
}
const props = withDefaults(defineProps<{ ambient?: boolean, framed?: boolean, selectedLayer?: string | null, runtimeLogs?: RuntimeLog[] }>(), { ambient: false, framed: false, selectedLayer: null, runtimeLogs: () => [] })
const emit = defineEmits<{ geometry: [value: FluxGeometry] }>()
const frame = ref<HTMLIFrameElement>()
const { presence, online } = useMiyaPresence()
const { mode, composition, paused, portrait, avatarSource } = useMiyaFluxPreferences()
const sceneUrl = computed(() => `${import.meta.env.BASE_URL}haloflux/lab.html?ambient=1&miya=1${props.framed ? '&framed=1' : ''}`)
const origin = window.location.origin
const fileOrigin = window.location.protocol === 'file:'
const targetOrigin = fileOrigin || origin === 'null' ? '*' : origin
const payload = computed(() => ({
  type: 'miya:presence',
  online: online.value,
  phase: online.value ? presence.value.phase : null,
  emotionIntensity: online.value ? presence.value.emotionIntensity : null,
  messageCount: online.value ? presence.value.messageCount : null,
  memoryCount: online.value ? presence.value.memoryCount : null,
  memoryLayers: online.value ? { ...presence.value.memoryLayers } : {},
  platformCount: online.value ? presence.value.platformCount : null,
  composition: props.framed ? composition.value : 'ambient',
  selectedLayer: props.selectedLayer,
  runtimeLogs: runtimeTelemetry(props.runtimeLogs).map(entry => ({ seq: entry.seq, name: entry.name, text: entry.text.slice(0, 120), category: entry.category })),
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
  if (event.source !== frame.value?.contentWindow || !trustedOrigin)
    return
  if (event.data?.type === 'miya:ready')
    syncAll()
  if (event.data?.type === 'miya:geometry') {
    const value = event.data.geometry
    if (value && ['width', 'height', 'x', 'y', 'radius', 'outerRadius'].every(key => typeof value[key] === 'number' && Number.isFinite(value[key]))
      && value.width > 0 && value.height > 0 && value.radius > 0 && value.outerRadius >= value.radius) {
      emit('geometry', value)
    }
  }
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
