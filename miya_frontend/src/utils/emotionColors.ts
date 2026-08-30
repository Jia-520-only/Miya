// ─── 弥娅情感颜色表 —— 单一数据源 ─────────────────────
// 供 MessageItem.vue / SoulCard.vue / ConfigView.vue 共享

export const EMOTION_DEFAULTS: Record<string, string> = {
  joy: '#ffd700',
  sadness: '#7dd3fc',
  anger: '#ef4444',
  fear: '#b44dff',
  love: '#ff6b9d',
  surprise: '#fbbf24',
  neutral: '#94a3b8',
  warm: '#ff8c69',
  calm: '#67e8f9',
  sweet: '#f472b6',
  nostalgic: '#d8b4fe',
  shy: '#fbcfe8',
  anticipation: '#facc15',
  attachment: '#c084fc',
  moved: '#c4b5fd',
  tender: '#a5b4fc',
  curious: '#67e8f9',
}

const EMOTION_ALIASES: Record<string, string> = {
  喜悦: 'joy',
  爱: 'love',
  心动: 'love',
  温暖: 'warm',
  幸福: 'warm',
  安心: 'calm',
  满足: 'calm',
  挂念: 'attachment',
  思念: 'attachment',
  害羞: 'shy',
  期待: 'anticipation',
  依恋: 'attachment',
  忧伤: 'sadness',
  甜蜜: 'sweet',
  温柔: 'tender',
  感动: 'moved',
  好奇: 'curious',
  怀旧: 'nostalgic',
  心疼: 'warm',
  烦躁: 'anger',
  无奈: 'neutral',
  愧疚: 'tender',
  释然: 'calm',
  sadness: 'sadness',
  anger: 'anger',
  fear: 'fear',
  surprise: 'surprise',
  disgust: 'neutral',
  joy: 'joy',
  love: 'love',
  neutral: 'neutral',
}

// 解析情绪名 → 标准英文名
export function resolveEmotionName(name: string): string {
  return EMOTION_ALIASES[name] || name
}

// 获取情绪对应的 CSS 变量名
export function getEmotionCSSVar(name: string): string {
  const canonical = resolveEmotionName(name)
  return `--miya-comp-emotion-${canonical}`
}

// 从 CSS 变量解析颜色（运行时），带降级
export function emotionColor(name: string, fallback?: string): string {
  const cssVar = getEmotionCSSVar(name)
  const canonical = resolveEmotionName(name)
  const fb = fallback || EMOTION_DEFAULTS[canonical] || '#00ADB5'
  const root = getComputedStyle(document.documentElement)
  return root.getPropertyValue(cssVar).trim() || fb
}

// 构建全部情绪 → 颜色映射（供 computed 使用）
export function buildEmotionColorMap(): Record<string, string> {
  const root = getComputedStyle(document.documentElement)
  const map: Record<string, string> = {}
  for (const [name, canonical] of Object.entries(EMOTION_ALIASES)) {
    const cssVar = `--miya-comp-emotion-${canonical}`
    const fb = EMOTION_DEFAULTS[canonical] || '#00ADB5'
    map[name] = root.getPropertyValue(cssVar).trim() || fb
  }
  // 也补上英文名
  for (const canonical of Object.keys(EMOTION_DEFAULTS)) {
    const cssVar = `--miya-comp-emotion-${canonical}`
    const fb = EMOTION_DEFAULTS[canonical] || '#00ADB5'
    map[canonical] = root.getPropertyValue(cssVar).trim() || fb
  }
  return map
}

// 情绪渐变（从基色派生，保持可定制）
export function emotionGradient(name: string): string {
  const color = emotionColor(name)
  const canonical = resolveEmotionName(name)
  // 特殊情绪 → 双色渐变
  switch (canonical) {
    case 'joy':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 70%, #ff8c00))`
    case 'love':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 70%, #ff4488))`
    case 'warm':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #ff6b9d))`
    case 'calm':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #00ADB5))`
    case 'attachment':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #e879f9))`
    case 'sadness':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #38bdf8))`
    case 'anger':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #f87171))`
    case 'fear':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #7c3aed))`
    case 'surprise':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #fbbf24))`
    case 'anticipation':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #f59e0b))`
    case 'sweet':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #ec4899))`
    case 'shy':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #f9a8d4))`
    case 'tender':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #818cf8))`
    case 'moved':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 70%, #fcd34d))`
    case 'curious':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #06b6d4))`
    case 'nostalgic':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 70%, #00ADB5))`
    case 'neutral':
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 80%, #cbd5e1))`
    default:
      return `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 75%, transparent))`
  }
}
