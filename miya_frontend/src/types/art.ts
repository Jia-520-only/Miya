export interface ArtProviderInfo {
  name: string
  display_name: string
  description: string
  enabled: boolean
  available?: boolean
}

export interface ArtImageEntry {
  id: string
  filename: string
  path: string
  size: number
  provider: string
  prompt: string
  width: number
  height: number
  created_at: string
  metadata?: Record<string, any>
}

export interface ArtGenerateResult {
  success: boolean
  task_id: string
  provider: string
  model: string
  prompt: string
  image_count: number
  images: ArtImageEntry[]
  seed?: number
  width: number
  height: number
  generation_time: number
  error?: string
}

export interface ArtStats {
  total_images: number
  total_size_bytes: number
  total_size_mb: number
}
