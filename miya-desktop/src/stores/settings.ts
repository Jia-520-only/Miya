import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type Theme = 'dark' | 'light'
export type Language = 'zh-CN' | 'en-US'

export interface Settings {
  theme: Theme
  language: Language
  fontSize: number
  messageAnimation: boolean
  soundEnabled: boolean
  autoScroll: boolean
  showTimestamp: boolean
  codeHighlight: boolean
  markdownEnabled: boolean
  showEmotion: boolean
  showPersonality: boolean
  streamingResponse: boolean
  responseTimeout: number
  ttsEnabled: boolean        // TTS总开关
  ttsAutoPlay: boolean     // 自动播放
}

export const useSettingsStore = defineStore('settings', () => {
  // 默认设置
  const defaultSettings: Settings = {
    theme: 'dark',
    language: 'zh-CN',
    fontSize: 14,
    messageAnimation: true,
    soundEnabled: false,
    autoScroll: true,
    showTimestamp: true,
    codeHighlight: true,
    markdownEnabled: true,
    showEmotion: false,
    showPersonality: false,
    streamingResponse: true,
    responseTimeout: 30000,
    ttsEnabled: false,
    ttsAutoPlay: false
  }

  // State
  const settings = ref<Settings>({ ...defaultSettings })

  // Computed
  const isDark = ref(settings.value.theme === 'dark')

  // Actions
  function updateSetting<K extends keyof Settings>(key: K, value: Settings[K]) {
    settings.value[key] = value
    saveToStorage()

    // 特殊处理主题
    if (key === 'theme') {
      isDark.value = value === 'dark'
      applyTheme(value)
    }
  }

  function updateAll(newSettings: Partial<Settings>) {
    settings.value = { ...settings.value, ...newSettings }
    saveToStorage()

    // 处理主题
    if (newSettings.theme) {
      isDark.value = newSettings.theme === 'dark'
      applyTheme(newSettings.theme)
    }
  }

  function resetSettings() {
    settings.value = { ...defaultSettings }
    saveToStorage()
    applyTheme(defaultSettings.theme)
  }

  function applyTheme(theme: Theme) {
    if (theme === 'dark') {
      document.body.classList.add('dark-mode')
      document.body.classList.remove('light-mode')
    } else {
      document.body.classList.add('light-mode')
      document.body.classList.remove('dark-mode')
    }
  }

  function loadFromStorage() {
    try {
      const saved = localStorage.getItem('miya-settings')
      if (saved) {
        const parsed = JSON.parse(saved)
        settings.value = { ...defaultSettings, ...parsed }
        isDark.value = settings.value.theme === 'dark'
        applyTheme(settings.value.theme)
      }
    } catch (error) {
      console.error('Failed to load settings:', error)
    }
  }

  function saveToStorage() {
    try {
      localStorage.setItem('miya-settings', JSON.stringify(settings.value))
    } catch (error) {
      console.error('Failed to save settings:', error)
    }
  }

  // 监听设置变化
  watch(settings, () => {
    saveToStorage()
  }, { deep: true })

  // 初始化
  function initialize() {
    loadFromStorage()
  }

  return {
    // State
    settings,
    isDark,

    // Actions
    updateSetting,
    updateAll,
    resetSettings,
    applyTheme,
    loadFromStorage,
    initialize
  }
})
