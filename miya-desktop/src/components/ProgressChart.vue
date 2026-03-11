<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  value: number
  max?: number
  label?: string
  color?: string
  size?: 'sm' | 'md' | 'lg'
  showPercentage?: boolean
  animated?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  max: 100,
  color: '#e94560',
  size: 'md',
  showPercentage: true,
  animated: true
})

const percentage = computed(() => {
  return Math.min((props.value / props.max) * 100, 100)
})

const sizeConfig = computed(() => {
  const configs = {
    sm: { height: 6, fontSize: 11 },
    md: { height: 8, fontSize: 12 },
    lg: { height: 12, fontSize: 14 }
  }
  return configs[props.size]
})

// 根据百分比获取颜色
const getColor = computed(() => {
  const p = percentage.value
  if (p < 50) return '#22c55e'
  if (p < 80) return '#eab308'
  return props.color
})
</script>

<template>
  <div class="progress-chart">
    <div v-if="label" class="progress-label">
      <span>{{ label }}</span>
      <span v-if="showPercentage" class="percentage">{{ percentage.toFixed(0) }}%</span>
    </div>
    <div class="progress-track">
      <div
        class="progress-bar"
        :class="{ animated }"
        :style="{
          width: percentage + '%',
          background: getColor,
          height: sizeConfig.height + 'px'
        }"
      ></div>
    </div>
  </div>
</template>

<style scoped>
.progress-chart {
  width: 100%;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--text-primary);
}

.percentage {
  font-weight: 600;
  color: var(--text-secondary);
}

.progress-track {
  width: 100%;
  height: 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-bar.animated {
  animation: progress-fill 1.5s ease-out;
}

@keyframes progress-fill {
  from {
    width: 0;
  }
}

/* 亮色主题 */
:deep(.light-mode .progress-track) {
  background: rgba(0, 0, 0, 0.05);
}
</style>
