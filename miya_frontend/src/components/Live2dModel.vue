<script lang="ts">
import * as PIXI from 'pixi.js'
import { install as installUnsafeEval } from '@pixi/unsafe-eval'
installUnsafeEval(PIXI)
</script>

<script setup lang="ts">
import type { Live2DModel } from 'pixi-live2d-display/cubism4'
import { computed, nextTick, onMounted, onUnmounted, useTemplateRef, watch } from 'vue'
import { CONFIG } from '@/utils/config'
import { ensureLive2dCoreLoaded } from '@/utils/live2dCoreLoader'
import { destroyController, initController } from '@/utils/live2dController'

const props = withDefaults(defineProps<{
  source: string
  width: number
  height: number
  x?: number
  y?: number
  fillRatio?: number
  ssaa?: number
}>(), {
  x: 0.5,
  y: 0.4,
  fillRatio: 0.75,
  ssaa: 2,
})

const emit = defineEmits<{
  modelReady: [pos: { faceX: number, faceY: number }]
}>()

;(window as Window & typeof globalThis & { PIXI: typeof PIXI }).PIXI = PIXI

let app: PIXI.Application

const bufWidth = computed(() => props.width * props.ssaa)
const bufHeight = computed(() => props.height * props.ssaa)

const canvas = useTemplateRef('canvas')

onMounted(async () => {
  if (!canvas.value) return

  app = new PIXI.Application({
    view: canvas.value,
    width: bufWidth.value,
    height: bufHeight.value,
    antialias: true,
    backgroundAlpha: 0,
  })

  watch(() => [props.width, props.height, props.ssaa], () => nextTick().then(() => app.resize()))

  watch(() => props.source, async (source, _, onCleanUp) => {
    try {
      await ensureLive2dCoreLoaded()
      // Load the adapter only after Cubism Core has registered its runtime.
      const { Live2DModel } = await import('pixi-live2d-display/cubism4')
      const rawModel = await Live2DModel.from(source)
      const model = Object.assign(rawModel, {
        rawWidth: rawModel.width,
        rawHeight: rawModel.height,
      })

      function relayout() {
        const fitScale = Math.min(
          bufWidth.value / model.rawWidth,
          bufHeight.value / model.rawHeight,
        ) * props.fillRatio

        model.scale.set(fitScale)
        model.x = props.x * (bufWidth.value - model.rawWidth * fitScale)
        model.y = props.y * (bufHeight.value - model.rawHeight * fitScale)

        const faceY = CONFIG.value.web_live2d.face_y_ratio ?? 0.25
        const faceX = (model.x + model.rawWidth * fitScale * 0.5) / props.ssaa
        const fY = (model.y + model.rawHeight * fitScale * faceY) / props.ssaa
        emit('modelReady', { faceX, faceY: fY })
      }

      relayout()

      const relayoutHandle = watch(
        () => [props.width, props.height, props.ssaa, props.x, props.y, props.fillRatio],
        () => nextTick().then(relayout),
      )

      model.autoInteract = false
      app.stage.addChild(model)
      await initController(rawModel, source)
      console.log('[Live2D Embedded] Model loaded:', model.rawWidth, 'x', model.rawHeight, 'scale:', model.scale.x)

      onCleanUp(() => {
        destroyController()
        relayoutHandle()
        app.stage.removeChild(model)
        model.destroy()
      })
    }
    catch (error) {
      console.error('Failed to initialize Live2D:', error)
    }
  }, { immediate: true })
})

onUnmounted(() => {
  if (app) {
    app.destroy(true, { children: true })
  }
})
</script>

<template>
  <canvas
    ref="canvas"
    :width="bufWidth" :height="bufHeight"
    :style="{ transform: `scale(${1 / props.ssaa})`, transformOrigin: '0 0', touchAction: 'none' }"
  />
</template>
