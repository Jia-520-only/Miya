<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useSettingsStore } from './stores/settings'
import { useRoute } from 'vue-router'
import TitleBar from '@components/TitleBar.vue'
import Live2DFull from '@components/Live2DFull.vue'
import { LIVE2D_MODELS } from './config/live2dModels'

const route = useRoute()
const settingsStore = useSettingsStore()

// 判断是否是桌宠窗口路由
const isDesktopPetRoute = computed(() => route.path === '/live2d')

// Live2D 状态
const selectedModelId = ref('ht')
const currentEmotion = ref('平静')
const live2DComponentRef = ref<InstanceType<typeof Live2DFull>>()

// 可用模型列表
const availableModels = ref(Object.values(LIVE2D_MODELS))

// 动作列表
const motions = [
  { name: '待机', index: 0 },
  { name: '动作1', index: 1 },
  { name: '动作2', index: 2 },
  { name: '动作3', index: 3 }
]

// 表情列表
const expressions = [
  { name: '开心', index: 0 },
  { name: '害羞', index: 1 },
  { name: '生气', index: 2 },
  { name: '悲伤', index: 3 },
  { name: '平静', index: 4 },
  { name: '兴奋', index: 5 },
  { name: '调皮', index: 6 },
  { name: '嘘声', index: 7 }
]

// 当前模型路径
const currentModelPath = computed(() => {
  const model = availableModels.value.find(m => m.id === selectedModelId.value)
  return model?.path || '/live2d/ht/ht.model3.json'
})

// 切换模型
function changeModel(modelId: string) {
  selectedModelId.value = modelId
  console.log('[App] 切换模型:', modelId)
}

// 设置表情
function setExpression(index: number) {
  if (live2DComponentRef.value) {
    live2DComponentRef.value.setExpression(index)
    currentEmotion.value = expressions[index].name
    console.log('[App] 设置表情:', expressions[index].name)
  }
}

// 播放动作
function playMotion(index: number) {
  if (live2DComponentRef.value) {
    live2DComponentRef.value.playMotion(index)
    console.log('[App] 播放动作:', motions[index].name)
  }
}

// 下拉选择动作
function onMotionChange(event: Event) {
  const select = event.target as HTMLSelectElement
  const index = parseInt(select.value)
  if (!isNaN(index)) {
    playMotion(index)
    select.value = '' // 重置选择
  }
}

// 下拉选择表情
function onExpressionChange(event: Event) {
  const select = event.target as HTMLSelectElement
  const expr = expressions.find(e => e.name === select.value)
  if (expr) {
    setExpression(expr.index)
  }
}

onMounted(() => {
  // 初始化设置
  settingsStore.initialize()

  // 应用主题
  settingsStore.applyTheme(settingsStore.settings.theme)

  console.log('弥娅桌面应用已启动')
})
</script>

<template>
  <div class="app-container" :class="{ 'dark-mode': settingsStore.isDark, 'light-mode': !settingsStore.isDark }">
    <!-- 科技感背景层 -->
    <div class="tech-background">
      <div class="grid-lines"></div>
      <div class="glow-orb orb-1"></div>
      <div class="glow-orb orb-2"></div>
      <div class="glow-orb orb-3"></div>
      <div class="glow-orb orb-4"></div>
    </div>

    <!-- 标题栏 - 桌宠窗口路由下隐藏 -->
    <TitleBar v-if="!isDesktopPetRoute" />

    <!-- 主内容区域 -->
    <div class="main-content" :class="{ 'no-right-panel': isDesktopPetRoute }">
      <router-view />
    </div>

    <!-- 右侧 Live2D 面板 - 桌宠窗口路由下隐藏 -->
    <div v-if="!isDesktopPetRoute" class="right-live2d-panel">
      <Live2DFull
        ref="live2DComponentRef"
        :modelPath="currentModelPath"
        :emotion="currentEmotion"
        :width="360"
        :height="560"
      />

      <!-- 简化控制 - 下拉选择 -->
      <div class="live2d-controls">
        <select v-model="selectedModelId" @change="changeModel(selectedModelId)" class="control-select">
          <option v-for="model in availableModels" :key="model.id" :value="model.id">
            {{ model.name }}
          </option>
        </select>

        <select :value="currentEmotion" @change="onExpressionChange" class="control-select">
          <option v-for="expr in expressions" :key="expr.index" :value="expr.name">
            {{ expr.name }}
          </option>
        </select>

        <select @change="onMotionChange" class="control-select">
          <option value="" disabled selected>选择动作</option>
          <option v-for="motion in motions" :key="motion.index" :value="motion.index">
            {{ motion.name }}
          </option>
        </select>
      </div>
    </div>
  </div>
</template>

<style>
/* 全局 CSS 变量 */
:root {
  --primary-bg: linear-gradient(135deg, #042f2e 0%, #0d9488 50%, #0ea5e9 100%);
  --secondary-bg: #0d9488;
  --accent: #2dd4bf;
  --text-primary: #f0fdfa;
  --text-secondary: #5eead4;
  --border: rgba(45, 212, 191, 0.3);
  --success: #22c55e;
  --warning: #eab308;
  --error: #ef4444;
}

/* 亮色主题 */
.light-mode {
  --primary-bg: linear-gradient(135deg, #f0fdfa 0%, #e0f2fe 100%);
  --secondary-bg: #ffffff;
  --accent: #2dd4bf;
  --text-primary: #042f2e;
  --text-secondary: #0f766e;
  --border: rgba(45, 212, 191, 0.3);
}

.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #0a0f0e 0%, #0d1a19 50%, #0f2020 100%);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  overflow: hidden;
  position: relative;
  transition: background 0.5s ease;
}

/* 亮色主题背景 */
.light-mode .app-container {
  background: linear-gradient(135deg, #f0fdfa 0%, #e0f2fe 50%, #e0f7fa 100%);
}

/* 亮色主题背景效果 */
.light-mode .grid-lines {
  background-image:
    linear-gradient(rgba(13, 148, 136, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(13, 148, 136, 0.08) 1px, transparent 1px);
}

.light-mode .grid-lines::after {
  background-image:
    radial-gradient(circle at 50% 50%, rgba(13, 148, 136, 0.05) 1px, transparent 1px);
}

.light-mode .orb-1 {
  background: radial-gradient(circle, rgba(13, 148, 136, 0.3) 0%, transparent 70%);
  opacity: 0.3;
}

.light-mode .orb-2 {
  background: radial-gradient(circle, rgba(14, 165, 233, 0.25) 0%, transparent 70%);
  opacity: 0.25;
}

.light-mode .orb-3 {
  background: radial-gradient(circle, rgba(139, 92, 246, 0.2) 0%, transparent 70%);
  opacity: 0.2;
}

.light-mode .orb-4 {
  background: radial-gradient(circle, rgba(234, 179, 8, 0.15) 0%, transparent 70%);
  opacity: 0.15;
}

/* 科技感背景 */
.tech-background {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}

.grid-lines {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image:
    linear-gradient(rgba(45, 212, 191, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(45, 212, 191, 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
  animation: grid-move 20s linear infinite;
}

.grid-lines::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image:
    radial-gradient(circle at 50% 50%, rgba(45, 212, 191, 0.03) 1px, transparent 1px);
  background-size: 80px 80px;
}

@keyframes grid-move {
  0% {
    transform: translate(0, 0);
  }
  100% {
    transform: translate(40px, 40px);
  }
}

.glow-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.4;
  animation: float 12s ease-in-out infinite;
}

.orb-1 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(45, 212, 191, 0.5) 0%, transparent 70%);
  top: -150px;
  right: -150px;
  animation-delay: 0s;
}

.orb-2 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(14, 165, 233, 0.4) 0%, transparent 70%);
  bottom: -120px;
  left: -120px;
  animation-delay: -4s;
}

.orb-3 {
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, rgba(167, 139, 250, 0.35) 0%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation-delay: -8s;
}

.orb-4 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(234, 179, 8, 0.25) 0%, transparent 70%);
  top: 30%;
  left: 20%;
  animation-delay: -2s;
}

@keyframes float {
  0%, 100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(30px, -30px);
  }
}

.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
  z-index: 1;
  padding-right: 400px;
}

/* 桌宠窗口路由下不需要右侧 padding */
.main-content.no-right-panel {
  padding-right: 0;
}

/* 右侧 Live2D 面板 - 更大更高 */
.right-live2d-panel {
  position: fixed;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  width: 380px;
  height: 680px;
  z-index: 50;
  background: rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px;
}

/* Live2D 控制区域 - 极简下拉 */
.live2d-controls {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px;
  margin-top: 2px;
}

/* 下拉选择器 */
.control-select {
  width: 100%;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.8);
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  outline: none;
}

.control-select:hover {
  background: rgba(255, 255, 255, 0.1);
}

.control-select option {
  background: rgba(6, 78, 59, 0.98);
  color: #e0f2fe;
}

/* 全局重置 */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

a {
  text-decoration: none;
  color: inherit;
}

button {
  font-family: inherit;
  cursor: pointer;
  border: none;
  background: transparent;
}

input,
textarea {
  font-family: inherit;
  outline: none;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: rgba(45, 212, 191, 0.1);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, #2dd4bf, #0ea5e9);
  border-radius: 3px;
  transition: background 0.3s ease;
}

::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, #5eead4, #38bdf8);
}

.light-mode ::-webkit-scrollbar-track {
  background: rgba(45, 212, 191, 0.1);
}

.light-mode ::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, #0d9488, #0ea5e9);
}

.light-mode ::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, #0f766e, #0284c7);
}

/* 选中样式 */
::selection {
  background: rgba(45, 212, 191, 0.3);
  color: #fff;
}
</style>
