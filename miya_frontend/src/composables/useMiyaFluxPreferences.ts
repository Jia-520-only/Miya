import { useStorage } from '@vueuse/core'
import { computed } from 'vue'

export type MiyaFluxMode = 'resonance' | 'surge' | 'quiet'
export type MiyaFluxComposition = 'complete' | 'closeup'

export function useMiyaFluxPreferences() {
  const mode = useStorage<MiyaFluxMode>('miya-flux-mode', 'resonance')
  const storedComposition = useStorage<string>('miya-flux-composition', 'complete')
  const composition = computed<MiyaFluxComposition>({
    get: () => storedComposition.value === 'closeup' ? 'closeup' : 'complete',
    set: value => storedComposition.value = value,
  })
  const paused = useStorage('miya-flux-paused', window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const portrait = useStorage('miya-flux-portrait', {
    image: '',
    zoom: 1,
    x: 50,
    y: 42,
    flow: 32,
  }, undefined, { mergeDefaults: true })
  const defaultAvatar = new URL(`${import.meta.env.BASE_URL}haloflux/miya-avatar.png`, document.baseURI).href
  const avatarSource = computed(() => portrait.value.image || defaultAvatar)

  function savePortrait(image: string) {
    const next = { image, zoom: 1, x: 50, y: 42, flow: portrait.value.flow }
    // Verify persistence before changing the visible image, so a full disk/quota
    // leaves the previous portrait intact and can be explained by the editor.
    localStorage.setItem('miya-flux-portrait', JSON.stringify(next))
    portrait.value = next
  }

  return { mode, composition, paused, portrait, avatarSource, savePortrait }
}
