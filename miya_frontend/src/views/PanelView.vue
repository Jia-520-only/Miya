<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import API from '@/api/core'
import EarthAPI from '@/api/earth'
import { bgmState, fetchMusicLibrary, playBgm, setBgmPlaybackMode, setBgmPlaylist, stopBgm, type BgmPlaybackMode, type MusicTrack } from '@/composables/useAudio'
import { useHomeBriefing } from '@/composables/useHomeBriefing'
import { pX, pY } from '@/utils/parallax'

const router = useRouter()

const backendOnline = ref(false)
const miyaPersona = ref('默认')
const soulActive = ref(87)
const currentTime = ref('')
const latestMiyaNote = ref('')
const currentBgm = ref('')
const miyaPlatforms = ref(3)
const memoryTotal = ref(0)
const emotionName = ref('平静')
const reservedNotice = ref('')
let reservedNoticeTimer: ReturnType<typeof setTimeout> | null = null
let timer: ReturnType<typeof setInterval> | null = null
let statusTimer: ReturnType<typeof setInterval> | null = null

// ═══ 隐藏/显示面板 ═══
const panelsHidden = useStorage('miya-panels-hidden', false)
function togglePanels() {
  panelsHidden.value = !panelsHidden.value
}

// ═══ 透视 / 陀螺仪开关 ═══
const perspectiveEnabled = useStorage('miya-perspective-enabled', true)
const gyroEnabled = useStorage('miya-gyro-enabled', true)
function togglePerspective() {
  perspectiveEnabled.value = !perspectiveEnabled.value
}
function toggleGyro() {
  gyroEnabled.value = !gyroEnabled.value
}

const musicLibrary = ref<MusicTrack[]>([])
const musicLoading = ref(false)
const musicExpanded = ref(false)
const musicError = ref('')
const musicMode = useStorage<BgmPlaybackMode>('miya-music-playback-mode', 'sequence')
const musicModes: Array<{ id: BgmPlaybackMode, label: string, icon: string, title: string }> = [
  { id: 'sequence', label: '顺序', icon: '≋', title: '顺序播放' },
  { id: 'random', label: '随机', icon: '⤨', title: '随机播放' },
  { id: 'single', label: '单曲', icon: '↻1', title: '单曲循环' },
]
type MusicFilter = 'original' | 'cover' | 'all'
const musicFilter = ref<MusicFilter>('original')
const musicFilters: Array<{ id: MusicFilter, label: string }> = [
  { id: 'original', label: '原曲' },
  { id: 'cover', label: '弥娅翻唱' },
  { id: 'all', label: '全部' },
]
const playableMusicLibrary = computed(() => musicLibrary.value.filter(track => track.playable && track.kind !== 'material'))
const filteredMusicLibrary = computed(() => musicFilter.value === 'all'
  ? playableMusicLibrary.value
  : playableMusicLibrary.value.filter(track => track.kind === musicFilter.value))
const bgmAvailable = computed(() => filteredMusicLibrary.value.length > 0)
const currentMusicIndex = computed(() => filteredMusicLibrary.value.findIndex(track => track.url === bgmState.file))
const musicSectionTitle = computed(() => musicFilters.find(filter => filter.id === musicFilter.value)?.label || '音乐')
const musicModeTitle = computed(() => musicModes.find(mode => mode.id === musicMode.value)?.title || '顺序播放')

function musicCount(kind: MusicFilter) {
  return kind === 'all' ? playableMusicLibrary.value.length : playableMusicLibrary.value.filter(track => track.kind === kind).length
}

async function selectMusic(track: MusicTrack) {
  if (!track.playable) {
    musicError.value = '素材仅供查看，不参与播放'
    return
  }
  musicError.value = ''
  try {
    await playBgm(track.url, track.title)
    currentBgm.value = track.title
    musicExpanded.value = false
  }
  catch {
    musicError.value = '音乐加载失败，请确认后端在线且文件可读'
  }
}

async function toggleBgm() {
  if (!bgmAvailable.value) return
  if (bgmState.playing) {
    stopBgm()
    return
  }
  const firstTrack = filteredMusicLibrary.value[0]
  if (firstTrack) await selectMusic(firstTrack)
}

async function playRelative(direction: -1 | 1) {
  const tracks = filteredMusicLibrary.value
  if (!tracks.length) return
  const index = currentMusicIndex.value >= 0 ? currentMusicIndex.value : (direction > 0 ? -1 : 0)
  const next = tracks[(index + direction + tracks.length) % tracks.length]
  if (next) await selectMusic(next)
}

function toggleMusicExpanded(event: Event) {
  event.stopPropagation()
  musicExpanded.value = !musicExpanded.value
}

async function loadMusicLibrary() {
  musicLoading.value = true
  musicError.value = ''
  try {
    musicLibrary.value = await fetchMusicLibrary()
    const firstPlayableTrack = musicLibrary.value.find(track => track.playable)
    if (firstPlayableTrack && !currentBgm.value)
      currentBgm.value = firstPlayableTrack.title
    const activeTrack = musicLibrary.value.find(track => track.url === bgmState.file)
    if (activeTrack) {
      currentBgm.value = activeTrack.title
      if (activeTrack.kind !== 'material')
        musicFilter.value = activeTrack.kind
    }
    if (!playableMusicLibrary.value.length)
      musicError.value = '暂无可播放音乐，请确认后端在线且 data/singing 目录有音频文件'
  }
  finally {
    musicLoading.value = false
  }
}

onMounted(loadMusicLibrary)

watch([musicFilter, playableMusicLibrary], () => {
  setBgmPlaylist(filteredMusicLibrary.value.map(track => ({ file: track.url, title: track.title })))
})

watch(musicMode, (mode) => {
  setBgmPlaybackMode(mode)
}, { immediate: true })

watch(() => bgmState.title, (title) => {
  if (title)
    currentBgm.value = title
})

async function loadSystemStatus() {
  try {
    const [statusRes, personaRes] = await Promise.all([
      API.systemStatus(),
      API.getCurrentPersona(),
    ])
    backendOnline.value = true

    // 人格信息
    miyaPersona.value = personaRes?.persona?.name || personaRes?.persona?.id || '默认'

    // 从 systemStatus 读取实时数据
    if (statusRes?.identity) {
      // 情感状态
      const emotion = statusRes.emotion || {}
      emotionName.value = emotion.emotion_name || '平静'
      soulActive.value = emotion.intensity ?? emotion.emotions?.[0]?.intensity ?? 87

      // 记忆统计
      const mem = statusRes.memory_stats || {}
      memoryTotal.value = mem.total || mem.short_term || 0

      // 平台信息
      const plat = statusRes.platform_info || {}
      miyaPlatforms.value = plat.enabled_count ?? plat.total_count ?? 3
    }

    // 如果有 soul 数据
    if (personaRes?.soul) {
      soulActive.value = personaRes.soul.activity || soulActive.value
    }
  }
  catch {
    backendOnline.value = false
  }
}

async function loadLatestMiyaNote() {
  try {
    const notes = await EarthAPI.listNotes(12)
    latestMiyaNote.value = (notes.find(note => Boolean(note.pinned)) || notes[0])?.content?.trim() || ''
  }
  catch {
    latestMiyaNote.value = ''
  }
}

onMounted(async () => {
  await Promise.all([loadSystemStatus(), loadLatestMiyaNote()])
  updateTime()
  timer = setInterval(updateTime, 10000)
  statusTimer = setInterval(() => {
    loadSystemStatus()
    loadLatestMiyaNote()
  }, 30000)
})

onUnmounted(() => {
  if (timer)
    clearInterval(timer)
  if (statusTimer)
    clearInterval(statusTimer)
  if (reservedNoticeTimer)
    clearTimeout(reservedNoticeTimer)
})

function updateTime() {
  currentTime.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const leftCards = [
  { id: 'chat', label: '对话', desc: '灵魂共鸣', path: '/chat' },
  { id: 'mind', label: '记忆', desc: '认知星河', path: '/mind' },
  { id: 'platforms', label: '平台', desc: '在线状态', path: '/platforms' },
  { id: 'inbox', label: '收件箱', desc: '跨平台消息', path: '/inbox' },
  { id: 'artboard', label: '画板', desc: 'AI 创作', path: '/artboard' },
]

interface QuickModule {
  id: string
  label: string
  desc: string
  icon: string
  path?: string
  reserved?: boolean
}

const quickModules: QuickModule[] = [
  { id: 'community', label: '社区', desc: '共鸣网络', icon: '✧', path: '/community' },
  { id: 'earth', label: '地球', desc: 'ONLINE', icon: '◎', path: '/earth' },
  { id: 'terminal', label: '终端', desc: '引擎接口', icon: '▤', path: '/terminal' },
  { id: 'senses', label: '感知', desc: '待接入', icon: '⊙', reserved: true },
]

// ═══ 首页动态简报 ═══
const { items: briefingItems, autoPlay: briefingAutoPlay, intervalSeconds: briefingInterval, showCaption: briefingShowCaption, fallbackGreeting } = useHomeBriefing()
const bannerIdx = ref(0)
let bannerTimer: ReturnType<typeof setInterval> | null = null

const currentBriefing = computed(() => briefingItems.value[bannerIdx.value] || null)
const currentBannerImg = computed(() => {
  const image = currentBriefing.value?.image || ''
  return image.startsWith('/api/') ? EarthAPI.imageUrl(image) : image
})
const homeGreeting = computed(() => latestMiyaNote.value || fallbackGreeting.value)

function restartBannerTimer() {
  if (bannerTimer)
    clearInterval(bannerTimer)
  bannerTimer = null
  if (!briefingAutoPlay.value || briefingItems.value.length < 2)
    return
  bannerTimer = setInterval(() => {
    bannerIdx.value = (bannerIdx.value + 1) % briefingItems.value.length
  }, Math.max(3, Math.min(15, briefingInterval.value)) * 1000)
}

function stepBriefing(direction: -1 | 1) {
  if (briefingItems.value.length < 2)
    return
  bannerIdx.value = (bannerIdx.value + direction + briefingItems.value.length) % briefingItems.value.length
  restartBannerTimer()
}

watch([briefingItems, briefingAutoPlay, briefingInterval], () => {
  if (bannerIdx.value >= briefingItems.value.length)
    bannerIdx.value = 0
  restartBannerTimer()
}, { deep: true, immediate: true })

onUnmounted(() => {
  if (bannerTimer)
    clearInterval(bannerTimer)
})

// ═══ 陀螺仪效果 ═══
// 面板级：鼠标位置动态调节 3D 旋转
const gyroLeftPanel = computed(() => {
  if (panelsHidden.value)
    return ''
  if (!perspectiveEnabled.value)
    return 'none'
  if (!gyroEnabled.value)
    return 'rotateY(30deg)'
  const ry = 30 + pX.value * 8
  const rx = pY.value * -4
  return `rotateY(${ry.toFixed(1)}deg) rotateX(${rx.toFixed(1)}deg)`
})

const gyroRightPanel = computed(() => {
  if (panelsHidden.value)
    return ''
  if (!perspectiveEnabled.value)
    return 'none'
  if (!gyroEnabled.value)
    return 'rotateY(-30deg)'
  const ry = -30 + pX.value * 8
  const rx = pY.value * -4
  return `rotateY(${ry.toFixed(1)}deg) rotateX(${rx.toFixed(1)}deg)`
})

// CSS 变量注入：传给子卡片做 calc() 叠加
const gyroVarsRight = computed(() => ({
  '--gyro-rx': gyroEnabled.value ? `${(pY.value * -3).toFixed(1)}deg` : '0deg',
  '--gyro-ry': gyroEnabled.value ? `${(pX.value * 5).toFixed(1)}deg` : '0deg',
}))

const gyroVarsLeft = computed(() => ({
  '--gyro-rx': gyroEnabled.value ? `${(pY.value * -2).toFixed(1)}deg` : '0deg',
  '--gyro-ry': gyroEnabled.value ? `${(pX.value * 3).toFixed(1)}deg` : '0deg',
}))

function navigate(path: string) {
  router.push(path)
}

function activateModule(module: QuickModule) {
  if (module.path) {
    navigate(module.path)
    return
  }
  reservedNotice.value = `${module.label} // INTERFACE RESERVED · AWAITING LINK`
  if (reservedNoticeTimer)
    clearTimeout(reservedNoticeTimer)
  reservedNoticeTimer = setTimeout(() => { reservedNotice.value = '' }, 2600)
}

const chatExpanded = ref(false)

function toggleChat() {
  chatExpanded.value = !chatExpanded.value
}
</script>

<template>
  <div class="command-center">
    <!-- ═══ 左面板 ═══ -->
    <div class="cmd-panel cmd-left" :class="{ 'panel-hidden': panelsHidden }" :style="{ transform: gyroLeftPanel, ...gyroVarsLeft }">
      <div class="cmd-top">
        <div class="cmd-eyebrow"><span>SOUL INTERFACE</span><span>LINK {{ backendOnline ? 'STABLE' : 'WAIT' }}</span></div>
        <div class="cmd-level">
          <div class="cmd-level-head">
            <span class="cmd-level-label">灵魂活跃度</span>
            <span class="cmd-level-val">{{ soulActive }}</span>
          </div>
          <div class="cmd-level-bar">
            <div class="cmd-level-fill" :style="{ width: `${Math.min(soulActive, 100)}%` }" />
          </div>
        </div>
        <div class="cmd-name">
          <span class="cmd-name-main">弥娅</span>
          <span class="cmd-name-sub">MIYA · {{ miyaPersona }} · {{ emotionName }}</span>
        </div>
      </div>

      <div class="cmd-center">
        <div class="cmd-toggle-row">
          <div class="cmd-music-wrap" :class="{ expanded: musicExpanded }">
            <div class="cmd-music" :title="bgmState.playing ? '暂停 BGM' : '播放 BGM'" @click="toggleBgm">
              <span class="cmd-music-icon" :class="{ playing: bgmState.playing }">♪</span>
              <div class="cmd-music-scroll"><span class="cmd-music-text">{{ bgmState.playing ? `正在播放 — ${bgmState.title || currentBgm}` : currentBgm ? `已暂停 — ${currentBgm}` : 'BGM 已暂停' }}</span></div>
              <button type="button" class="cmd-music-expand" :aria-expanded="musicExpanded" :aria-label="musicExpanded ? '收起音乐列表' : '展开音乐列表'" aria-controls="cmd-music-actions" @click.stop="toggleMusicExpanded">{{ musicExpanded ? '×' : '⋯' }}</button>
            </div>
            <div v-if="musicExpanded" id="cmd-music-actions" class="cmd-music-actions" @click.stop>
              <span v-if="musicLoading" class="cmd-music-status">正在读取音乐列表…</span>
              <div class="cmd-music-toolbar">
                <div class="cmd-music-filters" role="tablist" aria-label="音乐分类">
                  <button v-for="filter in musicFilters" :key="filter.id" type="button" role="tab" :aria-selected="musicFilter === filter.id" :class="{ active: musicFilter === filter.id }" @click="musicFilter = filter.id">{{ filter.label }} <small>{{ musicCount(filter.id) }}</small></button>
                </div>
                <div class="cmd-music-modes" role="group" aria-label="播放模式">
                  <button v-for="mode in musicModes" :key="mode.id" type="button" :class="{ active: musicMode === mode.id }" :aria-pressed="musicMode === mode.id" :title="mode.title" :aria-label="mode.title" @click="musicMode = mode.id">
                    <span>{{ mode.icon }}</span><small>{{ mode.label }}</small>
                  </button>
                </div>
                <div class="cmd-music-nav">
                  <button type="button" title="上一首" aria-label="上一首" :disabled="!bgmAvailable" @click="playRelative(-1)">‹</button>
                  <button type="button" title="下一首" aria-label="下一首" :disabled="!bgmAvailable" @click="playRelative(1)">›</button>
                </div>
              </div>
              <div class="cmd-music-section-label"><span>{{ musicSectionTitle }}</span><small>{{ filteredMusicLibrary.length }} 首 · {{ musicModeTitle }}</small></div>
              <div class="cmd-music-list" role="listbox" @wheel.stop>
                <button v-for="track in filteredMusicLibrary" :key="track.id" type="button" :disabled="!track.playable" :aria-disabled="!track.playable" :class="{ active: bgmState.file === track.url, 'is-material': !track.playable }" @click="selectMusic(track)">
                  <span class="cmd-music-track-title">{{ track.title }}</span>
                  <small>{{ track.kind === 'cover' ? '弥娅翻唱' : '原曲' }}</small>
                </button>
                <span v-if="!musicLoading && !filteredMusicLibrary.length" class="cmd-music-status">此分类暂无音乐</span>
              </div>
              <span v-if="musicError" class="cmd-music-error">{{ musicError }}</span>
              <button v-if="!musicLoading && !musicLibrary.length" type="button" class="cmd-music-retry" @click="loadMusicLibrary">重新读取</button>
            </div>
          </div>
        </div>

        <div class="cmd-nav">
          <button
            v-for="card in leftCards" :key="card.id"
            class="cmd-nav-card"
            @click="navigate(card.path)"
          >
            <span class="cmd-nav-icon">{{ { chat: '◆', mind: '◇', platforms: '⊟', inbox: '✉', artboard: '⬡' }[card.id] }}</span>
            <span class="cmd-nav-title">{{ card.label }}</span>
            <span class="cmd-nav-desc">{{ card.desc }}</span>
          </button>
        </div>
      </div>

      <div class="cmd-bottom-area">
        <div class="cmd-banner" :class="{ empty: !currentBriefing }">
          <div class="cmd-banner-track">
            <Transition name="banner-slide" mode="out-in">
              <div :key="currentBriefing?.id || 'empty'" class="cmd-banner-slide">
                <img v-if="currentBannerImg" :src="currentBannerImg" class="cmd-banner-img" :alt="currentBriefing?.title || '动态简报'">
                <div v-else class="cmd-banner-placeholder"><span>≋</span><small>MIYA BRIEFING CHANNEL</small></div>
              </div>
            </Transition>
            <div v-if="briefingItems.length > 1" class="cmd-banner-nav">
              <button title="上一条简报" aria-label="上一条简报" @click.stop="stepBriefing(-1)">‹</button>
              <span>{{ String(bannerIdx + 1).padStart(2, '0') }} / {{ String(briefingItems.length).padStart(2, '0') }}</span>
              <button title="下一条简报" aria-label="下一条简报" @click.stop="stepBriefing(1)">›</button>
            </div>
          </div>
          <div v-if="briefingShowCaption" class="cmd-banner-label">
            <Transition name="banner-fade" mode="out-in">
              <div :key="currentBriefing?.id || 'empty-caption'" class="cmd-banner-copy">
                <span class="cmd-banner-text">{{ currentBriefing?.title || '动态简报' }}</span>
                <small>{{ currentBriefing?.description || '等待新的情报接入' }}</small>
              </div>
            </Transition>
          </div>
        </div>
        <div class="cmd-chat" :class="{ expanded: chatExpanded }" @click="toggleChat">
          <div class="cmd-chat-icon">
            💬
          </div>
          <div class="cmd-chat-text">
            <span class="cmd-chat-line cmd-miya-note" :title="homeGreeting">❦「{{ homeGreeting }}」</span>
            <span class="cmd-chat-line">💭 记忆条目: {{ memoryTotal }} | 情感: {{ emotionName }}</span>
            <span class="cmd-chat-line">🎵 {{ bgmState.playing ? `BGM: ${bgmState.title || currentBgm}` : currentBgm ? `BGM 已暂停 · ${currentBgm}` : 'BGM 已暂停' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ 右面板 ═══ -->
    <div class="cmd-panel cmd-right" :class="{ 'panel-hidden': panelsHidden }" :style="{ transform: gyroRightPanel, ...gyroVarsRight }">
      <div class="cmd-resources">
        <div class="cmd-res-item" @click="navigate('/chat')">
          <span class="cmd-res-icon">◆</span>
          <span class="cmd-res-val" :title="`灵魂活跃度: ${soulActive}`">{{ soulActive }}</span>
          <span class="cmd-res-plus">+</span>
        </div>
        <div class="cmd-res-item">
          <span class="cmd-res-icon">⬢</span>
          <span class="cmd-res-val" :title="`接入平台: ${miyaPlatforms}`">{{ miyaPlatforms }}</span>
          <span class="cmd-res-plus">+</span>
        </div>
        <div class="cmd-res-item">
          <span class="cmd-res-icon">⬡</span>
          <span class="cmd-res-val time-font">{{ currentTime }}</span>
          <span class="cmd-res-plus">+</span>
        </div>
      </div>

      <div class="cmd-right-heading">
        <span>COMMAND INTERFACE</span>
        <span class="cmd-right-sequence">SYS / 06</span>
      </div>

      <div class="cmd-right-center">
        <!-- 时间 + 图标 -->
        <div class="cmd-time-row">
          <span class="cmd-time-icon" :class="{ active: backendOnline }" :title="backendOnline ? '后端在线' : '后端离线'">🔋</span>
          <span class="cmd-time-val">{{ currentTime }}</span>
          <div class="cmd-time-icons">
            <button class="cmd-time-icn" title="消息收件箱" @click="navigate('/inbox')">
              <span class="cmd-time-icn-symbol">✉</span><small>MAIL</small>
            </button>
            <button class="cmd-time-icn" title="灵魂调谐与设置" @click="navigate('/config')">
              <span class="cmd-time-icn-symbol">⚙</span><small>SET</small>
            </button>
            <button
              class="cmd-time-icn cmd-mode-icn"
              :class="{ active: perspectiveEnabled }"
              :title="perspectiveEnabled ? '关闭左右透视' : '开启左右透视'"
              :aria-pressed="perspectiveEnabled"
              @click="togglePerspective"
            >
              <span class="cmd-time-icn-symbol">◇</span><small>PERS</small>
            </button>
            <button
              class="cmd-time-icn cmd-mode-icn cmd-gyro-icn"
              :class="{ active: gyroEnabled }"
              :title="gyroEnabled ? '关闭鼠标陀螺跟随' : '开启鼠标陀螺跟随'"
              :aria-pressed="gyroEnabled"
              @click="toggleGyro"
            >
              <span class="cmd-time-icn-symbol">◎</span><small>GYRO</small>
            </button>
            <span class="cmd-time-icn cmd-hide-icn" title="隐藏面板" @click="togglePanels">⊙</span>
          </div>
        </div>

        <!-- 看板娘卡片 -->
        <div class="cmd-boxline cmd-boxline1">
          <div class="cmd-portrait" @click="navigate('/chat')">
            <div class="cmd-portrait-gloss" />
            <div class="cmd-portrait-avatar">
              <span class="cmd-portrait-char">弥</span>
            </div>
          </div>
          <div class="cmd-battle-info" @click="navigate('/chat')">
            <div class="cmd-battle-left">
              <h1>对话</h1>
              <span class="cmd-battle-tip">灵魂共鸣</span>
              <span class="cmd-battle-nd" :style="{ color: backendOnline ? 'rgba(0,255,245,0.6)' : 'rgba(255,100,100,0.5)' }">
                {{ backendOnline ? '弥娅在线' : '弥娅离线' }}
              </span>
            </div>
            <div class="cmd-battle-right">
              <h2 class="cmd-battle-pct">
                ∞
              </h2>
              <span>陪伴</span>
            </div>
          </div>
          <div class="cmd-mascot" @click="navigate('/mind')">
            <span class="cmd-mascot-icon">◆</span>
            <span class="cmd-mascot-label">记忆</span>
            <span class="cmd-mascot-val">{{ memoryTotal }}</span>
          </div>
        </div>

        <!-- 任务卡 -->
        <div class="cmd-boxline cmd-boxline2">
          <div class="cmd-quest">
            <div class="cmd-quest-left">
              <h2>今日状态</h2>
              <span>{{ emotionName }}</span>
            </div>
            <div class="cmd-quest-right">
              <p>{{ backendOnline ? '灵魂系统连接稳定' : '正在等待灵魂系统' }}</p>
              <span class="cmd-quest-check">✓</span>
            </div>
          </div>
          <div class="cmd-quest-spacer" />
        </div>

        <!-- 功能区 -->
        <div class="cmd-boxline cmd-boxline3">
          <button class="cmd-feat-card" @click="navigate('/platforms')">
            <h1>平台</h1>
            <span>{{ miyaPlatforms }} 个接入</span>
          </button>
          <button class="cmd-feat-card" @click="navigate('/inbox')">
            <h1>收件箱</h1>
            <span>跨平台消息</span>
            <div class="cmd-feat-badge">
              联
            </div>
          </button>
          <div class="cmd-feat-spacer" />
        </div>

        <!-- 系统中枢：保留为首页唯一的高级功能聚合入口 -->
        <div class="cmd-boxline cmd-boxline4" @click="navigate('/hub')">
          <span class="cmd-guild-title">弥娅中枢</span>
          <span class="cmd-guild-desc">MIYA HUB · 系统功能聚合</span>
        </div>
      </div>

      <div class="cmd-bottom-nav" aria-label="快捷功能">
        <button
          v-for="module in quickModules"
          :key="module.id"
          class="cmd-bottom-item"
          :class="{ reserved: module.reserved }"
          @click="activateModule(module)"
        >
          <span class="cmd-bottom-icon">{{ module.icon }}</span>
          <h1>{{ module.label }}</h1>
          <span>{{ module.desc }}</span>
        </button>
      </div>

    </div>

    <Transition name="notice-rise">
      <div v-if="reservedNotice" class="cmd-reserved-notice">
        <span class="cmd-reserved-mark">◇</span>
        <div><strong>模块尚未接入</strong><small>{{ reservedNotice }}</small></div>
      </div>
    </Transition>

    <!-- 恢复面板按钮 -->
    <Transition name="show-btn">
      <button v-if="panelsHidden" class="cmd-show-btn" title="显示面板" @click="togglePanels">
        <span>⊙</span>
      </button>
    </Transition>
  </div>
</template>

<style scoped>
/* ═══ 容器 ═══ */
.command-center {
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  width: 100%;
  height: 100%;
  perspective: 600px;
  -webkit-perspective: 600px;
  perspective-origin: center;
  -webkit-perspective-origin: center;
  user-select: none;
  animation: cmd-enter 0.7s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: visible;
  padding: 0.2rem 3% 0;
  position: relative;
}

@keyframes cmd-enter {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}

/* ═══ 面板容器 ═══ */
.cmd-panel {
  height: 92%;
  display: flex;
  flex-direction: column;
  transition: transform 0.5s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.5s ease;
  will-change: transform, opacity;
  overflow: hidden;
  background: transparent;
}

.cmd-left {
  width: 28%;
  min-width: 190px;
  transform: rotateY(30deg);
  padding: 0.5rem 0.5rem 0.2rem;
  transform-origin: center left;
}

.cmd-right {
  width: 32%;
  min-width: 230px;
  transform: rotateY(-30deg);
  padding: 0.5rem 0.5rem 0.2rem;
  transform-origin: center right;
}

/* ═══ 隐藏/显示 ═══ */
.panel-hidden {
  opacity: 0;
  pointer-events: none;
  transform: rotateY(50deg) scale(0.95) !important;
}

.cmd-right.panel-hidden {
  transform: rotateY(-50deg) scale(0.95) !important;
}

/* 恢复显示按钮 */
.cmd-show-btn {
  position: fixed;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 100;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 15%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 25%, transparent);
  cursor: pointer;
  transition: all 0.4s ease;
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 55%, transparent);
  font-size: 1rem;
  font-family: inherit;
  user-select: none;
}

.cmd-show-btn:hover {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 30%, transparent);
  border-color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 50%, transparent);
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 85%, transparent);
  transform: translateY(-50%) scale(1.1);
  box-shadow: 0 0 16px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 15%, transparent);
}

.show-btn-enter-active,
.show-btn-leave-active {
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}
.show-btn-enter-from,
.show-btn-leave-to {
  opacity: 0;
  transform: translateY(-50%) translateX(-20px);
}

/* ═══ 左面板: 顶部 (固定高度) ═══ */
.cmd-top {
  flex-shrink: 0;
  padding-bottom: 0.2rem;
}

.cmd-level {
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: all 0.5s ease;
}

.cmd-level:hover {
  letter-spacing: 0.15em;
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 6%, transparent);
  border-radius: 2px;
}

.cmd-level-head {
  display: flex;
  align-items: baseline;
  gap: 0.3rem;
}

.cmd-level-label {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 45%, transparent);
  font-size: clamp(0.45rem, 1.2vw, 0.6rem);
  font-family: 'Noto Sans SC', sans-serif;
  transition: color 0.4s;
}

.cmd-level:hover .cmd-level-label {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 40%, transparent);
}

.cmd-level-val {
  color: var(--miya-text, #E4ECF0);
  font-size: clamp(1.2rem, 2.5vw, 1.8rem);
  font-weight: 700;
  font-family: 'Noto Serif SC', serif;
  line-height: 1;
  transition: color 0.4s, text-shadow 0.4s;
}

.cmd-level:hover .cmd-level-val {
  text-shadow: 0 0 12px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 25%, transparent);
}

.cmd-level-bar {
  width: 28%;
  height: 3px;
  background: linear-gradient(90deg, color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 40%, transparent) 50%, rgba(57, 62, 70, 0.4) 50%);
  margin-top: 0.15rem;
  transition: width 0.5s ease;
}

.cmd-level:hover .cmd-level-bar {
  width: 40%;
}

.cmd-level-fill {
  height: 100%;
  background: linear-gradient(90deg, color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 55%, transparent), color-mix(in srgb, var(--miya-accent, #00ADB5) 70%, transparent));
  transition: width 0.6s ease;
  box-shadow: 0 0 4px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 30%, transparent);
}

.cmd-name {
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: all 0.4s ease;
}

.cmd-name-main {
  color: var(--miya-text, #E4ECF0);
  font-size: clamp(1rem, 2.2vw, 1.3rem);
  font-weight: 700;
  font-family: 'Noto Serif SC', serif;
  letter-spacing: 0.1em;
  transition: letter-spacing 0.8s, color 0.5s, text-shadow 0.5s;
  line-height: 1.3;
}

.cmd-name:hover .cmd-name-main {
  letter-spacing: 0.3em;
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 90%, transparent);
  text-shadow: 0 0 15px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 30%, transparent);
}

.cmd-name-sub {
  color: color-mix(in srgb, var(--miya-accent, #00ADB5) 50%, transparent);
  font-size: clamp(0.4rem, 0.9vw, 0.55rem);
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: 0.06em;
  transition: letter-spacing 0.5s, color 0.4s;
}

.cmd-name:hover .cmd-name-sub {
  letter-spacing: 0.18em;
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 60%, transparent);
}

/* ═══ 左面板: 中间 (弹性填充) ═══ */
.cmd-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 0.3rem;
  min-height: 0;
  overflow: visible;
}

.cmd-toggle-row {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  flex-shrink: 0;
}

.cmd-toggle-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.4s ease;
  flex-shrink: 0;
  color: color-mix(in srgb, var(--miya-accent, #00ADB5) 30%, transparent);
  font-size: 0.85rem;
  font-family: inherit;
}

.cmd-toggle-btn:hover {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 12%, transparent);
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 65%, transparent);
  transform: skewX(-8deg);
}

.cmd-toggle-icon {
  display: block;
  transition: transform 0.4s ease;
}

.cmd-toggle-btn:hover .cmd-toggle-icon {
  transform: scale(1.2);
}

/* 陀螺仪按钮状态 */
.cmd-gyro-btn {
  color: color-mix(in srgb, var(--miya-accent, #00ADB5) 15%, transparent);
}

.cmd-gyro-btn.active {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 45%, transparent);
}

.cmd-gyro-btn.active:hover {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 70%, transparent);
}

.cmd-music-wrap { position: relative; margin-left: 0.5rem; flex-shrink: 0; min-width: 0; }
.cmd-music { display: flex; align-items: center; gap: 0.3rem; width: clamp(150px, 17vw, 220px); min-width: 0; padding: 0.1rem 0.15rem; cursor: pointer; }
.cmd-music:hover { background: color-mix(in srgb, var(--miya-accent, #00ADB5) 8%, transparent); }
.cmd-music-icon { width: 20px; height: 20px; display: grid; place-items: center; color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 35%, transparent); }
.cmd-music-icon.playing { color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 70%, transparent); animation: music-pulse 1.5s ease-in-out infinite; }
.cmd-music-scroll { overflow: hidden; flex: 1 1 auto; min-width: 0; }
.cmd-music-text { display: block; width: max-content; min-width: 100%; color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 65%, transparent); font-size: clamp(0.5rem, 1vw, 0.6rem); white-space: nowrap; animation: music-scroll 8s linear infinite; }
.cmd-music-expand { border: 0; background: transparent; color: var(--miya-text-muted); cursor: pointer; }
.cmd-music-actions { position: absolute; z-index: 10; bottom: calc(100% + 0.4rem); top: auto; right: 0; display: grid; gap: 0.25rem; width: min(360px, calc(100vw - 2rem)); max-height: min(340px, 48vh); overflow: hidden; padding: 0.35rem; background: var(--miya-surface-2); border: 1px solid var(--miya-accent); box-shadow: 0 8px 24px rgba(0,0,0,0.42); overscroll-behavior: contain; }
.cmd-music-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 0.35rem; min-width: 0; }
.cmd-music-filters { display: flex; min-width: 0; overflow-x: auto; scrollbar-width: thin; }
.cmd-music-filters button,
.cmd-music-nav button { border: 0; background: transparent; color: var(--miya-text-muted); cursor: pointer; white-space: nowrap; }
.cmd-music-filters button { padding: 0.28rem 0.38rem; font-size: 0.62rem; }
.cmd-music-filters button.active { color: var(--miya-chat-ai, #00FFF5); border-bottom: 1px solid currentColor; }
.cmd-music-filters button small { margin-left: 0.12rem; font-size: 0.5rem; opacity: 0.7; }
.cmd-music-modes { display: flex; flex-shrink: 0; gap: 0.08rem; }
.cmd-music-modes button { display: grid; place-items: center; min-width: 31px; height: 25px; padding: 0.1rem 0.16rem; border: 1px solid transparent; background: transparent; color: var(--miya-text-muted); cursor: pointer; font-family: inherit; }
.cmd-music-modes button span { font-size: 0.75rem; line-height: 1; }
.cmd-music-modes button small { font-size: 0.42rem; line-height: 1; }
.cmd-music-modes button.active { color: var(--miya-chat-ai, #00FFF5); border-color: rgba(162, 245, 238, 0.3); background: rgba(120, 207, 209, 0.11); }
.cmd-music-modes button:hover { color: var(--miya-chat-ai, #00FFF5); border-color: rgba(162, 245, 238, 0.2); }
.cmd-music-nav { display: flex; flex-shrink: 0; gap: 0.1rem; }
.cmd-music-nav button { width: 24px; height: 24px; padding: 0; font-size: 1.1rem; line-height: 1; }
.cmd-music-nav button:disabled { cursor: not-allowed; opacity: 0.3; }
.cmd-music-section-label { display: flex; align-items: baseline; justify-content: space-between; gap: 0.5rem; padding: 0.18rem 0.6rem 0.1rem; border-top: 1px solid color-mix(in srgb, var(--miya-accent) 18%, transparent); color: var(--miya-chat-ai, #00FFF5); font-size: 0.62rem; letter-spacing: 0.05em; }
.cmd-music-section-label small { color: var(--miya-text-muted); font-size: 0.52rem; letter-spacing: 0; }
.cmd-music-list { height: clamp(120px, 27vh, 230px); min-height: 72px; overflow-y: scroll; overscroll-behavior: contain; scrollbar-width: thin; scrollbar-gutter: stable; }
.cmd-music-list button { display: flex; align-items: baseline; justify-content: space-between; gap: 0.75rem; width: 100%; padding: 0.45rem 0.6rem; border: 0; background: transparent; color: var(--miya-text-body); text-align: left; cursor: pointer; }
.cmd-music-list button.active { color: var(--miya-chat-ai, #00FFF5); background: color-mix(in srgb, var(--miya-accent) 12%, transparent); }
.cmd-music-list button.is-material { cursor: not-allowed; opacity: 0.48; }
.cmd-music-list button.is-material:hover { background: transparent; }
.cmd-music-track-title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cmd-music-actions button small { flex-shrink: 0; color: var(--miya-text-muted); font-size: 0.62rem; }
.cmd-music-list button:hover { background: color-mix(in srgb, var(--miya-accent) 18%, transparent); }
.cmd-music-error { padding: 0.45rem 0.6rem; color: var(--miya-danger, #f88); font-size: 0.68rem; }
.cmd-music-status { padding: 0.45rem 0.6rem; color: var(--miya-text-muted); font-size: 0.68rem; }
.cmd-music-retry { color: var(--miya-accent, #00ADB5) !important; }
@keyframes music-pulse { 50% { transform: scale(1.15); opacity: 1; } }
@keyframes music-scroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-120%); } }

/* 导航卡 */
.cmd-nav {
  display: flex;
  gap: 0.3rem;
  flex-shrink: 0;
}

.cmd-nav-card {
  flex: 1;
  aspect-ratio: 1.05;
  min-height: 60px;
  max-height: 90px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  padding: 0.35rem;
  background: color-mix(in srgb, var(--miya-bg, #222831) 55%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00ADB5) 10%, transparent);
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  font-family: inherit;
  color: inherit;
  overflow: hidden;
  position: relative;
  transform: rotateX(calc(3deg + var(--gyro-rx, 0deg))) rotateY(calc(-5deg + var(--gyro-ry, 0deg)));
  box-shadow:
    2px 4px 12px rgba(0, 0, 0, 0.3),
    0 1px 0 color-mix(in srgb, var(--miya-accent, #00ADB5) 6%, transparent);
}

.cmd-nav-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 6%, transparent), transparent 60%);
  opacity: 0;
  transition: opacity 0.4s ease;
  pointer-events: none;
}

.cmd-nav-card:hover {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 18%, transparent);
  transform: rotateX(calc(1deg + var(--gyro-rx, 0deg))) rotateY(calc(-8deg + var(--gyro-ry, 0deg))) scale(1.04) translateY(-3px);
  border-color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 30%, transparent);
  box-shadow:
    3px 6px 20px color-mix(in srgb, var(--miya-accent, #00ADB5) 15%, transparent),
    0 2px 0 color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 12%, transparent);
}

.cmd-nav-card:active {
  transform: skewX(-5deg) scale(0.98);
  transition: transform 0.1s ease;
}

.cmd-nav-card:hover::before {
  opacity: 1;
}

.cmd-nav-icon {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 30%, transparent);
  font-size: clamp(0.6rem, 1.2vw, 0.8rem);
  margin-bottom: 0.15rem;
  transition: all 0.4s ease;
}

.cmd-nav-card:hover .cmd-nav-icon {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 65%, transparent);
  transform: scale(1.15);
}

.cmd-nav-title {
  color: var(--miya-text, #E4ECF0);
  font-size: clamp(0.7rem, 1.4vw, 0.9rem);
  font-weight: 700;
  margin-bottom: 0.25rem;
  transition: color 0.3s, text-shadow 0.3s;
}

.cmd-nav-card:hover .cmd-nav-title {
  text-shadow: 0 0 8px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 20%, transparent);
}

.cmd-nav-desc {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 30%, transparent);
  font-size: clamp(0.35rem, 0.7vw, 0.45rem);
  transition: color 0.3s;
}

.cmd-nav-card:hover .cmd-nav-desc {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 55%, transparent);
}

/* ═══ 左面板底部 (固定高度) ═══ */
.cmd-bottom-area {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding-top: 0.3rem;
}

/* Banner 图片轮播 */
.cmd-banner {
  display: flex;
  flex-direction: column;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00ADB5) 4%, transparent);
  flex-shrink: 0;
}

.cmd-banner:hover {
  border-color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 12%, transparent);
}

.cmd-banner:hover .cmd-banner-img {
  filter: brightness(1.15);
}

.cmd-banner-track {
  width: 100%;
  aspect-ratio: 2.8 / 1;
  overflow: hidden;
  background: color-mix(in srgb, var(--miya-bg, #222831) 40%, transparent);
  position: relative;
}

.cmd-banner-slide {
  width: 100%;
  height: 100%;
}

.cmd-banner-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: filter 0.5s ease;
}

.cmd-banner-placeholder {
  width: 100%; height: 100%; display: grid; place-content: center; justify-items: center; gap: 0.35rem;
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 58%, transparent);
  background: radial-gradient(circle at 50% 45%, color-mix(in srgb, var(--miya-accent, #00ADB5) 18%, transparent), transparent 38%), repeating-linear-gradient(135deg, transparent 0 14px, color-mix(in srgb, var(--miya-accent, #00ADB5) 5%, transparent) 14px 15px);
}
.cmd-banner-placeholder span { font-size: 2rem; line-height: 1; }
.cmd-banner-placeholder small { font-size: 0.45rem; letter-spacing: 0.2em; }
.cmd-banner-nav { position: absolute; right: 0.35rem; bottom: 0.3rem; z-index: 3; display: flex; align-items: center; gap: 0.3rem; opacity: 0; transition: opacity 0.2s; }
.cmd-banner:hover .cmd-banner-nav { opacity: 1; }
.cmd-banner-nav button { width: 20px; height: 20px; padding: 0; border: 1px solid color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 35%, transparent); background: rgba(3,8,12,0.7); color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 72%, transparent); cursor: pointer; line-height: 1; }
.cmd-banner-nav span { padding: 2px 4px; background: rgba(3,8,12,0.64); color: rgba(255,255,255,0.58); font-size: 0.42rem; letter-spacing: 0.08em; }

.cmd-banner-label {
  padding: 0.25rem 0.5rem;
  background: color-mix(in srgb, var(--miya-bg, #222831) 35%, transparent);
  min-height: 1.4em;
  display: flex;
  align-items: center;
}

.cmd-banner-copy { min-width: 0; display: flex; align-items: baseline; gap: 0.45rem; }
.cmd-banner-copy small { overflow: hidden; color: color-mix(in srgb, var(--miya-text, #eee) 35%, transparent); font-size: 0.46rem; text-overflow: ellipsis; white-space: nowrap; }

.cmd-banner-text {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 50%, transparent);
  font-size: clamp(0.45rem, 0.9vw, 0.55rem);
  font-weight: 600;
  letter-spacing: 0.04em;
}

.cmd-miya-note { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 轮播滑动动画 */
.banner-slide-enter-active {
  transition: all 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}
.banner-slide-leave-active {
  transition: all 0.5s cubic-bezier(0.22, 1, 0.36, 1);
  position: absolute;
}
.banner-slide-enter-from {
  opacity: 0;
  transform: translateX(30px);
}
.banner-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

.banner-fade-enter-active,
.banner-fade-leave-active {
  transition: all 0.3s ease;
}
.banner-fade-enter-from,
.banner-fade-leave-to {
  opacity: 0;
}

/* 聊天区 */
.cmd-chat {
  display: flex;
  align-items: flex-start;
  background: color-mix(in srgb, var(--miya-bg, #222831) 25%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00ADB5) 3%, transparent);
  cursor: pointer;
  position: relative;
  flex-shrink: 0;
  transition: background 0.4s, border-color 0.4s;
}

.cmd-chat:hover {
  background: color-mix(in srgb, var(--miya-bg, #222831) 40%, transparent);
  border-color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 8%, transparent);
}

.cmd-chat-icon {
  width: 28px;
  min-height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 35%, transparent);
  font-size: 0.75rem;
  flex-shrink: 0;
  transition: all 0.4s ease;
}

.cmd-chat-icon:hover {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 12%, transparent);
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 65%, transparent);
}

.cmd-chat-text {
  flex: 1;
  max-height: 1.4em;
  overflow: hidden;
  padding: 0.15rem 0.5rem 0 0;
  transition: all 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}

.cmd-chat-line {
  display: block;
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 60%, transparent);
  font-size: clamp(0.4rem, 0.85vw, 0.5rem);
  line-height: 1.4em;
}

.cmd-chat.expanded .cmd-chat-text {
  max-height: none;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.5);
  position: relative;
  bottom: 140px;
  border: 1px solid color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 8%, transparent);
}

/* ═══ 右面板: 资源栏 (固定高度) ═══ */
.cmd-resources {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  gap: 0.25rem;
  margin-bottom: 0.25rem;
}

.cmd-res-item {
  display: flex;
  align-items: center;
  height: clamp(24px, 3.5vh, 30px);
  flex: 1;
  background: color-mix(in srgb, var(--miya-bg, #222831) 55%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00ADB5) 8%, transparent);
  padding: 0 0.25rem;
  cursor: pointer;
  transition: all 0.35s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
  position: relative;
  transform: rotateX(calc(1deg + var(--gyro-rx, 0deg))) rotateY(calc(-3deg + var(--gyro-ry, 0deg)));
  box-shadow: 1px 2px 6px rgba(0, 0, 0, 0.25);
}

.cmd-res-item:hover {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 14%, transparent);
  border-color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 25%, transparent);
  transform: rotateX(calc(0deg + var(--gyro-rx, 0deg))) rotateY(calc(-5deg + var(--gyro-ry, 0deg))) scale(1.03);
  box-shadow: 1px 3px 12px color-mix(in srgb, var(--miya-accent, #00ADB5) 12%, transparent);
}

.cmd-res-item:active {
  transform: rotateX(1deg) rotateY(-3deg) scale(0.98);
  transition: transform 0.1s ease;
}

.cmd-res-icon {
  width: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 40%, transparent);
  font-size: 0.75rem;
  flex-shrink: 0;
  transition: all 0.4s ease;
}

.cmd-res-item:hover .cmd-res-icon {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 65%, transparent);
  transform: scale(1.15);
}

.cmd-res-val {
  flex: 1;
  color: var(--miya-text, #E4ECF0);
  font-size: clamp(0.65rem, 1.2vw, 0.8rem);
  font-family: 'JetBrains Mono', monospace;
  padding: 0 0.3rem;
  min-width: 0;
  transition: color 0.4s, text-shadow 0.4s;
}

.cmd-res-item:hover .cmd-res-val {
  text-shadow: 0 0 6px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 20%, transparent);
}

.time-font {
  font-size: clamp(0.5rem, 1vw, 0.65rem) !important;
}

.cmd-res-plus {
  width: 22px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 18%, transparent);
  color: var(--miya-text, #E4ECF0);
  font-size: 1.2rem;
  font-weight: 700;
  flex-shrink: 0;
  transition: all 0.4s ease;
}

.cmd-res-item:hover .cmd-res-plus {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 35%, transparent);
}

/* ═══ 右面板: 中间内容 (弹性) ═══ */
.cmd-right-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-height: 0;
  overflow: hidden;
}

/* 时间行 */
.cmd-time-row {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 0.05rem 0.4rem;
  gap: 0.3rem;
}

.cmd-time-icon {
  font-size: 0.9rem;
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 20%, transparent);
  cursor: pointer;
  transition: all 0.4s ease;
  flex-shrink: 0;
}

.cmd-time-icon.active {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 45%, transparent);
}

.cmd-time-icon:hover {
  transform: skewX(-10deg) scale(1.1);
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 55%, transparent);
}

.cmd-time-val {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 75%, transparent);
  font-size: clamp(0.8rem, 1.5vw, 1rem);
  font-family: 'JetBrains Mono', monospace;
  margin-right: auto;
  cursor: pointer;
  transition: all 0.5s ease;
}

.cmd-time-val:hover {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 85%, transparent);
  font-size: clamp(1rem, 2vw, 1.4rem);
  text-shadow: 0 0 10px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 25%, transparent);
}

.cmd-time-icons {
  display: flex;
  gap: 0.3rem;
}

.cmd-time-icn {
  width: 28px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  color: color-mix(in srgb, var(--miya-accent, #00ADB5) 25%, transparent);
  cursor: pointer;
  transition: all 0.4s ease;
}

.cmd-time-icn:hover {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 65%, transparent);
  transform: skewX(-8deg) scale(1.1);
}

.cmd-hide-icn:hover {
  color: rgba(255, 150, 150, 0.65);
  transform: skewX(8deg) scale(1.1);
}

/* ── boxline 通用 ── */
.cmd-boxline {
  display: flex;
  align-items: center;
  min-height: 0;
}

/* boxline1: 看板娘卡 (flex: 3.5) */
.cmd-boxline1 {
  flex: 3.5;
  justify-content: center;
  gap: 0.25rem;
  overflow: hidden;
}

.cmd-portrait {
  width: 18%;
  min-width: 70px;
  max-width: 100px;
  height: 100%;
  position: relative;
  cursor: pointer;
  overflow: hidden;
  background: color-mix(in srgb, var(--miya-bg, #222831) 30%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00ADB5) 6%, transparent);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.4s;
}

.cmd-portrait-avatar {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, color-mix(in srgb, var(--miya-accent, #00ADB5) 12%, transparent), color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 4%, transparent));
  transition: transform 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

.cmd-portrait:hover .cmd-portrait-avatar {
  transform: scale(1.08) rotateY(15deg);
}

.cmd-portrait-char {
  font-family: 'Noto Serif SC', serif;
  font-size: clamp(1.5rem, 3vw, 2rem);
  font-weight: 700;
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 65%, transparent);
  text-shadow: 0 0 12px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 25%, transparent);
  transition: all 0.5s ease;
}

.cmd-portrait:hover .cmd-portrait-char {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 90%, transparent);
  text-shadow: 0 0 20px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 40%, transparent);
}

.cmd-portrait-gloss {
  position: absolute;
  top: -15%;
  left: -10%;
  width: 4px;
  height: 130%;
  background: rgba(255, 255, 255, 0.18);
  transform: skewX(-20deg);
  box-shadow: 0 0 20px rgba(255, 255, 255, 0.2);
  z-index: 1;
  filter: blur(4px);
  animation: gloss-sweep 2.5s ease-in-out infinite;
  pointer-events: none;
}

@keyframes gloss-sweep {
  0% { left: -10%; }
  50% { left: 130%; }
  100% { left: 130%; }
}

.cmd-portrait:not(:hover) :deep(canvas) {
  width: 100% !important;
  height: 100% !important;
  object-fit: contain;
}

.cmd-portrait:hover {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 8%, transparent);
}

.cmd-battle-info {
  flex: 1;
  height: 100%;
  display: flex;
  background: color-mix(in srgb, var(--miya-bg, #222831) 55%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00ADB5) 8%, transparent);
  padding: 0.25rem 0.4rem;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
  transform: rotateX(calc(2deg + var(--gyro-rx, 0deg))) rotateY(calc(-4deg + var(--gyro-ry, 0deg)));
  box-shadow:
    2px 3px 10px rgba(0, 0, 0, 0.3),
    0 1px 0 color-mix(in srgb, var(--miya-accent, #00ADB5) 6%, transparent);
}

.cmd-battle-info:hover {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 14%, transparent);
  border-color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 25%, transparent);
  transform: rotateX(calc(1deg + var(--gyro-rx, 0deg))) rotateY(calc(-7deg + var(--gyro-ry, 0deg))) scale(1.02);
  box-shadow:
    3px 5px 18px color-mix(in srgb, var(--miya-accent, #00ADB5) 12%, transparent),
    0 2px 0 color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 12%, transparent);
}

.cmd-battle-info:active {
  transform: rotateX(2deg) rotateY(-4deg) scale(0.98);
  transition: transform 0.1s ease;
}

.cmd-battle-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
}

.cmd-battle-left h1 {
  color: var(--miya-text, #E4ECF0);
  font-size: clamp(1rem, 2vw, 1.4rem);
  font-weight: 700;
  line-height: 1.2;
  margin: 0;
  transition: color 0.3s, text-shadow 0.3s;
}

.cmd-battle-info:hover .cmd-battle-left h1 {
  text-shadow: 0 0 8px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 20%, transparent);
}

.cmd-battle-tip {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 45%, transparent);
  font-size: clamp(0.45rem, 0.9vw, 0.55rem);
  transition: color 0.3s;
}

.cmd-battle-info:hover .cmd-battle-tip {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 65%, transparent);
}

.cmd-battle-nd {
  font-size: clamp(0.4rem, 0.8vw, 0.5rem);
  transition: all 0.4s ease;
}

.cmd-battle-right {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: clamp(36px, 9%, 48px);
  height: clamp(36px, 9%, 48px);
  border: 2px solid color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 20%, transparent);
  border-radius: 50%;
  flex-shrink: 0;
  transition: all 0.4s ease;
}

.cmd-battle-info:hover .cmd-battle-right {
  border-color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 45%, transparent);
  box-shadow: 0 0 8px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 15%, transparent);
}

.cmd-battle-pct {
  color: var(--miya-text, #E4ECF0);
  font-size: clamp(0.7rem, 1.3vw, 0.9rem);
  font-weight: 700;
  margin: 0;
  line-height: 1;
}

.cmd-battle-right span {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 30%, transparent);
  font-size: clamp(0.35rem, 0.6vw, 0.45rem);
  transition: color 0.3s;
}

.cmd-battle-info:hover .cmd-battle-right span {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 60%, transparent);
}

.cmd-mascot {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 10%;
  min-width: 35px;
  max-width: 50px;
  height: 100%;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  gap: 0.1rem;
  flex-shrink: 0;
}

.cmd-mascot:hover {
  transform: scale(1.15);
}

.cmd-mascot-icon {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 35%, transparent);
  font-size: clamp(0.8rem, 1.5vw, 1.1rem);
  transition: all 0.4s ease;
}

.cmd-mascot:hover .cmd-mascot-icon {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 70%, transparent);
}

.cmd-mascot-label {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 40%, transparent);
  font-size: clamp(0.35rem, 0.6vw, 0.4rem);
  font-weight: bold;
  transition: color 0.3s;
}

.cmd-mascot:hover .cmd-mascot-label {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 70%, transparent);
}

.cmd-mascot-val {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 40%, transparent);
  font-size: clamp(0.35rem, 0.6vw, 0.4rem);
  font-family: 'JetBrains Mono', monospace;
  transition: color 0.3s;
}

.cmd-mascot:hover .cmd-mascot-val {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 80%, transparent);
}

/* boxline2: 任务卡 (flex: 1.3) */
.cmd-boxline2 {
  flex: 1.3;
  justify-content: center;
  gap: 0.25rem;
  overflow: hidden;
}

.cmd-quest {
  flex: 1;
  height: 100%;
  display: flex;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  overflow: hidden;
  transform: rotateX(calc(2deg + var(--gyro-rx, 0deg))) rotateY(calc(-3deg + var(--gyro-ry, 0deg)));
  box-shadow: 1px 2px 8px rgba(0, 0, 0, 0.25);
}

.cmd-quest:hover {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 10%, transparent);
  transform: rotateX(calc(1deg + var(--gyro-rx, 0deg))) rotateY(calc(-6deg + var(--gyro-ry, 0deg))) scale(1.02);
  box-shadow: 2px 4px 14px color-mix(in srgb, var(--miya-accent, #00ADB5) 10%, transparent);
}

.cmd-quest:active {
  transform: rotateX(2deg) rotateY(-3deg) scale(0.98);
  transition: transform 0.1s ease;
}

.cmd-quest-left {
  width: 25%;
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 8%, transparent);
  padding: 0.25rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  transition: background 0.4s;
}

.cmd-quest:hover .cmd-quest-left {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 16%, transparent);
}

.cmd-quest-left h2 {
  color: var(--miya-text, #E4ECF0);
  font-size: clamp(0.7rem, 1.3vw, 0.85rem);
  font-weight: 700;
  margin: 0;
}

.cmd-quest-left span {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 30%, transparent);
  font-size: clamp(0.35rem, 0.7vw, 0.45rem);
}

.cmd-quest:hover .cmd-quest-left span {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 55%, transparent);
}

.cmd-quest-right {
  flex: 1;
  background: color-mix(in srgb, var(--miya-bg, #222831) 55%, transparent);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0.4rem;
  position: relative;
  overflow: hidden;
  transition: background 0.4s;
}

.cmd-quest:hover .cmd-quest-right {
  background: color-mix(in srgb, var(--miya-bg, #222831) 70%, transparent);
}

.cmd-quest-right p {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 50%, transparent);
  font-size: clamp(0.4rem, 0.8vw, 0.5rem);
  font-weight: bold;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.3s;
}

.cmd-quest:hover .cmd-quest-right p {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 75%, transparent);
}

.cmd-quest-check {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 40%, transparent);
  font-size: clamp(0.7rem, 1.2vw, 0.85rem);
  position: absolute;
  right: 4px;
  bottom: 1px;
  flex-shrink: 0;
  transition: all 0.4s ease;
}

.cmd-quest:hover .cmd-quest-check {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 75%, transparent);
  transform: scale(1.2);
}

.cmd-quest-spacer {
  width: 12%;
  min-width: 45px;
  max-width: 70px;
  height: 60%;
  background: color-mix(in srgb, var(--miya-bg, #222831) 20%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00ADB5) 2%, transparent);
  align-self: flex-end;
  flex-shrink: 0;
  transition: background 0.4s;
}

/* boxline3: 功能区 (flex: 1.8) */
.cmd-boxline3 {
  flex: 1.8;
  justify-content: center;
  gap: 0.25rem;
  overflow: hidden;
}

.cmd-feat-card {
  flex: 1;
  height: 100%;
  background: color-mix(in srgb, var(--miya-bg, #222831) 55%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00ADB5) 8%, transparent);
  padding: 0.3rem;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  position: relative;
  font-family: inherit;
  color: inherit;
  text-align: left;
  overflow: hidden;
  transform: rotateX(calc(3deg + var(--gyro-rx, 0deg))) rotateY(calc(-4deg + var(--gyro-ry, 0deg)));
  box-shadow:
    2px 4px 10px rgba(0, 0, 0, 0.3),
    0 1px 0 color-mix(in srgb, var(--miya-accent, #00ADB5) 6%, transparent);
}

.cmd-feat-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 5%, transparent), transparent 50%);
  opacity: 0;
  transition: opacity 0.4s ease;
  pointer-events: none;
}

.cmd-feat-card:hover {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 15%, transparent);
  transform: rotateX(calc(1deg + var(--gyro-rx, 0deg))) rotateY(calc(-7deg + var(--gyro-ry, 0deg))) scale(1.03) translateY(-3px);
  border-color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 28%, transparent);
  box-shadow:
    3px 6px 18px color-mix(in srgb, var(--miya-accent, #00ADB5) 12%, transparent),
    0 2px 0 color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 12%, transparent);
}

.cmd-feat-card:active {
  transform: rotateX(3deg) rotateY(-4deg) scale(0.98);
  transition: transform 0.1s ease;
}

.cmd-feat-card:hover::before { opacity: 1; }
.cmd-feat-card:hover h1 { color: var(--miya-text, #E4ECF0); text-shadow: 0 0 10px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 25%, transparent); }
.cmd-feat-card:hover span { color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 65%, transparent); }

.cmd-feat-card h1 {
  color: var(--miya-text, #E4ECF0);
  font-size: clamp(0.65rem, 1.3vw, 0.85rem);
  font-weight: 700;
  margin: 0 0 0.1rem 0;
  transition: color 0.3s, text-shadow 0.3s;
}

.cmd-feat-card span {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 30%, transparent);
  font-size: clamp(0.35rem, 0.7vw, 0.45rem);
  transition: color 0.3s;
}

.cmd-feat-badge {
  position: absolute;
  right: 4px;
  top: 4px;
  background: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 60%, transparent);
  color: #111;
  font-size: clamp(0.3rem, 0.5vw, 0.35rem);
  font-weight: bold;
  padding: 1px 4px;
  border-radius: 2px;
  transition: all 0.3s ease;
}

.cmd-feat-card:hover .cmd-feat-badge {
  background: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 80%, transparent);
  transform: scale(1.1);
}

.cmd-feat-spacer {
  width: 10%;
  min-width: 40px;
  max-width: 60px;
  height: 100%;
  background: color-mix(in srgb, var(--miya-bg, #222831) 20%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00ADB5) 2%, transparent);
  flex-shrink: 0;
}

/* boxline4: 社区 (flex: 1) */
.cmd-boxline4 {
  flex: 1;
  width: 70%;
  background: color-mix(in srgb, var(--miya-bg, #222831) 50%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00ADB5) 8%, transparent);
  padding: 0 0.6rem;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  align-self: flex-end;
  overflow: hidden;
}

.cmd-boxline4:hover {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 14%, transparent);
  border-color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 20%, transparent);
  width: 100%;
  box-shadow: 0 0 14px color-mix(in srgb, var(--miya-accent, #00ADB5) 8%, transparent);
}

.cmd-guild-title {
  color: var(--miya-text, #E4ECF0);
  font-size: clamp(0.6rem, 1.1vw, 0.7rem);
  font-weight: 700;
  transition: color 0.3s, text-shadow 0.3s;
}

.cmd-boxline4:hover .cmd-guild-title {
  text-shadow: 0 0 10px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 30%, transparent);
}

.cmd-guild-desc {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 30%, transparent);
  font-size: clamp(0.4rem, 0.75vw, 0.5rem);
  transition: color 0.3s;
}

.cmd-boxline4:hover .cmd-guild-desc {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 65%, transparent);
}

/* ═══ 底部导航 (固定高度) ═══ */
.cmd-bottom-nav {
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.15rem;
  padding-top: 0.2rem;
}

.cmd-bottom-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0.3rem 0.15rem;
  cursor: pointer;
  transition: all 0.35s cubic-bezier(0.22, 1, 0.36, 1);
  background: color-mix(in srgb, var(--miya-bg, #222831) 40%, transparent);
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00ADB5) 6%, transparent);
  font-family: inherit;
  color: inherit;
  overflow: hidden;
  gap: 0.08rem;
  transform: rotateX(calc(2deg + var(--gyro-rx, 0deg))) rotateY(calc(-3deg + var(--gyro-ry, 0deg)));
  box-shadow: 1px 2px 6px rgba(0, 0, 0, 0.25);
}

.cmd-bottom-item:hover {
  background: color-mix(in srgb, var(--miya-accent, #00ADB5) 15%, transparent);
  border-color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 20%, transparent);
  box-shadow: 3px 5px 16px rgba(0, 0, 0, 0.35), 0 0 10px color-mix(in srgb, var(--miya-accent, #00ADB5) 10%, transparent);
  transform: rotateX(calc(1deg + var(--gyro-rx, 0deg))) rotateY(calc(-6deg + var(--gyro-ry, 0deg))) translateY(-3px);
}

.cmd-bottom-item:active {
  transform: rotateX(2deg) rotateY(-3deg) scale(0.97);
  transition: transform 0.1s ease;
}

.cmd-bottom-item:hover h1 {
  text-shadow: 0 0 12px color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 35%, transparent);
}

.cmd-bottom-icon {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 25%, transparent);
  font-size: clamp(0.5rem, 0.9vw, 0.6rem);
  transition: all 0.4s ease;
}

.cmd-bottom-item:hover .cmd-bottom-icon {
  color: color-mix(in srgb, var(--miya-chat-ai, #00FFF5) 60%, transparent);
  transform: scale(1.1);
}

.cmd-bottom-item h1 {
  color: var(--miya-text, #E4ECF0);
  font-size: clamp(0.5rem, 1vw, 0.6rem);
  font-weight: 700;
  margin: 0;
  transition: text-shadow 0.4s;
}

.cmd-bottom-item span {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 30%, transparent);
  font-size: clamp(0.35rem, 0.7vw, 0.45rem);
  transition: color 0.4s;
}

.cmd-bottom-item:hover span {
  color: color-mix(in srgb, var(--miya-accent, var(--miya-text)) 65%, transparent);
}

/* Miya OS: 首页保留沉浸构图，但降低持续透视与霓虹噪声。 */
.command-center {
  padding: var(--miya-space-3) clamp(1rem, 3vw, 3rem);
  perspective: 1200px;
}

.cmd-panel {
  height: 96%;
  padding: var(--miya-space-4);
  background: linear-gradient(180deg, rgba(12, 20, 31, 0.72), rgba(8, 14, 22, 0.54));
  border: 1px solid var(--miya-line-soft);
  position: relative;
  border-radius: 0;
  box-shadow:
    inset 2px 0 rgba(120, 207, 209, 0.22),
    inset -1px 0 rgba(120, 207, 209, 0.08),
    0 22px 56px rgba(0, 0, 0, 0.32);
  backdrop-filter: blur(16px);
}

.cmd-panel::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 52px;
  height: 18px;
  border-top: 2px solid rgba(162, 245, 238, 0.55);
  border-right: 2px solid rgba(162, 245, 238, 0.55);
  clip-path: polygon(18px 0, 100% 0, 100% 100%, calc(100% - 2px) 100%, calc(100% - 2px) 2px, 20px 2px);
  pointer-events: none;
}

.cmd-panel::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: 0;
  width: 38%;
  height: 2px;
  background: linear-gradient(90deg, var(--miya-accent-soft), rgba(120, 207, 209, 0.08), transparent);
  box-shadow: 0 0 10px rgba(120, 207, 209, 0.22);
  pointer-events: none;
}

.cmd-left::before { content: 'MIYA // COMPANION'; }
.cmd-right::before { content: 'SYSTEM // CORE'; }
.cmd-left::before,
.cmd-right::before {
  width: auto;
  height: auto;
  padding: 4px 9px 3px 24px;
  color: rgba(162, 245, 238, 0.5);
  background: linear-gradient(90deg, transparent, rgba(120, 207, 209, 0.07));
  border: 0;
  border-top: 1px solid rgba(162, 245, 238, 0.3);
  border-right: 2px solid rgba(162, 245, 238, 0.48);
  clip-path: polygon(14px 0, 100% 0, 100% 100%, 0 100%);
  font: 500 0.45rem/1.2 'JetBrains Mono', monospace;
  letter-spacing: 0.14em;
}

.cmd-left { transform: rotateY(5deg); }
.cmd-right { transform: rotateY(-5deg); }

.cmd-nav-card {
  border-color: var(--miya-line-soft);
  border-radius: 0;
  background:
    linear-gradient(135deg, rgba(120, 207, 209, 0.1), transparent 36%),
    rgba(10, 18, 28, 0.78);
  box-shadow: inset 0 -2px rgba(120, 207, 209, 0.08), 0 8px 24px rgba(0, 0, 0, 0.18);
  clip-path: polygon(0 0, calc(100% - 9px) 0, 100% 9px, 100% 100%, 9px 100%, 0 calc(100% - 9px));
  transform: none;
}

.cmd-nav-card:hover {
  transform: translateY(-3px) skewX(-2deg);
  border-color: var(--miya-line-strong);
  background: rgba(120, 207, 209, 0.09);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.24);
}

.cmd-res-item,
.cmd-battle-info,
.cmd-quest,
.cmd-feat-card,
.cmd-boxline4 {
  border-radius: 0;
  border-color: rgba(120, 207, 209, 0.13);
  background-color: rgba(8, 15, 24, 0.74);
}

.cmd-res-item,
.cmd-feat-card {
  clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%);
}

.cmd-boxline4 {
  position: relative;
  overflow: hidden;
  border-left: 2px solid rgba(216, 189, 130, 0.5);
  background:
    linear-gradient(90deg, rgba(216, 189, 130, 0.09), transparent 52%),
    rgba(8, 15, 24, 0.76);
}

.cmd-boxline4::after {
  content: 'ACCESS 06';
  position: absolute;
  right: 8px;
  bottom: 5px;
  color: rgba(216, 189, 130, 0.35);
  font: 0.44rem 'JetBrains Mono', monospace;
  letter-spacing: 0.12em;
}

.cmd-guild-title { color: var(--miya-life); }

.cmd-name-main { color: var(--miya-text-strong); }
.cmd-name-sub,
.cmd-nav-desc { color: var(--miya-text-muted); }

@media (max-width: 1000px) {
  .cmd-left,
  .cmd-right { transform: none; }
}

/* Miya Command Center: restore spatial hierarchy without exaggerated motion. */
.command-center {
  padding: clamp(0.5rem, 1.4vh, 1rem) clamp(1.25rem, 3.5vw, 4rem) 0;
  perspective: 980px;
  perspective-origin: 50% 48%;
}

.command-center::before {
  content: '';
  position: absolute;
  inset: 5% 31% 8%;
  pointer-events: none;
  background:
    linear-gradient(90deg, transparent 49.8%, rgba(162, 245, 238, 0.13) 50%, transparent 50.2%),
    linear-gradient(180deg, rgba(162, 245, 238, 0.08), transparent 22%, transparent 76%, rgba(216, 189, 130, 0.08));
  mask-image: linear-gradient(180deg, transparent, black 15%, black 84%, transparent);
}

.cmd-panel {
  height: 97%;
  overflow: visible;
  padding: 0.8rem;
  background: linear-gradient(180deg, rgba(8, 15, 24, 0.34), rgba(8, 15, 24, 0.08));
  border-color: rgba(162, 245, 238, 0.07);
  box-shadow: inset 2px 0 rgba(120, 207, 209, 0.2), 0 24px 60px rgba(0, 0, 0, 0.16);
  backdrop-filter: blur(5px);
}

.cmd-left { width: 27%; transform: rotateY(13deg); transform-origin: left center; }
.cmd-right { width: 34%; transform: rotateY(-15deg); transform-origin: right center; }

.cmd-eyebrow,
.cmd-right-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: rgba(162, 245, 238, 0.38);
  font: 500 0.42rem/1 'JetBrains Mono', monospace;
  letter-spacing: 0.16em;
}

.cmd-eyebrow { margin: 0 0 0.45rem; padding-bottom: 0.35rem; border-bottom: 1px solid rgba(162, 245, 238, 0.12); }
.cmd-right-heading { margin: 0.48rem 0 0.15rem; padding: 0 0.15rem; }
.cmd-right-sequence { color: rgba(216, 189, 130, 0.58); }

.cmd-nav-card,
.cmd-res-item,
.cmd-battle-info,
.cmd-quest,
.cmd-feat-card,
.cmd-boxline4,
.cmd-bottom-item {
  position: relative;
  overflow: hidden;
  background-color: rgba(6, 13, 21, 0.68);
  border-color: rgba(162, 245, 238, 0.14);
  backdrop-filter: blur(10px);
}

.cmd-battle-info {
  flex: 1.45;
  border-left: 2px solid rgba(162, 245, 238, 0.62);
  background: linear-gradient(112deg, rgba(120, 207, 209, 0.17), transparent 48%), rgba(6, 13, 21, 0.82);
}

.cmd-battle-info::after {
  content: 'PRIMARY ACCESS';
  position: absolute;
  top: 5px;
  right: 7px;
  color: rgba(162, 245, 238, 0.27);
  font: 0.36rem 'JetBrains Mono', monospace;
  letter-spacing: 0.12em;
}

.cmd-quest-spacer,
.cmd-feat-spacer {
  background: repeating-linear-gradient(135deg, rgba(120, 207, 209, 0.07) 0 2px, transparent 2px 8px), rgba(7, 14, 22, 0.3);
  border-color: rgba(120, 207, 209, 0.08);
}

.cmd-bottom-nav { gap: 0.3rem; padding-top: 0.45rem; }
.cmd-bottom-item { min-height: 56px; text-align: left; align-items: flex-start; padding: 0.42rem 0.5rem; clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%); }
.cmd-bottom-item.reserved { border-style: dashed; opacity: 0.62; }
.cmd-bottom-item.reserved::after { content: 'LOCK'; position: absolute; right: 4px; top: 4px; color: rgba(216, 189, 130, 0.62); font: 0.34rem 'JetBrains Mono', monospace; letter-spacing: 0.08em; }

.cmd-reserved-notice {
  position: absolute;
  left: 50%;
  bottom: 3.5rem;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 0.7rem;
  width: min(360px, 42vw);
  padding: 0.7rem 0.9rem;
  transform: translateX(-50%);
  color: var(--miya-text-body);
  background: linear-gradient(90deg, rgba(8, 17, 27, 0.94), rgba(13, 25, 38, 0.88));
  border: 1px solid rgba(216, 189, 130, 0.28);
  border-left: 3px solid var(--miya-life);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(16px);
}
.cmd-reserved-mark { color: var(--miya-life); font-size: 1.1rem; }
.cmd-reserved-notice div { display: flex; flex-direction: column; gap: 0.16rem; }
.cmd-reserved-notice strong { color: var(--miya-text-strong); font-size: 0.68rem; letter-spacing: 0.12em; }
.cmd-reserved-notice small { color: var(--miya-text-muted); font: 0.45rem 'JetBrains Mono', monospace; letter-spacing: 0.08em; }
.notice-rise-enter-active, .notice-rise-leave-active { transition: opacity 0.24s ease, transform 0.32s var(--miya-ease-out); }
.notice-rise-enter-from, .notice-rise-leave-to { opacity: 0; transform: translate(-50%, 12px); }

@media (max-width: 1180px) {
  .command-center { padding-inline: 1rem; }
  .cmd-left { width: 29%; }
  .cmd-right { width: 36%; }
  .cmd-bottom-item { padding-inline: 0.3rem; }
}

@media (max-width: 1000px) {
  .cmd-panel { backdrop-filter: blur(10px); }
}

@media (max-width: 760px) {
  .command-center { overflow-y: auto; align-items: flex-start; gap: 0.7rem; padding-bottom: 15rem; }
  .cmd-left, .cmd-right { width: 46%; min-width: 260px; height: auto; }
  .cmd-bottom-nav { display: grid; grid-template-columns: 1fr 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .cmd-panel { transition-duration: 0.01ms; }
  .cmd-nav-card,
  .cmd-res-item,
  .cmd-battle-info,
  .cmd-quest,
  .cmd-feat-card,
  .cmd-bottom-item { transition-duration: 0.01ms; }
}

/* PGR composition: the wings are spatial groups, never visible containers. */
.command-center {
  padding: 0.2rem 3% 0;
  perspective: 600px;
  -webkit-perspective: 600px;
  perspective-origin: center;
  -webkit-perspective-origin: center;
}

.command-center::before { opacity: 0.48; }

.cmd-panel {
  height: 92%;
  padding: 0.5rem 0.5rem 0.2rem;
  overflow: visible;
  background: transparent;
  border: 0;
  box-shadow: none;
  backdrop-filter: none;
}

.cmd-panel::before,
.cmd-panel::after { display: none; }

.cmd-left {
  width: 30%;
  min-width: 190px;
  transform-origin: center left;
  position: relative;
  z-index: 4;
}

.cmd-right {
  width: 36%;
  min-width: 230px;
  transform-origin: center right;
  position: relative;
  z-index: 3;
}

.cmd-eyebrow,
.cmd-right-heading {
  padding-inline: 0;
  border-color: rgba(162, 245, 238, 0.09);
  background: transparent;
  text-shadow: 0 0 10px rgba(120, 207, 209, 0.22);
}

.cmd-nav-card,
.cmd-res-item,
.cmd-battle-info,
.cmd-quest,
.cmd-feat-card,
.cmd-boxline4,
.cmd-bottom-item {
  backdrop-filter: blur(7px);
  box-shadow:
    2px 4px 12px rgba(0, 0, 0, 0.34),
    inset 0 1px rgba(162, 245, 238, 0.06);
}

.cmd-nav-card { transform: rotateX(calc(3deg + var(--gyro-rx, 0deg))) rotateY(calc(-5deg + var(--gyro-ry, 0deg))); }
.cmd-nav-card:hover { transform: rotateX(calc(1deg + var(--gyro-rx, 0deg))) rotateY(calc(-8deg + var(--gyro-ry, 0deg))) scale(1.04) translateY(-3px); }

.cmd-mode-btn {
  width: auto;
  min-width: 76px;
  padding: 0 0.48rem;
  gap: 0.32rem;
  border: 1px solid rgba(162, 245, 238, 0.15);
  background: rgba(5, 13, 21, 0.58);
  clip-path: polygon(0 0, calc(100% - 7px) 0, 100% 7px, 100% 100%, 0 100%);
}

.cmd-mode-btn.active {
  border-color: rgba(162, 245, 238, 0.4);
  background: linear-gradient(90deg, rgba(120, 207, 209, 0.15), rgba(5, 13, 21, 0.58));
  box-shadow: inset 2px 0 rgba(162, 245, 238, 0.65), 0 0 12px rgba(120, 207, 209, 0.08);
}

.cmd-toggle-label {
  color: rgba(196, 220, 224, 0.68);
  font: 0.42rem/1 'JetBrains Mono', monospace;
  letter-spacing: 0.08em;
  white-space: nowrap;
}

.cmd-mode-btn.active .cmd-toggle-label { color: var(--miya-accent-bright); }

.cmd-nav { gap: 0.22rem; }
.cmd-nav-card { min-width: 0; min-height: 58px; padding: 0.34rem 0.3rem; }
.cmd-nav-icon { font-size: clamp(0.5rem, 0.8vw, 0.64rem); margin-bottom: 0.12rem; }
.cmd-nav-title { font-size: clamp(0.58rem, 1vw, 0.76rem); margin-bottom: 0.18rem; }
.cmd-nav-desc { font-size: clamp(0.3rem, 0.56vw, 0.4rem); white-space: nowrap; }

.cmd-time-icons { align-items: stretch; gap: 0.24rem; }
.cmd-time-icn {
  width: 36px;
  height: 30px;
  padding: 0;
  border: 1px solid rgba(162, 245, 238, 0.12);
  background: rgba(5, 13, 21, 0.52);
  flex-direction: column;
  gap: 1px;
  font-family: inherit;
}
.cmd-time-icn small { color: rgba(127, 145, 154, 0.6); font: 0.28rem/1 'JetBrains Mono', monospace; letter-spacing: 0.08em; }
.cmd-time-icn-symbol { font-size: 0.66rem; line-height: 1; }
.cmd-time-icn:hover { border-color: rgba(162, 245, 238, 0.35); background: rgba(120, 207, 209, 0.11); }
.cmd-mode-icn { width: 40px; }
.cmd-mode-icn.active {
  color: var(--miya-accent-bright, #a2f5ee);
  border-color: rgba(162, 245, 238, 0.4);
  background: linear-gradient(180deg, rgba(120, 207, 209, 0.15), rgba(5, 13, 21, 0.52));
  box-shadow: inset 2px 0 rgba(162, 245, 238, 0.65), 0 0 12px rgba(120, 207, 209, 0.08);
}
.cmd-mode-icn:not(.active) { color: rgba(162, 245, 238, 0.3); }
.cmd-hide-icn { width: 28px; }

.cmd-toggle-row { position: relative; z-index: 5; }
.cmd-music-actions {
  left: 0;
  right: auto;
  width: min(360px, calc(100vw - 2rem));
  max-height: min(360px, calc(100vh - 3rem));
}

@media (max-width: 1180px) {
  .command-center { padding-inline: 1.4rem; }
  .cmd-left { width: 30%; }
  .cmd-right { width: 37%; }
}

@media (max-width: 1000px) {
  .cmd-left,
  .cmd-right { transform-style: preserve-3d; }
  .cmd-panel { backdrop-filter: none; }
}

@media (max-width: 760px) {
  .cmd-left,
  .cmd-right { transform: none !important; }
  .cmd-time-icons { gap: 0.16rem; }
  .cmd-time-icn:not(.cmd-mode-icn):not(.cmd-hide-icn) { width: 32px; }
  .cmd-mode-icn { width: 28px; }
  .cmd-hide-icn { width: 24px; }
  .cmd-mode-icn small { display: none; }
  .cmd-music-modes { gap: 0; }
  .cmd-music-modes button { min-width: 26px; padding-inline: 0.08rem; }
  .cmd-music-modes button small { display: none; }
}
</style>
