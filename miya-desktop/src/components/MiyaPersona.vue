<script setup lang="ts">
import { computed } from 'vue'
import { useSystemStore } from '../stores/system'

const systemStore = useSystemStore()

// 计算人格数据
const personalityData = computed(() => {
  if (!systemStore.status?.personality) return null
  return systemStore.status.personality
})

// 计算最大值（用于归一化）
const maxValue = computed(() => {
  if (!personalityData.value) return 1
  return Math.max(...Object.values(personalityData.value))
})

// 获取人格中文映射
const personalityLabels: Record<string, string> = {
  warmth: '温暖',
  logic: '理性',
  creativity: '创造',
  empathy: '共情',
  resilience: '韧性'
}

// 获取人格颜色
const personalityColors: Record<string, string> = {
  warmth: '#e94560',
  logic: '#3b82f6',
  creativity: '#a855f7',
  empathy: '#22c55e',
  resilience: '#f59e0b'
}

// 获取主导人格
const dominantPersonality = computed(() => {
  if (!personalityData.value) return null
  const entries = Object.entries(personalityData.value)
  const dominant = entries.reduce((a, b) => a[1] > b[1] ? a : b)
  return {
    key: dominant[0],
    label: personalityLabels[dominant[0]],
    value: dominant[1],
    color: personalityColors[dominant[0]]
  }
})

// 获取雷达图背景点
const getRadarPoints = (scale: number) => {
  const points: string[] = []
  for (let i = 0; i < 5; i++) {
    const angle = (i * 72 - 90) * Math.PI / 180
    const radius = scale * 80
    const x = 100 + Math.cos(angle) * radius
    const y = 100 + Math.sin(angle) * radius
    points.push(`${x},${y}`)
  }
  return points.join(' ')
}

// 获取数据点
const getDataPoints = () => {
  if (!personalityData.value || !maxValue.value) return '100,100'

  const keys = Object.keys(personalityData.value)
  const points = keys.map((key, index) => {
    const angle = (index * 72 - 90) * Math.PI / 180
    const value = personalityData.value[key] / maxValue.value * 80
    const x = 100 + Math.cos(angle) * value
    const y = 100 + Math.sin(angle) * value
    return `${x},${y}`
  })
  return points.join(' ')
}
</script>

<template>
  <div class="miya-persona" v-if="personalityData">
    <!-- 主导人格显示 -->
    <div v-if="dominantPersonality" class="dominant-personality">
      <div class="personality-icon" :style="{ background: dominantPersonality.color }">
        <i class="pi pi-heart"></i>
      </div>
      <div class="personality-info">
        <div class="personality-label">当前人格</div>
        <div class="personality-value" :style="{ color: dominantPersonality.color }">
          {{ dominantPersonality.label }}
        </div>
      </div>
    </div>

    <!-- 人格雷达图 -->
    <div class="radar-chart">
      <svg viewBox="0 0 200 200" class="radar-svg">
        <!-- 背景网格 -->
        <polygon
          v-for="i in 4"
          :key="'grid-' + i"
          :points="getRadarPoints(i / 4)"
          fill="none"
          stroke="rgba(255, 255, 255, 0.1)"
          :stroke-width="1"
        />

        <!-- 轴线 -->
        <line
          v-for="i in 5"
          :key="'axis-' + i"
          :x1="100"
          :y1="100"
          :x2="100 + Math.cos((i * 72 - 90) * Math.PI / 180) * 80"
          :y2="100 + Math.sin((i * 72 - 90) * Math.PI / 180) * 80"
          stroke="rgba(255, 255, 255, 0.1)"
          stroke-width="1"
        />

        <!-- 数据区域 -->
        <polygon
          :points="getDataPoints()"
          fill="rgba(233, 69, 96, 0.3)"
          stroke="#e94560"
          stroke-width="2"
        />

        <!-- 数据点 -->
        <circle
          v-for="(value, key, index) in personalityData"
          :key="'point-' + key"
          :cx="100 + Math.cos((index * 72 - 90) * Math.PI / 180) * (value / maxValue * 80)"
          :cy="100 + Math.sin((index * 72 - 90) * Math.PI / 180) * (value / maxValue * 80)"
          r="4"
          :fill="personalityColors[key]"
        />
      </svg>
    </div>

    <!-- 人格详情列表 -->
    <div class="personality-details">
      <div
        v-for="(value, key) in personalityData"
        :key="key"
        class="personality-item"
      >
        <div class="personality-label-small">
          <span
            class="color-dot"
            :style="{ background: personalityColors[key] }"
          ></span>
          {{ personalityLabels[key] }}
        </div>
        <div class="personality-bar-container">
          <div
            class="personality-bar"
            :style="{
              width: (value / maxValue * 100) + '%',
              background: personalityColors[key]
            }"
          />
        </div>
        <div class="personality-value-small">{{ (value * 100).toFixed(0) }}%</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.miya-persona {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

.dominant-personality {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}

.personality-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.personality-info {
  flex: 1;
}

.personality-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 2px;
}

.personality-value {
  font-size: 16px;
  font-weight: 600;
}

.radar-chart {
  width: 100%;
  aspect-ratio: 1;
}

.radar-svg {
  width: 100%;
  height: 100%;
}

.personality-details {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.personality-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.personality-label-small {
  width: 50px;
  font-size: 12px;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.personality-bar-container {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
}

.personality-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.personality-value-small {
  width: 40px;
  font-size: 12px;
  color: var(--text-secondary);
  text-align: right;
}

/* 亮色主题 */
:deep(.light-mode .dominant-personality) {
  background: rgba(0, 0, 0, 0.03);
}

:deep(.light-mode .personality-bar-container) {
  background: rgba(0, 0, 0, 0.05);
}
</style>
