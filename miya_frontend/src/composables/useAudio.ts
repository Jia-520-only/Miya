import { useStorage } from '@vueuse/core'
import { reactive, watch } from 'vue'
import audioManifest from '@/generated/audio-manifest.json'
import { discoverApiPort } from '@/utils/api-port'

// ─── 持久化设置（纯前端 localStorage） ─────────────────
export const audioSettings = useStorage('naga-audio-settings', {
  bgmVolume: 0.3,
  effectVolume: 0.5,
  wakeVoice: '默认',
  clickEffect: '翻书.mp3',
  bgmEnabled: true,
  effectEnabled: true,
})

// 清单由构建脚本生成，避免 public 音频被 Vite 再复制一份进 assets。
export const wakeVoiceMap: Record<string, string[]> = audioManifest.startVoices
export const wakeVoiceOptions = Object.keys(wakeVoiceMap)
export const effectFileOptions = audioManifest.effects

export type MusicTrackKind = 'original' | 'cover' | 'material'
export interface MusicTrack {
  id: string
  title: string
  source: 'singing_input' | 'singing'
  kind: MusicTrackKind
  playable: boolean
  format: string
  sizeBytes: number
  url: string
}

export interface BgmPlaylistTrack {
  file: string
  title: string
}

export type BgmPlaybackMode = 'sequence' | 'random' | 'single'

// 所有页面共享同一个 BGM 状态，避免配置页和首页各自维护一份“播放中”标记。
export const bgmState = reactive({
  playing: false,
  file: '',
  title: '',
  error: '',
})

export async function fetchMusicLibrary(): Promise<MusicTrack[]> {
  // Electron 启动时后端可能还在监听端口，短暂重试避免曲库永久显示为空。
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const port = await discoverApiPort()
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 5000)
      let response: Response
      try {
        response = await fetch(`http://localhost:${port}/api/music/library`, { signal: controller.signal })
      }
      finally {
        clearTimeout(timeout)
      }
      if (!response.ok)
        throw new Error(`music library request failed: ${response.status}`)
      const tracks = await response.json()
      if (!Array.isArray(tracks))
        return []
      return tracks
        .filter((track: unknown): track is MusicTrack => {
        if (!track || typeof track !== 'object') return false
        const item = track as Partial<MusicTrack>
        return typeof item.id === 'string' && typeof item.title === 'string'
          && typeof item.url === 'string' && (item.source === 'singing' || item.source === 'singing_input')
      })
      .map(track => ({
        ...track,
        kind: track.kind || 'original',
        playable: track.playable ?? track.kind !== 'material',
        format: track.format || (track.url.split('?')[0] || '').split('.').pop() || 'audio',
        sizeBytes: track.sizeBytes || 0,
        url: track.url.startsWith('http') ? track.url : `http://localhost:${port}${track.url}`,
      }))
    }
    catch {
      if (attempt < 2)
        await new Promise(resolve => setTimeout(resolve, 700))
    }
  }
  return []
}

interface BgmDelegate { playFile: (file: string) => void, pause: () => void }
let bgmDelegate: BgmDelegate | null = null
let bgmAudio: HTMLAudioElement | null = null
let bgmCurrentFile = ''
let bgmRequest = 0
let bgmPlaylist: BgmPlaylistTrack[] = []
let bgmPlaybackMode: BgmPlaybackMode = 'sequence'

export function setBgmPlaylist(tracks: BgmPlaylistTrack[]) {
  bgmPlaylist = tracks.filter(track => track.file).map(track => ({ ...track }))
}

export function setBgmPlaybackMode(mode: BgmPlaybackMode) {
  bgmPlaybackMode = mode
}

export function registerBgmDelegate(delegate: BgmDelegate) {
  // 先停止兜底播放器，再切换委托；否则 stopBgm 会把 pause 发给新委托，
  // 旧的 HTMLAudioElement 会继续播放并与音乐盒叠音。
  stopBgm()
  bgmDelegate = delegate
}

export function unregisterBgmDelegate() {
  bgmDelegate?.pause()
  bgmDelegate = null
  bgmState.playing = false
  bgmState.file = ''
  bgmState.title = ''
  bgmState.error = ''
}

function fadeTo(audio: HTMLAudioElement, targetVolume: number, duration = 600): Promise<void> {
  return new Promise((resolve) => {
    const start = audio.volume
    const started = performance.now()
    const step = () => {
      const progress = Math.min((performance.now() - started) / duration, 1)
      audio.volume = start + (targetVolume - start) * progress
      if (progress < 1) requestAnimationFrame(step)
      else resolve()
    }
    requestAnimationFrame(step)
  })
}

export async function playBgm(file: string, title = '') {
  if (!audioSettings.value.bgmEnabled) {
    bgmState.playing = false
    bgmState.file = ''
    bgmState.title = ''
    bgmState.error = ''
    return
  }
  if (bgmDelegate) {
    bgmDelegate.playFile(file)
    bgmState.playing = true
    bgmState.file = file
    bgmState.title = title
    bgmState.error = ''
    return
  }
  if (bgmAudio && bgmCurrentFile === file && bgmState.playing)
    return
  stopBgm()
  const request = ++bgmRequest
  const audio = new Audio(file)
  // 翻唱混音通常是几十 MB 的 WAV，先只取元数据，播放时由浏览器按需流式读取。
  audio.preload = 'metadata'
  audio.loop = false
  audio.muted = false
  audio.volume = 0
  bgmAudio = audio
  bgmCurrentFile = file
  bgmState.file = file
  bgmState.title = title
  bgmState.error = ''
  audio.onerror = () => {
    if (request !== bgmRequest) return
    bgmAudio = null
    bgmCurrentFile = ''
    bgmState.playing = false
    bgmState.file = ''
    bgmState.title = ''
    bgmState.error = '音频加载失败'
  }
  audio.onended = () => {
    if (request !== bgmRequest || bgmAudio !== audio)
      return
    if (bgmPlaybackMode === 'single') {
      audio.currentTime = 0
      void audio.play().catch(() => {
        if (request !== bgmRequest || bgmAudio !== audio) return
        bgmState.playing = false
        bgmState.error = '音频播放失败，请检查音乐文件或浏览器权限'
      })
      return
    }
    const index = bgmPlaylist.findIndex(track => track.file === file)
    let next: BgmPlaylistTrack | undefined
    if (bgmPlaylist.length > 0 && bgmPlaybackMode === 'random') {
      const candidates = bgmPlaylist.filter(track => track.file !== file)
      next = candidates.length > 0
        ? candidates[Math.floor(Math.random() * candidates.length)]
        : bgmPlaylist[0]
    }
    else if (bgmPlaylist.length > 0) {
      next = bgmPlaylist[(index + 1 + bgmPlaylist.length) % bgmPlaylist.length]
    }
    if (next) {
      bgmState.playing = false
      void playBgm(next.file, next.title)
      return
    }
    bgmAudio = null
    bgmCurrentFile = ''
    bgmState.playing = false
  }
  try {
    await audio.play()
    if (request !== bgmRequest || bgmAudio !== audio) return
    bgmState.playing = true
    await fadeTo(audio, audioSettings.value.bgmVolume)
  }
  catch {
    if (request !== bgmRequest) return
    bgmAudio = null
    bgmCurrentFile = ''
    bgmState.playing = false
    bgmState.file = ''
    bgmState.title = ''
    bgmState.error = '音频播放失败，请检查音乐文件或浏览器权限'
    throw new Error('音频播放失败，请检查音乐文件或浏览器权限')
  }
}

export function stopBgm() {
  bgmRequest++
  if (bgmDelegate) {
    bgmDelegate.pause()
    bgmState.playing = false
    bgmState.file = ''
    bgmState.title = ''
    bgmState.error = ''
    return
  }
  const audio = bgmAudio
  if (!audio) {
    bgmState.playing = false
    bgmState.file = ''
    bgmState.title = ''
    bgmState.error = ''
    return
  }
  bgmAudio = null
  bgmCurrentFile = ''
  bgmState.playing = false
  bgmState.file = ''
  bgmState.title = ''
  bgmState.error = ''
  fadeTo(audio, 0).then(() => {
    audio.pause()
    audio.src = ''
  })
}

// ─── 唤醒语音 ──────────────────────────────────────
export function playWakeVoice() {
  let pack = audioSettings.value.wakeVoice
  let files = wakeVoiceMap[pack]
  // 兼容旧版 localStorage 残留的英文 key（如 "Default"），回退到第一个可用语音包
  if (!files || files.length === 0) {
    const fallback = wakeVoiceOptions[0]
    if (fallback) {
      console.warn(`[Audio] 唤醒语音包 "${pack}" 无可用文件，回退到 "${fallback}"`)
      pack = fallback
      files = wakeVoiceMap[pack]
      audioSettings.value.wakeVoice = fallback
    }
    if (!files || files.length === 0) {
      console.warn(`[Audio] 无任何可用唤醒语音包`)
      return
    }
  }

  const file = files[Math.floor(Math.random() * files.length)]!
  const url = `/voices/start/${encodeURIComponent(pack)}/${encodeURIComponent(file)}`
  const audio = new Audio(url)
  audio.volume = audioSettings.value.effectVolume
  audio.play().catch((e) => {
    console.error(`[Audio] 唤醒语音播放失败: ${url}`, e)
  })
}

// ─── 点击音效 ──────────────────────────────────────
export function playClickEffect() {
  if (!audioSettings.value.effectEnabled)
    return
  const file = audioSettings.value.clickEffect
  const audio = new Audio(`/voices/effect/${encodeURIComponent(file)}`)
  audio.volume = audioSettings.value.effectVolume
  audio.play().catch((e) => {
    console.warn(`[Audio] 点击音效播放失败:`, e.message)
  })
}

watch(() => audioSettings.value.bgmVolume, (volume) => {
  if (bgmAudio) bgmAudio.volume = volume
})

watch(() => audioSettings.value.bgmEnabled, (enabled) => {
  if (!enabled) stopBgm()
})
