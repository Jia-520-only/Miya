import { useStorage } from '@vueuse/core'
import { isLegacyBackground } from '@/utils/backgroundAssets'

export interface HomeBriefingItem {
  id: string
  image: string
  title: string
  description: string
}

export const DEFAULT_HOME_BRIEFINGS: HomeBriefingItem[] = []

export function useHomeBriefing() {
  const items = useStorage<HomeBriefingItem[]>('miya-home-briefing-items', DEFAULT_HOME_BRIEFINGS)
  items.value = items.value.filter(item => !isLegacyBackground(item.image))
  const autoPlay = useStorage('miya-home-briefing-autoplay', true)
  const intervalSeconds = useStorage('miya-home-briefing-interval', 4)
  const showCaption = useStorage('miya-home-briefing-show-caption', true)
  const fallbackGreeting = useStorage('miya-home-briefing-fallback-greeting', '佳，有什么需要帮忙的吗？')
  return { items, autoPlay, intervalSeconds, showCaption, fallbackGreeting }
}
