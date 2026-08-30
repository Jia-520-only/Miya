<script setup lang="ts">
import { useTemplateRef } from 'vue'

defineProps<{
  pt?: unknown
}>()

const viewport = useTemplateRef<HTMLElement>('viewport')

function scrollTop(value: number) {
  const element = viewport.value
  if (!element)
    return
  element.scrollTop = Number.isFinite(value) ? value : element.scrollHeight
}

defineExpose({ scrollTop })
</script>

<template>
  <div ref="viewport" class="miya-scroll-panel">
    <slot />
  </div>
</template>

<style scoped>
.miya-scroll-panel {
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-color: rgba(55, 55, 55, 0.85) transparent;
  scrollbar-width: thin;
}

.miya-scroll-panel::-webkit-scrollbar { width: 8px; }
.miya-scroll-panel::-webkit-scrollbar-track { background: transparent; }
.miya-scroll-panel::-webkit-scrollbar-thumb {
  border-radius: 4px;
  background: rgba(55, 55, 55, 0.85);
}
</style>
