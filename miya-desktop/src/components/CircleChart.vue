<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  value: number
  max?: number
  size?: number
  strokeWidth?: number
  color?: string
  label?: string
  showPercentage?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  max: 100,
  size: 120,
  strokeWidth: 8,
  color: '#e94560',
  showPercentage: true
})

const percentage = computed(() => {
  return Math.min((props.value / props.max) * 100, 100)
})

const radius = computed(() => {
  return (props.size - props.strokeWidth) / 2
})

const circumference = computed(() => {
  return 2 * Math.PI * radius.value
})

const strokeDashoffset = computed(() => {
  return circumference.value - (percentage.value / 100) * circumference.value
})

// 根据百分比获取颜色
const getColor = computed(() => {
  const p = percentage.value
  if (p < 50) return '#22c55e'
  if (p < 80) return '#eab308'
  return props.color
})

// 旋转角度（从顶部开始）
const rotation = computed(() => {
  return -90
})
</script>

<template>
  <div class="circle-chart" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :width="size" :height="size" class="chart-svg">
      <!-- 背景圆 -->
      <circle
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        :stroke-width="strokeWidth"
        fill="none"
        stroke="rgba(255, 255, 255, 0.1)"
      />

      <!-- 进度圆 -->
      <circle
        :cx="size / 2"
        :cy="size / 2"
        :r="radius"
        :stroke-width="strokeWidth"
        fill="none"
        :stroke="getColor"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="strokeDashoffset"
        :transform="`rotate(${rotation}, ${size / 2}, ${size / 2})`"
        stroke-linecap="round"
        class="progress-circle"
      />
    </svg>

    <!-- 中心内容 -->
    <div class="chart-content">
      <div v-if="showPercentage" class="percentage">
        {{ percentage.toFixed(0) }}%
      </div>
      <div v-if="label" class="label">{{ label }}</div>
    </div>
  </div>
</template>

<style scoped>
.circle-chart {
  position: relative;
  display: inline-flex;
}

.chart-svg {
  transform: rotate(-90deg);
}

.progress-circle {
  transition: stroke-dashoffset 0.5s ease;
}

.chart-content {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.percentage {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

/* 亮色主题 */
:deep(.light-mode .percentage) {
  color: #1a1a2e;
}

:deep(.light-mode .label) {
  color: rgba(0, 0, 0, 0.6);
}
</style>
