<template>
  <div class="settings-panel">
    <div class="settings-header">
      <h2>设置</h2>
      <button class="close-btn" @click="$emit('close')">
        <i class="pi pi-times"></i>
      </button>
    </div>

    <div class="settings-content">
      <!-- Live2D 模型设置 -->
      <section class="settings-section">
        <h3>Live2D 模型</h3>
        <div class="setting-item">
          <label>当前模型</label>
          <div class="model-info">
            <span>{{ currentModel }}</span>
            <button class="btn-primary" @click="openModelSelector">
              选择模型
            </button>
          </div>
        </div>

        <div class="setting-item">
          <label>模型大小</label>
          <div class="size-selector">
            <button
              v-for="size in sizes"
              :key="size.value"
              :class="['size-btn', { active: modelSize === size.value }]"
              @click="modelSize = size.value"
            >
              {{ size.label }}
            </button>
          </div>
        </div>

        <div class="setting-item">
          <label>显示选项</label>
          <div class="toggle-group">
            <label class="toggle-label">
              <input type="checkbox" v-model="showEmotions" />
              <span>显示表情动画</span>
            </label>
            <label class="toggle-label">
              <input type="checkbox" v-model="autoIdle" />
              <span>自动待机动画</span>
            </label>
            <label class="toggle-label">
              <input type="checkbox" v-model="enableInteraction" />
              <span>启用鼠标交互</span>
            </label>
          </div>
        </div>
      </section>

      <!-- 主题设置 -->
      <section class="settings-section">
        <h3>外观主题</h3>
        <div class="setting-item">
          <label>主题模式</label>
          <div class="theme-selector">
            <button
              v-for="theme in themes"
              :key="theme.value"
              :class="['theme-btn', { active: currentTheme === theme.value }]"
              @click="changeTheme(theme.value)"
            >
              <i :class="theme.icon"></i>
              <span>{{ theme.label }}</span>
            </button>
          </div>
        </div>

        <!-- 预设主题 -->
        <div class="setting-item">
          <label>预设主题</label>
          <div class="preset-theme-grid">
            <button
              v-for="(preset, key) in presetThemes"
              :key="key"
              :class="['preset-theme-btn', { active: currentPresetTheme === key }]"
              @click="selectPresetTheme(key)"
              :title="preset.name"
            >
              <div class="preset-preview" :style="{ background: preset.background }">
                <div class="preset-accent" :style="{ background: preset.accent }"></div>
              </div>
              <span class="preset-name">{{ preset.name }}</span>
            </button>
          </div>
        </div>

        <!-- 自定义主题 -->
        <div class="setting-item">
          <label>自定义主题颜色</label>
          <div class="custom-theme-section">
            <div class="color-input-row">
              <label>主色调</label>
              <input type="color" v-model="customColors.primary" @change="applyCustomTheme" />
            </div>
            <div class="color-input-row">
              <label>次色调</label>
              <input type="color" v-model="customColors.secondary" @change="applyCustomTheme" />
            </div>
            <div class="color-input-row">
              <label>强调色</label>
              <input type="color" v-model="customColors.accent" @change="applyCustomTheme" />
            </div>
            <div class="color-input-row">
              <label>背景色</label>
              <input type="color" v-model="customColors.background" @change="applyCustomTheme" />
            </div>
            <div class="color-input-row">
              <label>文字色</label>
              <input type="color" v-model="customColors.text" @change="applyCustomTheme" />
            </div>
            <button class="btn-secondary" @click="resetToDefaultTheme">
              恢复默认
            </button>
          </div>
        </div>
      </section>

      <!-- TTS 语音设置 -->
      <section class="settings-section">
        <h3>语音合成 (TTS)</h3>
        <div class="setting-item">
          <label>语音功能</label>
          <div class="toggle-group">
            <label class="toggle-label">
              <input type="checkbox" v-model="ttsEnabled" />
              <span>启用语音合成</span>
            </label>
            <label class="toggle-label" :class="{ disabled: !ttsEnabled }">
              <input type="checkbox" v-model="ttsAutoPlay" :disabled="!ttsEnabled" />
              <span>自动播放新消息语音</span>
            </label>
          </div>
        </div>
        <div class="setting-item">
          <label>说明</label>
          <p class="setting-hint">
            启用后，AI回复将自动转为语音播放。您也可以点击消息旁的扬声器图标手动播放。
          </p>
        </div>
      </section>

      <!-- 快捷键设置 -->
      <section class="settings-section">
        <h3>快捷键</h3>
        <div class="setting-item">
          <label>打开快捷指令</label>
          <kbd>Ctrl + K</kbd>
        </div>
        <div class="setting-item">
          <label>切换工具箱</label>
          <kbd>Ctrl + T</kbd>
        </div>
        <div class="setting-item">
          <label>打开设置</label>
          <kbd>Ctrl + ,</kbd>
        </div>
      </section>

      <!-- 关于 -->
      <section class="settings-section">
        <h3>关于</h3>
        <div class="about-info">
          <p><strong>弥娅桌面版</strong></p>
          <p>版本: {{ version }}</p>
          <p>基于 Vue 3 + Electron 构建</p>
          <p>© 2026 MIYA Project</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useSettingsStore, PRESET_THEMES, type PresetTheme, type CustomThemeColors } from '../stores/settings'

interface Props {
  modelPath?: string
}

const props = withDefaults(defineProps<Props>(), {
  modelPath: '/live2d/ht/ht.model3.json'
})

const settingsStore = useSettingsStore()

const emit = defineEmits<{
  close: []
  'update-model': [modelPath: string]
}>()

// 状态
const currentModel = ref('Hiyori')
const modelSize = ref('medium')
const showEmotions = ref(true)
const autoIdle = ref(true)
const enableInteraction = ref(true)
const currentTheme = ref<'dark' | 'light'>('dark')
const accentColor = ref('#3b82f6')
const version = ref('1.0.0')
const ttsEnabled = ref(false)
const ttsAutoPlay = ref(false)

// 主题相关状态
const currentPresetTheme = ref<PresetTheme>('default')
const useCustomTheme = ref(false)
const customColors = ref<CustomThemeColors>({
  primary: '#2dd4bf',
  secondary: '#0ea5e9',
  background: 'rgba(4, 47, 46, 0.95)',
  backgroundSecondary: 'rgba(6, 78, 59, 0.6)',
  text: '#f0fdfa',
  textSecondary: '#94a3b8',
  accent: '#2dd4bf'
})

// 预设主题列表
const presetThemes = PRESET_THEMES

// 配置选项
const sizes = [
  { label: '小', value: 'small' },
  { label: '中', value: 'medium' },
  { label: '大', value: 'large' }
]

const themes = [
  { label: '深色', value: 'dark', icon: 'pi pi-moon' },
  { label: '浅色', value: 'light', icon: 'pi pi-sun' },
  { label: '跟随系统', value: 'system', icon: 'pi pi-desktop' }
]

const accentColors = [
  { label: '蓝色', value: '#3b82f6' },
  { label: '紫色', value: '#8b5cf6' },
  { label: '绿色', value: '#10b981' },
  { label: '橙色', value: '#f59e0b' },
  { label: '红色', value: '#ef4444' }
]

// 方法
function openModelSelector() {
  console.log('打开模型选择器')
}

function changeTheme(theme: string) {
  console.log('切换主题模式:', theme)
  currentTheme.value = theme as 'dark' | 'light'
  settingsStore.updateSetting('theme', currentTheme.value)
  // 强制更新主题
  settingsStore.applyTheme(currentTheme.value)
}

function changeAccentColor(color: string) {
  accentColor.value = color
  document.documentElement.style.setProperty('--accent-color', color)
}

// 选择预设主题
function selectPresetTheme(presetKey: string) {
  console.log('选择预设主题:', presetKey)
  currentPresetTheme.value = presetKey as PresetTheme
  useCustomTheme.value = false
  settingsStore.setPresetTheme(presetKey as PresetTheme)
  // 强制更新主题
  settingsStore.applyTheme(currentTheme.value)
}

// 应用自定义主题
function applyCustomTheme() {
  console.log('应用自定义主题:', customColors.value)
  useCustomTheme.value = true
  settingsStore.setCustomTheme(customColors.value)
  // 强制更新主题
  settingsStore.applyTheme(currentTheme.value)
}

// 重置为默认主题
function resetToDefaultTheme() {
  console.log('重置为默认主题')
  currentPresetTheme.value = 'default'
  useCustomTheme.value = false
  customColors.value = {
    primary: '#2dd4bf',
    secondary: '#0ea5e9',
    background: 'rgba(4, 47, 46, 0.95)',
    backgroundSecondary: 'rgba(6, 78, 59, 0.6)',
    text: '#f0fdfa',
    textSecondary: '#94a3b8',
    accent: '#2dd4bf'
  }
  settingsStore.setPresetTheme('default')
  // 强制更新主题
  settingsStore.applyTheme(currentTheme.value)
}

onMounted(() => {
  loadSettings()
})

function loadSettings() {
  try {
    const saved = localStorage.getItem('miya-settings')
    if (saved) {
      const settings = JSON.parse(saved)
      modelSize.value = settings.modelSize || 'medium'
      showEmotions.value = settings.showEmotions ?? true
      autoIdle.value = settings.autoIdle ?? true
      enableInteraction.value = settings.enableInteraction ?? true
      currentTheme.value = settings.theme || 'dark'
      accentColor.value = settings.accentColor || '#3b82f6'
      // 主题设置
      currentPresetTheme.value = settings.presetTheme || 'default'
      useCustomTheme.value = settings.useCustomTheme ?? false
      if (settings.customTheme) {
        customColors.value = settings.customTheme
      }
      // TTS 设置
      ttsEnabled.value = settings.ttsEnabled ?? false
      ttsAutoPlay.value = settings.ttsAutoPlay ?? false
    }
  } catch (error) {
    console.error('加载设置失败:', error)
  }
}

function saveSettings() {
  try {
    const settings = {
      modelSize: modelSize.value,
      showEmotions: showEmotions.value,
      autoIdle: autoIdle.value,
      enableInteraction: enableInteraction.value,
      theme: currentTheme.value,
      accentColor: accentColor.value,
      // 主题设置
      presetTheme: currentPresetTheme.value,
      useCustomTheme: useCustomTheme.value,
      customTheme: useCustomTheme.value ? customColors.value : null,
      // TTS 设置
      ttsEnabled: ttsEnabled.value,
      ttsAutoPlay: ttsAutoPlay.value
    }
    localStorage.setItem('miya-settings', JSON.stringify(settings))
    // 同时更新 settings store
    settingsStore.updateSetting('ttsEnabled', ttsEnabled.value)
    settingsStore.updateSetting('ttsAutoPlay', ttsAutoPlay.value)
  } catch (error) {
    console.error('保存设置失败:', error)
  }
}

// 监听设置变化并自动保存
watch([modelSize, showEmotions, autoIdle, enableInteraction, currentTheme, accentColor, ttsEnabled, ttsAutoPlay, currentPresetTheme, useCustomTheme, customColors], saveSettings, { deep: true })
</script>

<style scoped>
.settings-panel {
  width: 600px;
  max-width: 90vw;
  max-height: 80vh;
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid var(--border-secondary);
  background: var(--bg-secondary);
}

.settings-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-base);
}

.close-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-xl);
}

.settings-section {
  margin-bottom: var(--spacing-xl);
}

.settings-section:last-child {
  margin-bottom: 0;
}

.settings-section h3 {
  margin: 0 0 var(--spacing-md) 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.setting-item {
  margin-bottom: var(--spacing-lg);
}

.setting-item label {
  display: block;
  margin-bottom: var(--spacing-sm);
  font-size: 14px;
  color: var(--text-secondary);
}

.model-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-tertiary);
}

.size-selector,
.theme-selector {
  display: flex;
  gap: var(--spacing-sm);
}

.size-btn,
.theme-btn {
  flex: 1;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--border-tertiary);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  transition: all var(--transition-base);
}

.size-btn:hover,
.theme-btn:hover {
  background: var(--bg-hover);
  border-color: var(--border-secondary);
}

.size-btn.active,
.theme-btn.active {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: white;
}

.theme-btn i {
  font-size: 16px;
}

.toggle-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-tertiary);
  cursor: pointer;
  transition: all var(--transition-base);
}

.toggle-label:hover {
  background: var(--bg-hover);
  border-color: var(--border-secondary);
}

.toggle-label.disabled {
  opacity: 0.5;
  pointer-events: none;
}

.toggle-label.disabled input[type="checkbox"] {
  cursor: not-allowed;
}

.toggle-label input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--accent-color);
}

.setting-hint {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
  padding: var(--spacing-sm);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-tertiary);
}

.color-selector {
  display: flex;
  gap: var(--spacing-md);
}

.color-btn {
  width: 40px;
  height: 40px;
  border: 3px solid transparent;
  border-radius: 50%;
  cursor: pointer;
  transition: all var(--transition-base);
}

.color-btn:hover {
  transform: scale(1.1);
}

.color-btn.active {
  border-color: var(--text-primary);
  box-shadow: 0 0 0 3px var(--bg-primary), 0 0 0 5px var(--accent-color);
}

kbd {
  display: inline-block;
  padding: 4px 10px;
  font-family: monospace;
  font-size: 13px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-tertiary);
  border-radius: 4px;
  color: var(--text-secondary);
}

.about-info {
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-tertiary);
}

.about-info p {
  margin: var(--spacing-sm) 0;
  font-size: 14px;
  color: var(--text-secondary);
}

.btn-primary {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--accent-color);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition-base);
}

.btn-primary:hover {
  opacity: 0.9;
}

/* 滚动条样式 */
.settings-content::-webkit-scrollbar {
  width: 8px;
}

.settings-content::-webkit-scrollbar-track {
  background: var(--bg-secondary);
}

.settings-content::-webkit-scrollbar-thumb {
  background: var(--border-tertiary);
  border-radius: 4px;
}

.settings-content::-webkit-scrollbar-thumb:hover {
  background: var(--border-secondary);
}

/* 预设主题网格 */
.preset-theme-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
}

.preset-theme-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm);
  border: 2px solid var(--border-tertiary);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  cursor: pointer;
  transition: all var(--transition-base);
}

.preset-theme-btn:hover {
  border-color: var(--border-secondary);
  transform: translateY(-2px);
}

.preset-theme-btn.active {
  border-color: var(--accent-color);
  box-shadow: 0 0 0 2px var(--accent-color);
}

.preset-preview {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  padding: 4px;
  position: relative;
  overflow: hidden;
}

.preset-accent {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.8);
}

.preset-name {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.preset-theme-btn.active .preset-name {
  color: var(--accent-color);
  font-weight: 500;
}

/* 自定义主题 */
.custom-theme-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-tertiary);
}

.color-input-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.color-input-row label {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.color-input-row input[type="color"] {
  width: 40px;
  height: 30px;
  padding: 0;
  border: 1px solid var(--border-tertiary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  background: transparent;
}

.color-input-row input[type="color"]::-webkit-color-swatch-wrapper {
  padding: 2px;
}

.color-input-row input[type="color"]::-webkit-color-swatch {
  border: none;
  border-radius: 2px;
}

.btn-secondary {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border: 1px solid var(--border-tertiary);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 13px;
  transition: all var(--transition-base);
}

.btn-secondary:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
</style>
