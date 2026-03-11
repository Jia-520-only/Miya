import { ref, computed } from 'vue'

export function useVirtualScroll(options: {
  items: any[]
  itemSize: number
  containerHeight: number
  buffer?: number
}) {
  const { items, itemSize, containerHeight, buffer = 5 } = options

  const containerRef = ref<HTMLElement>()
  const scrollTop = ref(0)

  // 计算可见的项目数量
  const visibleCount = computed(() => {
    return Math.ceil(containerHeight / itemSize)
  })

  // 计算起始索引
  const startIndex = computed(() => {
    return Math.max(0, Math.floor(scrollTop.value / itemSize) - buffer)
  })

  // 计算结束索引
  const endIndex = computed(() => {
    return Math.min(
      items.value.length - 1,
      startIndex.value + visibleCount.value + buffer * 2
    )
  })

  // 可见项目
  const visibleItems = computed(() => {
    return items.value.slice(startIndex.value, endIndex.value + 1)
  })

  // 总高度
  const totalHeight = computed(() => {
    return items.value.length * itemSize
  })

  // 偏移量
  const offsetY = computed(() => {
    return startIndex.value * itemSize
  })

  function handleScroll(event: Event) {
    const target = event.target as HTMLElement
    scrollTop.value = target.scrollTop
  }

  function scrollToItem(index: number) {
    if (containerRef.value) {
      containerRef.value.scrollTop = index * itemSize
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

  return {
    containerRef,
    scrollTop,
    startIndex,
    endIndex,
    visibleItems,
    totalHeight,
    offsetY,
    handleScroll,
    scrollToItem,
    scrollToTop,
    scrollToBottom
  }
}
