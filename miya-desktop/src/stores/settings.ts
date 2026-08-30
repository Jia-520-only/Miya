import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type Theme = 'dark' | 'light'
export type PresetTheme = 'default' | 'sakura' | 'sky' | 'purple' | 'mint' | 'sunset' | 'ocean' | 'forest'
export type Language = 'zh-CN' | 'en-US'

// 预设主题配置
export const PRESET_THEMES: Record<PresetTheme, {
  name: string
  primary: string
  secondary: string
  background: string
  backgroundSecondary: string
  text: string
  textSecondary: string
  accent: string
  isDark: boolean
}> = {
  default: {
    name: '默认',
    primary: '#2dd4bf',
    secondary: '#0ea5e9',
    background: 'rgba(4, 47, 46, 0.95)',
    backgroundSecondary: 'rgba(6, 78, 59, 0.6)',
    text: '#f0fdfa',
    textSecondary: '#94a3b8',
    accent: '#2dd4bf',
    isDark: true
  },
  sakura: {
    name: '樱花粉',
    primary: '#f472b6',
    secondary: '#ec4899',
    background: 'rgba(255, 240, 245, 0.95)',
    backgroundSecondary: 'rgba(255, 228, 240, 0.8)',
    text: '#831843',
    textSecondary: '#9d174d',
    accent: '#f472b6',
    isDark: false
  },
  sky: {
    name: '天空蓝',
    primary: '#38bdf8',
    secondary: '#0ea5e9',
    background: 'rgba(224, 242, 254, 0.95)',
    backgroundSecondary: 'rgba(186, 230, 253, 0.8)',
    text: '#0c4a6e',
    textSecondary: '#075985',
    accent: '#38bdf8',
    isDark: false
  },
  purple: {
    name: '暗夜紫',
    primary: '#a855f7',
    secondary: '#8b5cf6',
    background: 'rgba(88, 28, 135, 0.95)',
    backgroundSecondary: 'rgba(76, 29, 149, 0.8)',
    text: '#f5d0fe',
    textSecondary: '#c4b5fd',
    accent: '#a855f7',
    isDark: true
  },
  mint: {
    name: '薄荷绿',
    primary: '#34d399',
    secondary: '#10b981',
    background: 'rgba(236, 253, 245, 0.95)',
    backgroundSecondary: 'rgba(209, 250, 229, 0.8)',
    text: '#064e3b',
    textSecondary: '#047857',
    accent: '#34d399',
    isDark: false
  },
  sunset: {
    name: '日落橙',
    primary: '#fb923c',
    secondary: '#f97316',
    background: 'rgba(255, 237, 213, 0.95)',
    backgroundSecondary: 'rgba(254, 215, 170, 0.8)',
    text: '#7c2d12',
    textSecondary: '#9a3412',
    accent: '#fb923c',
    isDark: false
  },
  ocean: {
    name: '深海蓝',
    primary: '#0ea5e9',
    secondary: '#0284c7',
    background: 'rgba(30, 58, 138, 0.95)',
    backgroundSecondary: 'rgba(29, 78, 131, 0.8)',
    text: '#dbeafe',
    textSecondary: '#93c5fd',
    accent: '#0ea5e9',
    isDark: true
  },
  forest: {
    name: '森林绿',
    primary: '#22c55e',
    secondary: '#16a34a',
    background: 'rgba(220, 252, 231, 0.95)',
    backgroundSecondary: 'rgba(187, 247, 208, 0.8)',
    text: '#14532d',
    textSecondary: '#166534',
    accent: '#22c55e',
    isDark: false
  }
}

export interface CustomThemeColors {
  primary: string
  secondary: string
  background: string
  backgroundSecondary: string
  text: string
  textSecondary: string
  accent: string
}

export interface Settings {
  theme: Theme
  presetTheme: PresetTheme
  customTheme: CustomThemeColors | null
  useCustomTheme: boolean
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
  ttsEnabled: boolean
  ttsAutoPlay: boolean
}

export const useSettingsStore = defineStore('settings', () => {
  // 默认设置
  const defaultSettings: Settings = {
    theme: 'dark',
    presetTheme: 'default',
    customTheme: null,
    useCustomTheme: false,
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

  function applyTheme(theme?: Theme) {
    const currentTheme = theme || settings.value.theme

    // 移除所有主题类
    document.body.classList.remove('dark-mode', 'light-mode')

    // 确定是否为深色模式
    let isDarkMode = currentTheme === 'dark'

    // 如果使用预设主题
    if (settings.value.useCustomTheme && settings.value.customTheme) {
      isDarkMode = !settings.value.customTheme.background.includes('255,')
    } else if (settings.value.presetTheme && settings.value.presetTheme !== 'default') {
      isDarkMode = PRESET_THEMES[settings.value.presetTheme]?.isDark ?? (currentTheme === 'dark')
    }

    // 应用基础主题类
    if (isDarkMode) {
      document.body.classList.add('dark-mode')
    } else {
      document.body.classList.add('light-mode')
    }

    // 应用自定义颜色到CSS变量
    applyCustomColors()
  }

  function applyCustomColors() {
    let colors: CustomThemeColors | null = null

    if (settings.value.useCustomTheme && settings.value.customTheme) {
      colors = settings.value.customTheme
    } else if (settings.value.presetTheme && settings.value.presetTheme !== 'default') {
      const preset = PRESET_THEMES[settings.value.presetTheme]
      if (preset) {
        colors = {
          primary: preset.primary,
          secondary: preset.secondary,
          background: preset.background,
          backgroundSecondary: preset.backgroundSecondary,
          text: preset.text,
          textSecondary: preset.textSecondary,
          accent: preset.accent
        }
      }
    }

    if (colors) {
      document.documentElement.style.setProperty('--theme-primary', colors.primary)
      document.documentElement.style.setProperty('--theme-secondary', colors.secondary)
      document.documentElement.style.setProperty('--theme-background', colors.background)
      document.documentElement.style.setProperty('--theme-background-secondary', colors.backgroundSecondary)
      document.documentElement.style.setProperty('--theme-text', colors.text)
      document.documentElement.style.setProperty('--theme-text-secondary', colors.textSecondary)
      document.documentElement.style.setProperty('--theme-accent', colors.accent)
    } else {
      // 重置为默认颜色
      document.documentElement.style.removeProperty('--theme-primary')
      document.documentElement.style.removeProperty('--theme-secondary')
      document.documentElement.style.removeProperty('--theme-background')
      document.documentElement.style.removeProperty('--theme-background-secondary')
      document.documentElement.style.removeProperty('--theme-text')
      document.documentElement.style.removeProperty('--theme-text-secondary')
      document.documentElement.style.removeProperty('--theme-accent')
    }
  }

  function setPresetTheme(preset: PresetTheme) {
    settings.value.presetTheme = preset
    settings.value.useCustomTheme = false
    applyTheme()
    saveToStorage()
  }

  function setCustomTheme(colors: CustomThemeColors) {
    settings.value.customTheme = colors
    settings.value.useCustomTheme = true
    applyTheme()
    saveToStorage()
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

    // Theme
    presetThemes: PRESET_THEMES,

    // Actions
    updateSetting,
    updateAll,
    resetSettings,
    applyTheme,
    applyCustomColors,
    setPresetTheme,
    setCustomTheme,
    loadFromStorage,
    initialize
  }
})
