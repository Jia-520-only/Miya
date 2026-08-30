export interface Live2DCallback {
  onStateChange?: (state: string) => void
  onEmotionChange?: (emotion: string) => void
}
