<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'

interface Props {
  items: any[]
  itemSize: number
  containerHeight: number
  buffer?: number
}

const props = withDefaults(defineProps<Props>(), {
  buffer: 5
})

const emit = defineEmits<{
  (e: 'visible-change', start: number, end: number): void
}>()

const containerRef = ref<HTMLElement>()
const scrollTop = ref(0)

// 计算可见的项目数量
const visibleCount = computed(() => {
  return Math.ceil(props.containerHeight / props.itemSize)
})

// 计算起始索引
const startIndex = computed(() => {
  return Math.max(0, Math.floor(scrollTop.value / props.itemSize) - props.buffer)
})

// 计算结束索引
const endIndex = computed(() => {
  return Math.min(
    props.items.length - 1,
    startIndex.value + visibleCount.value + props.buffer * 2
  )
})

// 可见项目
const visibleItems = computed(() => {
  return props.items.slice(startIndex.value, endIndex.value + 1)
})

// 总高度
const totalHeight = computed(() => {
  return props.items.length * props.itemSize
})

// 偏移量
const offsetY = computed(() => {
  return startIndex.value * props.itemSize
})

function handleScroll(event: Event) {
  const target = event.target as HTMLElement
  scrollTop.value = target.scrollTop
  emit('visible-change', startIndex.value, endIndex.value)
}

function scrollToItem(index: number) {
  if (containerRef.value) {
    containerRef.value.scrollTop = index * props.itemSize
  }
}

function scrollToTop() {
  if (containerRef.value) {
    containerRef.value.scrollTop = 0
  }
}

function scrollToBottom() {
  if (containerRef.value) {
    containerRef.value.scrollTop = totalHeight.value
  }
}

// 暴露方法
defineExpose({
  scrollToItem,
  scrollToTop,
  scrollToBottom
})
</script>

<template>
  <div
    ref="containerRef"
    class="virtual-list"
    :style="{ height: containerHeight + 'px' }"
    @scroll="handleScroll"
  >
    <div
      class="virtual-list-content"
      :style="{
        height: totalHeight + 'px',
        transform: `translateY(${offsetY}px)`
      }"
    >
      <slot
        name="item"
        v-for="(item, index) in visibleItems"
        :key="startIndex + index"
        :item="item"
        :index="startIndex + index"
      />
    </div>
  </div>
</template>

<style scoped>
.virtual-list {
  overflow-y: auto;
  position: relative;
}

.virtual-list-content {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  will-change: transform;
}
</style>
