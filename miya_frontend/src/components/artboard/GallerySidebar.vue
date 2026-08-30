<script setup lang="ts">
import type { ArtImageEntry } from '@/types/art'
import API from '@/api/art'

defineProps<{
  images: ArtImageEntry[]
  selectedId?: string
}>()

const emit = defineEmits<{
  select: [img: ArtImageEntry]
  delete: [img: ArtImageEntry]
}>()

function getThumbSrc(img: ArtImageEntry): string {
  return API.getImageUrl(img.filename)
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}
</script>

<template>
  <div class="h-full flex flex-col">
    <div class="p-3 border-b border-gray-800 text-xs text-gray-500">
      画廊 · {{ images.length }} 张
    </div>
    <div class="flex-1 overflow-y-auto p-2 space-y-2">
      <div v-if="images.length === 0" class="text-xs text-gray-600 p-4 text-center">
        等待弥娅的创作...
      </div>
      <div
        v-for="img in images"
        :key="img.id"
        class="group relative rounded-lg overflow-hidden border-2 transition-all cursor-pointer"
        :class="selectedId === img.id ? 'border-blue-500' : 'border-transparent hover:border-gray-600'"
        @click="emit('select', img)"
      >
        <img
          :src="getThumbSrc(img)"
          class="w-full aspect-square object-cover"
          loading="lazy"
        >
        <div class="absolute inset-x-0 bottom-0 p-1.5 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
          <div class="text-xs text-white truncate">{{ img.prompt?.slice(0, 30) || '' }}</div>
          <div class="text-2xs text-gray-400">{{ formatTime(img.created_at) }}</div>
        </div>
        <button
          class="absolute top-1 right-1 w-5 h-5 rounded-full bg-red-600/80 text-white text-xs opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
          title="删除"
          @click.stop="emit('delete', img)"
        >
          ✕
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.text-2xs {
  font-size: 0.6rem;
  line-height: 0.8rem;
}
</style>
