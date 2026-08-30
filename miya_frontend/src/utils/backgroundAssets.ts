export const LEGACY_BACKGROUND_PATHS = new Set([
  '/backgrounds/aims.jpg',
  '/backgrounds/bg.png',
  '/backgrounds/01.png',
  '/backgrounds/feixue.jpg',
  '/backgrounds/02.jpg',
  '/backgrounds/004.png',
  '/backgrounds/005.png',
])

export function isLegacyBackground(path: string): boolean {
  return LEGACY_BACKGROUND_PATHS.has(path) || LEGACY_BACKGROUND_PATHS.has(`/backgrounds/${path}`)
}
