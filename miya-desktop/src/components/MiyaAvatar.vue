<script setup lang="ts">
import { computed } from 'vue'
import type { EmotionState } from '../stores/chat'

interface Props {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  emotion?: EmotionState
  isTyping?: boolean
  showGlow?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
  isTyping: false,
  showGlow: true
})

// 获取情绪表情
const emotionEmoji = computed(() => {
  if (props.isTyping) return '💭'

  const emojiMap: Record<string, string> = {
    '快乐': '😊',
    '悲伤': '😢',
    '愤怒': '😠',
    '焦虑': '😰',
    '平静': '😌',
    '兴奋': '🤩',
    '困惑': '😕',
    '专注': '🧐',
    '疲惫': '😴',
    '惊讶': '😲'
  }
  return emojiMap[props.emotion?.dominant || '快乐'] || '😊'
})

// 获取情绪颜色
const emotionColor = computed(() => {
  if (!props.emotion) return 'rgba(233, 69, 96, 0.6)'

  const intensity = props.emotion.intensity
  if (intensity < 0.3) return 'rgba(76, 175, 80, 0.6)'
  if (intensity < 0.6) return 'rgba(255, 152, 0, 0.6)'
  return 'rgba(233, 69, 96, 0.6)'
})

// 尺寸配置
const sizeConfig = computed(() => {
  const configs = {
    sm: { width: '32px', height: '32px', fontSize: '14px' },
    md: { width: '40px', height: '40px', fontSize: '16px' },
    lg: { width: '56px', height: '56px', fontSize: '22px' },
    xl: { width: '80px', height: '80px', fontSize: '32px' }
  }
  return configs[props.size]
})
</script>

<template>
  <div class="miya-avatar" :class="[size, { typing: isTyping, 'show-glow': showGlow }]">
    <div class="avatar-emoji">{{ emotionEmoji }}</div>
    <div v-if="showGlow" class="avatar-glow" :style="{ background: emotionColor }"></div>
  </div>
</template>

<style scoped>
.miya-avatar {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #e94560, #8b5cf6);
  color: white;
  font-weight: 600;
  flex-shrink: 0;
  overflow: hidden;
  transition: transform 0.3s ease;
}

.miya-avatar:hover {
  transform: scale(1.05);
}

.miya-avatar.sm {
  width: 32px;
  height: 32px;
  font-size: 14px;
}

.miya-avatar.md {
  width: 40px;
  height: 40px;
  font-size: 16px;
}

.miya-avatar.lg {
  width: 56px;
  height: 56px;
  font-size: 22px;
}

.miya-avatar.xl {
  width: 80px;
  height: 80px;
  font-size: 32px;
}

.avatar-emoji {
  position: relative;
  z-index: 2;
  animation: float 3s ease-in-out infinite;
}

.avatar-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
  border-radius: 50%;
  filter: blur(8px);
  opacity: 0.6;
  animation: pulse 2s ease-in-out infinite;
  z-index: 1;
}

.miya-avatar.typing .avatar-emoji {
  animation: typing-bounce 1.4s infinite;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-3px);
  }
}

@keyframes pulse {
  0%, 100% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.6;
  }
  50% {
    transform: translate(-50%, -50%) scale(1.2);
    opacity: 0.3;
  }
}

@keyframes typing-bounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-5px);
  }
}

/* 亮色主题 */
:deep(.light-mode .miya-avatar) {
  background: linear-gradient(135deg, #e94560, #ff6b8a);
}
</style>
