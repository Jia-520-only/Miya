import { resolveEmotionName } from './emotionColors'

// Emotion changes the glaze within Miya's blue-and-white porcelain palette.
const GLAZE_COLORS: Record<string, string> = {
  joy: '#bdd9ff',
  love: '#b3c5ef',
  warm: '#b3d2ed',
  sweet: '#c2cfee',
  shy: '#d1dff5',
  sadness: '#80a7d9',
  anger: '#6e98ed',
  fear: '#8d9fcf',
  nostalgic: '#a3b5de',
  calm: '#a0c9ed',
  curious: '#92bdf4',
}

export function porcelainEmotionColor(name: string): string {
  return GLAZE_COLORS[resolveEmotionName(name)] ?? '#94b8ef'
}
