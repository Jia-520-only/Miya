<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import EarthAPI, {
  type EarthAchievement,
  type EarthActivity,
  type EarthBattlePass,
  type EarthCharacter,
  type EarthCheckinStatus,
  type EarthExchangeRates,
  type EarthItem,
  type EarthMemoryPool,
  type EarthMemoryPullItem,
  type EarthMemoryPullRecord,
  type EarthMiyaNote,
  type EarthPlayer,
  type EarthQuest,
  type EarthStats,
  type EarthStory,
  type EarthTemplates,
  type EarthTheme,
  type EarthTitles,
  type EarthWeeklyChallenge,
  type EarthWeeklyReport,
  type EarthLifeHub,
  type EarthWorldDiscovery,
  type EarthWorldRegion,
  type EarthWorldStatus,
  type EarthRealContext,
  type EarthWorldShop,
  type EarthMiyaShop,
} from '@/api/earth'
import Markdown from '@/components/Markdown.vue'
import { isLegacyBackground } from '@/utils/backgroundAssets'

// ── 前台展示面板: 玩家视角 · 鸣潮官网式整屏分节布局 ──
// 7 个导航节 (首页/委托/背包/角色/剧情/档案/数据) + 结尾页 · 滚轮/导航翻页

const loading = ref(false)
const player = ref<EarthPlayer | null>(null)
const items = ref<EarthItem[]>([])
const quests = ref<EarthQuest[]>([])
const characters = ref<EarthCharacter[]>([])
const stories = ref<EarthStory[]>([])
const templates = ref<EarthTemplates | null>(null)
const achievements = ref<EarthAchievement[]>([])
const checkin = ref<EarthCheckinStatus | null>(null)
const notes = ref<EarthMiyaNote[]>([])
const stats = ref<EarthStats | null>(null)
const activity = ref<EarthActivity[]>([])
const titles = ref<EarthTitles | null>(null)
const dueSoonList = ref<EarthQuest[]>([])
const weekly = ref<EarthWeeklyReport | null>(null)
const rates = ref<EarthExchangeRates | null>(null)
const worldRegions = ref<EarthWorldRegion[]>([])
const worldDiscoveries = ref<EarthWorldDiscovery[]>([])
const worldStatus = ref<EarthWorldStatus | null>(null)
const realContext = ref<EarthRealContext | null>(null)
const worldShop = ref<EarthWorldShop | null>(null)
const miyaShop = ref<EarthMiyaShop | null>(null)
// ── v17: 回忆卡池 / 每周纪行 / 周挑战 ──
const memory = ref<EarthMemoryPool | null>(null)
const memoryPullRecords = ref<EarthMemoryPullRecord[]>([])
const battlePass = ref<EarthBattlePass | null>(null)
const weeklyChallenge = ref<EarthWeeklyChallenge | null>(null)
const lifeHub = ref<EarthLifeHub | null>(null)
const degradedModules = ref<string[]>([])
const lifeHubRealityLabel = computed(() => {
  const context = lifeHub.value?.facts.real_context
  if (!context?.enabled) return '现实连接已关闭'
  if (context.source_status !== 'ok') return '现实数据未同步'
  return context.is_stale ? '现实数据已过期' : `${context.city || '当前城市'} · 已同步`
})
const lifeHubOperatorLabel = computed(() => {
  const operator = lifeHub.value?.facts.operator
  if (!operator?.enabled) return '自主运营已关闭'
  if (operator.in_quiet_hours) return '自主运营 · 静默时段'
  if (!operator.last_cycle_at) return '自主运营 · 等待首次巡检'
  return `上次巡检 ${formatDate(operator.last_cycle_at)} · ${operator.last_actions} 个动作`
})
const todayAction = computed(() => {
  const pending = lifeHub.value?.pending_confirmation?.[0]
  if (pending)
    return { title: '先确认一件事', detail: pending.text, action: pending.key, label: pending.key === 'checkin' ? '确认并签到' : '确认' }
  const recommendation = lifeHub.value?.recommendations?.[0]
  if (recommendation)
    return { title: '弥娅的今日建议', detail: recommendation.text, action: recommendation.key, label: recommendation.key === 'due_quests' ? '查看委托' : '去看看' }
  const current = ongoingQuests.value[0] || pendingQuests.value[0]
  if (current)
    return { title: current.status === 'ongoing' ? '继续进行中的委托' : '今天可以接取的委托', detail: current.title, action: 'quest', label: current.status === 'ongoing' ? '继续委托' : '查看委托' }
  if (!checkin.value?.checked_today)
    return { title: '今日签到还未完成', detail: '告诉弥娅昨晚睡得怎么样，领取今天的恢复与奖励。', action: 'checkin', label: '去签到' }
  return { title: '今天暂时没有待处理事项', detail: '可以记录一段剧情，或者去世界里留下一个发现。', action: 'activity', label: '看动态' }
})
function openTodayAction(action: string) {
  if (action === 'checkin') {
    doCheckin()
    return
  }
  if (action === 'activity') {
    goTo(6)
    return
  }
  goTo(1)
}
function actLifeHub(key: string) {
  if (key === 'checkin') {
    doCheckin()
    return
  }
  goTo(1)
}
// ── 加载失败状态 (loadAll 兜底) ──
const loadError = ref('')
const worldBusy = ref(false)
const worldMessage = ref('')
const worldCompanion = ref<{ speaker: string, text: string, tone: string, region: string } | null>(null)
const worldChoiceBusy = ref(false)
const worldChoiceDiscovery = ref<EarthWorldDiscovery | null>(null)
const toast = ref('')
const toastQueue = ref<string[]>([])
let toastTimer: number | undefined
// ── 任务历史归档 (最近完成/失败/取消的委托) ──
const questHistoryList = ref<EarthQuest[]>([])
const showQuestHistory = ref(false)
// ── 角色好感度变动日志 (角色抽屉展示) ──
const charAffinityLogs = ref<Array<{ id: number, delta: number, reason: string, created_at: string }>>([])
const charLogsBusy = ref(false)

// ── 双币制 · 弥娅币(互动货币) + 地球币/现实资产(佳管理, 人民币/美元切换) ──
type EarthMoneyMode = 'cny' | 'usd'
const earthMoneyMode = ref<EarthMoneyMode>('cny')
const EARTH_MONEY_LABELS: Record<EarthMoneyMode, string> = { cny: '人民币', usd: '美元' }
function switchEarthMoney() {
  earthMoneyMode.value = earthMoneyMode.value === 'cny' ? 'usd' : 'cny'
  showToast(`现实资产已切换为${EARTH_MONEY_LABELS[earthMoneyMode.value]}显示`)
}
function formatMiyaCoins(amount: number): string {
  return `◆${amount}`
}
function formatEarthMoney(amount: number): string {
  if (earthMoneyMode.value === 'cny')
    return `¥ ${amount.toFixed(2)}`
  const usd = amount * (rates.value?.usd_per_cny ?? 0.14)
  return `$ ${usd.toFixed(2)}`
}

// 前台主题 (默认跟随 Miya OS 青碧配色, 可在设置中自定义)
const theme = ref<EarthTheme>({ accent: '#78cfd1', accent_light: '#a2f5ee', accent_deep: '#4f9fa5', background: '', background_opacity: 0.25, glass: true })
const themeVars = computed(() => ({
  '--pv-gold': theme.value.accent,
  '--pv-gold-light': theme.value.accent_light,
  '--pv-gold-deep': theme.value.accent_deep,
  '--pv-glass': theme.value.glass ? 'blur(14px) saturate(1.25)' : 'none',
}))
const isMiyaDefaultTheme = computed(() => theme.value.accent.toLowerCase() === '#78cfd1' && theme.value.accent_light.toLowerCase() === '#a2f5ee' && theme.value.accent_deep.toLowerCase() === '#4f9fa5')

// ── 弥娅关怀按钮: 到期提醒 / 一键签到 / 动态流 ──
function onCareClick() {
  if (dueSoonList.value.length > 0) {
    goTo(1)
    return
  }
  if (!checkin.value?.checked_today) {
    doCheckin()
    return
  }
  goTo(6)
}
function wallpaperUrl(name: string): string {
  if (!name || isLegacyBackground(name))
    return ''
  return name.startsWith('/api/') ? EarthAPI.imageUrl(name) : name
}

function worldRegionStyle(region: EarthWorldRegion): Record<string, string> {
  const style: Record<string, string> = { '--world-color': region.color }
  if (region.image_path)
    style.backgroundImage = `linear-gradient(180deg, rgba(7,8,12,0.28), rgba(7,8,12,0.94)), url(${EarthAPI.imageUrl(region.image_path)})`
  return style
}

const RARITY_COLORS: Record<string, string> = {
  common: '#9e9e9e', uncommon: '#4caf50', rare: '#29b6f6', epic: '#ab47bc', legendary: '#ffb300',
}
const RARITY_LABELS: Record<string, string> = {
  common: '普通', uncommon: '稀有', rare: '珍贵', epic: '史诗', legendary: '传说',
}
const CATEGORY_LABELS: Record<string, string> = {
  digital: '数码', book: '书籍', life: '生活', food: '食品', tool: '工具', clothing: '服饰', collectible: '收藏', other: '其他',
}
const QUEST_TYPE_LABELS: Record<string, string> = {
  main: '主线', branch: '支线', daily: '日常', optional: '可选',
}
const QUEST_TYPE_COLORS: Record<string, string> = {
  main: '#ffb300', branch: '#00adb5', daily: '#29b6f6', optional: '#ab47bc',
}
const RELATIONSHIP_LABELS: Record<string, string> = {
  family: '家人', friend: '朋友', colleague: '同事', partner: '恋人', other: '其他',
}
const EVENT_TYPE_LABELS: Record<string, string> = {
  life: '生活', achievement: '成就', quest: '任务', character: '人物',
}
const ITEM_CAT_ICONS: Record<string, string> = {
  all: '◇', digital: '▣', book: '≣', life: '◈', food: '◍', tool: '◫', clothing: '◭', collectible: '✦', other: '◻',
}
const MOOD_ICONS: Record<string, string> = {
  neutral: '✦', happy: '✧', caring: '❦', excited: '✸', proud: '✪', sleepy: '☾', sad: '❋',
}

// ── 板块 Tab 导航 (顶部导航切换, 当前板块整页自由滚动) ──
const SECTIONS = [
  { id: 'home', label: '首页', en: 'HOME' },
  { id: 'board', label: '委托', en: 'QUEST' },
  { id: 'items', label: '背包', en: 'BACKPACK' },
  { id: 'chars', label: '角色', en: 'CHARACTERS' },
  { id: 'story', label: '剧情', en: 'STORY' },
  { id: 'profile', label: '档案', en: 'PROFILE' },
  { id: 'stats', label: '数据', en: 'DATA' },
  { id: 'world', label: '世界', en: 'WORLD' },
  { id: 'shop', label: '商城', en: 'SHOP' },
] as const
// 玩家端只暴露用户真正需要的五个入口，细分板块仍保留给页面内部使用。
const NAV_GROUPS = [
  { id: 'home', label: '指挥舱', en: 'COMMAND', target: 0, sections: [0] },
  { id: 'missions', label: '委托', en: 'MISSIONS', target: 1, sections: [1] },
  { id: 'archive', label: '档案', en: 'ARCHIVE', target: 2, sections: [2, 3, 4] },
  { id: 'world', label: '世界', en: 'WORLD', target: 7, sections: [7, 8] },
  { id: 'profile', label: '玩家', en: 'PROFILE', target: 5, sections: [5, 6] },
] as const
const NAV_SUBNAV: Record<string, readonly { target: number, label: string, en: string }[]> = {
  archive: [
    { target: 2, label: '背包', en: 'INVENTORY' },
    { target: 3, label: '角色', en: 'ROSTER' },
    { target: 4, label: '剧情', en: 'CHRONICLE' },
  ],
  world: [
    { target: 7, label: '区域探索', en: 'REGIONS' },
    { target: 8, label: '商城', en: 'SHOP' },
  ],
  profile: [
    { target: 5, label: '玩家档案', en: 'IDENTITY' },
    { target: 6, label: '数据与动态', en: 'TELEMETRY' },
  ],
}
const activeSection = ref(0)
const stageEl = ref<HTMLElement | null>(null)
function isNavGroupActive(group: typeof NAV_GROUPS[number]) {
  return group.sections.some(section => section === activeSection.value)
}
const activeNavGroup = computed(() => NAV_GROUPS.find(group => isNavGroupActive(group)) || NAV_GROUPS[0])
const activeSubnav = computed(() => NAV_SUBNAV[activeNavGroup.value.id] || [])
function goTo(i: number) {
  const target = Math.max(0, Math.min(SECTIONS.length - 1, i))
  if (target === activeSection.value) {
    return
  }
  activeSection.value = target
  stageEl.value?.scrollTo({ top: 0 })
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && (drawerItem.value || drawerChar.value || drawerRegion.value || showProfileEdit.value)) {
    closeDrawer()
    return
  }
  const t = e.target as HTMLElement | null
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable))
    return
  if (e.key === 'ArrowRight')
    goTo(activeSection.value + 1)
  else if (e.key === 'ArrowLeft')
    goTo(activeSection.value - 1)
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  if (toastTimer)
    window.clearTimeout(toastTimer)
})

// ── 数据加载 ──
function showNextToast() {
  const next = toastQueue.value.shift()
  if (!next) {
    toast.value = ''
    toastTimer = undefined
    return
  }
  toast.value = next
  toastTimer = window.setTimeout(() => {
    toast.value = ''
    showNextToast()
  }, 2800)
}
function showToast(msg: string) {
  toastQueue.value.push(msg)
  if (!toast.value && !toastTimer)
    showNextToast()
}

// ── v17: 回忆卡池 / 每周纪行 / 周挑战 (各自兜底, 单项失败不影响整页) ──
async function loadMemory() {
  try {
    const [pool, pulls] = await Promise.all([EarthAPI.memoryPool(), EarthAPI.memoryPulls(5)])
    memory.value = pool
    memoryPullRecords.value = pulls || []
  }
  catch { memory.value = null }
}
async function loadBattlePass() {
  try {
    battlePass.value = await EarthAPI.battlePass()
  }
  catch {
    battlePass.value = null
  }
}
async function loadWeeklyChallenge() {
  try {
    weeklyChallenge.value = await EarthAPI.weeklyChallenge()
  }
  catch {
    weeklyChallenge.value = null
  }
}

async function loadAll() {
  loading.value = true
  loadError.value = ''
  degradedModules.value = []
  try {
    const [p, it, q, c, s, t] = await Promise.all([
      EarthAPI.getPlayer(),
      EarthAPI.listItems(),
      EarthAPI.listQuests(),
      EarthAPI.listCharacters(),
      EarthAPI.listStory(),
      EarthAPI.getTemplates(),
    ])
    player.value = p
    items.value = it
    quests.value = q
    characters.value = c
    stories.value = s
    templates.value = t
    const optional = <T>(label: string, request: Promise<T>, fallback: T): Promise<T> => request.catch(() => {
      degradedModules.value.push(label)
      return fallback
    })
    const [a, ck, n, st, ac, ti, due, wk, rt, th, world] = await Promise.all([
      optional('成就', EarthAPI.listAchievements(), []),
      optional('签到', EarthAPI.checkinStatus(), null),
      optional('寄语', EarthAPI.listNotes(), []),
      optional('统计', EarthAPI.stats(), null),
      optional('动态', EarthAPI.activity(60), []),
      optional('称号', EarthAPI.titles(), null),
      optional('到期提醒', EarthAPI.dueSoon(3), []),
      optional('周报', EarthAPI.weeklyReport(), null),
      optional('汇率', EarthAPI.exchangeRates(), null),
      optional('主题', EarthAPI.getTheme(), theme.value),
      optional('世界', EarthAPI.world(), { regions: [], discoveries: [], status: null }),
    ])
    achievements.value = a
    checkin.value = ck
    notes.value = n
    stats.value = st
    activity.value = ac
    titles.value = ti
    dueSoonList.value = due
    weekly.value = wk
    rates.value = rt
    theme.value = { ...th, background: isLegacyBackground(th.background) ? '' : th.background }
    worldRegions.value = world.regions || []
    worldDiscoveries.value = world.discoveries || []
    worldStatus.value = world.status || null
    realContext.value = world.status?.real_context || null
    try { lifeHub.value = await EarthAPI.lifeHub() } catch { lifeHub.value = null; degradedModules.value.push('生活中枢') }
    const activeEvent = (world.status?.event_areas || []).find(e => e.active)
    const [eventShop, miyaShopData, questHistory] = await Promise.all([
      activeEvent ? optional('活动商店', EarthAPI.worldEventShop(activeEvent.key), null) : Promise.resolve(null),
      optional('弥娅商城', EarthAPI.miyaShop(), null),
      optional('任务历史', EarthAPI.questHistory(10), []),
    ])
    await Promise.all([loadMemory(), loadBattlePass(), loadWeeklyChallenge()])
    worldShop.value = eventShop
    miyaShop.value = miyaShopData
    questHistoryList.value = questHistory
  }
  catch (e: any) {
    loadError.value = e?.response?.data?.detail || e?.message || '网络或服务异常'
  }
  finally {
    loading.value = false
  }
}

async function buyWorldShopItem(item: EarthWorldShop['items'][number]) {
  const eventKey = worldShop.value?.event_key
  if (!eventKey || !item.can_buy || worldBusy.value)
    return
  worldBusy.value = true
  try {
    await EarthAPI.buyWorldEventItem(eventKey, item.key)
    showToast(`已兑换「${item.name}」，纪念物已收入背包`)
    await loadAll()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '活动兑换失败')
  }
  finally {
    worldBusy.value = false
  }
}

async function buyMiyaShopItem(item: EarthMiyaShop['items'][number]) {
  if (!item.can_buy || worldBusy.value)
    return
  worldBusy.value = true
  try {
    const result = await EarthAPI.buyMiyaShopItem(item.key)
    if (item.kind === 'interaction') {
      // v18: 互动商品不再即时消耗, 兑换后变成背包里的「服务券」, 使用时才触发互动
      worldMessage.value = `已兑换「${item.name}」 · 服务券已放入背包`
      showToast('服务券已放入背包，想用的时候来找我，或点背包里的「使用」')
    }
    else if (result.interaction) {
      worldCompanion.value = { speaker: '弥娅', text: result.interaction, tone: '专属互动', region: '弥娅商城' }
      worldMessage.value = `已兑换「${item.name}」 · 这段互动已经写入动态`
      showToast(`◆ 已消耗 ${item.cost} 弥娅币`)
    }
    else {
      worldMessage.value = `已兑换「${item.name}」`
      showToast(`◆ 已消耗 ${item.cost} 弥娅币`)
    }
    await loadAll()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '弥娅商城兑换失败')
  }
  finally {
    worldBusy.value = false
  }
}

async function refreshRealContext() {
  if (worldBusy.value)
    return
  worldBusy.value = true
  try {
    const context = await EarthAPI.refreshRealContext()
    realContext.value = context
    worldStatus.value = await EarthAPI.worldStatus()
    const label = context.source_status === 'ok' ? `现实天气已同步：${context.city} · ${context.weather}` : '现实天气暂未同步，未使用模拟数据'
    worldMessage.value = label
    showToast(label)
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '现实数据同步失败')
  }
  finally {
    worldBusy.value = false
  }
}

async function configureRealCity() {
  const current = realContext.value?.city || ''
  const city = window.prompt('输入你希望用于天气同步的城市（只保存城市名，不读取 GPS）', current)
  if (city === null)
    return
  try {
    await EarthAPI.updateRealContextSettings({ city: city.trim(), allow_precise_location: false })
    await refreshRealContext()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '现实地点保存失败')
  }
}

onMounted(loadAll)

// 获取浏览器定位坐标 (地理围栏区域探索需要真实坐标)
function getGeolocation(): Promise<{ latitude: number, longitude: number } | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve(null)
      return
    }
    navigator.geolocation.getCurrentPosition(
      pos => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    )
  })
}

async function exploreRegion(region: EarthWorldRegion) {
  if (worldBusy.value)
    return
  worldBusy.value = true
  worldMessage.value = ''
  try {
    // 区域启用地理围栏时先取真实坐标，缺失则直接给出提示，不打后端
    let coords: { latitude: number, longitude: number } | undefined
    if ((region.geofence_radius || 0) > 0) {
      showToast('⌖ 正在获取定位…')
      const pos = await getGeolocation()
      if (!pos) {
        worldMessage.value = `「${region.name}」是真实地点，需要开启浏览器定位并到达附近 ${region.geofence_radius} 米内才能探索哦`
        showToast(worldMessage.value)
        return
      }
      coords = pos
    }
    const res = await EarthAPI.exploreWorld(region.key, coords)
    if (res.geofence?.enabled && res.geofence.distance_m != null)
      showToast(`⌖ 距「${region.name}」${res.geofence.distance_m} 米 · 围栏内 ✓`)
    if (res.discovery) {
      worldMessage.value = `${res.discovery.title} · +${res.discovery.reward_currency} 弥娅币 · +${res.discovery.reward_exp} 经验`
      worldCompanion.value = res.discovery.companion || null
      worldChoiceDiscovery.value = res.discovery
      showToast(`✦ 发现「${res.discovery.title}」`)
    }
    else {
      worldMessage.value = res.message || `「${region.name}」已经探索完毕`
      showToast(worldMessage.value)
    }
    await loadAll()
    if (drawerRegion.value?.key === region.key)
      drawerRegion.value = worldRegions.value.find(r => r.key === region.key) || region
    await refreshAchievementsQuiet()
  }
  catch (e: any) {
    worldMessage.value = e?.response?.data?.detail || '探索失败，请稍后再试'
    showToast(worldMessage.value)
  }
  finally {
    worldBusy.value = false
  }
}

async function chooseWorldDiscovery(choice: 'continue' | 'record' | 'rest', target?: EarthWorldDiscovery) {
  const discovery = target || worldChoiceDiscovery.value
  if (!discovery?.id || worldChoiceBusy.value)
    return
  worldChoiceBusy.value = true
  try {
    const result = await EarthAPI.chooseWorldDiscovery(discovery.id, choice)
    worldMessage.value = `${result.label} · 区域共鸣 Lv.${result.resonance?.level || 1}`
    showToast(`已选择「${result.label}」· 获得共鸣`)
    const chosen = { ...discovery, choice: { choice, chosen_at: new Date().toISOString() } }
    if (worldChoiceDiscovery.value?.id === chosen.id)
      worldChoiceDiscovery.value = chosen
    pendingChoiceAnsweredId.value = chosen.id || null
    await loadAll()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '同行选择失败')
  }
  finally {
    worldChoiceBusy.value = false
  }
}

// 「最近发现」里最新一条还未做同行选择的发现，也可补选
const pendingChoiceAnsweredId = ref<number | null>(null)
const pendingChoiceDiscovery = computed(() => {
  const latest = worldDiscoveries.value[0]
  if (latest && !latest.choice && latest.id && latest.id !== pendingChoiceAnsweredId.value)
    return latest
  return null
})

async function commissionRegion(region: EarthWorldRegion) {
  if (worldBusy.value)
    return
  worldBusy.value = true
  try {
    const res = await EarthAPI.regionCommission(region.key)
    worldMessage.value = res.created ? `已领取「${res.quest.title}」，委托已放入任务板` : `今天已经领取过「${res.quest.title}」`
    showToast(res.created ? '✦ 区域专属委托已出现' : '这份区域委托还在任务板上')
    await loadAll()
    if (drawerRegion.value?.key === region.key)
      drawerRegion.value = worldRegions.value.find(r => r.key === region.key) || region
  }
  catch (e: any) {
    worldMessage.value = e?.response?.data?.detail || '领取区域委托失败'
    showToast(worldMessage.value)
  }
  finally {
    worldBusy.value = false
  }
}

async function refreshAchievementsQuiet() {
  try {
    const res = await EarthAPI.refreshAchievements()
    if (res.newly_unlocked?.length) {
      const names = res.newly_unlocked.map(x => `${x.icon} ${x.title}`).join(' · ')
      showToast(`✦ 成就解锁: ${names}`)
    }
  }
  catch { /* 静默 */ }
}

function affinityLevel(affinity: number) {
  const levels = templates.value?.affinity_levels || []
  return levels.find(l => affinity >= l.min && affinity <= l.max) || { label: '未知', color: '#9e9e9e' }
}

function stars(difficulty: number): string {
  const d = Math.max(1, Math.min(5, difficulty || 1))
  return '★'.repeat(d) + '☆'.repeat(5 - d)
}

// The default Earth Online curve consumes `100 * level` EXP for each level.
// Keep the HUD progress relative to the current level instead of total EXP.
function expProgress(exp: number, level: number): number {
  const safeLevel = Math.max(1, level || 1)
  const previousLevelExp = 100 * safeLevel * (safeLevel - 1) / 2
  const currentLevelExp = Math.max(0, (exp || 0) - previousLevelExp)
  return Math.min(100, Math.max(0, currentLevelExp / (100 * safeLevel) * 100))
}

const pendingQuests = computed(() => quests.value.filter(q => q.status === 'pending'))
const ongoingQuests = computed(() => quests.value.filter(q => q.status === 'ongoing'))
const doneQuests = computed(() => quests.value.filter(q => ['completed', 'failed', 'cancelled'].includes(q.status)))

// ── 任务交互 ──
async function acceptQuest(q: EarthQuest) {
  questActionsOpen.value = false
  try {
    await EarthAPI.acceptQuest(q.id)
    showToast(`已接取「${q.title}」，开始你的开拓之旅！`)
    await loadAll()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '接取委托失败，请稍后再试')
  }
}
async function completeQuest(q: EarthQuest) {
  questActionsOpen.value = false
  try {
    const res = await EarthAPI.completeQuest(q.id)
    player.value = res.player
    showToast(`任务完成！+${res.reward.currency} 弥娅币, +${res.reward.exp} 经验`)
    if (res.level_up)
      showToast(`✦ 升级！Lv.${res.level_up.old_level} → Lv.${res.level_up.new_level}，升级礼包 +${res.level_up.reward_currency} 弥娅币`)
    if (res.recurring_reset)
      window.setTimeout(() => showToast('↻ 循环任务已重置，新的一轮开始'), 1600)
    await loadAll()
    await refreshAchievementsQuiet()
  }
  catch (e: any) {
    const msg = e?.response?.data?.detail || '操作失败'
    showToast(msg)
    await loadAll()
  }
}
async function failQuest(q: EarthQuest) {
  questActionsOpen.value = false
  if (!confirm(`放弃「${q.title}」？将扣除${q.penalty_currency} 弥娅币`))
    return
  try {
    await EarthAPI.failQuest(q.id)
    showToast('任务已失败，弥娅币已扣除')
    await loadAll()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '操作失败，请稍后再试')
  }
}
async function cancelQuest(q: EarthQuest) {
  questActionsOpen.value = false
  if (!confirm(`取消「${q.title}」？(无惩罚`))
    return
  try {
    await EarthAPI.cancelQuest(q.id)
    showToast('任务已取消')
    await loadAll()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '操作失败，请稍后再试')
  }
}

// ── 子任务进度跟踪 ──
function subtaskProgress(q: EarthQuest | null) {
  const subs = q?.subtasks || []
  const done = subs.filter(s => s.done).length
  return { subs, done, total: subs.length, all_done: subs.length > 0 && done >= subs.length }
}
async function toggleSubtask(q: EarthQuest, index: number) {
  try {
    const res = await EarthAPI.toggleSubtask(q.id, index)
    if (!res.success) {
      showToast(res.message || '更新失败')
      return
    }
    await loadAll()
    const prog = subtaskProgress(res.quest)
    if (prog.total > 0 && prog.all_done)
      showToast(`「${q.title}」全部子任务完成，可以提交委托了！✦`)
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '子任务更新失败，请稍后再试')
  }
}

// ── 签到 (v17: 先问一句昨晚睡得怎么样) ──
const checkinBusy = ref(false)
const showSleepModal = ref(false)
const sleepHours = ref(8)
function doCheckin() {
  if (checkinBusy.value)
    return
  // 已签到时不再重复请求；未签到先询问昨晚睡眠时长。
  if (checkin.value?.checked_today) {
    showToast('今天已经签到过啦，明天再来吧～')
    return
  }
  sleepHours.value = 8
  showSleepModal.value = true
}
function confirmSleepCheckin() {
  const hours = Math.max(0, Math.min(24, Number(sleepHours.value) || 0))
  performCheckin(hours)
}
function skipSleepCheckin() {
  performCheckin()
}
async function performCheckin(hours?: number) {
  if (checkinBusy.value)
    return
  checkinBusy.value = true
  try {
    const res = await EarthAPI.checkin(hours)
    if (res.success && res.reward) {
      const sleepNote = res.sleep?.note
      showToast(`✦ 签到成功！+${res.reward.currency} 弥娅币, +${res.reward.exp} 经验 · 连签 ${res.streak} 天${sleepNote ? ` · ${sleepNote}` : ''}`)
      if (res.sleep && (res.sleep.energy_bonus || res.sleep.mood_extra))
        window.setTimeout(() => showToast(`☾ 睡眠回馈: 体力 +${res.sleep?.energy_bonus ?? 0} · 心情 +${res.sleep?.mood_extra ?? 0}`), 1400)
      if (res.level_up)
        window.setTimeout(() => showToast(`✦ 升级！Lv.${res.level_up?.old_level} → Lv.${res.level_up?.new_level}，升级礼包 +${res.level_up?.reward_currency} 弥娅币`), 2600)
    }
    else {
      showToast('今天已经签到过啦，明天再来吧～')
    }
    await loadAll()
    await refreshAchievementsQuiet()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '签到失败，请稍后再试')
  }
  finally {
    showSleepModal.value = false
    checkinBusy.value = false
  }
}

// ── 称号系统 ──
const showTitles = ref(false)
async function equipTitle(title: string) {
  try {
    const res = await EarthAPI.equipTitle(title)
    if (res.success) {
      titles.value = res.titles
      showToast(`已佩戴称号「${title}」`)
      await loadAll()
    }
    else {
      showToast('佩戴失败，该称号尚未解锁')
    }
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '佩戴称号失败，请稍后再试')
  }
}

// ── 委托节 · 列表筛选 ──
const boardTab = ref<'pending' | 'ongoing' | 'done'>('pending')
const boardType = ref<'all' | 'main' | 'branch' | 'daily' | 'optional'>('all')
const selectedQuestId = ref<number | null>(null)
const boardQuests = computed(() => {
  let list: EarthQuest[] = []
  if (boardTab.value === 'pending')
    list = pendingQuests.value
  else if (boardTab.value === 'ongoing')
    list = ongoingQuests.value
  else list = doneQuests.value
  if (boardType.value !== 'all')
    list = list.filter(q => q.quest_type === boardType.value)
  return list
})
const selectedQuest = computed(() => {
  if (selectedQuestId.value) {
    const found = boardQuests.value.find(q => q.id === selectedQuestId.value)
    if (found)
      return found
  }
  return boardQuests.value[0] || null
})
function pickQuest(q: EarthQuest) {
  selectedQuestId.value = q.id
  questActionsOpen.value = false
}

const questActionsOpen = ref(false)

// ── 背包节 · 分类筛选 ──
const itemCat = ref<'all' | string>('all')
const filteredItems = computed(() =>
  itemCat.value === 'all' ? items.value : items.value.filter(i => i.category === itemCat.value),
)
function pickCat(c: string) {
  itemCat.value = c
}

// ── 剧情节 · 轮播 ──
const storyIndex = ref(0)
const storyMode = ref<'carousel' | 'book'>('carousel')
const storyWindow = computed(() => {
  const s = stories.value
  if (!s.length)
    return { prev: null as EarthStory | null, cur: null as EarthStory | null, next: null as EarthStory | null }
  const n = s.length
  const i = ((storyIndex.value % n) + n) % n
  return { prev: s[(i - 1 + n) % n], cur: s[i], next: s[(i + 1) % n] }
})
function storyStep(d: number) {
  if (!stories.value.length)
    return
  storyIndex.value = ((storyIndex.value + d) % stories.value.length + stories.value.length) % stories.value.length
}

// ── 档案节 · 编辑玩家卡 ──
const showProfileEdit = ref(false)
const profileForm = reactive({ name: '', title: '', avatar_path: '', bio: '' })
function openProfileEdit() {
  const p = player.value
  if (!p)
    return
  Object.assign(profileForm, {
    name: p.name || '玩家',
    title: p.title || '',
    avatar_path: p.avatar_path || '',
    bio: p.bio || '',
  })
  drawerItem.value = null
  drawerChar.value = null
  drawerRegion.value = null
  showProfileEdit.value = true
}
async function saveProfile() {
  try {
    await EarthAPI.updatePlayer({ ...profileForm, name: profileForm.name.trim() || '玩家' })
    showProfileEdit.value = false
    showToast('玩家卡已更新')
    await loadAll()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '玩家卡保存失败，请稍后再试')
  }
}
async function onPickProfileAvatar(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file)
    return
  try {
    const res = await EarthAPI.uploadImage(file)
    profileForm.avatar_path = res.image_path
    showToast('头像已上传～')
  }
  catch (err: any) {
    showToast(err?.response?.data?.detail || '头像上传失败，请稍后再试')
  }
  finally {
    input.value = ''
  }
}

// ── 现实资产编辑 ──
const showEarthMoneyEdit = ref(false)
const earthMoneyForm = ref(0)
function openEarthMoneyEdit() {
  earthMoneyForm.value = player.value?.earth_currency ?? 0
  showEarthMoneyEdit.value = true
}
async function saveEarthMoney() {
  try {
    await EarthAPI.updatePlayer({ earth_currency: Math.max(0, earthMoneyForm.value) })
    showEarthMoneyEdit.value = false
    showToast('现实资产已更新')
    await loadAll()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '现实资产保存失败，请稍后再试')
  }
}

// ── v17: 地球币记账 (收入/支出流水, 弥娅帮你把账记在动态里) ──
const showLedgerModal = ref(false)
const ledgerBusy = ref(false)
const ledgerForm = reactive({ amount: 0, reason: '' })
function openLedger() {
  ledgerForm.amount = 0
  ledgerForm.reason = ''
  showLedgerModal.value = true
}
async function submitLedger() {
  if (ledgerBusy.value)
    return
  const amount = Number(ledgerForm.amount)
  if (!amount) {
    showToast('金额不能为 0，正数记收入、负数记支出哦～')
    return
  }
  ledgerBusy.value = true
  try {
    const res = await EarthAPI.adjustEarthCurrency(amount, ledgerForm.reason.trim() || (amount > 0 ? '现实收入' : '现实支出'))
    showLedgerModal.value = false
    player.value = res.player
    showToast(`已记账 ${amount > 0 ? '+' : ''}${amount} 元 · 余额 ¥${res.balance.toFixed(2)}`)
    await loadAll()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '记账失败，请稍后再试')
  }
  finally {
    ledgerBusy.value = false
  }
}

// ── v17: 回忆卡池 · 抽取 ──
const pullBusy = ref(false)
const showPullModal = ref(false)
const pullResults = ref<EarthMemoryPullItem[]>([])
const pullRefundTotal = ref(0)
const pullCost = ref(0)
const miyaBalance = computed(() => player.value?.miya_currency ?? player.value?.currency ?? 0)
const pityPercent = computed(() => {
  const m = memory.value
  if (!m)
    return 0
  return Math.min(100, Math.round((m.pity / Math.max(1, m.pity_threshold)) * 100))
})
async function doMemoryPull(times: 1 | 10) {
  const m = memory.value
  if (!m || pullBusy.value)
    return
  const cost = times === 10 ? m.cost_ten : m.cost_single
  if (miyaBalance.value < cost) {
    showToast(`弥娅币不够啦，还差 ◆${cost - miyaBalance.value}，去完成委托攒一攒吧～`)
    return
  }
  pullBusy.value = true
  try {
    const res = await EarthAPI.memoryPull(times)
    pullResults.value = res.results || []
    pullRefundTotal.value = res.refund_total || 0
    pullCost.value = res.cost || cost
    showPullModal.value = true
    player.value = res.player
    await loadMemory()
    await refreshAchievementsQuiet()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '抽取失败，请稍后再试')
  }
  finally {
    pullBusy.value = false
  }
}

// ── v17: 每周纪行 · 领取档位奖励 ──
const bpClaimBusy = ref(false)
const BP_SOURCE_LABELS: Record<string, string> = {
  quest_completed: '完成委托',
  checkin: '签到',
  discovery: '区域发现',
  story: '剧情记录',
  memory_pull: '回忆抽取',
}
// 距下一档的进度 (全部达成则 100%)
const bpNextPercent = computed(() => {
  const bp = battlePass.value
  if (!bp || !bp.tiers.length)
    return 0
  const next = bp.tiers.find(t => t.threshold > bp.points)
  if (!next)
    return 100
  const prev = bp.tiers.filter(t => t.threshold <= bp.points).pop()?.threshold ?? 0
  const span = Math.max(1, next.threshold - prev)
  return Math.min(100, Math.max(0, Math.round(((bp.points - prev) / span) * 100)))
})
const bpNextHint = computed(() => {
  const bp = battlePass.value
  if (!bp)
    return ''
  const next = bp.tiers.find(t => t.threshold > bp.points)
  if (!next)
    return '全部档位已达成'
  return `距第 ${next.tier} 档还差 ${next.threshold - bp.points} 分`
})
async function claimBattlePassTier(tier: number) {
  if (bpClaimBusy.value)
    return
  bpClaimBusy.value = true
  try {
    const res = await EarthAPI.claimBattlePass(tier)
    battlePass.value = res.battle_pass
    showToast(`纪行第 ${res.tier} 档奖励已领取 · +${res.reward_currency} 弥娅币`)
    await loadAll()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '纪行奖励领取失败，请稍后再试')
  }
  finally {
    bpClaimBusy.value = false
  }
}

// ── v17: 动态流 · 弥娅小评论 ──
const showCommentModal = ref(false)
const commentTarget = ref<EarthActivity | null>(null)
const commentText = ref('')
const commentBusy = ref(false)
function openComment(a: EarthActivity) {
  commentTarget.value = a
  commentText.value = a.comment || ''
  showCommentModal.value = true
}
async function submitComment() {
  const target = commentTarget.value
  if (!target || commentBusy.value)
    return
  if (!commentText.value.trim()) {
    showToast('评论内容不能为空～')
    return
  }
  commentBusy.value = true
  try {
    const updated = await EarthAPI.commentActivity(target.id, commentText.value.trim())
    const idx = activity.value.findIndex(x => x.id === updated.id)
    if (idx >= 0)
      activity.value[idx] = updated
    showCommentModal.value = false
    showToast('评论已写下，弥娅收到啦～')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '评论失败，请稍后再试')
  }
  finally {
    commentBusy.value = false
  }
}

// ── 档案抽屉 (物品/角色) ──
const drawerItem = ref<EarthItem | null>(null)
const drawerChar = ref<EarthCharacter | null>(null)
const drawerRegion = ref<EarthWorldRegion | null>(null)
const drawerExpanded = ref(false)
function openItemDrawer(item: EarthItem) {
  drawerItem.value = item
  drawerChar.value = null
  drawerRegion.value = null
  showProfileEdit.value = false
  drawerExpanded.value = false
}
function openCharDrawer(c: EarthCharacter) {
  drawerChar.value = c
  drawerItem.value = null
  drawerRegion.value = null
  showProfileEdit.value = false
  drawerExpanded.value = false
  // 打开角色抽屉时拉取好感度变动日志
  charAffinityLogs.value = []
  charLogsBusy.value = true
  EarthAPI.affinityLogs(c.id, 30)
    .then(logs => (charAffinityLogs.value = logs))
    .catch(() => (charAffinityLogs.value = []))
    .finally(() => (charLogsBusy.value = false))
}
function openRegionDrawer(region: EarthWorldRegion) {
  drawerRegion.value = region
  drawerItem.value = null
  drawerChar.value = null
  showProfileEdit.value = false
  drawerExpanded.value = false
}
function closeDrawer() {
  drawerItem.value = null
  drawerChar.value = null
  drawerRegion.value = null
  showProfileEdit.value = false
  drawerExpanded.value = false
}

// ── v18: 服务券 · 使用背包里的互动服务券 (fields.service_ticket) ──
const ticketBusy = ref(false)
const ticketResult = ref<{ name: string, interaction: string, remaining: number } | null>(null)
async function useServiceTicket() {
  const item = drawerItem.value
  if (!item?.fields?.service_ticket || ticketBusy.value)
    return
  ticketBusy.value = true
  try {
    const res = await EarthAPI.redeemService(item.id)
    ticketResult.value = { name: res.name, interaction: res.interaction, remaining: res.remaining }
    player.value = res.player
    // 刷新背包与玩家数据, 并同步抽屉里的这张券 (用完则收起抽屉)
    await loadAll()
    const fresh = items.value.find(i => i.id === item.id)
    if (fresh)
      drawerItem.value = fresh
    else
      closeDrawer()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '服务券使用失败，请稍后再试')
  }
  finally {
    ticketBusy.value = false
  }
}
function closeTicketModal() {
  ticketResult.value = null
}

// ── 首页背景 ──
const homeBg = computed(() => {
  const p = player.value
  if (p?.avatar_path)
    return EarthAPI.imageUrl(p.avatar_path)
  const withImg = items.value.filter(i => i.image_path)
  const last = withImg.length ? withImg[withImg.length - 1] : undefined
  if (last?.image_path)
    return EarthAPI.imageUrl(last.image_path)
  return ''
})
const homeBgStyle = computed(() => (homeBg.value ? { backgroundImage: `url(${homeBg.value})` } : {}))
const pinnedNotes = computed(() => notes.value.filter(n => n.pinned).slice(0, 3))
const latestNote = computed(() => pinnedNotes.value[0] || notes.value[0] || null)

function fieldChips(fields: Record<string, any> | undefined, limit = 3): Array<[string, any]> {
  if (!fields)
    return []
  return Object.entries(fields).slice(0, limit)
}
function formatDate(iso: string): string {
  if (!iso)
    return ''
  return iso.replace('T', ' ').slice(0, 16)
}
function shortDate(iso: string): string {
  return iso ? iso.slice(5, 10) : ''
}

// ── 数据中心: 签到足迹近 28 天 ──
const checkinDays = computed(() => {
  const set = new Set(checkin.value?.history.map(h => h.date) || [])
  const days: Array<{ date: string, checked: boolean, day: number }> = []
  const today = new Date()
  for (let i = 27; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    days.push({ date: iso, checked: set.has(iso), day: d.getDate() })
  }
  return days
})

const MAX_TREND = computed(() => {
  const trend = stats.value?.quests?.trend_7d || []
  return Math.max(1, ...trend.map((d: { count?: number }) => d.count || 0), 1)
})
const STATS_ITEM_RARITY_ORDER = ['legendary', 'epic', 'rare', 'uncommon', 'common']
const STATS_ITEM_CAT_ORDER = ['digital', 'book', 'life', 'food', 'tool', 'clothing', 'collectible', 'other']
// 到期标记: 3 天内视为即将到期
const dueHorizonIso = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() + 3)
  return d.toISOString()
})
const unlockedAchievements = computed(() => achievements.value.filter(a => a.unlocked_at))
function achievementShown(a: EarthAchievement) {
  return !!a.unlocked_at || !a.hidden
}
</script>

<template>
  <div class="pv" :class="{ 'miya-skin': isMiyaDefaultTheme }" :style="themeVars">
    <!-- 全局壁纸背景 (外观设置可选) -->
    <div v-if="theme.background" class="pv-wallpaper" :style="{ backgroundImage: `url(${wallpaperUrl(theme.background)})`, opacity: theme.background_opacity }" />
    <!-- 顶部渐变黑幕 + 固定导航 (鸣潮 c2f 风格) -->
    <div class="pv-banner" />
    <header class="pv-nav">
      <button class="pv-nav-logo" type="button" aria-label="返回地球online首页" @click="goTo(0)">
        <span class="pv-nav-logo-glyph">地</span>
        <span class="pv-nav-logo-text">地球online</span>
      </button>
      <nav class="pv-nav-center" aria-label="地球online主要板块">
        <a
          v-for="group in NAV_GROUPS"
          :key="group.id"
          href="#"
          :class="{ active: isNavGroupActive(group) }"
          :aria-current="isNavGroupActive(group) ? 'page' : undefined"
          @click.prevent="goTo(group.target)"
        >
          <span class="nv-deco" />
          {{ group.label }}
        </a>
      </nav>
      <div class="pv-nav-side">
        <button class="pv-nav-avatar" type="button" aria-label="打开玩家档案" @click="goTo(5)">
          <img v-if="player?.avatar_path" :src="EarthAPI.imageUrl(player.avatar_path)" alt="" />
          <template v-else>地</template>
        </button>
        <div class="pv-nav-id">
          <span class="pv-nav-name">{{ player?.name || '玩家' }}</span>
          <span class="pv-nav-level">Lv.{{ player?.level ?? 1 }}</span>
          <i class="pv-nav-xp"><em :style="{ width: `${expProgress(player?.exp ?? 0, player?.level ?? 1)}%` }" /></i>
        </div>
        <div class="pv-nav-coins">
          <div class="pv-nav-coin miya" title="弥娅币 · 弥娅发放的互动货币">{{ formatMiyaCoins(player?.miya_currency ?? player?.currency ?? 0) }}</div>
          <button class="pv-nav-coin earth" type="button" :title="`地球币/现实资产 (${EARTH_MONEY_LABELS[earthMoneyMode]}显示, 点击切换)`" @click="switchEarthMoney">
            {{ formatEarthMoney(player?.earth_currency ?? 0) }}
            <span class="pv-nav-coin-switch">⇄</span>
          </button>
        </div>
        <button
          class="pv-nav-care"
          :class="{ due: dueSoonList.length > 0, checkin: dueSoonList.length === 0 && !checkin?.checked_today }"
          :title="dueSoonList.length > 0 ? `${dueSoonList.length} 个委托即将到期, 点击查看` : (!checkin?.checked_today ? '还没签到, 点击一键签到' : '一切安好, 去看动态流')"
          @click="onCareClick"
        >
          <template v-if="dueSoonList.length > 0">⚑ {{ dueSoonList.length }}</template>
          <template v-else-if="!checkin?.checked_today">◷</template>
          <template v-else>✦</template>
        </button>
      </div>
      <div v-if="activeSubnav.length" class="pv-context-nav" :data-context="activeNavGroup.id">
        <span class="pv-context-label">{{ activeNavGroup.label }} <i>/</i></span>
        <button
          v-for="item in activeSubnav"
          :key="item.target"
          type="button"
          class="pv-context-item"
          :class="{ active: activeSection === item.target }"
          :aria-current="activeSection === item.target ? 'page' : undefined"
          @click="goTo(item.target)"
        >
          <span>{{ item.label }}</span><small>{{ item.en }}</small>
        </button>
      </div>
    </header>

    <!-- 板块舞台: 顶部 Tab 切换, 当前板块整页自由滚动 -->
    <main ref="stageEl" class="pv-stage" :class="{ 'has-context-nav': activeSubnav.length }">
      <!-- ═══ 1 首页 · 现实生活指挥舱 ═══ -->
      <section v-show="activeSection === 0" class="pv-section pv-home">
        <div class="pv-home-bg" :style="homeBgStyle" />
        <div class="pv-home-veil" />
        <div class="pv-command-deck">
          <div class="pv-command-copy">
            <p class="pv-home-en">EARTH ONLINE · REALITY OPERATING SYSTEM</p>
            <h1 class="pv-home-title">地球online</h1>
            <p class="pv-home-welcome">{{ player?.name || '玩家' }}，欢迎回来。<template v-if="player?.title">「{{ player.title }}」</template></p>
            <div class="pv-home-rule"><span /> <b>MIYA / FIELD COMMAND</b> <span /></div>
          </div>

          <div class="pv-home-feature">
            <aside class="pv-home-player">
              <div class="pv-panel-kicker">PLAYER PROFILE <span>SYS / 01</span></div>
              <button class="pv-home-portrait" type="button" aria-label="打开玩家档案" @click="goTo(5)">
                <img v-if="player?.avatar_path" :src="EarthAPI.imageUrl(player.avatar_path)" alt="" />
                <span v-else>地</span>
              </button>
              <div class="pv-home-player-copy"><strong>{{ player?.name || '玩家' }}</strong><small>Lv.{{ player?.level ?? 1 }} · {{ player?.title || '地球online 玩家' }}</small></div>
              <div class="pv-home-xp"><div><span>开拓经验</span><b>{{ player?.exp ?? 0 }} EXP</b></div><i><em :style="{ width: `${expProgress(player?.exp ?? 0, player?.level ?? 1)}%` }" /></i></div>
            </aside>

            <div class="pv-home-action">
              <div class="pv-panel-kicker">TODAY'S NEXT STEP <span>MISSION / {{ ongoingQuests.length ? 'ACTIVE' : 'READY' }}</span></div>
              <div v-if="todayAction" class="pv-home-action-main">
                <span class="pv-mission-mark">◎</span>
                <div><small>{{ todayAction.action === 'checkin' ? 'DAILY RITUAL' : 'FIELD DIRECTIVE' }}</small><h2>{{ todayAction.title }}</h2><p>{{ todayAction.detail }}</p></div>
                <button type="button" class="pv-command-primary" @click="openTodayAction(todayAction.action)">{{ todayAction.label }}</button>
              </div>
              <div class="pv-mission-counts"><span><b>{{ ongoingQuests.length }}</b> 进行中</span><span><b>{{ pendingQuests.length }}</b> 待接取</span><span><b>{{ dueSoonList.length }}</b> 临近到期</span></div>
              <button v-if="latestNote" type="button" class="pv-command-note" aria-label="查看弥娅寄语" @click="goTo(6)"><span>{{ MOOD_ICONS[latestNote.mood] || '✦' }}</span><div><small>弥娅寄语 · {{ formatDate(latestNote.created_at).slice(0, 10) }}</small><p>{{ latestNote.content }}</p></div><b>↗</b></button>
            </div>
          </div>

          <div class="pv-home-status">
            <div class="pv-home-status-block pv-home-status-player">
              <div class="pv-home-status-label">FIELD STATUS</div>
              <div class="pv-home-status-values">
                <div><b>{{ formatMiyaCoins(player?.miya_currency ?? player?.currency ?? 0) }}</b><span>弥娅币</span></div>
                <button type="button" @click="switchEarthMoney"><b>{{ formatEarthMoney(player?.earth_currency ?? 0) }}</b><span>现实资产 ⇄</span></button>
                <div v-for="attr in (player?.attrs || []).slice(0, 2)" :key="attr.key"><b>{{ attr.value }}</b><span>{{ attr.label }}</span></div>
              </div>
            </div>
            <div class="pv-home-status-block pv-home-status-reality">
              <div class="pv-home-status-label">REALITY LINK</div>
              <div class="pv-home-reality-copy">
                <span v-if="lifeHub" :class="{ warning: lifeHub.facts.real_context.source_status !== 'ok' || lifeHub.facts.real_context.is_stale }">◎ {{ lifeHubRealityLabel }}</span>
                <span v-if="lifeHub" :class="{ quiet: lifeHub.facts.operator.in_quiet_hours }">✦ {{ lifeHubOperatorLabel }}</span>
                <span v-if="worldStatus">{{ worldStatus.period_icon }} {{ worldStatus.period }} · {{ worldStatus.weather_icon }} {{ worldStatus.weather }}</span>
                <span :class="{ done: checkin?.checked_today }">◷ 连签 {{ checkin?.streak ?? 0 }} 天 · {{ checkin?.checked_today ? '今日已签到' : '等待签到' }}</span>
                <button type="button" @click="doCheckin">{{ checkin?.checked_today ? '查看签到记录' : '完成今日签到' }}</button>
              </div>
            </div>
            <div class="pv-home-status-block pv-home-status-world">
              <div class="pv-home-status-label">WORLD SIGNAL</div>
              <div class="pv-world-signal-main">
                <strong>{{ worldRegions.filter(r => r.discovered).length }}<small>/{{ worldRegions.length }}</small></strong>
                <span>区域已同步</span>
              </div>
              <button type="button" class="pv-world-signal-link" @click="goTo(7)">展开世界图谱 <b>↗</b></button>
            </div>
          </div>

          <div class="pv-home-menu pv-command-menu">
            <button v-for="group in NAV_GROUPS.slice(1)" :key="group.id" type="button" class="pv-home-card" @click="goTo(group.target)"><span class="pv-home-card-en">{{ group.en }}</span><span class="pv-home-card-name">{{ group.label }}</span><span class="pv-command-menu-arrow">↗</span></button>
          </div>
          <div v-if="degradedModules.length" class="pv-degraded">◇ 部分增强模块暂不可用：{{ degradedModules.join('、') }}。核心档案与委托仍可正常使用。</div>
        </div>
        <button class="pv-home-checkin" :class="{ done: checkin?.checked_today }" @click="doCheckin"><span class="pv-home-checkin-main">{{ checkin?.checked_today ? '已签到' : '每日签到' }}</span><span class="pv-home-checkin-sub">连签 {{ checkin?.streak ?? 0 }} 天</span></button>
        <button type="button" class="pv-home-scroll" aria-label="开始探索委托" @click="goTo(1)">
          <span>OPEN QUEST BOARD</span><span class="pv-home-scroll-arrow">⌄</span>
        </button>
      </section>

      <!-- ═══ 2 委托 (仿鸣潮 News) ═══ -->
      <section v-show="activeSection === 1" class="pv-section pv-board">
        <div class="pv-board-wrap">
          <div class="pv-board-left">
            <div class="pv-board-head">
              <p class="pv-board-title">委托</p>
              <span class="pv-board-en">QUEST BOARD</span>
              <div class="pv-line" />
              <div class="pv-board-tabs">
                <a v-for="t in [['pending', '待接取'], ['ongoing', '进行中'], ['done', '已结束']] as const" :key="t[0]" href="#" :class="{ active: boardTab === t[0] }" @click.prevent="boardTab = t[0]">
                  {{ t[1] }} <b class="pv-tab-count">{{ t[0] === 'pending' ? pendingQuests.length : t[0] === 'ongoing' ? ongoingQuests.length : doneQuests.length }}</b><div class="pv-tab-underline" />
                </a>
                <span class="pv-board-type-filter">
                  <a v-for="t in [['all', '全部'], ['main', '主线'], ['branch', '支线'], ['daily', '日常'], ['optional', '可选']] as const" :key="t[0]" href="#" :class="{ active: boardType === t[0] }" @click.prevent="boardType = t[0]">{{ t[1] }}</a>
                </span>
              </div>
              <div class="pv-line" />
            </div>
            <div class="pv-board-list">
              <div v-if="boardQuests.length === 0" class="pv-empty">
                {{ boardTab === 'pending' ? '暂时没有新委托，去后台让弥娅给你安排一个吧～' : boardTab === 'ongoing' ? '没有进行中的任务～' : '还没有已结束的任务～' }}
              </div>
              <button v-for="q in boardQuests" :key="q.id" type="button" class="pv-board-item" :class="{ active: selectedQuest?.id === q.id }" :aria-pressed="selectedQuest?.id === q.id" @click="pickQuest(q)">
                <span class="pv-board-item-type" :style="{ color: QUEST_TYPE_COLORS[q.quest_type] || '#888' }">{{ QUEST_TYPE_LABELS[q.quest_type] || q.quest_type }}</span>
                <span v-if="q.recurring === 'daily' || q.recurring === 'weekly'" class="pv-board-item-rec" :title="q.recurring === 'daily' ? '每天循环' : '每周循环'">↻</span>
                <span class="pv-board-item-title">{{ q.title }}</span>
                <span class="pv-board-item-meta">{{ stars(q.difficulty) }}<small v-if="q.subtasks?.length">{{ subtaskProgress(q).done }}/{{ q.subtasks.length }}</small></span>
                <span v-if="q.deadline && q.deadline < dueHorizonIso" class="pv-board-item-due" :class="{ overdue: q.deadline < new Date().toISOString() }">
                  {{ q.deadline < new Date().toISOString() ? '已逾期' : '即将到期' }}
                </span>
                <span v-if="q.status === 'completed'" class="pv-board-item-status done">✓</span>
                <span v-else-if="q.status === 'failed'" class="pv-board-item-status failed">✕</span>
                <span v-else-if="q.status === 'cancelled'" class="pv-board-item-status">−</span>
                <span class="pv-board-item-underline" />
              </button>
            </div>
            <!-- 历史归档: 和列表同属左侧栏，避免挤成第三列 -->
            <div class="pv-board-history">
              <button class="pv-board-history-toggle" @click="showQuestHistory = !showQuestHistory">
                <span>≣ 历史归档 · {{ questHistoryList.length }} 份</span>
                <span class="pv-board-history-arrow" :class="{ open: showQuestHistory }">{{ showQuestHistory ? '▴' : '▾' }}</span>
              </button>
              <div v-if="showQuestHistory" class="pv-board-history-list">
                <div v-if="questHistoryList.length === 0" class="pv-empty">还没有归档的委托～</div>
                <button v-for="q in questHistoryList" :key="q.id" type="button" class="pv-board-history-item" :class="q.status" @click="pickQuest(q); boardTab = 'done'">
                  <span class="pv-board-history-mark">{{ q.status === 'completed' ? '✓' : q.status === 'failed' ? '✕' : '−' }}</span>
                  <span class="pv-board-history-title">{{ q.title }}</span>
                  <span class="pv-board-history-time">{{ formatDate(q.completed_at || q.created_at || '') }}</span>
                </button>
              </div>
            </div>
          </div>
          <div class="pv-board-right">
            <template v-if="selectedQuest">
              <div class="pv-quest-show">
                <div class="pv-quest-show-type" :style="{ borderColor: QUEST_TYPE_COLORS[selectedQuest.quest_type] || '#888', color: QUEST_TYPE_COLORS[selectedQuest.quest_type] || '#888' }">
                  {{ QUEST_TYPE_LABELS[selectedQuest.quest_type] || selectedQuest.quest_type }}
                </div>
                <div class="pv-quest-show-kicker"><span>FIELD DIRECTIVE</span><b :class="`status-${selectedQuest.status}`">{{ selectedQuest.status === 'pending' ? 'READY' : selectedQuest.status === 'ongoing' ? 'LIVE' : 'ARCHIVED' }}</b></div>
                <h3 class="pv-quest-show-title">{{ selectedQuest.title }}</h3>
                <div class="pv-quest-show-stars">{{ stars(selectedQuest.difficulty) }}</div>
                <p v-if="selectedQuest.description" class="pv-quest-show-desc">{{ selectedQuest.description }}</p>
                <div class="pv-quest-show-meta">
                  <div class="pv-quest-show-cell"><span class="k">奖励</span><span class="v gold">+{{ selectedQuest.reward_currency }} 弥娅币 · +{{ selectedQuest.reward_exp }} 经验</span></div>
                  <div class="pv-quest-show-cell"><span class="k">鸽了惩罚</span><span class="v red">-{{ selectedQuest.penalty_currency || 0 }} 弥娅币</span></div>
                  <div class="pv-quest-show-cell"><span class="k">截止</span><span class="v">{{ selectedQuest.deadline ? formatDate(selectedQuest.deadline) : '不限时' }}</span></div>
                  <div class="pv-quest-show-cell"><span class="k">循环</span><span class="v">{{ (selectedQuest.recurring === 'daily' && '每天循环 ↻') || (selectedQuest.recurring === 'weekly' && '每周循环 ↻') || '一次性' }}</span></div>
                </div>
                <!-- 子任务进度跟踪 -->
                <div v-if="subtaskProgress(selectedQuest).total > 0" class="pv-quest-subtasks">
                  <div class="pv-quest-subtasks-head">
                    <span class="pv-quest-subtasks-title">任务进度</span>
                    <span class="pv-quest-subtasks-num">{{ subtaskProgress(selectedQuest).done }} / {{ subtaskProgress(selectedQuest).total }}</span>
                  </div>
                  <div class="pv-quest-subtasks-bar">
                    <div class="pv-quest-subtasks-fill" :style="{ width: `${Math.round(subtaskProgress(selectedQuest).done / subtaskProgress(selectedQuest).total * 100)}%` }" />
                  </div>
                  <label
                    v-for="(sub, i) in subtaskProgress(selectedQuest).subs"
                    :key="i"
                    class="pv-quest-subtask"
                    :class="{ done: sub.done }"
                  >
                    <input
                      type="checkbox"
                      :checked="!!sub.done"
                      :disabled="!['pending', 'ongoing'].includes(selectedQuest.status)"
                      @change="toggleSubtask(selectedQuest, i)"
                    />
                    <span class="pv-quest-subtask-mark">{{ sub.done ? '◉' : '○' }}</span>
                    <span class="pv-quest-subtask-text">{{ sub.text }}</span>
                  </label>
                </div>
                <div v-if="selectedQuest.status === 'ongoing' && subtaskProgress(selectedQuest).total > 0 && !subtaskProgress(selectedQuest).all_done" class="pv-quest-subtasks-hint">
                  ◈ 勾选全部子任务后才能提交委托                </div>
                <div class="pv-quest-show-actions">
                  <button v-if="selectedQuest.status === 'pending'" class="pv-btn-accept" @click="acceptQuest(selectedQuest)">⚔ 接取委托</button>
                  <template v-else-if="selectedQuest.status === 'ongoing'">
                    <button class="pv-btn-primary" :disabled="subtaskProgress(selectedQuest).total > 0 && !subtaskProgress(selectedQuest).all_done" @click="completeQuest(selectedQuest)">✦ 完成</button>
                    <div class="pv-quest-more">
                      <button class="pv-btn-ghost pv-quest-more-toggle" :aria-expanded="questActionsOpen" @click="questActionsOpen = !questActionsOpen">⋯ 更多</button>
                      <div v-if="questActionsOpen" class="pv-quest-more-menu">
                        <button class="pv-btn-ghost" @click="cancelQuest(selectedQuest)">取消委托</button>
                        <button class="pv-btn-danger" @click="failQuest(selectedQuest)">放弃委托</button>
                      </div>
                    </div>
                  </template>
                  <span v-else class="pv-quest-show-done">{{ selectedQuest.status === 'completed' ? '✓ 已完成' : selectedQuest.status === 'failed' ? '✕ 已失败' : '− 已取消' }} {{ formatDate(selectedQuest.completed_at || '') }}</span>
                </div>
              </div>
            </template>
            <div v-else class="pv-empty">在左侧选择一份委托查看详情～</div>
          </div>
        </div>
      </section>

      <!-- ═══ 3 背包照片墙 (图封面方格, 大小不一整齐排列) ═══ -->
      <section v-show="activeSection === 2" class="pv-section pv-items">
        <div class="pv-items-wrap">
          <div class="pv-items-head">
            <div>
              <span class="pv-items-en">BACKPACK</span>
              <h3 class="pv-items-title">{{ itemCat === 'all' ? '我的背包' : CATEGORY_LABELS[itemCat] || itemCat }}</h3>
            </div>
            <span class="pv-currency" title="弥娅币 · 弥娅发放的互动货币">{{ formatMiyaCoins(player?.miya_currency ?? player?.currency ?? 0) }}</span>
          </div>
          <div class="pv-items-filters">
            <button v-for="c in ['all', 'digital', 'book', 'life', 'food', 'tool', 'clothing', 'collectible', 'other']" :key="c" class="pv-filter-chip" :class="{ active: itemCat === c }" @click="pickCat(c)">
              {{ ITEM_CAT_ICONS[c] || '◇' }} {{ c === 'all' ? '全部' : CATEGORY_LABELS[c] || c }}
            </button>
          </div>
          <div class="pv-line" />
          <div v-if="filteredItems.length === 0" class="pv-empty">这个分类还没有物品，去后台录入你的收藏吧～</div>
          <div v-else class="pv-wall">
            <div v-for="item in filteredItems" :key="item.id" class="pv-wall-card" role="button" tabindex="0" :aria-label="`查看物品 ${item.name}`" :style="{ borderColor: `${RARITY_COLORS[item.rarity]}55` }" @click="openItemDrawer(item)" @keydown.enter.prevent="openItemDrawer(item)" @keydown.space.prevent="openItemDrawer(item)">
              <div class="pv-wall-cover" :class="{ ph: !item.image_path }">
                <img v-if="item.image_path" :src="EarthAPI.imageUrl(item.image_path)" class="pv-wall-img" alt="" />
                <span v-else class="pv-wall-ph">{{ item.name[0] }}</span>
                <span class="pv-wall-rarity" :style="{ background: RARITY_COLORS[item.rarity] }">{{ RARITY_LABELS[item.rarity] }}</span>
                <span v-if="item.quantity > 1" class="pv-wall-qty">×{{ item.quantity }}</span>
              </div>
              <div class="pv-wall-info">
                <div class="pv-wall-name">{{ item.name }}</div>
                <div class="pv-wall-sub">{{ CATEGORY_LABELS[item.category] || item.category }}<template v-if="item.description"> · {{ item.description.slice(0, 24) }}<template v-if="item.description.length > 24">…</template></template></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ═══ 4 角色图鉴 (角色卡照片墙) ═══ -->
      <section v-show="activeSection === 3" class="pv-section pv-chars">
        <div class="pv-chars-wrap">
          <div class="pv-items-head">
            <div>
              <span class="pv-items-en">CHARACTERS</span>
              <h3 class="pv-items-title">角色图鉴</h3>
            </div>
            <span class="pv-currency">{{ characters.length }} 位角色</span>
          </div>
          <div class="pv-line" />
          <div v-if="characters.length === 0" class="pv-empty">图鉴还没有角色，去后台添加一位重要的人吧～</div>
          <div v-else class="pv-wall pv-chars-wall">
            <div v-for="c in characters" :key="c.id" class="pv-char-card" role="button" tabindex="0" :aria-label="`查看角色 ${c.name}`" @click="openCharDrawer(c)" @keydown.enter.prevent="openCharDrawer(c)" @keydown.space.prevent="openCharDrawer(c)">
              <div class="pv-char-card-cover" :class="{ ph: !c.avatar_path }">
                <img v-if="c.avatar_path" :src="EarthAPI.imageUrl(c.avatar_path)" class="pv-char-card-img" alt="" />
                <span v-else class="pv-char-card-ph" :style="{ background: `hsl(${(c.id * 47) % 360}, 60%, 40%)` }">{{ c.name[0] }}</span>
              </div>
              <div class="pv-char-card-info">
                <div class="pv-char-card-name">{{ c.name }}<span v-if="c.nickname" class="pv-char-card-nick">「{{ c.nickname }}」</span></div>
                <div class="pv-char-card-rel">{{ RELATIONSHIP_LABELS[c.relationship] || c.relationship }} · <span :style="{ color: affinityLevel(c.affinity).color }">{{ affinityLevel(c.affinity).label }}</span></div>
                <div class="pv-char-card-aff">
                  <div class="pv-char-card-aff-bar"><div class="pv-char-card-aff-fill" :style="{ width: `${c.affinity}%` }" /></div>
                  <span class="pv-char-card-aff-num">{{ c.affinity }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ═══ 5 剧情 (轮播 / 书本 双模式 ═══ -->
      <section v-show="activeSection === 4" class="pv-section pv-story">
        <!-- 模式切换 -->
        <div class="pv-story-mode">
          <button class="pv-story-mode-btn" :class="{ active: storyMode === 'carousel' }" @click="storyMode = 'carousel'">◈ 轮播模式</button>
          <button class="pv-story-mode-btn" :class="{ active: storyMode === 'book' }" @click="storyMode = 'book'">≋ 书本模式</button>
        </div>

        <!-- 轮播模式 (仿鸣潮 Lore) -->
        <div v-if="storyMode === 'carousel'" class="pv-story-wrap">
          <div class="pv-story-left">
            <article
              v-if="storyWindow.cur"
              class="pv-story-archive"
              :class="{ 'has-image': storyWindow.cur.image_path }"
              :style="storyWindow.cur.image_path ? { backgroundImage: `url(${EarthAPI.imageUrl(storyWindow.cur.image_path)})` } : {}"
            >
              <div class="pv-story-archive-top">
                <span class="pv-story-archive-mark">≋</span>
                <div>
                  <span class="pv-story-archive-en">STORY ARCHIVE</span>
                  <span class="pv-story-archive-cn">人生剧情</span>
                </div>
                <span class="pv-story-archive-page">
                  {{ String(storyIndex + 1).padStart(2, '0') }} / {{ String(stories.length).padStart(2, '0') }}
                </span>
              </div>

              <div v-if="!storyWindow.cur.image_path" class="pv-story-archive-fallback">
                <span>≋</span>
                <small>PERSONAL NARRATIVE · {{ String(storyIndex + 1).padStart(2, '0') }}</small>
              </div>

              <div class="pv-story-archive-body">
                <div class="pv-story-meta">
                  <span class="pv-story-type">{{ EVENT_TYPE_LABELS[storyWindow.cur.event_type] || storyWindow.cur.event_type }}</span>
                  <span class="pv-story-time">{{ formatDate(storyWindow.cur.happened_at) }}</span>
                </div>
                <h4 class="pv-story-cur-title">{{ storyWindow.cur.title }}</h4>
                <div class="pv-story-content pv-story-archive-excerpt">
                  <Markdown v-if="storyWindow.cur.content" :source="storyWindow.cur.content" />
                  <p v-else>这段剧情还没有正文～</p>
                </div>
                <div class="pv-story-archive-nav">
                  <button :disabled="stories.length < 2" aria-label="上一段剧情" @click="storyStep(-1)">‹</button>
                  <span>SWITCH RECORD</span>
                  <button :disabled="stories.length < 2" aria-label="下一段剧情" @click="storyStep(1)">›</button>
                </div>
              </div>
            </article>
            <div v-else class="pv-story-archive pv-story-archive-empty">
              <span class="pv-story-archive-mark">≋</span>
              <strong>STORY ARCHIVE</strong>
              <p>还没有剧情，每一天都可以是故事～</p>
            </div>
           </div>
          <div class="pv-story-right">
            <button class="pv-story-arrow" :disabled="stories.length < 2" @click="storyStep(-1)">‹</button>
            <div class="pv-story-router">
              <div v-if="storyWindow.prev" class="pv-story-card side" role="button" tabindex="0" :aria-label="`查看上一段剧情 ${storyWindow.prev.title}`" :style="storyWindow.prev.image_path ? { backgroundImage: `linear-gradient(180deg, rgba(7,8,12,0.55), rgba(7,8,12,0.85)), url(${EarthAPI.imageUrl(storyWindow.prev.image_path)})` } : {}" @click="storyStep(-1)" @keydown.enter.prevent="storyStep(-1)" @keydown.space.prevent="storyStep(-1)">
                <span class="pv-story-card-type">{{ EVENT_TYPE_LABELS[storyWindow.prev.event_type] || storyWindow.prev.event_type }}</span>
                <div class="pv-story-card-title">{{ storyWindow.prev.title }}</div>
                <div class="pv-story-card-time">{{ formatDate(storyWindow.prev.happened_at) }}</div>
              </div>
              <div v-if="storyWindow.cur" class="pv-story-card main" :style="storyWindow.cur.image_path ? { backgroundImage: `linear-gradient(180deg, rgba(7,8,12,0.5), rgba(7,8,12,0.85)), url(${EarthAPI.imageUrl(storyWindow.cur.image_path)})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}">
                <span class="pv-story-card-type">{{ EVENT_TYPE_LABELS[storyWindow.cur.event_type] || storyWindow.cur.event_type }}</span>
                <div class="pv-story-card-title">{{ storyWindow.cur.title }}</div>
                <div class="pv-story-card-time">{{ formatDate(storyWindow.cur.happened_at) }}</div>
              </div>
              <div v-if="storyWindow.next" class="pv-story-card side" role="button" tabindex="0" :aria-label="`查看下一段剧情 ${storyWindow.next.title}`" :style="storyWindow.next.image_path ? { backgroundImage: `linear-gradient(180deg, rgba(7,8,12,0.55), rgba(7,8,12,0.85)), url(${EarthAPI.imageUrl(storyWindow.next.image_path)})` } : {}" @click="storyStep(1)" @keydown.enter.prevent="storyStep(1)" @keydown.space.prevent="storyStep(1)">
                <span class="pv-story-card-type">{{ EVENT_TYPE_LABELS[storyWindow.next.event_type] || storyWindow.next.event_type }}</span>
                <div class="pv-story-card-title">{{ storyWindow.next.title }}</div>
                <div class="pv-story-card-time">{{ formatDate(storyWindow.next.happened_at) }}</div>
              </div>
            </div>
            <button class="pv-story-arrow" :disabled="stories.length < 2" @click="storyStep(1)">›</button>
          </div>
        </div>

        <!-- 书本模式 (对开书页: 左目录右正文) -->
        <div v-else class="pv-book">
          <div class="pv-book-page pv-book-toc">
            <div class="pv-book-toc-head">
              <span class="pv-book-toc-en">CONTENTS</span>
              <span class="pv-book-toc-title">人生剧情 · 目录</span>
            </div>
            <div class="pv-book-toc-list">
              <div
                v-for="(s, i) in stories"
                :key="s.id"
                class="pv-book-toc-item"
                :class="{ active: storyWindow.cur?.id === s.id }"
                @click="storyIndex = i"
              >
                <span class="pv-book-toc-no">{{ String(i + 1).padStart(2, '0') }}</span>
                <div class="pv-book-toc-body">
                  <div class="pv-book-toc-name">{{ s.title }}</div>
                  <div class="pv-book-toc-meta">{{ EVENT_TYPE_LABELS[s.event_type] || s.event_type }} · {{ formatDate(s.happened_at) }}</div>
                </div>
              </div>
              <div v-if="stories.length === 0" class="pv-empty">还没有剧情，每一天都可以是故事～</div>
            </div>
          </div>
          <div class="pv-book-spine" />
          <div class="pv-book-page pv-book-content">
            <template v-if="storyWindow.cur">
              <div class="pv-book-content-head">
                <span class="pv-book-content-type">{{ EVENT_TYPE_LABELS[storyWindow.cur.event_type] || storyWindow.cur.event_type }}</span>
                <span class="pv-book-content-time">{{ formatDate(storyWindow.cur.happened_at) }}</span>
              </div>
              <h3 class="pv-book-content-title">{{ storyWindow.cur.title }}</h3>
              <img v-if="storyWindow.cur.image_path" :src="EarthAPI.imageUrl(storyWindow.cur.image_path)" class="pv-book-content-img" alt="" />
              <div class="pv-book-content-md">
                <Markdown v-if="storyWindow.cur.content" :source="storyWindow.cur.content" />
                <p v-else class="pv-empty">这段剧情还没有正文～</p>
              </div>
            </template>
            <div v-else class="pv-empty">还没有剧情～</div>
            <div class="pv-book-content-foot">
              <button class="pv-btn-ghost pv-book-nav-btn" :disabled="stories.length < 2" @click="storyStep(-1)">‹ 上一章</button>
              <span class="pv-book-page-no">{{ stories.length ? storyIndex + 1 : 0 }} / {{ stories.length }}</span>
              <button class="pv-btn-ghost pv-book-nav-btn" :disabled="stories.length < 2" @click="storyStep(1)">下一章 ›</button>
            </div>
          </div>
        </div>
      </section>

      <!-- ═══ 6 玩家档案 (仿鸣潮 Regions) ═══ -->
      <section v-show="activeSection === 5" class="pv-section pv-profile">
        <div class="pv-profile-bg" :style="homeBgStyle" />
        <div class="pv-profile-veil" />
        <div class="pv-profile-wrap">
          <div class="pv-profile-hero">
            <div class="pv-profile-avatar">
              <img v-if="player?.avatar_path" :src="EarthAPI.imageUrl(player.avatar_path)" alt="" />
              <span v-else>地</span>
            </div>
            <div class="pv-profile-id">
              <h2 class="pv-profile-name">{{ player?.name || '玩家' }}</h2>
              <p class="pv-profile-title">
                <button class="pv-title-badge" @click="showTitles = true">「{{ titles?.equipped || '地球online 玩家' }}」▾</button>
              </p>
              <p class="pv-profile-en">Lv.{{ player?.level ?? 1 }} · EXP {{ player?.exp ?? 0 }}</p>
              <div class="pv-profile-money">
                <div class="pv-profile-money-item" title="弥娅发放的互动货币">
                  <span class="pv-profile-money-label">弥娅币</span>
                  <span class="pv-profile-money-num gold">{{ formatMiyaCoins(player?.miya_currency ?? player?.currency ?? 0) }}</span>
                </div>
                <div class="pv-profile-money-item clickable" :title="`现实资产 (自己记录, 点击修改, 当前${EARTH_MONEY_LABELS[earthMoneyMode]}显示)`" @click="openEarthMoneyEdit">
                  <span class="pv-profile-money-label">
                    地球币 · 现实资产 ⇄
                    <button class="pv-ledger-btn" title="记一笔现实收入 / 支出，弥娅帮你写进动态流" @click.stop="openLedger">✎ 记账</button>
                  </span>
                  <span class="pv-profile-money-num">{{ formatEarthMoney(player?.earth_currency ?? 0) }}</span>
                </div>
              </div>
            </div>
            <button class="pv-btn-primary pv-profile-edit" @click="openProfileEdit">✎ 编辑玩家卡</button>
          </div>
          <div class="pv-profile-attrs">
            <div v-for="attr in (player?.attrs || [])" :key="attr.key" class="pv-profile-attr" :class="{ low: attr.key === 'energy' && attr.value < 20 }">
              <span class="pv-profile-attr-label">{{ attr.label || attr.key }}</span>
              <div class="pv-attr-bar"><div class="pv-attr-fill" :style="{ width: `${Math.min(100, (attr.value / (attr.max || 100)) * 100)}%` }" /></div>
              <span class="pv-profile-attr-value">{{ attr.value }}/{{ attr.max || 100 }}</span>
            </div>
          </div>
          <div class="pv-profile-bio">
            <Markdown v-if="player?.bio" :source="player.bio" />
            <p v-else class="pv-empty">还没有自我介绍～ 点右上角「编辑玩家卡」，用 Markdown 写一段关于自己的文字吧～</p>
          </div>
          <div class="pv-profile-career">
            <div class="pv-career-item"><span class="pv-career-num">{{ player?.total_completed ?? 0 }}</span><span class="pv-career-label">完成任务</span></div>
            <div class="pv-career-item"><span class="pv-career-num">{{ player?.total_failed ?? 0 }}</span><span class="pv-career-label">失败任务</span></div>
            <div class="pv-career-item"><span class="pv-career-num">{{ items.length }}</span><span class="pv-career-label">背包物品</span></div>
            <div class="pv-career-item"><span class="pv-career-num">{{ characters.length }}</span><span class="pv-career-label">图鉴角色</span></div>
            <div class="pv-career-item"><span class="pv-career-num">{{ stories.length }}</span><span class="pv-career-label">剧情记录</span></div>
            <div class="pv-career-item"><span class="pv-career-num">{{ checkin?.total_days ?? 0 }}</span><span class="pv-career-label">签到天数</span></div>
          </div>
        </div>
      </section>

      <!-- ═══ 7 数据中心 (成就/签到/统计/寄语) ═══ -->
      <section v-show="activeSection === 6" class="pv-section pv-stats">
        <div class="pv-stats-wrap">
          <div class="pv-stats-grid">
            <!-- 成就墙 -->
            <div class="pv-stats-card pv-ach">
              <div class="pv-stats-card-head">
                <h3>✪ 成就墙</h3>
                <span class="pv-stats-card-sub">{{ unlockedAchievements.length }}/{{ achievements.length }}</span>
              </div>
              <div class="pv-ach-grid">
                <div v-for="a in achievements.filter(achievementShown)" :key="a.id" class="pv-ach-item" :class="{ unlocked: a.unlocked_at }">
                  <span class="pv-ach-icon">{{ a.icon || '✦' }}</span>
                  <div class="pv-ach-info">
                    <div class="pv-ach-title">{{ a.unlocked_at ? a.title : '???' }}</div>
                    <div class="pv-ach-desc">{{ a.unlocked_at ? a.description : '尚未解锁' }}</div>
                    <div class="pv-ach-progress">
                      <div class="pv-ach-progress-fill" :style="{ width: `${Math.min(100, Math.round(a.progress / a.target * 100))}%` }" />
                    </div>
                  </div>
                  <span v-if="a.unlocked_at" class="pv-ach-date">{{ shortDate(a.unlocked_at) }}</span>
                </div>
              </div>
            </div>

            <!-- 签到足迹 -->
            <div class="pv-stats-card pv-check">
              <div class="pv-stats-card-head">
                <h3>◷ 签到足迹</h3>
                <span class="pv-stats-card-sub">连签 {{ checkin?.streak ?? 0 }} 天 · 累计 {{ checkin?.total_days ?? 0 }} 天</span>
              </div>
              <div class="pv-check-grid">
                <div v-for="d in checkinDays" :key="d.date" class="pv-check-day" :class="{ checked: d.checked, today: d.date === checkin?.today }" :title="d.date">
                  {{ d.day }}
                </div>
              </div>
              <button class="pv-btn-accept pv-check-btn" :disabled="checkin?.checked_today || checkinBusy" @click="doCheckin">
                {{ checkin?.checked_today ? '✓ 今日已签到' : '✦ 每日签到' }}
              </button>
            </div>

            <!-- 每周纪行 (v17) -->
            <div v-if="battlePass" class="pv-stats-card pv-bp">
              <div class="pv-stats-card-head">
                <h3>◈ {{ battlePass.name }}</h3>
                <span class="pv-stats-card-sub">{{ battlePass.week_start }} 起 · {{ battlePass.claimable_count }} 档可领</span>
              </div>
              <div class="pv-bp-points">
                <span class="pv-bp-points-num">{{ battlePass.points }}</span>
                <span class="pv-bp-points-label">纪行积分</span>
                <span class="pv-bp-points-next">{{ bpNextHint }}</span>
              </div>
              <div class="pv-bp-bar"><div class="pv-bp-bar-fill" :style="{ width: `${bpNextPercent}%` }" /></div>
              <div class="pv-bp-tiers">
                <div
                  v-for="t in battlePass.tiers"
                  :key="t.tier"
                  class="pv-bp-tier"
                  :class="{ claimed: t.claimed, claimable: t.claimable, locked: !t.reached }"
                  :title="`第 ${t.tier} 档 · ${t.threshold} 积分 · 奖励 ◆${t.reward_currency}`"
                >
                  <span class="pv-bp-tier-no">{{ t.tier }}</span>
                  <span class="pv-bp-tier-reward">◆{{ t.reward_currency }}</span>
                  <button v-if="t.claimable" class="pv-bp-claim-btn" :disabled="bpClaimBusy" @click="claimBattlePassTier(t.tier)">领取</button>
                  <span v-else-if="t.claimed" class="pv-bp-tier-state">✓ 已领</span>
                  <span v-else class="pv-bp-tier-state">{{ t.threshold }}分</span>
                </div>
              </div>
              <div class="pv-bp-breakdown">
                <span v-for="(v, k) in battlePass.breakdown" :key="k" class="pv-sts-chip">{{ BP_SOURCE_LABELS[k] || k }} ×{{ v.count }} (+{{ v.count * v.points_each }})</span>
              </div>
            </div>

            <!-- 周挑战 (v17) -->
            <div v-if="weeklyChallenge" class="pv-stats-card pv-week-challenge">
              <div class="pv-stats-card-head">
                <h3>✦ {{ weeklyChallenge.name }}</h3>
                <span class="pv-stats-card-sub">{{ weeklyChallenge.theme.name }}</span>
              </div>
              <div class="pv-wc-stars">
                <span class="pv-wc-stars-label">{{ weeklyChallenge.stars_label }}</span>
                <span class="pv-wc-stars-sub">{{ weeklyChallenge.stars }}/3 星</span>
              </div>
              <p v-if="weeklyChallenge.theme.description" class="pv-wc-desc">{{ weeklyChallenge.theme.description }}</p>
              <div class="pv-wc-progress">
                <span class="pv-wc-progress-label">本周完成委托 {{ weeklyChallenge.completed_quests }}/{{ weeklyChallenge.goal }}</span>
                <div class="pv-bp-bar"><div class="pv-bp-bar-fill" :style="{ width: `${Math.min(100, weeklyChallenge.progress_percent)}%` }" /></div>
              </div>
              <ul v-if="(weeklyChallenge.theme.suggestions || []).length" class="pv-wc-suggestions">
                <li v-for="(s, i) in weeklyChallenge.theme.suggestions" :key="i">◈ {{ s }}</li>
              </ul>
            </div>

            <!-- 任务统计 -->
            <div class="pv-stats-card pv-sts-quest">
              <div class="pv-stats-card-head">
                <h3>≣ 任务统计</h3>
              </div>
              <div class="pv-sts-big">
                <span class="pv-sts-rate">{{ stats?.quests?.completion_rate ?? 0 }}<small>%</small></span>
                <span class="pv-sts-rate-label">任务完成率</span>
              </div>
              <div class="pv-sts-bar"><div class="pv-sts-bar-fill" :style="{ width: `${stats?.quests?.completion_rate ?? 0}%` }" /></div>
              <div class="pv-sts-trend">
                <div v-for="d in (stats?.quests?.trend_7d || [])" :key="d.date" class="pv-sts-trend-col">
                  <div class="pv-sts-trend-bar" :style="{ height: `${Math.max(4, Math.round(d.count / MAX_TREND * 100))}%` }">
                    <span v-if="d.count">{{ d.count }}</span>
                  </div>
                  <span class="pv-sts-trend-label">{{ shortDate(d.date) }}</span>
                </div>
              </div>
              <div class="pv-sts-line">
                <span>累计完成 <b class="gold">{{ stats?.quests?.completed ?? 0 }}</b> · 失败 <b class="red">{{ stats?.quests?.failed ?? 0 }}</b> · 总数 <b>{{ stats?.quests?.total ?? 0 }}</b></span>
              </div>
            </div>

            <!-- 收集分布 -->
            <div class="pv-stats-card pv-sts-collect">
              <div class="pv-stats-card-head">
                <h3>▤ 收集分布</h3>
                <span class="pv-stats-card-sub">{{ stats?.items?.total ?? 0 }} 件物品 · 图鉴 {{ (stats?.items?.categories ? Object.keys(stats.items.categories).filter(k => ((stats?.items?.categories || {})[k] || 0) > 0).length : 0) }}/8 类</span>
              </div>
              <div class="pv-sts-rows">
                <div v-for="r in STATS_ITEM_RARITY_ORDER" :key="r" class="pv-sts-row">
                  <span class="pv-sts-row-dot" :style="{ background: RARITY_COLORS[r] }" />
                  <span class="pv-sts-row-label">{{ RARITY_LABELS[r] }}</span>
                  <div class="pv-sts-row-bar"><div class="pv-sts-row-fill" :style="{ width: `${((stats?.items?.rarity || {})[r] || 0) / Math.max(1, stats?.items?.total || 1) * 100}%`, background: RARITY_COLORS[r] }" /></div>
                  <span class="pv-sts-row-num">{{ (stats?.items?.rarity || {})[r] || 0 }}</span>
                </div>
              </div>
              <div class="pv-sts-chips">
                <span v-for="c in STATS_ITEM_CAT_ORDER" :key="c" class="pv-sts-chip">
                  {{ ITEM_CAT_ICONS[c] }} {{ CATEGORY_LABELS[c] }} <b>{{ (stats?.items?.categories || {})[c] || 0 }}</b>
                </span>
              </div>
            </div>

            <!-- 好感度排行 -->
            <div class="pv-stats-card pv-sts-aff">
              <div class="pv-stats-card-head">
                <h3>❖ 好感度排行</h3>
              </div>
              <div v-if="(stats?.characters?.affinity_ranking || []).length" class="pv-aff-rank">
                <div v-for="(c, i) in (stats?.characters?.affinity_ranking || [])" :key="c.id" class="pv-aff-rank-item">
                  <span class="pv-aff-rank-no" :class="{ top: i < 3 }">{{ i + 1 }}</span>
                  <span class="pv-aff-rank-name">{{ c.name }}</span>
                  <div class="pv-aff-rank-bar"><div class="pv-aff-rank-fill" :style="{ width: `${c.affinity}%` }" /></div>
                  <span class="pv-aff-rank-num">{{ c.affinity }}</span>
                </div>
              </div>
              <div v-else class="pv-empty">还没有角色数据～</div>
            </div>

            <!-- 本周报告 -->
            <div class="pv-stats-card pv-weekly">
              <div class="pv-stats-card-head">
                <h3>◈ 本周报告</h3>
                <span class="pv-stats-card-sub">自 {{ weekly?.week_start || '—' }} 起</span>
              </div>
              <div class="pv-weekly-grid">
                <div class="pv-weekly-cell"><span class="pv-weekly-num">{{ weekly?.quests?.completed ?? 0 }}</span><span class="pv-weekly-label">完成任务</span></div>
                <div class="pv-weekly-cell"><span class="pv-weekly-num red">{{ weekly?.quests?.failed ?? 0 }}</span><span class="pv-weekly-label">失败任务</span></div>
                <div class="pv-weekly-cell"><span class="pv-weekly-num">{{ weekly?.quests?.completion_rate ?? 0 }}%</span><span class="pv-weekly-label">完成率</span></div>
                <div class="pv-weekly-cell"><span class="pv-weekly-num">{{ weekly?.checkins ?? 0 }}</span><span class="pv-weekly-label">签到天数</span></div>
                <div class="pv-weekly-cell"><span class="pv-weekly-num">{{ weekly?.achievements ?? 0 }}</span><span class="pv-weekly-label">成就解锁</span></div>
                <div class="pv-weekly-cell"><span class="pv-weekly-num gold">+{{ weekly?.earned?.currency ?? 0 }}</span><span class="pv-weekly-label">本周地球币</span></div>
              </div>
            </div>

            <!-- 到期提醒 -->
            <div class="pv-stats-card pv-due">
              <div class="pv-stats-card-head">
                <h3>◷ 到期提醒</h3>
                <span class="pv-stats-card-sub">{{ dueSoonList.length }} 项</span>
              </div>
              <div v-if="dueSoonList.length === 0" class="pv-empty">近期没有到期的委托～</div>
              <div v-else class="pv-due-list">
                <div v-for="q in dueSoonList" :key="q.id" class="pv-due-item" @click="pickQuest(q); goTo(1)">
                  <span class="pv-due-tag" :class="{ overdue: q.deadline && q.deadline < new Date().toISOString() }">
                    {{ q.deadline && q.deadline < new Date().toISOString() ? '已逾期' : '即将到期' }}
                  </span>
                  <span class="pv-due-title">{{ q.title }}</span>
                  <span class="pv-due-time">{{ formatDate(q.deadline) }}</span>
                </div>
              </div>
            </div>

            <!-- 弥娅寄语 -->
            <div class="pv-stats-card pv-notes">
              <div class="pv-stats-card-head">
                <h3>✉ 弥娅寄语</h3>
                <span class="pv-stats-card-sub">{{ notes.length }} 条</span>
              </div>
              <div class="pv-notes-list">
                <div v-for="n in notes" :key="n.id" class="pv-note-item" :class="{ pinned: n.pinned }">
                  <span class="pv-note-mood">{{ MOOD_ICONS[n.mood] || '✦' }}</span>
                  <div class="pv-note-body">
                    <div class="pv-note-content"><Markdown :source="n.content" /></div>
                    <div class="pv-note-meta">
                      <span v-if="n.pinned" class="pv-note-pin">▲ 置顶</span>
                      <span>{{ formatDate(n.created_at) }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="notes.length === 0" class="pv-empty">弥娅还没有留言，去后台写一条吧～</div>
              </div>
            </div>

            <!-- 全局动态流 (数据互通, 所有模块事件自动记录) -->
            <div class="pv-stats-card pv-feed">
              <div class="pv-stats-card-head">
                <h3>≋ 全局动态流</h3>
                <span class="pv-stats-card-sub">{{ activity.length }} 条事件</span>
              </div>
              <div class="pv-feed-list">
                <div v-for="a in activity" :key="a.id" class="pv-feed-item" :class="{ miya: a.kind === 'miya' }">
                  <span class="pv-feed-icon">{{ a.icon || '·' }}</span>
                  <div class="pv-feed-body">
                    <div class="pv-feed-summary">{{ a.summary }}</div>
                    <div v-if="a.detail" class="pv-feed-detail">{{ a.detail }}</div>
                    <div v-if="a.comment" class="pv-feed-comment">❦ 弥娅: {{ a.comment }}</div>
                  </div>
                  <div class="pv-feed-side">
                    <span class="pv-feed-time">{{ formatDate(a.created_at).slice(5, 16) }}</span>
                    <button class="pv-feed-comment-btn" :title="a.comment ? '修改这条动态的评论' : '给这条动态写一句评论'" @click="openComment(a)">
                      ✎ {{ a.comment ? '改评论' : '评论' }}
                    </button>
                  </div>
                </div>
                <div v-if="activity.length === 0" class="pv-empty">还没有动态，去接个委托或签个到吧～</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ═══ 8 单人世界地图 / 区域探索 ═══ -->
      <section v-show="activeSection === 7" class="pv-section pv-world">
        <div class="pv-world-wrap">
          <div class="pv-world-head">
            <div>
              <p class="pv-story-en">WORLD MAP</p>
              <h2>你的地球，正在展开</h2>
              <p>每个区域都对应现实生活的一种侧面。探索不是打卡，而是把今天认真走过的路留下坐标。</p>
            </div>
            <div class="pv-world-count">{{ worldDiscoveries.length }} / {{ worldRegions.reduce((sum, r) => sum + r.event_total, 0) }} 发现</div>
          </div>
          <div v-if="worldStatus" class="pv-world-atmosphere">
            <span>{{ worldStatus.period_icon }} {{ worldStatus.period }}</span>
            <span>{{ worldStatus.weather_icon }} {{ worldStatus.weather }}</span>
            <span>{{ worldStatus.date }} · {{ worldStatus.time }}</span>
            <span class="pv-world-source" :class="{ synced: realContext?.source_status === 'ok' }">
              {{ realContext?.source_status === 'ok' ? `现实同步 · ${realContext.city}` : '现实天气未同步' }}
            </span>
            <button class="pv-btn-ghost pv-world-refresh" :disabled="worldBusy" @click="configureRealCity">⌖ 设置城市</button>
            <button class="pv-btn-ghost pv-world-refresh" :disabled="worldBusy" @click="refreshRealContext">↻ 刷新现实</button>
          </div>
          <div class="pv-world-grid">
            <article v-for="region in worldRegions" :key="region.key" class="pv-world-region" :class="{ 'has-photo': !!region.image_path, locked: (player?.level || 1) < region.level_req }" :style="worldRegionStyle(region)" role="button" tabindex="0" :aria-label="`查看区域 ${region.name}`" @click="openRegionDrawer(region)" @keydown.enter.self.prevent="openRegionDrawer(region)" @keydown.space.self.prevent="openRegionDrawer(region)">
              <div class="pv-world-region-top">
                <span class="pv-world-icon">{{ region.icon }}</span>
                <div class="pv-world-region-top-actions"><span class="pv-world-level">Lv.{{ region.level_req }}+</span><span class="pv-world-state" :class="{ complete: region.discovery_total >= region.event_total, locked: (player?.level || 1) < region.level_req }">{{ (player?.level || 1) < region.level_req ? 'LOCKED' : region.discovery_total >= region.event_total ? 'COMPLETE' : 'AVAILABLE' }}</span></div>
              </div>
              <h3>{{ region.name }}</h3>
              <span class="pv-world-subtitle">{{ region.subtitle }}</span>
              <div class="pv-world-region-desc"><Markdown v-if="region.description" :source="region.description" /></div>
              <div class="pv-world-progress"><span :style="{ width: `${region.exploration_percent}%` }" /></div>
              <div class="pv-world-meta"><span>{{ region.discovery_total }} / {{ region.event_total }} 个发现</span><span>{{ region.exploration_percent }}%</span></div>
              <button class="pv-btn-primary pv-world-explore" :disabled="worldBusy || (player?.level || 1) < region.level_req" @click.stop="exploreRegion(region)">
                {{ (player?.level || 1) < region.level_req ? `Lv.${region.level_req} 解锁` : region.discovery_total >= region.event_total ? '再次回望' : '探索区域' }}
              </button>
              <button class="pv-btn-ghost pv-world-commission" @click.stop="openRegionDrawer(region)">查看区域档案</button>
            </article>
          </div>
          <div v-if="worldMessage" class="pv-world-message">✦ {{ worldMessage }}</div>
          <div v-if="worldCompanion" class="pv-world-companion">
            <div class="pv-world-companion-mark">❦</div>
            <div><span class="pv-world-companion-label">{{ worldCompanion.speaker }} · {{ worldCompanion.tone }}</span><p>{{ worldCompanion.text }}</p></div>
          </div>
          <div v-if="worldChoiceDiscovery && !worldChoiceDiscovery.choice" class="pv-world-choice">
            <div class="pv-world-choice-title">弥娅想和你一起决定接下来怎么走</div>
            <div class="pv-world-choice-buttons">
              <button class="pv-btn-ghost" :disabled="worldChoiceBusy" @click="chooseWorldDiscovery('continue')">→ 继续前进</button>
              <button class="pv-btn-ghost" :disabled="worldChoiceBusy" @click="chooseWorldDiscovery('record')">✎ 记录此刻</button>
              <button class="pv-btn-ghost" :disabled="worldChoiceBusy" @click="chooseWorldDiscovery('rest')">☾ 先休息</button>
            </div>
          </div>
          <div v-if="worldDiscoveries.length" class="pv-world-log">
            <div class="pv-world-log-head"><span>最近发现</span><span>弥娅已为你存档</span></div>
            <div v-for="discovery in worldDiscoveries.slice(0, 5)" :key="`${discovery.region_key}-${discovery.event_key}`" class="pv-world-log-item">
              <span class="pv-world-log-mark">◇</span><span class="pv-world-log-title">{{ discovery.title }}</span><span class="pv-world-log-reward">+{{ discovery.reward_currency }} ◆ · +{{ discovery.reward_exp }} EXP</span>
            </div>
            <!-- 最新一条发现还没做同行选择时，可在归档里补选 -->
            <div v-if="pendingChoiceDiscovery" class="pv-world-log-choice">
              <span class="pv-world-log-choice-label">「{{ pendingChoiceDiscovery.title }}」还欠弥娅一个同行决定:</span>
              <div class="pv-world-choice-buttons">
                <button class="pv-btn-ghost" :disabled="worldChoiceBusy" @click="chooseWorldDiscovery('continue', pendingChoiceDiscovery)">→ 继续前进</button>
                <button class="pv-btn-ghost" :disabled="worldChoiceBusy" @click="chooseWorldDiscovery('record', pendingChoiceDiscovery)">✎ 记录此刻</button>
                <button class="pv-btn-ghost" :disabled="worldChoiceBusy" @click="chooseWorldDiscovery('rest', pendingChoiceDiscovery)">☾ 先休息</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ═══ 9 商城 (活动商店 + 弥娅兑换所) ═══ -->
      <section v-show="activeSection === 8" class="pv-section pv-shop">
        <div class="pv-shop-wrap">
          <div class="pv-world-head">
            <div>
              <p class="pv-story-en">SHOP</p>
              <h2>兑换所</h2>
              <p>限时活动的纪念物、弥娅的专属互动都在这里。花掉的是认真生活攒下的弥娅币，留下的是能翻回去看的档案。</p>
            </div>
            <div class="pv-world-count">余额 ◆ {{ player?.miya_currency ?? player?.currency ?? 0 }}</div>
          </div>
          <div v-for="eventArea in (worldStatus?.event_areas || []).filter(e => e.active)" :key="eventArea.key" class="pv-world-event" :style="{ '--world-color': eventArea.color }">
            <span class="pv-world-event-icon">{{ eventArea.icon }}</span>
            <div class="pv-world-event-copy"><strong>{{ eventArea.name }}</strong><span>{{ eventArea.subtitle }}</span><p>{{ eventArea.description }}</p></div>
            <span class="pv-world-event-status">活动商店已开放</span>
          </div>
          <div v-if="worldShop?.active" class="pv-world-shop">
            <div class="pv-world-shop-head"><div><strong>活动商店 · {{ worldShop.name }}</strong><span>{{ worldShop.start }} 至 {{ worldShop.end }}</span></div><span class="pv-world-shop-currency">使用弥娅币兑换</span></div>
            <div class="pv-world-shop-grid">
              <article v-for="item in worldShop.items" :key="item.key" class="pv-world-shop-item">
                <div class="pv-world-shop-item-kind">{{ item.kind === 'collectible' ? '纪念物' : item.kind === 'title' ? '称号' : item.kind === 'story' ? '剧情' : '徽章' }}</div>
                <h4>{{ item.name }}</h4>
                <p>{{ item.description }}</p>
                <div class="pv-world-shop-foot"><span>◆ {{ item.cost }}</span><button class="pv-btn-ghost" :disabled="worldBusy || !item.can_buy" @click="buyWorldShopItem(item)">{{ item.purchased ? '已兑换' : item.requires_discoveries ? `需 ${item.requires_discoveries} 个发现` : '兑换' }}</button></div>
              </article>
            </div>
          </div>
          <div v-if="miyaShop" class="pv-world-shop pv-miya-shop">
            <div class="pv-world-shop-head"><div><strong>弥娅专属兑换所</strong><span>用弥娅币换一段只属于你的互动、剧情或纪念物</span></div><span class="pv-world-shop-currency">余额 ◆ {{ player?.miya_currency ?? player?.currency ?? 0 }}</span></div>
            <div class="pv-world-shop-grid">
              <article v-for="item in miyaShop.items" :key="item.key" class="pv-world-shop-item">
                <div class="pv-world-shop-item-kind">{{ item.kind === 'interaction' ? '亲昵互动' : item.kind === 'story' ? '短篇剧情' : item.kind === 'title' ? '专属称号' : '现实辅助' }}</div>
                <h4>{{ item.name }}</h4>
                <p>{{ item.description }}</p>
                <div class="pv-world-shop-foot"><span>◆ {{ item.cost }} <small v-if="item.limit < 10">· {{ item.purchased }}/{{ item.limit }}</small></span><button class="pv-btn-ghost" :disabled="worldBusy || !item.can_buy" @click="buyMiyaShopItem(item)">{{ item.purchased >= item.limit ? '已售罄' : '兑换' }}</button></div>
              </article>
            </div>
          </div>
          <!-- 回忆卡池 (v17: 弥娅记忆碎片) -->
          <div v-if="memory" class="pv-world-shop pv-miya-shop pv-memory-shop">
            <div class="pv-world-shop-head">
              <div>
                <strong>回忆卡池 · {{ memory.name }}</strong>
                <span>用认真生活攒下的弥娅币，把回忆碎片一枚枚带回家 · 每 {{ memory.pity_threshold }} 抽必得高品质回忆</span>
              </div>
              <span class="pv-world-shop-currency">余额 ◆ {{ miyaBalance }}</span>
            </div>
            <div class="pv-memory-stats">
              <div class="pv-memory-stat">
                <span class="pv-memory-stat-label">保底进度 {{ memory.pity }}/{{ memory.pity_threshold }}</span>
                <div class="pv-bp-bar"><div class="pv-bp-bar-fill" :style="{ width: `${pityPercent}%` }" /></div>
              </div>
              <div class="pv-memory-stat">
                <span class="pv-memory-stat-label">收集进度 {{ memory.collected }}/{{ memory.pool_size }}</span>
                <div class="pv-bp-bar"><div class="pv-bp-bar-fill memory" :style="{ width: `${memory.pool_size ? Math.round((memory.collected / memory.pool_size) * 100) : 0}%` }" /></div>
              </div>
              <div class="pv-memory-stat">
                <span class="pv-memory-stat-label">累计抽取</span>
                <span class="pv-memory-stat-num">{{ memory.total_pulls }} 次</span>
              </div>
            </div>
            <div class="pv-memory-actions">
              <button
                class="pv-btn-primary"
                :disabled="pullBusy || miyaBalance < memory.cost_single"
                :title="miyaBalance < memory.cost_single ? `弥娅币不足，还差 ◆${memory.cost_single - miyaBalance}` : '抽取 1 枚回忆碎片'"
                @click="doMemoryPull(1)"
              >
                ✦ 单抽 ◆{{ memory.cost_single }}
              </button>
              <button
                class="pv-btn-accept"
                :disabled="pullBusy || miyaBalance < memory.cost_ten"
                :title="miyaBalance < memory.cost_ten ? `弥娅币不足，还差 ◆${memory.cost_ten - miyaBalance}` : '抽取 10 枚回忆碎片'"
                @click="doMemoryPull(10)"
              >
                ✧ 十连 ◆{{ memory.cost_ten }}
              </button>
            </div>
            <div v-if="memoryPullRecords.length" class="pv-memory-records">
              <span class="pv-memory-records-label">最近抽取</span>
              <span
                v-for="(r, i) in memoryPullRecords"
                :key="r.id ?? i"
                class="pv-memory-record"
                :style="{ borderColor: `${RARITY_COLORS[r.rarity] || '#888'}66` }"
              >
                {{ r.title }}<template v-if="r.is_new"> · NEW</template>
              </span>
            </div>
          </div>
          <div v-if="!worldShop?.active && !miyaShop && !memory" class="pv-empty">货架正在整理中～</div>
        </div>
      </section>

    </main>

    <!-- 加载遮罩 -->
    <div v-if="loading" class="pv-loading">加载中…</div>

    <!-- 加载失败横幅 (点击重试) -->
    <div v-else-if="loadError" class="pv-loading pv-load-error" role="alert">
      <span class="pv-load-error-title">✕ 加载失败：{{ loadError }}</span>
      <span class="pv-load-error-sub">别紧张，可能只是服务打了个盹儿～</span>
      <button class="pv-btn-accept" @click="loadAll">点击重试</button>
    </div>

    <!-- 档案侧边栏 (玩家/区域/物品/角色) -->
    <Transition name="drawer">
      <div v-if="drawerItem || drawerChar || drawerRegion || showProfileEdit" class="pv-drawer-mask" @click.self="closeDrawer">
        <aside class="pv-drawer">
          <div class="pv-drawer-head">
            <span class="pv-drawer-head-label">{{ showProfileEdit ? '玩家档案' : drawerRegion ? '区域档案' : '档案' }}</span>
            <button class="pv-drawer-close" @click="closeDrawer">✕</button>
          </div>

          <template v-if="drawerItem">
            <div class="pv-drawer-cover">
              <img v-if="drawerItem.image_path" :src="EarthAPI.imageUrl(drawerItem.image_path)" class="pv-drawer-cover-img" />
              <div v-else class="pv-drawer-cover-ph">{{ drawerItem.name[0] }}</div>
              <span class="pv-drawer-rarity" :style="{ background: RARITY_COLORS[drawerItem.rarity] || '#888' }">{{ RARITY_LABELS[drawerItem.rarity] || drawerItem.rarity }}</span>
            </div>
            <div class="pv-drawer-body">
              <div class="pv-drawer-title">{{ drawerItem.name }}</div>
              <div class="pv-drawer-sub">
                <span class="pv-drawer-cat">{{ CATEGORY_LABELS[drawerItem.category] || drawerItem.category }}</span>
                <span v-if="drawerItem.quantity > 1" class="pv-drawer-qty">×{{ drawerItem.quantity }}</span>
              </div>
              <div class="pv-drawer-section">≣ 简介</div>
              <p class="pv-drawer-brief">{{ drawerItem.description || '还没有简介～ 去后台编辑补一段吧。' }}</p>
              <button
                v-if="drawerItem.fields?.service_ticket"
                class="pv-btn-primary pv-drawer-ticket"
                :disabled="ticketBusy"
                @click="useServiceTicket"
              >{{ ticketBusy ? '弥娅正在赶来…' : '✦ 使用服务券' }}</button>
              <div v-if="fieldChips(drawerItem.fields).length" class="pv-chips">
                <span v-for="[k, v] in fieldChips(drawerItem.fields)" :key="k" class="pv-chip">{{ k }}: {{ v }}</span>
              </div>
              <div class="pv-drawer-section">≋ 详细档案</div>
              <button v-if="!drawerExpanded" class="pv-btn-primary pv-drawer-expand" @click="drawerExpanded = true">展开完整档案</button>
              <div v-else class="pv-drawer-md">
                <Markdown :source="drawerItem.markdown || '_还没有详细档案，去后台用 Markdown 写一份吧～_'" />
              </div>
              <button v-if="drawerExpanded" class="pv-btn-ghost" @click="drawerExpanded = false">收起详情</button>
            </div>
          </template>

          <template v-else-if="drawerChar">
            <div class="pv-drawer-cover pv-drawer-cover-char">
              <img v-if="drawerChar.avatar_path" :src="EarthAPI.imageUrl(drawerChar.avatar_path)" class="pv-drawer-cover-img" />
              <div v-else class="pv-drawer-cover-ph" :style="{ background: `hsl(${(drawerChar.id * 47) % 360}, 60%, 40%)` }">{{ drawerChar.name[0] }}</div>
            </div>
            <div class="pv-drawer-body">
              <div class="pv-drawer-title">{{ drawerChar.name }}<span v-if="drawerChar.nickname" class="pv-drawer-nick">{{ drawerChar.nickname }}</span></div>
              <div class="pv-drawer-sub">
                <span class="pv-drawer-cat">{{ RELATIONSHIP_LABELS[drawerChar.relationship] || drawerChar.relationship }}</span>
                <span :style="{ color: affinityLevel(drawerChar.affinity).color }">{{ affinityLevel(drawerChar.affinity).label }}</span>
                <span class="pv-drawer-qty">好感 {{ drawerChar.affinity }}/100</span>
              </div>
              <div v-if="drawerChar.birthday" class="pv-drawer-birthday">❖ {{ drawerChar.birthday }}</div>
              <!-- 好感度变动日志 -->
              <div class="pv-drawer-section">❖ 好感度轨迹</div>
              <div v-if="charLogsBusy" class="pv-empty">好感度日志加载中…</div>
              <div v-else-if="charAffinityLogs.length" class="pv-aff-logs">
                <div v-for="log in charAffinityLogs" :key="log.id" class="pv-aff-log">
                  <span class="pv-aff-log-delta" :class="{ up: log.delta > 0, down: log.delta < 0 }">{{ log.delta > 0 ? `+${log.delta}` : log.delta }}</span>
                  <span class="pv-aff-log-reason">{{ log.reason || '—' }}</span>
                  <span class="pv-aff-log-time">{{ formatDate(log.created_at) }}</span>
                </div>
              </div>
              <p v-else class="pv-empty">还没有好感度变动记录～</p>
              <div class="pv-drawer-section">≣ 简介</div>
              <p class="pv-drawer-brief">{{ drawerChar.notes || '还没有备注～ 去后台编辑补一段吧。' }}</p>
              <div v-if="fieldChips(drawerChar.fields).length" class="pv-chips">
                <span v-for="[k, v] in fieldChips(drawerChar.fields)" :key="k" class="pv-chip">{{ k }}: {{ v }}</span>
              </div>
              <div class="pv-drawer-section">≋ 详细档案</div>
              <button v-if="!drawerExpanded" class="pv-btn-primary pv-drawer-expand" @click="drawerExpanded = true">展开完整档案</button>
              <div v-else class="pv-drawer-md">
                <Markdown :source="drawerChar.markdown || '_还没有详细档案，去后台用 Markdown 写一份吧～_'" />
              </div>
              <button v-if="drawerExpanded" class="pv-btn-ghost" @click="drawerExpanded = false">收起详情</button>
            </div>
          </template>

          <template v-else-if="drawerRegion">
            <div class="pv-drawer-cover pv-drawer-cover-region" :style="worldRegionStyle(drawerRegion)">
              <span class="pv-region-drawer-icon">{{ drawerRegion.icon }}</span>
              <span class="pv-drawer-region-state" :class="{ locked: (player?.level || 1) < drawerRegion.level_req, complete: drawerRegion.discovery_total >= drawerRegion.event_total }">{{ (player?.level || 1) < drawerRegion.level_req ? 'LOCKED' : drawerRegion.discovery_total >= drawerRegion.event_total ? 'COMPLETE' : 'AVAILABLE' }}</span>
            </div>
            <div class="pv-drawer-body">
              <div class="pv-drawer-title">{{ drawerRegion.name }}</div>
              <div class="pv-drawer-sub"><span>{{ drawerRegion.subtitle }}</span><span>Lv.{{ drawerRegion.level_req }}+</span></div>
              <div class="pv-drawer-section">◇ 区域同步</div>
              <div class="pv-drawer-brief pv-region-drawer-description"><Markdown v-if="drawerRegion.description" :source="drawerRegion.description" /><span v-else>这个区域还没有更多记录。</span></div>
              <div class="pv-region-drawer-progress"><div><span>探索进度</span><b>{{ drawerRegion.discovery_total }} / {{ drawerRegion.event_total }}</b></div><i><em :style="{ width: `${drawerRegion.exploration_percent}%` }" /></i></div>
              <div class="pv-world-resonance pv-region-drawer-resonance"><div><span>区域共鸣 · Lv.{{ drawerRegion.resonance_level || 1 }}</span><span>{{ drawerRegion.resonance_xp || 0 }} / {{ drawerRegion.resonance_next_xp || 40 }}</span></div><div class="pv-world-resonance-bar"><span :style="{ width: `${Math.min(100, Math.round((drawerRegion.resonance_xp || 0) / Math.max(1, drawerRegion.resonance_next_xp || 40) * 100))}%` }" /></div></div>
              <div v-if="drawerRegion.condition_events?.length" class="pv-world-conditions pv-region-drawer-conditions"><span v-for="event in drawerRegion.condition_events" :key="event.title" :class="{ available: event.available }">{{ event.available ? '✦' : '◇' }} {{ event.available ? event.title : event.condition_label }}</span></div>
              <div class="pv-region-drawer-actions">
                <button class="pv-btn-primary" :disabled="worldBusy || (player?.level || 1) < drawerRegion.level_req" @click="exploreRegion(drawerRegion)">{{ (player?.level || 1) < drawerRegion.level_req ? `Lv.${drawerRegion.level_req} 解锁` : '探索区域' }}</button>
                <button class="pv-btn-ghost" :disabled="worldBusy || (player?.level || 1) < drawerRegion.level_req" @click="commissionRegion(drawerRegion)">领取区域委托</button>
              </div>
            </div>
          </template>

          <template v-else-if="showProfileEdit">
            <div class="pv-drawer-profile-mark">PROFILE / IDENTITY</div>
            <div class="pv-drawer-body pv-drawer-profile-body">
              <p class="pv-drawer-brief">更新你的昵称、称号和自我介绍，这些信息会同步到地球online 的玩家档案。</p>
              <label>昵称</label>
              <input v-model="profileForm.name" class="pv-drawer-input" placeholder="你的名字/昵称" />
              <label>称号</label>
              <input v-model="profileForm.title" class="pv-drawer-input" placeholder="如 地球online 玩家" />
              <label>头像</label>
              <div class="pv-modal-upload">
                <img v-if="profileForm.avatar_path" :src="EarthAPI.imageUrl(profileForm.avatar_path)" class="pv-modal-preview" />
                <label class="pv-btn-ghost pv-upload-btn">选择照片<input type="file" accept="image/*" hidden @change="onPickProfileAvatar" /></label>
              </div>
              <label>关于我 (Markdown)</label>
              <textarea v-model="profileForm.bio" class="pv-md-editor" placeholder="# 你好，我是……&#10;&#10;- 兴趣爱好&#10;- 近期目标&#10;" />
              <label v-if="profileForm.bio">预览</label>
              <div v-if="profileForm.bio" class="pv-bio pv-bio-preview"><Markdown :source="profileForm.bio" /></div>
              <div class="pv-modal-actions">
                <button class="pv-btn-ghost" @click="closeDrawer">取消</button>
                <button class="pv-btn-primary" @click="saveProfile">保存档案</button>
              </div>
            </div>
          </template>
        </aside>
      </div>
    </Transition>

    <!-- 弹窗：称号选择 -->
    <div v-if="showTitles" class="pv-modal-mask" @click.self="showTitles = false">
      <div class="pv-modal">
        <h3>◆ 佩戴称号</h3>
        <p class="pv-titles-hint">完成成就解锁更多称号</p>
        <div class="pv-titles-list">
          <div
            class="pv-title-item"
            :class="{ equipped: (titles?.equipped || titles?.default) === (titles?.default || '地球online 玩家') }"
            @click="equipTitle(titles?.default || '地球online 玩家')"
          >
            <span class="pv-title-item-icon">◇</span>
            <span class="pv-title-item-name">{{ titles?.default || '地球online 玩家' }}</span>
            <span class="pv-title-item-tag">默认</span>
          </div>
          <div
            v-for="t in (titles?.unlocked || [])"
            :key="t.key"
            class="pv-title-item"
            :class="{ equipped: titles?.equipped === t.title }"
            @click="equipTitle(t.title)"
          >
            <span class="pv-title-item-icon">{{ t.icon || '✦' }}</span>
            <span class="pv-title-item-name">{{ t.title }}</span>
            <span class="pv-title-item-tag unlocked">已解锁</span>
          </div>
        </div>
        <div class="pv-modal-actions">
          <button class="pv-btn-ghost" @click="showTitles = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：现实资产编辑 -->
    <div v-if="showEarthMoneyEdit" class="pv-modal-mask" @click.self="showEarthMoneyEdit = false">
      <div class="pv-modal pv-modal-sm">
        <h3>✎ 现实资产 (地球币)</h3>
        <p class="pv-titles-hint">记录你现实中拥有的钱（单位：人民币元），完成现实任务赚到钱后就自己更新它～</p>
        <label>金额 (元)</label>
        <input v-model.number="earthMoneyForm" type="number" min="0" step="0.01" />
        <div class="pv-modal-actions">
          <button class="pv-btn-ghost" @click="showEarthMoneyEdit = false">取消</button>
          <button class="pv-btn-primary" @click="saveEarthMoney">保存</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：签到睡眠 (v17) -->
    <div v-if="showSleepModal" class="pv-modal-mask" @click.self="showSleepModal = false">
      <div class="pv-modal pv-modal-sm">
        <h3>☾ 昨晚睡了几个小时？</h3>
        <p class="pv-titles-hint">告诉弥娅真实的睡眠时长，会有小小的体力与心情回馈哦～ (0-24 小时)</p>
        <label>睡眠时长 (小时)</label>
        <input v-model.number="sleepHours" type="number" min="0" max="24" step="0.5" />
        <div class="pv-modal-actions">
          <button class="pv-btn-ghost" :disabled="checkinBusy" @click="skipSleepCheckin">跳过</button>
          <button class="pv-btn-primary" :disabled="checkinBusy" @click="confirmSleepCheckin">{{ checkinBusy ? '签到中…' : '✦ 确认签到' }}</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：地球币记账 (v17) -->
    <div v-if="showLedgerModal" class="pv-modal-mask" @click.self="showLedgerModal = false">
      <div class="pv-modal pv-modal-sm">
        <h3>✎ 地球币记账</h3>
        <p class="pv-titles-hint">记一笔现实流水：正数 = 收入，负数 = 支出（单位：元），弥娅会把它写进动态流～</p>
        <label>金额 (元, 收入 + / 支出 -)</label>
        <input v-model.number="ledgerForm.amount" type="number" step="0.01" placeholder="如 25.5 或 -12" />
        <label>备注</label>
        <input v-model="ledgerForm.reason" placeholder="比如：午饭 / 兼职工资" maxlength="40" />
        <div class="pv-modal-actions">
          <button class="pv-btn-ghost" :disabled="ledgerBusy" @click="showLedgerModal = false">取消</button>
          <button class="pv-btn-primary" :disabled="ledgerBusy" @click="submitLedger">{{ ledgerBusy ? '记录中…' : '记一笔' }}</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：动态评论 (v17) -->
    <div v-if="showCommentModal && commentTarget" class="pv-modal-mask" @click.self="showCommentModal = false">
      <div class="pv-modal pv-modal-sm">
        <h3>✎ 评论这条动态</h3>
        <p class="pv-titles-hint">「{{ commentTarget.summary }}」</p>
        <label>评论内容</label>
        <textarea v-model="commentText" class="pv-comment-editor" placeholder="写一句想对这条动态说的话…" maxlength="120" />
        <div class="pv-modal-actions">
          <button class="pv-btn-ghost" :disabled="commentBusy" @click="showCommentModal = false">取消</button>
          <button class="pv-btn-primary" :disabled="commentBusy" @click="submitComment">{{ commentBusy ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：回忆抽取结果 (v17) -->
    <div v-if="showPullModal" class="pv-modal-mask" @click.self="showPullModal = false">
      <div class="pv-modal pv-pull-modal">
        <h3>✦ 回忆抽取结果</h3>
        <p class="pv-titles-hint">
          本次消耗 ◆{{ pullCost }}<template v-if="pullRefundTotal > 0"> · 重复碎片共转化 ◆{{ pullRefundTotal }}</template>
        </p>
        <div class="pv-pull-grid">
          <div v-for="(r, i) in pullResults" :key="i" class="pv-pull-card" :style="{ borderColor: RARITY_COLORS[r.rarity] || '#888' }">
            <span class="pv-pull-rarity" :style="{ background: RARITY_COLORS[r.rarity] || '#888' }">{{ RARITY_LABELS[r.rarity] || r.rarity }}</span>
            <span v-if="r.is_new" class="pv-pull-new">NEW</span>
            <div class="pv-pull-title">{{ r.title }}</div>
            <p class="pv-pull-text">{{ r.text }}</p>
            <span v-if="!r.is_new && r.refund_currency" class="pv-pull-refund">转化 +{{ r.refund_currency }} ◆</span>
          </div>
        </div>
        <div class="pv-modal-actions">
          <button class="pv-btn-primary" @click="showPullModal = false">收下回忆</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：服务券互动 · 弥娅的回应 (v18) -->
    <div v-if="ticketResult" class="pv-modal-mask" @click.self="closeTicketModal">
      <div class="pv-modal pv-modal-sm">
        <h3>✦ 服务券 · {{ ticketResult.name }}</h3>
        <div class="pv-ticket-card">
          <span class="pv-ticket-mood">❦</span>
          <div class="pv-ticket-body">
            <span class="pv-ticket-label">弥娅的回应</span>
            <p class="pv-ticket-text">{{ ticketResult.interaction }}</p>
          </div>
        </div>
        <p class="pv-titles-hint">
          {{ ticketResult.remaining > 0 ? `背包里还剩 ${ticketResult.remaining} 张「服务券 · ${ticketResult.name}」，想我的时候随时再用～` : '这张服务券已经用完啦，还想要的话就来商城找我～' }}
        </p>
        <div class="pv-modal-actions">
          <button class="pv-btn-primary" @click="closeTicketModal">收下这份心意</button>
        </div>
      </div>
    </div>

    <Transition name="toast">
      <div v-if="toast" class="pv-toast" role="status" aria-live="polite">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style>
/* 鸣潮官网同款游戏字体 (全局声明, 不参与 scoped) */
@font-face {
  font-family: 'mc-gamefont';
  src: url('/fonts/H7GBK-Heavy.woff') format('woff');
  font-display: swap;
}
</style>

<style scoped>
/* ── 鸣潮官网式整屏分节 · 黑底 + 鎏金 var(--pv-gold) ── */
.pv {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: var(--miya-text);
  background: #07080c;
}

/* 全局壁纸背景层 */
.pv-wallpaper {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-size: cover;
  background-position: center;
  pointer-events: none;
  filter: saturate(0.9);
}
/* 磨砂玻璃: 主要面板透明化 + 模糊 */
.pv-board-wrap,
.pv-quest-show,
.pv-stats-card,
.pv-wall-card,
.pv-char-card,
.pv-story-card,
.pv-book-page,
.pv-profile-money-item,
.pv-profile-attrs,
.pv-profile-bio,
.pv-career-item,
.pv-ach-item,
.pv-note-item,
.pv-feed-item,
.pv-home-note,
.pv-home-card {
  backdrop-filter: var(--pv-glass, none);
  -webkit-backdrop-filter: var(--pv-glass, none);
}

/* 顶部渐变黑幕 */
.pv-banner {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 22%;
  background: linear-gradient(rgba(0, 0, 0, 0.95), rgba(0, 0, 0, 0.01));
  z-index: 30;
  pointer-events: none;
}

/* ── 顶部固定导航 (仿 c2f) ── */
.pv-nav {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 56px;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  z-index: 40;
  padding-top: 10px;
}
.pv-nav-logo {
  position: absolute;
  left: 18px; top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  text-align: left;
  z-index: 41;
}
.pv-nav-logo-glyph {
  width: 30px; height: 30px;
  display: grid; place-items: center;
  font-family: 'Noto Serif SC', serif;
  font-weight: 700; font-size: 1rem;
  color: #1a1206;
  background: linear-gradient(135deg, var(--pv-gold-light), var(--pv-gold));
  clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%);
}
.pv-nav-logo-text {
  font-family: 'mc-gamefont', serif;
  font-size: 0.95rem;
  letter-spacing: 2px;
  color: var(--pv-gold-light);
  text-shadow: 0 0 14px color-mix(in srgb, var(--pv-gold) 50%, transparent);
}
.pv-nav-logo:focus-visible,
.pv-nav-avatar:focus-visible,
.pv-home-note:focus-visible,
.pv-home-card:focus-visible,
.pv-wall-card:focus-visible,
.pv-char-card:focus-visible,
.pv-story-card:focus-visible {
  outline: 2px solid var(--pv-gold-light);
  outline-offset: 3px;
}
.pv-nav-center {
  display: flex;
  gap: 22px;
  position: relative;
}
.pv-nav-center a {
  position: relative;
  display: inline-flex;
  padding: 4px 6px;
  cursor: pointer;
  font-family: 'mc-gamefont', serif;
  font-size: 0.78rem;
  letter-spacing: 2px;
  color: #d9d9d9;
  transition: color 0.4s;
  user-select: none;
}
.pv-nav-center a:focus-visible,
.pv-nav-more:focus-visible,
.pv-nav-more-menu button:focus-visible {
  outline: 2px solid var(--pv-gold-light);
  outline-offset: 2px;
}
.pv-nav-more {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  border: 0;
  background: transparent;
  color: #d9d9d9;
  cursor: pointer;
  font-family: 'mc-gamefont', serif;
  font-size: 0.78rem;
  letter-spacing: 2px;
}
.pv-nav-more:hover, .pv-nav-more.active { color: var(--pv-gold); }
.pv-nav-more-menu {
  position: absolute;
  top: 32px;
  right: -8px;
  min-width: 138px;
  padding: 6px;
  display: grid;
  gap: 3px;
  background: rgba(9, 11, 16, 0.97);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 42%, transparent);
  box-shadow: 0 12px 28px rgba(0,0,0,.45);
}
.pv-nav-more-menu button {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  padding: 8px 10px;
  border: 0;
  background: transparent;
  color: rgba(255,255,255,.72);
  text-align: left;
  cursor: pointer;
  font-size: .75rem;
}
.pv-nav-more-menu button:hover, .pv-nav-more-menu button.active { color: var(--pv-gold-light); background: color-mix(in srgb, var(--pv-gold) 12%, transparent); }
.pv-nav-more-menu small { color: rgba(255,255,255,.35); font-size: .52rem; letter-spacing: .12em; }
.pv-nav-center a:hover,
.pv-nav-center a.active {
  color: var(--pv-gold);
}
/* hover 鎏金装饰框 · 顶块 + 左右横线 + 底部角线 */
.nv-deco {
  position: absolute;
  inset: -5px -10px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.45s ease;
}
.nv-deco::before {
  content: '';
  position: absolute;
  top: 0; left: 50%;
  transform: translateX(-50%);
  width: 30px; height: 7px;
  border-top: 1px solid var(--pv-gold);
  border-left: 1px solid color-mix(in srgb, var(--pv-gold) 55%, transparent);
  border-right: 1px solid color-mix(in srgb, var(--pv-gold) 55%, transparent);
}
.nv-deco::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 6px;
  border-bottom: 1px solid var(--pv-gold);
  border-left: 1px solid color-mix(in srgb, var(--pv-gold) 40%, transparent);
  border-right: 1px solid color-mix(in srgb, var(--pv-gold) 40%, transparent);
}
.pv-nav-center a:hover .nv-deco,
.pv-nav-center a.active .nv-deco {
  opacity: 1;
}
.pv-nav-side {
  position: absolute;
  right: 16px; top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 41;
}
.pv-context-nav {
  position: absolute;
  top: 58px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 2px;
  min-height: 28px;
  padding: 2px 4px;
  border: 1px solid rgba(162, 245, 238, .12);
  border-top-color: rgba(162, 245, 238, .05);
  background: rgba(5, 13, 21, .72);
  box-shadow: 0 8px 22px rgba(0, 0, 0, .2);
  backdrop-filter: blur(12px);
  z-index: 39;
}
.pv-context-label {
  padding: 0 .55rem;
  color: var(--miya-text-faint);
  font: .48rem/1 'JetBrains Mono', monospace;
  letter-spacing: .12em;
  white-space: nowrap;
}
.pv-context-label i { color: var(--earth-accent-light); font-style: normal; margin-left: .25rem; }
.pv-context-item {
  display: inline-flex;
  align-items: baseline;
  gap: .35rem;
  min-height: 24px;
  padding: 3px 10px;
  border: 0;
  border-left: 1px solid rgba(162, 245, 238, .08);
  color: var(--miya-text-muted);
  background: transparent;
  cursor: pointer;
  font: inherit;
  white-space: nowrap;
  transition: color .2s, background .2s;
}
.pv-context-item span { font-size: .65rem; }
.pv-context-item small { color: rgba(162, 245, 238, .45); font: .42rem/1 'JetBrains Mono', monospace; letter-spacing: .08em; }
.pv-context-item:hover,
.pv-context-item.active { color: var(--earth-accent-light); background: rgba(120, 207, 209, .1); }
.pv-context-item.active { box-shadow: inset 0 -1px var(--earth-accent-light); }
.pv-nav-avatar {
  width: 30px; height: 30px;
  border-radius: 50%;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--pv-gold) 60%, transparent);
  display: grid; place-items: center;
  font-size: 0.85rem; font-weight: 700;
  color: #1a1206;
  background: linear-gradient(135deg, var(--pv-gold-light), var(--pv-gold));
  cursor: pointer;
  padding: 0;
  font: inherit;
}
.pv-nav-avatar img { width: 100%; height: 100%; object-fit: cover; }
.pv-nav-id { display: flex; flex-direction: column; line-height: 1.15; }
.pv-nav-name { font-size: 0.72rem; font-weight: 700; color: #f0e6cf; }
.pv-nav-level { font-size: 0.6rem; color: var(--pv-gold); }
.pv-nav-coin {
  font-size: 0.68rem; font-weight: 700; color: var(--pv-gold);
  padding: 3px 10px;
  border: 1px solid color-mix(in srgb, var(--pv-gold) 40%, transparent);
  border-radius: 20px;
  background: color-mix(in srgb, var(--pv-gold) 8%, transparent);
  font: inherit;
  text-align: left;
}

/* ── 分节舞台: 顶部 Tab 切换, 当前板块整页自由滚动 ── */
.pv-stage {
  position: absolute;
  inset: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--pv-gold) 45%, transparent) transparent;
}
.pv-stage.has-context-nav .pv-section { padding-top: 98px; }
.pv-stage::-webkit-scrollbar { width: 6px; }
.pv-stage::-webkit-scrollbar-thumb {
  border-radius: 4px;
  background: color-mix(in srgb, var(--pv-gold) 45%, transparent);
}
.pv-stage::-webkit-scrollbar-track { background: transparent; }
/* 全站统一细鎏金滚动条: 小窗/书页/抽屉/弹窗与主舞台一致 */
.pv * {
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--pv-gold) 45%, transparent) transparent;
}
.pv ::-webkit-scrollbar { width: 6px; height: 6px; }
.pv ::-webkit-scrollbar-thumb { border-radius: 4px; background: color-mix(in srgb, var(--pv-gold) 45%, transparent); }
.pv ::-webkit-scrollbar-track { background: transparent; }
.pv ::-webkit-scrollbar-corner { background: transparent; }
.pv-section {
  position: relative;
  width: 100%;
  min-height: 100%;
  display: flex;
  justify-content: center;
  align-items: safe center;
  box-sizing: border-box;
  /* 顶部固定导航安全区 + 底部收尾留白 */
  padding-top: 64px;
  padding-bottom: 48px;
  /* v-show 切换到 display:flex 时重放, 作为板块进场动画 */
  animation: pv-section-in 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}
@keyframes pv-section-in {
  from { opacity: 0; transform: translateY(18px); }
  to { opacity: 1; transform: none; }
}

/* ── 通用 ── */
.pv-line { width: 100%; height: 1px; background: linear-gradient(90deg, var(--pv-gold-deep), rgba(181, 152, 106, 0.15)); }
.pv-empty { padding: 1.6rem; text-align: center; color: rgba(255, 255, 255, 0.4); font-size: 0.8rem; }
.pv-gold, .gold { color: var(--pv-gold); }
.red { color: #ff6b6b; }
.pv-currency {
  font-size: 0.72rem; color: var(--pv-gold); font-weight: 700;
  padding: 4px 14px;
  border: 1px solid color-mix(in srgb, var(--pv-gold) 35%, transparent);
  border-radius: 20px;
  background: color-mix(in srgb, var(--pv-gold) 8%, transparent);
}
.pv-loading {
  position: absolute; inset: 0; z-index: 60;
  display: grid; place-items: center;
  background: rgba(7, 8, 12, 0.75);
  color: var(--pv-gold); font-family: 'mc-gamefont', serif;
  letter-spacing: 3px; font-size: 0.95rem;
}
.pv-btn-accept {
  padding: 0.55rem 1.8rem; border: none; border-radius: 6px; cursor: pointer;
  background: linear-gradient(135deg, var(--pv-gold-light), #a8873f);
  color: #1a1206; font-weight: 700; font-size: 0.85rem;
  letter-spacing: 1px;
  transition: filter 0.2s, transform 0.15s;
}
.pv-btn-accept:hover { filter: brightness(1.15); transform: translateY(-1px); }
.pv-btn-accept:disabled { filter: grayscale(0.6); cursor: not-allowed; transform: none; }
.pv-btn-primary {
  padding: 0.45rem 1.1rem; border: none; border-radius: 6px; cursor: pointer;
  background: linear-gradient(135deg, var(--pv-gold), #7c4dff);
  color: #fff; font-size: 0.78rem; font-weight: 600;
}
.pv-btn-ghost {
  padding: 0.45rem 0.95rem; border-radius: 6px; cursor: pointer; font-size: 0.78rem;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: var(--miya-text);
}
.pv-btn-danger { color: #ff6b6b; border-color: rgba(255, 107, 107, 0.35); background: rgba(255, 107, 107, 0.08); }
.pv-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.pv-chip {
  font-size: 0.6rem; padding: 1px 8px; border-radius: 10px;
  background: color-mix(in srgb, var(--pv-gold) 10%, transparent); border: 1px solid color-mix(in srgb, var(--pv-gold) 25%, transparent);
  color: var(--miya-text-dim);
}

/* ═══ 首页 (仿 Main) ═══ */
.pv-home-bg {
  position: absolute; inset: 0;
  background-size: cover; background-position: center;
  filter: blur(14px) brightness(0.45);
  transform: scale(1.15);
}
.pv-home-veil {
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse at 50% 30%, color-mix(in srgb, var(--pv-gold) 14%, transparent), transparent 60%),
    linear-gradient(180deg, rgba(7, 8, 12, 0.35), rgba(7, 8, 12, 0.92));
}
.pv-home-body {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.3rem;
  width: min(1000px, 92vw);
  padding: 0 1rem 2.5rem;
  margin-top: 2vh;
}
.pv-home-en {
  font-family: 'mc-gamefont', serif;
  letter-spacing: 0.7em;
  font-size: 0.8rem;
  color: color-mix(in srgb, var(--pv-gold) 65%, transparent);
  margin: 0;
}
.pv-home-title {
  margin: 0;
  font-family: 'mc-gamefont', serif;
  font-size: clamp(3rem, 7vw, 5.4rem);
  font-weight: 400;
  letter-spacing: 0.14em;
  background: linear-gradient(180deg, #f8edd2 20%, var(--pv-gold) 75%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  text-shadow: 0 0 42px color-mix(in srgb, var(--pv-gold) 35%, transparent);
  filter: drop-shadow(0 4px 22px rgba(0, 0, 0, 0.6));
}
.pv-home-welcome {
  margin: 0.1rem 0 0.9rem;
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.72);
  letter-spacing: 2px;
}
/* 首页信息层级：品牌先出现，今日行动优先于背景信息，入口最后出现。 */
.pv-home-body .pv-today-action { order: 1; }
.pv-home-body .pv-home-note { order: 2; }
.pv-home-body .pv-life-hub { order: 3; }
.pv-home-body .pv-degraded { order: 4; }
.pv-home-body .pv-home-menu { order: 5; }
/* 弥娅寄语卡 */
.pv-home-note {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  max-width: 560px;
  padding: 0.65rem 1rem;
  background: linear-gradient(135deg, color-mix(in srgb, var(--pv-gold) 14%, transparent), rgba(0, 0, 0, 0.55));
  border: 1px solid color-mix(in srgb, var(--pv-gold) 40%, transparent);
  border-left: 3px solid var(--pv-gold);
  border-radius: 8px;
  cursor: pointer;
  font: inherit;
  color: inherit;
  text-align: left;
  transition: all 0.3s;
}
.pv-home-note:hover { transform: translateY(-2px); box-shadow: 0 6px 24px rgba(0, 0, 0, 0.5), 0 0 16px color-mix(in srgb, var(--pv-gold) 18%, transparent); }
.pv-home-note-mood { font-size: 1.5rem; }
.pv-home-note-body { flex: 1; min-width: 0; }
.pv-home-note-label { display: block; font-size: 0.6rem; letter-spacing: 2px; color: var(--pv-gold); }
.pv-home-note-text {
  display: block;
  margin: 2px 0 0;
  font-size: 0.82rem;
  color: #f0e6cf;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pv-home-note-arrow { color: color-mix(in srgb, var(--pv-gold) 60%, transparent); font-size: 1.2rem; }
.pv-life-hub { width: min(560px, 88vw); margin: 1rem auto 0; padding: 0.8rem 1rem; border: 1px solid color-mix(in srgb, var(--pv-gold) 35%, transparent); background: rgba(8, 10, 16, 0.62); text-align: left; }
.pv-life-hub-head { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; color: var(--pv-gold-light); font-size: 0.78rem; }
.pv-life-hub-head small { color: rgba(255,255,255,.4); font-size: .5rem; letter-spacing: 1px; }
.pv-life-hub-facts { display: flex; gap: 1rem; margin: .55rem 0; color: rgba(255,255,255,.72); font-size: .68rem; }
.pv-life-hub-status { display: flex; flex-wrap: wrap; gap: .4rem .8rem; margin-top: .55rem; color: #9fe3c0; font-size: .6rem; }
.pv-life-hub-status .warning { color: #e6bd78; }
.pv-life-hub-status .quiet { color: rgba(255,255,255,.5); }
.pv-life-hub-status .privacy { color: #e59393; }
.pv-life-hub-line, .pv-life-hub-recommend, .pv-life-hub-pending { margin: .28rem 0 0; font-size: .68rem; line-height: 1.5; }
.pv-life-hub-line { color: rgba(255,255,255,.78); }
.pv-life-hub-recommend { color: var(--pv-gold-light); }
.pv-life-hub-pending { color: #d9b875; }
.pv-life-hub-action { display: flex; align-items: center; justify-content: space-between; gap: .75rem; }
.pv-life-hub-action p { flex: 1; }
.pv-life-hub-btn { flex: 0 0 auto; border: 1px solid color-mix(in srgb, var(--pv-gold) 55%, transparent); background: transparent; color: var(--pv-gold-light); padding: .28rem .55rem; font-size: .6rem; cursor: pointer; }
.pv-life-hub-btn:hover { background: color-mix(in srgb, var(--pv-gold) 16%, transparent); }
.pv-life-hub-boundary { margin: .55rem 0 0; color: rgba(255,255,255,.36); font-size: .55rem; line-height: 1.45; }
.pv-today-action {
  width: min(560px, 88vw);
  display: flex;
  align-items: center;
  gap: .75rem;
  margin: .65rem auto 0;
  padding: .75rem .9rem;
  border: 1px solid color-mix(in srgb, var(--pv-gold) 52%, transparent);
  background: linear-gradient(100deg, color-mix(in srgb, var(--pv-gold) 12%, transparent), rgba(8, 10, 16, .74));
  text-align: left;
}
.pv-today-action-mark { flex: 0 0 auto; color: var(--pv-gold); font-size: 1.35rem; }
.pv-today-action-copy { flex: 1; min-width: 0; }
.pv-today-action-kicker { display: block; color: color-mix(in srgb, var(--pv-gold) 72%, transparent); font-size: .52rem; letter-spacing: .18em; }
.pv-today-action-copy strong { display: block; margin-top: .18rem; color: #f0e6cf; font-size: .78rem; }
.pv-today-action-copy p { margin: .22rem 0 0; color: rgba(255,255,255,.58); font-size: .67rem; line-height: 1.45; }
.pv-today-action-btn { white-space: nowrap; }
.pv-degraded { width: min(560px, 88vw); margin: .55rem auto 0; padding: .45rem .7rem; border: 1px solid rgba(230,189,120,.28); background: rgba(72,50,20,.28); color: #e6bd78; font-size: .6rem; text-align: left; }
/* 菜单入口条 */
.pv-home-menu {
  display: flex;
  gap: 0.8rem;
  margin-top: 0.2rem;
  flex-wrap: wrap;
  justify-content: center;
}
.pv-home-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  width: 128px;
  padding: 0.95rem 0.5rem;
  background: rgba(0, 0, 0, 0.42);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 28%, transparent);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  /* 依次浮现 (section 显示时重放) */
  animation: pv-section-in 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
  font: inherit;
  color: inherit;
  text-align: center;
}
.pv-home-menu .pv-home-card:nth-child(2) { animation-delay: 60ms; }
.pv-home-menu .pv-home-card:nth-child(3) { animation-delay: 120ms; }
.pv-home-menu .pv-home-card:nth-child(4) { animation-delay: 180ms; }
.pv-home-menu .pv-home-card:nth-child(5) { animation-delay: 240ms; }
.pv-home-card:hover {
  transform: translateY(-4px);
  border-color: color-mix(in srgb, var(--pv-gold) 70%, transparent);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.5), 0 0 14px color-mix(in srgb, var(--pv-gold) 20%, transparent);
  background: color-mix(in srgb, var(--pv-gold) 10%, transparent);
}
.pv-home-card-en { font-family: 'mc-gamefont', serif; font-size: 0.56rem; letter-spacing: 2px; color: color-mix(in srgb, var(--pv-gold) 62%, transparent); }
.pv-home-card-name { font-size: 0.9rem; font-weight: 700; color: #f0e6cf; }
/* 签到竖标签 (仿 activity) */
.pv-home-checkin {
  position: absolute;
  right: 0;
  bottom: 24vh;
  width: 92px;
  padding: 8px 10px;
  border-width: 1px 0 3px 1px;
  border-style: solid;
  border-color: var(--pv-gold);
  background: rgba(0, 0, 0, 0.55);
  cursor: pointer;
  z-index: 3;
  display: flex;
  flex-direction: column;
  gap: 2px;
  transition: all 0.3s;
}
.pv-home-checkin:hover { background: color-mix(in srgb, var(--pv-gold) 18%, transparent); }
.pv-home-checkin.done { border-color: color-mix(in srgb, var(--pv-gold) 45%, transparent); }
.pv-home-checkin-main { font-family: 'mc-gamefont', serif; font-size: 0.68rem; color: #fff; }
.pv-home-checkin-sub { font-size: 0.58rem; color: var(--pv-gold); }
/* 底部滚动提示 */
.pv-home-scroll {
  position: absolute;
  bottom: 14px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  z-index: 3;
  color: color-mix(in srgb, var(--pv-gold) 75%, transparent);
  font-size: 0.62rem;
  letter-spacing: 2px;
  border: 0;
  padding: 0.25rem 0.5rem;
  background: transparent;
  font: inherit;
}
.pv-home-scroll-arrow { animation: tipMove 2.2s ease-in-out infinite; font-size: 0.9rem; }
@keyframes tipMove {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(7px); }
}

/* ═══ 委托 (仿 News) ═══ */
.pv-board { background: radial-gradient(ellipse at 20% 10%, color-mix(in srgb, var(--pv-gold) 7%, transparent), transparent 55%), rgba(7, 8, 12, 0.78); }
.pv-board-wrap {
  width: 92%;
  min-height: 82%;
  display: flex;
  gap: 2.4rem;
  align-items: stretch;
}
.pv-board-left { flex: 4.2; min-width: 0; display: flex; flex-direction: column; }
.pv-board-head { flex-shrink: 0; }
.pv-board-title {
  margin: 0;
  font-family: 'mc-gamefont', serif;
  font-size: 2.6rem;
  color: var(--pv-gold);
  letter-spacing: 6px;
  line-height: 1.1;
}
.pv-board-en { font-size: 0.6rem; letter-spacing: 4px; color: color-mix(in srgb, var(--pv-gold) 55%, transparent); }
.pv-board-tabs { display: flex; align-items: center; gap: 1.4rem; padding: 0.4rem 0.2rem; }
.pv-board-tabs > a {
  position: relative;
  cursor: pointer;
  font-family: 'mc-gamefont', serif;
  font-size: 0.8rem;
  color: #ddd;
  transition: color 0.3s;
  padding: 2px 0;
}
.pv-board-tabs > a:hover, .pv-board-tabs > a.active { color: var(--pv-gold); }
.pv-tab-underline {
  position: absolute;
  bottom: -3px; left: 50%;
  width: 0; height: 2px;
  background: var(--pv-gold);
  transform: translateX(-50%);
  transition: width 0.4s ease;
}
.pv-board-tabs > a.active .pv-tab-underline { width: 100%; }
.pv-board-type-filter { display: flex; gap: 0.9rem; margin-left: auto; }
.pv-board-type-filter a {
  cursor: pointer;
  font-size: 0.66rem;
  color: rgba(255, 255, 255, 0.45);
  border: 1px solid transparent;
  padding: 1px 7px;
  border-radius: 4px;
  transition: all 0.25s;
}
.pv-board-type-filter a:hover, .pv-board-type-filter a.active {
  color: var(--pv-gold);
  border-color: color-mix(in srgb, var(--pv-gold) 40%, transparent);
}
.pv-board-list {
  flex: 1;
  padding-top: 0.5rem;
  display: flex;
  flex-direction: column;
}
.pv-board-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.85rem 0.6rem;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  transition: background 0.25s;
  width: 100%;
  border-top: 0;
  border-left: 0;
  border-right: 0;
  background: transparent;
  font: inherit;
  color: inherit;
  text-align: left;
}
.pv-board-item:hover, .pv-board-item.active { background: color-mix(in srgb, var(--pv-gold) 7%, transparent); }
.pv-board-item-type {
  flex-shrink: 0;
  font-size: 0.62rem;
  border: 1px solid currentColor;
  padding: 1px 7px;
  border-radius: 4px;
}
.pv-board-item-title {
  flex: 1;
  min-width: 0;
  font-size: 0.88rem;
  color: #f0e6cf;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pv-board-item-status { font-size: 0.8rem; }
.pv-board-item-status.done { color: #81c784; }
.pv-board-item-status.failed { color: #ff6b6b; }
.pv-board-item-due {
  flex-shrink: 0;
  font-size: 0.6rem;
  padding: 1px 7px;
  border-radius: 4px;
  color: #ffb300;
  border: 1px solid rgba(255, 179, 0, 0.45);
  background: rgba(255, 179, 0, 0.08);
}
.pv-board-item-due.overdue { color: #ff6b6b; border-color: rgba(255, 107, 107, 0.5); background: rgba(255, 107, 107, 0.1); }
.pv-board-item-underline {
  position: absolute;
  bottom: 0; left: 0;
  width: 0; height: 2px;
  background: var(--pv-gold);
  transition: width 0.5s ease;
}
.pv-board-item.active .pv-board-item-underline { width: 100%; }
/* 历史归档 (可折叠) */
.pv-board-history { flex-shrink: 0; margin-top: 0.4rem; border-top: 1px solid rgba(255, 255, 255, 0.08); }
.pv-board-history-toggle {
  width: 100%; display: flex; align-items: center; justify-content: space-between;
  padding: 0.45rem 0.2rem; background: none; border: none; cursor: pointer;
  font-family: 'mc-gamefont', serif; font-size: 0.7rem; letter-spacing: 1px; color: rgba(255, 255, 255, 0.55);
  transition: color 0.3s;
}
.pv-board-history-toggle:hover { color: var(--pv-gold); }
.pv-board-history-arrow { font-size: 0.6rem; transition: transform 0.3s; }
.pv-board-history-list { padding-bottom: 0.3rem; }
.pv-board-history-item {
  display: flex; align-items: center; gap: 0.6rem; padding: 0.3rem 0.2rem; cursor: pointer;
  font-size: 0.68rem; color: var(--miya-text-dim); border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  transition: color 0.25s;
  width: 100%;
  border-top: 0;
  border-left: 0;
  border-right: 0;
  background: transparent;
  font: inherit;
  text-align: left;
}
.pv-board-history-item:hover { color: var(--pv-gold-light); }
.pv-board-history-mark { flex-shrink: 0; font-size: 0.66rem; }
.pv-board-history-item.completed .pv-board-history-mark { color: #81c784; }
.pv-board-history-item.failed .pv-board-history-mark { color: #ff6b6b; }
.pv-board-history-title { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pv-board-history-time { flex-shrink: 0; font-size: 0.56rem; color: rgba(255, 255, 255, 0.3); }
/* 右侧委托详情 */
.pv-board-right {
  flex: 5.8;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pv-quest-show {
  width: 100%;
  min-height: 360px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.85rem;
  padding: 2.2rem 2.4rem;
  background:
    linear-gradient(160deg, color-mix(in srgb, var(--pv-gold) 9%, transparent), rgba(0, 0, 0, 0.5)),
    repeating-linear-gradient(45deg, transparent, transparent 18px, color-mix(in srgb, var(--pv-gold) 3%, transparent) 18px, color-mix(in srgb, var(--pv-gold) 3%, transparent) 19px);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 35%, transparent);
  border-radius: 4px 20px 4px 4px;
  box-shadow: 0 14px 40px rgba(0, 0, 0, 0.55);
}
.pv-quest-show-type {
  align-self: flex-start;
  font-family: 'mc-gamefont', serif;
  font-size: 0.85rem;
  letter-spacing: 3px;
  border: 1px solid;
  padding: 3px 14px;
}
.pv-quest-show-title {
  margin: 0;
  font-family: 'mc-gamefont', serif;
  font-size: 1.9rem;
  font-weight: 400;
  letter-spacing: 2px;
  color: #f0e6cf;
}
.pv-quest-show-stars { color: #ffb300; font-size: 0.95rem; letter-spacing: 3px; }
.pv-quest-show-desc { margin: 0; font-size: 0.82rem; color: rgba(255, 255, 255, 0.6); line-height: 1.7; }
.pv-quest-show-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 0.7rem 1.6rem; }
.pv-quest-show-cell { display: flex; justify-content: space-between; font-size: 0.76rem; border-bottom: 1px dashed color-mix(in srgb, var(--pv-gold) 25%, transparent); padding-bottom: 4px; }
.pv-quest-show-cell .k { color: rgba(255, 255, 255, 0.45); }
.pv-quest-show-cell .v { color: #f0e6cf; }
.pv-quest-show-actions { display: flex; gap: 0.6rem; align-items: center; margin-top: 0.4rem; }
.pv-quest-show-done { color: rgba(255, 255, 255, 0.5); font-size: 0.78rem; }
.pv-btn-primary:disabled { filter: grayscale(0.7) brightness(0.7); cursor: not-allowed; }

/* 子任务进度跟踪 */
.pv-quest-subtasks {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0.7rem 0.9rem;
  background: rgba(0, 0, 0, 0.32);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 22%, transparent);
  border-radius: 8px;
}
.pv-quest-subtasks-head { display: flex; justify-content: space-between; align-items: center; }
.pv-quest-subtasks-title { font-size: 0.7rem; font-weight: 700; color: var(--pv-gold); letter-spacing: 2px; }
.pv-quest-subtasks-num { font-size: 0.68rem; color: rgba(255, 255, 255, 0.6); }
.pv-quest-subtasks-bar { height: 5px; border-radius: 3px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.pv-quest-subtasks-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--pv-gold), var(--pv-gold-light)); transition: width 0.4s ease; }
.pv-quest-subtask {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.78);
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 5px;
  transition: background 0.2s;
}
.pv-quest-subtask:hover { background: color-mix(in srgb, var(--pv-gold) 8%, transparent); }
.pv-quest-subtask input { display: none; }
.pv-quest-subtask-mark { color: color-mix(in srgb, var(--pv-gold) 70%, transparent); flex-shrink: 0; }
.pv-quest-subtask.done .pv-quest-subtask-mark { color: var(--pv-gold); }
.pv-quest-subtask.done .pv-quest-subtask-text { color: rgba(255, 255, 255, 0.45); text-decoration: line-through; }
.pv-quest-subtasks-hint { font-size: 0.66rem; color: color-mix(in srgb, var(--pv-gold) 75%, transparent); letter-spacing: 1px; }

/* ═══ 背包照片墙 / 角色卡墙 (图封面方格, 大小不一整齐排列) ═══ */
.pv-items { background: radial-gradient(ellipse at 15% 50%, color-mix(in srgb, var(--pv-gold) 6%, transparent), transparent 55%), rgba(7, 8, 12, 0.78); }
.pv-items-wrap {
  width: 92%;
  min-height: 88%;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.pv-items-head { display: flex; align-items: flex-end; justify-content: space-between; padding-top: 0.3rem; }
.pv-items-en { font-size: 0.6rem; letter-spacing: 4px; color: color-mix(in srgb, var(--pv-gold) 55%, transparent); }
.pv-items-title { margin: 2px 0 0; font-family: 'mc-gamefont', serif; font-size: 2rem; font-weight: 400; letter-spacing: 4px; color: var(--pv-gold); }
.pv-items-filters { display: flex; flex-wrap: wrap; gap: 0.45rem; }
.pv-filter-chip {
  padding: 0.3rem 0.85rem;
  border-radius: 20px;
  cursor: pointer;
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.6);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  transition: all 0.25s;
}
.pv-filter-chip:hover { color: var(--pv-gold); border-color: color-mix(in srgb, var(--pv-gold) 40%, transparent); }
.pv-filter-chip.active {
  color: #1a1206;
  font-weight: 700;
  background: linear-gradient(135deg, var(--pv-gold-light), var(--pv-gold));
  border-color: transparent;
  box-shadow: 0 0 12px color-mix(in srgb, var(--pv-gold) 35%, transparent);
}
/* 瀑布流照片墙: 大小不一的封面整齐排列 (整页滚动, 按内容自然分列) */
.pv-wall {
  flex: 1;
  column-count: 6;
  column-gap: 10px;
  padding: 0.4rem 0.1rem 1rem;
}
@media (max-width: 1400px) { .pv-wall { column-count: 5; } }
@media (max-width: 1100px) { .pv-wall { column-count: 4; } }
@media (max-width: 850px) { .pv-wall { column-count: 3; } }
@media (max-width: 600px) { .pv-wall { column-count: 2; } }
.pv-wall-card {
  break-inside: avoid;
  margin-bottom: 14px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid;
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.25s, box-shadow 0.25s;
}
.pv-wall-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.5), 0 0 14px color-mix(in srgb, var(--pv-gold) 14%, transparent);
}
.pv-wall-cover { position: relative; overflow: hidden; }
.pv-wall-cover.ph { height: 130px; display: grid; place-items: center; background: rgba(255, 255, 255, 0.04); }
.pv-wall-img { width: 100%; display: block; }
.pv-wall-ph { font-size: 2rem; color: rgba(255, 255, 255, 0.3); }
.pv-wall-rarity { position: absolute; top: 7px; left: 7px; padding: 2px 9px; border-radius: 4px; font-size: 0.6rem; color: #fff; }
.pv-wall-qty { position: absolute; bottom: 7px; right: 7px; padding: 1px 8px; background: rgba(0, 0, 0, 0.7); border-radius: 4px; font-size: 0.7rem; color: #fff; }
.pv-wall-info { padding: 0.55rem 0.7rem 0.65rem; }
.pv-wall-name { font-size: 0.85rem; font-weight: 700; color: #f0e6cf; }
.pv-wall-sub { font-size: 0.62rem; color: rgba(255, 255, 255, 0.45); margin-top: 2px; }

/* 角色卡墙 */
.pv-chars { background: radial-gradient(ellipse at 15% 50%, color-mix(in srgb, var(--pv-gold) 7%, transparent), transparent 55%), rgba(7, 8, 12, 0.78); }
.pv-chars-wrap {
  width: 92%;
  min-height: 88%;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.pv-chars-wall { column-count: 5; }
@media (max-width: 1300px) { .pv-chars-wall { column-count: 4; } }
@media (max-width: 1000px) { .pv-chars-wall { column-count: 3; } }
.pv-char-card {
  break-inside: avoid;
  margin-bottom: 14px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 25%, transparent);
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.25s, box-shadow 0.25s;
}
.pv-char-card:hover {
  transform: translateY(-3px);
  border-color: color-mix(in srgb, var(--pv-gold) 60%, transparent);
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.5), 0 0 16px color-mix(in srgb, var(--pv-gold) 20%, transparent);
}
.pv-char-card-cover { position: relative; overflow: hidden; }
.pv-char-card-cover.ph { height: 170px; }
.pv-char-card-img { width: 100%; display: block; }
.pv-char-card-ph { width: 100%; height: 170px; display: grid; place-items: center; font-size: 3.2rem; font-weight: 800; color: #fff; }
.pv-char-card-info { padding: 0.6rem 0.75rem 0.7rem; }
.pv-char-card-name { font-size: 0.92rem; font-weight: 700; color: #f0e6cf; }
.pv-char-card-nick { font-size: 0.66rem; color: rgba(255, 255, 255, 0.5); margin-left: 4px; }
.pv-char-card-rel { font-size: 0.66rem; color: rgba(255, 255, 255, 0.55); margin-top: 2px; }
.pv-char-card-aff { display: flex; align-items: center; gap: 0.5rem; margin-top: 7px; }
.pv-char-card-aff-bar { flex: 1; height: 6px; border-radius: 3px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.pv-char-card-aff-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--pv-gold), #ff6b6b); transition: width 0.4s; }
.pv-char-card-aff-num { font-size: 0.78rem; font-weight: 800; color: var(--pv-gold); }

/* ═══ 剧情 (仿 Lore) ═══ */
.pv-story { background: radial-gradient(ellipse at 30% 20%, color-mix(in srgb, var(--pv-gold) 6%, transparent), transparent 50%), rgba(7, 8, 12, 0.78); }
.pv-story-wrap { width: 90%; min-height: 82%; display: flex; gap: 2rem; align-items: center; }
/* 书本模式是"一屏阅读器"隐喻: 固定一屏高度, 目录/正文在书页内滚动 */
.pv-section.pv-story:has(.pv-book) { height: 100%; }
.pv-story-left { flex: 4; min-width: 0; display: flex; height: 100%; align-items: center; }
.pv-story-archive {
  position: relative;
  width: 100%;
  height: clamp(320px, 60vh, 560px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border: 1px solid color-mix(in srgb, var(--pv-gold) 55%, transparent);
  border-radius: 8px 2px 8px 2px;
  background:
    radial-gradient(circle at 72% 24%, color-mix(in srgb, var(--pv-gold-light) 24%, transparent), transparent 34%),
    repeating-linear-gradient(135deg, transparent 0 18px, color-mix(in srgb, var(--pv-gold) 6%, transparent) 18px 19px),
    linear-gradient(145deg, #171612, #08090d 72%);
  background-size: cover;
  background-position: center;
  box-shadow: 0 18px 45px rgba(0, 0, 0, 0.35), inset 0 0 50px rgba(0, 0, 0, 0.28);
}
.pv-story-archive::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(5, 7, 10, 0.42) 0%, rgba(5, 7, 10, 0.08) 34%, rgba(5, 7, 10, 0.96) 82%);
}
.pv-story-archive::after {
  content: '';
  position: absolute;
  inset: 10px;
  pointer-events: none;
  border: 1px solid color-mix(in srgb, var(--pv-gold) 22%, transparent);
  clip-path: polygon(0 0, 30% 0, 30% 1px, 70% 1px, 70% 0, 100% 0, 100% 100%, 68% 100%, 68% calc(100% - 1px), 32% calc(100% - 1px), 32% 100%, 0 100%);
}
.pv-story-archive-top { position: relative; z-index: 1; display: flex; align-items: center; gap: 0.65rem; padding: 1.25rem 1.35rem; }
.pv-story-archive-mark { display: grid; place-items: center; width: 35px; height: 35px; border: 1px solid color-mix(in srgb, var(--pv-gold) 65%, transparent); color: var(--pv-gold-light); font-size: 1.4rem; }
.pv-story-archive-en, .pv-story-archive-cn { display: block; line-height: 1.2; }
.pv-story-archive-en { color: rgba(255, 255, 255, 0.88); font-size: 0.72rem; letter-spacing: 0.18em; }
.pv-story-archive-cn { margin-top: 3px; color: var(--pv-gold); font-size: 0.65rem; letter-spacing: 0.28em; }
.pv-story-archive-page { margin-left: auto; color: rgba(255, 255, 255, 0.7); font: 600 0.68rem/1 monospace; letter-spacing: 0.12em; }
.pv-story-archive-fallback { position: absolute; inset: 20% 0 auto; display: grid; justify-items: center; color: color-mix(in srgb, var(--pv-gold) 48%, transparent); }
.pv-story-archive-fallback span { font-size: clamp(4.5rem, 8vw, 8rem); line-height: 1; text-shadow: 0 0 35px color-mix(in srgb, var(--pv-gold) 28%, transparent); }
.pv-story-archive-fallback small { margin-top: 0.7rem; font-size: 0.58rem; letter-spacing: 0.24em; }
.pv-story-archive-body { position: relative; z-index: 1; padding: 3.8rem 1.45rem 1.25rem; background: linear-gradient(180deg, transparent, rgba(5, 6, 9, 0.88) 34%); }
.pv-story-meta { display: flex; align-items: center; gap: 0.8rem; margin-top: 0.3rem; }
.pv-story-type { font-size: 0.62rem; color: var(--pv-gold); border: 1px solid color-mix(in srgb, var(--pv-gold) 40%, transparent); padding: 1px 8px; border-radius: 4px; }
.pv-story-time { font-size: 0.66rem; color: rgba(255, 255, 255, 0.45); }
.pv-story-cur-title { margin: 0.2rem 0 0; font-size: 1.15rem; font-weight: 700; color: #f0e6cf; }
.pv-story-content {
  font-size: 0.78rem; color: rgba(255, 255, 255, 0.62); line-height: 1.8;
  padding-right: 0.4rem;
}
.pv-story-content :deep(p) { margin: 0.3rem 0; }
.pv-story-content :deep(ul), .pv-story-content :deep(ol) { padding-left: 1.3rem; margin: 0.3rem 0; }
.pv-story-content :deep(code) { background: rgba(255, 255, 255, 0.08); padding: 1px 5px; border-radius: 4px; font-size: 0.8em; }
.pv-story-archive-excerpt { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 3; min-height: 3.9em; }
.pv-story-archive-excerpt :deep(p) { margin: 0.25rem 0; }
.pv-story-archive-nav { display: grid; grid-template-columns: 34px 1fr 34px; align-items: center; gap: 0.7rem; margin-top: 0.85rem; }
.pv-story-archive-nav::before, .pv-story-archive-nav::after { content: ''; position: absolute; }
.pv-story-archive-nav button { width: 34px; height: 28px; border: 1px solid color-mix(in srgb, var(--pv-gold) 52%, transparent); background: color-mix(in srgb, #050609 78%, transparent); color: var(--pv-gold-light); cursor: pointer; font-size: 1.15rem; line-height: 1; transition: 0.2s ease; }
.pv-story-archive-nav button:hover:not(:disabled) { background: color-mix(in srgb, var(--pv-gold) 22%, #050609); box-shadow: 0 0 12px color-mix(in srgb, var(--pv-gold) 22%, transparent); }
.pv-story-archive-nav button:disabled { opacity: 0.3; cursor: not-allowed; }
.pv-story-archive-nav span { overflow: hidden; color: rgba(255, 255, 255, 0.42); font-size: 0.55rem; letter-spacing: 0.22em; text-align: center; white-space: nowrap; }
.pv-story-archive-nav span::before, .pv-story-archive-nav span::after { content: ' ─ '; color: color-mix(in srgb, var(--pv-gold) 55%, transparent); }
.pv-story-archive-empty { align-items: center; justify-content: center; gap: 0.8rem; color: rgba(255, 255, 255, 0.55); text-align: center; }
.pv-story-archive-empty strong { color: var(--pv-gold); letter-spacing: 0.2em; }
.pv-story-archive-empty p { margin: 0; font-size: 0.76rem; }
.pv-story-right { flex: 6; min-width: 0; display: flex; align-items: center; gap: 0.8rem; height: 100%; }
.pv-story-arrow {
  flex-shrink: 0;
  width: 40px; height: 40px;
  border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--pv-gold) 50%, transparent);
  background: rgba(0, 0, 0, 0.4);
  color: var(--pv-gold);
  font-size: 1.4rem;
  cursor: pointer;
  transition: all 0.25s;
}
.pv-story-arrow:hover:not(:disabled) { background: color-mix(in srgb, var(--pv-gold) 18%, transparent); box-shadow: 0 0 14px color-mix(in srgb, var(--pv-gold) 30%, transparent); }
.pv-story-arrow:disabled { opacity: 0.25; cursor: not-allowed; }
/* 卡片轮播带封面背景: 恢复接近原 74%×82% 屏高的观感 (clamp 兼顾小屏) */
.pv-story-router { flex: 1; min-width: 0; display: flex; gap: 12px; align-items: stretch; height: clamp(320px, 60vh, 560px); }
.pv-story-card {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 1rem;
  border: 1px solid rgba(181, 152, 106, 0.5);
  border-radius: 6px;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--pv-gold) 12%, transparent), rgba(0, 0, 0, 0.75)),
    rgba(0, 0, 0, 0.4);
  transition: all 0.4s ease;
  overflow: hidden;
  position: relative;
}
.pv-story-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(160deg, color-mix(in srgb, var(--pv-gold) 16%, transparent), transparent 45%),
    repeating-linear-gradient(45deg, transparent, transparent 14px, color-mix(in srgb, var(--pv-gold) 5%, transparent) 14px, color-mix(in srgb, var(--pv-gold) 5%, transparent) 15px);
}
.pv-story-card.side { flex: 1; opacity: 0.4; cursor: pointer; transform: scale(0.96); }
.pv-story-card.main { flex: 2.1; opacity: 1; }
.pv-story-card.side:hover { opacity: 0.8; }
.pv-story-card-type { position: relative; font-size: 0.62rem; color: var(--pv-gold); border: 1px solid color-mix(in srgb, var(--pv-gold) 45%, transparent); align-self: flex-start; padding: 1px 8px; border-radius: 4px; }
.pv-story-card-title { position: relative; margin-top: 0.5rem; font-size: 0.95rem; font-weight: 700; color: #f0e6cf; }
.pv-story-card-time { position: relative; margin-top: 4px; font-size: 0.62rem; color: rgba(255, 255, 255, 0.45); }
.pv-story-card.side, .pv-story-card.main { background-size: cover; background-position: center; background-repeat: no-repeat; }

/* 模式切换 (避让顶部固定导航的安全区) */
.pv-story-mode {
  position: absolute;
  top: 76px;
  right: 46px;
  z-index: 5;
  display: flex;
  gap: 0.4rem;
}
.pv-story-mode-btn {
  padding: 0.35rem 1rem;
  border-radius: 20px;
  cursor: pointer;
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.6);
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 30%, transparent);
  transition: all 0.25s;
}
.pv-story-mode-btn:hover { color: var(--pv-gold); border-color: color-mix(in srgb, var(--pv-gold) 60%, transparent); }
.pv-story-mode-btn.active {
  color: #1a1206;
  font-weight: 700;
  background: linear-gradient(135deg, var(--pv-gold-light), var(--pv-gold));
  border-color: transparent;
  box-shadow: 0 0 12px color-mix(in srgb, var(--pv-gold) 35%, transparent);
}

/* 书本模式: 对开书页 */
.pv-book {
  width: 92%;
  height: 82%;
  display: flex;
  align-items: stretch;
}
.pv-book-page {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 1.4rem 1.6rem;
  background:
    linear-gradient(105deg, transparent 0%, color-mix(in srgb, var(--pv-gold) 5%, transparent) 100%),
    linear-gradient(180deg, #15120b, #0d0b07);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 30%, transparent);
  box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.5), 0 10px 40px rgba(0, 0, 0, 0.55);
}
.pv-book-page:first-child { border-radius: 12px 0 0 12px; }
.pv-book-page:last-child { border-radius: 0 12px 12px 0; }
.pv-book-spine {
  width: 18px;
  flex-shrink: 0;
  background: linear-gradient(90deg, color-mix(in srgb, var(--pv-gold) 75%, transparent), rgba(120, 95, 45, 0.9) 50%, color-mix(in srgb, var(--pv-gold) 75%, transparent));
  box-shadow: 0 0 14px rgba(0, 0, 0, 0.7);
}
/* 左页: 目录 */
.pv-book-toc-head { display: flex; flex-direction: column; gap: 2px; padding-bottom: 0.7rem; border-bottom: 1px solid color-mix(in srgb, var(--pv-gold) 25%, transparent); }
.pv-book-toc-en { font-family: 'mc-gamefont', serif; font-size: 0.7rem; letter-spacing: 5px; color: color-mix(in srgb, var(--pv-gold) 60%, transparent); }
.pv-book-toc-title { font-size: 1rem; font-weight: 700; letter-spacing: 3px; color: #f0e6cf; }
.pv-book-toc-list { flex: 1; min-height: 0; overflow-y: auto; padding-top: 0.6rem; display: flex; flex-direction: column; gap: 0.3rem; }
.pv-book-toc-item {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.5rem 0.6rem;
  border-radius: 7px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
}
.pv-book-toc-item:hover { background: color-mix(in srgb, var(--pv-gold) 7%, transparent); }
.pv-book-toc-item.active { background: color-mix(in srgb, var(--pv-gold) 12%, transparent); border-color: color-mix(in srgb, var(--pv-gold) 40%, transparent); }
.pv-book-toc-no { font-family: 'mc-gamefont', serif; font-size: 1rem; color: var(--pv-gold); flex-shrink: 0; }
.pv-book-toc-body { flex: 1; min-width: 0; }
.pv-book-toc-name { font-size: 0.8rem; font-weight: 700; color: #f0e6cf; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pv-book-toc-meta { font-size: 0.6rem; color: rgba(255, 255, 255, 0.45); margin-top: 1px; }
/* 右页: 正文 */
.pv-book-content-head { display: flex; justify-content: space-between; align-items: center; padding-bottom: 0.5rem; border-bottom: 1px solid color-mix(in srgb, var(--pv-gold) 20%, transparent); }
.pv-book-content-type { font-size: 0.62rem; color: var(--pv-gold); border: 1px solid color-mix(in srgb, var(--pv-gold) 40%, transparent); padding: 1px 8px; border-radius: 4px; }
.pv-book-content-time { font-size: 0.64rem; color: rgba(255, 255, 255, 0.45); }
.pv-book-content-title { margin: 0.8rem 0 0.4rem; font-family: 'mc-gamefont', serif; font-size: 1.6rem; font-weight: 400; letter-spacing: 3px; color: var(--pv-gold-light); }
.pv-book-content-img {
  width: 100%;
  max-height: 34%;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid color-mix(in srgb, var(--pv-gold) 35%, transparent);
  margin-bottom: 0.6rem;
}
.pv-book-content-md {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  font-size: 0.82rem;
  line-height: 1.9;
  color: rgba(255, 255, 255, 0.78);
  padding-right: 0.4rem;
}
.pv-book-content-md :deep(p) { margin: 0.4rem 0; }
.pv-book-content-md :deep(h1), .pv-book-content-md :deep(h2), .pv-book-content-md :deep(h3) { margin: 0.7rem 0 0.3rem; color: var(--pv-gold-light); }
.pv-book-content-md :deep(ul), .pv-book-content-md :deep(ol) { padding-left: 1.4rem; margin: 0.4rem 0; }
.pv-book-content-md :deep(code) { background: rgba(255, 255, 255, 0.08); padding: 1px 5px; border-radius: 4px; font-size: 0.8em; }
.pv-book-content-md :deep(blockquote) { border-left: 3px solid var(--pv-gold); margin: 0.4rem 0; padding-left: 0.8rem; color: rgba(255, 255, 255, 0.55); }
.pv-book-content-foot { display: flex; align-items: center; justify-content: space-between; padding-top: 0.7rem; border-top: 1px solid color-mix(in srgb, var(--pv-gold) 20%, transparent); }
.pv-book-nav-btn { font-size: 0.72rem; }
.pv-book-page-no { font-size: 0.66rem; color: color-mix(in srgb, var(--pv-gold) 70%, transparent); font-family: 'mc-gamefont', serif; letter-spacing: 2px; }

/* ═══ 玩家档案 (仿 Regions) ═══ */
.pv-profile-bg {
  position: absolute; inset: 0;
  background-size: cover; background-position: center;
  filter: blur(10px) brightness(0.4);
  transform: scale(1.15);
}
.pv-profile-veil {
  position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(7, 8, 12, 0.55), rgba(7, 8, 12, 0.92));
}
.pv-profile-wrap {
  position: relative;
  z-index: 2;
  width: 86%;
  min-height: 86%;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}
.pv-profile-hero { display: flex; align-items: center; gap: 1.3rem; }
.pv-profile-avatar {
  width: 108px; height: 108px;
  flex-shrink: 0;
  border-radius: 50%;
  overflow: hidden;
  border: 2px solid color-mix(in srgb, var(--pv-gold) 70%, transparent);
  box-shadow: 0 0 26px color-mix(in srgb, var(--pv-gold) 38%, transparent), 0 0 64px color-mix(in srgb, var(--pv-gold) 14%, transparent);
  display: grid; place-items: center;
  font-size: 2.6rem; font-weight: 800;
  color: #1a1206;
  background: linear-gradient(135deg, var(--pv-gold-light), var(--pv-gold));
}
.pv-profile-avatar img { width: 100%; height: 100%; object-fit: cover; }
.pv-profile-id { flex: 1; }
.pv-profile-name { margin: 0; font-family: 'mc-gamefont', serif; font-size: 2.4rem; font-weight: 400; letter-spacing: 4px; color: #f0e6cf; }
.pv-profile-title { margin: 2px 0 0; font-size: 0.85rem; color: var(--pv-gold); letter-spacing: 2px; }
.pv-title-badge {
  background: none;
  border: 1px solid color-mix(in srgb, var(--pv-gold) 45%, transparent);
  border-radius: 20px;
  padding: 3px 12px;
  color: var(--pv-gold);
  font-size: 0.8rem;
  letter-spacing: 1px;
  cursor: pointer;
  transition: all 0.25s;
}
.pv-title-badge:hover { background: color-mix(in srgb, var(--pv-gold) 12%, transparent); box-shadow: 0 0 10px color-mix(in srgb, var(--pv-gold) 25%, transparent); }
.pv-profile-en { margin: 4px 0 0; font-size: 0.68rem; color: rgba(255, 255, 255, 0.5); letter-spacing: 1px; }
.pv-profile-edit { flex-shrink: 0; }
.pv-profile-attrs {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.6rem 1.4rem;
  padding: 0.9rem 1.1rem;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 20%, transparent);
  border-radius: 10px;
}
.pv-profile-attr { display: flex; align-items: center; gap: 0.6rem; font-size: 0.72rem; }
.pv-profile-attr-label { color: rgba(255, 255, 255, 0.6); width: 52px; text-align: right; flex-shrink: 0; }
.pv-profile-attr-value { color: var(--pv-gold); width: 52px; flex-shrink: 0; }
.pv-attr-bar { flex: 1; height: 6px; border-radius: 3px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.pv-attr-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--pv-gold), var(--pv-gold-light)); transition: width 0.5s; }
/* 体力过低红色警示 */
.pv-profile-attr.low .pv-attr-fill { background: linear-gradient(90deg, #ff6b6b, #ff9e9e); animation: attrLowPulse 1.6s ease-in-out infinite; }
.pv-profile-attr.low .pv-profile-attr-label,
.pv-profile-attr.low .pv-profile-attr-value { color: #ff6b6b; }
@keyframes attrLowPulse {
  0%, 100% { filter: brightness(1); }
  50% { filter: brightness(1.35); }
}
.pv-profile-bio {
  padding: 0.9rem 1.1rem;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 15%, transparent);
  border-radius: 10px;
  font-size: 0.82rem;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.75);
}
.pv-profile-bio :deep(p) { margin: 0.4rem 0; }
.pv-profile-bio :deep(h1), .pv-profile-bio :deep(h2), .pv-profile-bio :deep(h3) { margin: 0.6rem 0 0.3rem; }
.pv-profile-bio :deep(ul), .pv-profile-bio :deep(ol) { padding-left: 1.4rem; margin: 0.4rem 0; }
.pv-profile-bio :deep(code) { background: rgba(255, 255, 255, 0.08); padding: 1px 5px; border-radius: 4px; font-size: 0.78em; }
.pv-profile-bio :deep(blockquote) { border-left: 3px solid var(--pv-gold); margin: 0.4rem 0; padding-left: 0.8rem; color: var(--miya-text-dim); }
.pv-profile-career { display: flex; gap: 0.8rem; flex-wrap: wrap; }
.pv-career-item {
  display: flex; flex-direction: column; align-items: center;
  flex: 1; min-width: 90px;
  padding: 0.7rem 1rem;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 20%, transparent);
  border-radius: 10px;
}
.pv-career-num { font-size: 1.25rem; font-weight: 800; color: var(--pv-gold); }
.pv-career-label { font-size: 0.62rem; color: rgba(255, 255, 255, 0.5); }

/* ═══ 数据中心 ═══ */
.pv-stats { background: radial-gradient(ellipse at 80% 10%, color-mix(in srgb, var(--pv-gold) 6%, transparent), transparent 55%), rgba(7, 8, 12, 0.78); }
.pv-stats-wrap {
  width: 92%;
  min-height: 92%;
}
.pv-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 0.75rem;
  padding-bottom: 1rem;
}
/* 数据卡依次浮现, 形成层次感 (section 显示时重放) */
.pv-stats-grid > .pv-stats-card { animation: pv-section-in 0.5s cubic-bezier(0.22, 1, 0.36, 1) both; }
.pv-stats-grid > .pv-stats-card:nth-child(2) { animation-delay: 50ms; }
.pv-stats-grid > .pv-stats-card:nth-child(3) { animation-delay: 100ms; }
.pv-stats-grid > .pv-stats-card:nth-child(4) { animation-delay: 150ms; }
.pv-stats-grid > .pv-stats-card:nth-child(5) { animation-delay: 200ms; }
.pv-stats-grid > .pv-stats-card:nth-child(6) { animation-delay: 250ms; }
.pv-stats-grid > .pv-stats-card:nth-child(7) { animation-delay: 300ms; }
.pv-stats-grid > .pv-stats-card:nth-child(8) { animation-delay: 350ms; }
.pv-stats-grid > .pv-stats-card:nth-child(9) { animation-delay: 400ms; }
.pv-stats-grid > .pv-stats-card:nth-child(10) { animation-delay: 450ms; }
.pv-stats-grid > .pv-stats-card:nth-child(n+11) { animation-delay: 500ms; }
.pv-stats-card {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.95rem 1.05rem;
  background: linear-gradient(160deg, color-mix(in srgb, var(--pv-gold) 6%, transparent), rgba(0, 0, 0, 0.45));
  border: 1px solid color-mix(in srgb, var(--pv-gold) 22%, transparent);
  border-radius: 12px;
}
.pv-stats-card-head { display: flex; align-items: center; justify-content: space-between; }
.pv-stats-card-head h3 { margin: 0; font-size: 0.95rem; letter-spacing: 1px; }
.pv-stats-card-sub { font-size: 0.66rem; color: rgba(255, 255, 255, 0.45); }
/* 成就墙 */
/* 数据中心各列表: 紧凑小窗内滚动, 避免整页被拉得过长 */
.pv-ach-grid { display: flex; flex-direction: column; gap: 0.45rem; max-height: 300px; overflow-y: auto; }
.pv-ach-item {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.5rem 0.6rem;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 0.25s;
}
.pv-ach-item.unlocked { border-color: color-mix(in srgb, var(--pv-gold) 45%, transparent); background: color-mix(in srgb, var(--pv-gold) 8%, transparent); box-shadow: 0 0 12px color-mix(in srgb, var(--pv-gold) 10%, transparent); }
.pv-ach-item:not(.unlocked) { filter: grayscale(0.9); opacity: 0.55; }
.pv-ach-icon { font-size: 1.3rem; flex-shrink: 0; }
.pv-ach-info { flex: 1; min-width: 0; }
.pv-ach-title { font-size: 0.8rem; font-weight: 700; color: #f0e6cf; }
.pv-ach-desc { font-size: 0.62rem; color: rgba(255, 255, 255, 0.45); }
.pv-ach-progress { height: 4px; border-radius: 2px; background: rgba(255, 255, 255, 0.09); overflow: hidden; margin-top: 4px; }
.pv-ach-progress-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, var(--pv-gold), var(--pv-gold-light)); transition: width 0.5s; }
.pv-ach-date { font-size: 0.6rem; color: var(--pv-gold); flex-shrink: 0; }
/* 签到足迹 */
.pv-check-grid {
  display: grid;
  grid-template-columns: repeat(14, 1fr);
  gap: 5px;
}
.pv-check-day {
  aspect-ratio: 1;
  display: grid; place-items: center;
  font-size: 0.6rem;
  border-radius: 5px;
  color: rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.07);
}
.pv-check-day.checked {
  color: #1a1206;
  font-weight: 700;
  background: linear-gradient(135deg, var(--pv-gold-light), var(--pv-gold));
  box-shadow: 0 0 8px color-mix(in srgb, var(--pv-gold) 35%, transparent);
}
.pv-check-day.today { border-color: var(--pv-gold); }
.pv-check-btn { align-self: center; margin-top: 0.2rem; }
/* 任务统计 */
.pv-sts-big { display: flex; align-items: baseline; gap: 0.6rem; }
.pv-sts-rate { font-family: 'mc-gamefont', serif; font-size: 2.6rem; color: var(--pv-gold); }
.pv-sts-rate small { font-size: 1.1rem; }
.pv-sts-rate-label { font-size: 0.72rem; color: rgba(255, 255, 255, 0.55); }
.pv-sts-bar { height: 8px; border-radius: 4px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.pv-sts-bar-fill { height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--pv-gold), #7c4dff); transition: width 0.6s; }
.pv-sts-trend { display: flex; align-items: flex-end; gap: 6px; height: 84px; }
.pv-sts-trend-col { flex: 1; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 3px; }
.pv-sts-trend-bar {
  width: 70%;
  min-height: 4px;
  border-radius: 3px 3px 0 0;
  background: linear-gradient(180deg, var(--pv-gold-light), color-mix(in srgb, var(--pv-gold) 35%, transparent));
  display: flex; align-items: flex-start; justify-content: center;
  color: var(--pv-gold); font-size: 0.58rem;
  transition: height 0.5s;
}
.pv-sts-trend-label { font-size: 0.56rem; color: rgba(255, 255, 255, 0.4); }
.pv-sts-line { font-size: 0.7rem; color: rgba(255, 255, 255, 0.55); }
/* 收集分布 */
.pv-sts-rows { display: flex; flex-direction: column; gap: 0.4rem; }
.pv-sts-row { display: flex; align-items: center; gap: 0.55rem; font-size: 0.7rem; }
.pv-sts-row-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.pv-sts-row-label { width: 38px; color: rgba(255, 255, 255, 0.6); }
.pv-sts-row-bar { flex: 1; height: 7px; border-radius: 4px; background: rgba(255, 255, 255, 0.08); overflow: hidden; }
.pv-sts-row-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
.pv-sts-row-num { width: 22px; text-align: right; color: #f0e6cf; }
.pv-sts-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.pv-sts-chip {
  font-size: 0.62rem;
  padding: 2px 9px;
  border-radius: 12px;
  color: rgba(255, 255, 255, 0.6);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.09);
}
.pv-sts-chip b { color: var(--pv-gold); }
/* 好感度排行 */
.pv-aff-rank { display: flex; flex-direction: column; gap: 0.45rem; max-height: 300px; overflow-y: auto; }
.pv-aff-rank-item { display: flex; align-items: center; gap: 0.6rem; font-size: 0.74rem; }
.pv-aff-rank-no {
  width: 20px; height: 20px;
  flex-shrink: 0;
  display: grid; place-items: center;
  border-radius: 5px;
  font-size: 0.62rem; font-weight: 700;
  background: rgba(255, 255, 255, 0.07);
  color: rgba(255, 255, 255, 0.55);
}
.pv-aff-rank-no.top { background: linear-gradient(135deg, var(--pv-gold-light), var(--pv-gold)); color: #1a1206; }
.pv-aff-rank-name { width: 76px; flex-shrink: 0; color: #f0e6cf; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pv-aff-rank-bar { flex: 1; height: 7px; border-radius: 4px; background: rgba(255, 255, 255, 0.08); overflow: hidden; }
.pv-aff-rank-fill { height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--pv-gold), #ff6b6b); transition: width 0.5s; }
.pv-aff-rank-num { width: 28px; text-align: right; color: var(--pv-gold); font-weight: 700; }
/* 弥娅寄语列表 */
.pv-notes-list { display: flex; flex-direction: column; gap: 0.5rem; max-height: 300px; overflow-y: auto; }
.pv-note-item {
  display: flex;
  gap: 0.65rem;
  padding: 0.6rem 0.7rem;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.pv-note-item.pinned { border-color: color-mix(in srgb, var(--pv-gold) 45%, transparent); background: color-mix(in srgb, var(--pv-gold) 7%, transparent); }
.pv-note-mood { font-size: 1.2rem; flex-shrink: 0; }
.pv-note-body { flex: 1; min-width: 0; }
.pv-note-content { font-size: 0.76rem; color: rgba(255, 255, 255, 0.78); line-height: 1.6; }
.pv-note-content :deep(p) { margin: 0.15rem 0; }
.pv-note-meta { display: flex; gap: 0.6rem; margin-top: 4px; font-size: 0.6rem; color: rgba(255, 255, 255, 0.4); }
.pv-note-pin { color: var(--pv-gold); }

/* 全局动态流 */
.pv-feed-list { display: flex; flex-direction: column; gap: 0.35rem; max-height: 300px; overflow-y: auto; }.pv-feed-item {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.035);
  border-left: 2px solid color-mix(in srgb, var(--pv-gold) 35%, transparent);
}
.pv-feed-icon {
  flex-shrink: 0;
  width: 20px; height: 20px;
  display: grid; place-items: center;
  font-size: 0.72rem;
  color: var(--pv-gold);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 35%, transparent);
  border-radius: 5px;
}
.pv-feed-body { flex: 1; min-width: 0; }
.pv-feed-summary { font-size: 0.76rem; color: #f0e6cf; }
.pv-feed-detail { font-size: 0.64rem; color: rgba(255, 255, 255, 0.45); margin-top: 1px; }
.pv-feed-time { flex-shrink: 0; font-size: 0.58rem; color: rgba(255, 255, 255, 0.35); margin-top: 2px; }
.pv-feed-item.miya {
  border-left-color: rgba(255, 255, 255, 0.2);
  background: color-mix(in srgb, var(--pv-gold) 5%, transparent);
}
.pv-feed-comment {
  margin-top: 4px;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 0.66rem;
  color: var(--pv-gold-light);
  background: color-mix(in srgb, var(--pv-gold) 10%, transparent);
  border-left: 2px solid var(--pv-gold);
}

/* 币种按钮 */
.pv-currency-btn {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: all 0.25s;
}
.pv-currency-btn:hover { border-color: color-mix(in srgb, var(--pv-gold) 70%, transparent); background: color-mix(in srgb, var(--pv-gold) 14%, transparent); }
.pv-nav-coins { display: flex; align-items: center; gap: 6px; }
.pv-nav-coin {
  cursor: default;
  transition: all 0.25s;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.68rem;
  font-weight: 700;
  padding: 3px 10px;
  border: 1px solid color-mix(in srgb, var(--pv-gold) 40%, transparent);
  border-radius: 20px;
  background: color-mix(in srgb, var(--pv-gold) 8%, transparent);
}
.pv-nav-coin.miya { color: var(--pv-gold); }
.pv-nav-coin.earth { color: #9fe3c0; cursor: pointer; border-color: rgba(159, 227, 192, 0.4); background: rgba(159, 227, 192, 0.07); }
.pv-nav-coin.earth:hover { border-color: rgba(159, 227, 192, 0.8); background: rgba(159, 227, 192, 0.14); }
.pv-nav-coin-switch { font-size: 0.62rem; opacity: 0.7; }
.pv-nav-care {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 700;
  color: #f0e6cf;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 40%, transparent);
  transition: all 0.25s;
}
.pv-nav-care:hover { color: var(--pv-gold); border-color: color-mix(in srgb, var(--pv-gold) 80%, transparent); box-shadow: 0 0 10px color-mix(in srgb, var(--pv-gold) 30%, transparent); }
.pv-nav-care.due {
  color: #ff8f8f;
  border-color: rgba(255, 107, 107, 0.65);
  background: rgba(255, 107, 107, 0.14);
  animation: carePulse 1.8s ease-in-out infinite;
}
.pv-nav-care.checkin {
  color: var(--pv-gold);
  border-color: color-mix(in srgb, var(--pv-gold) 75%, transparent);
  box-shadow: 0 0 12px color-mix(in srgb, var(--pv-gold) 35%, transparent);
}
@keyframes carePulse {
  0%, 100% { box-shadow: 0 0 4px rgba(255, 107, 107, 0.3); }
  50% { box-shadow: 0 0 14px rgba(255, 107, 107, 0.6); }
}

/* 循环任务标记 */
.pv-board-item-rec {
  flex-shrink: 0;
  font-size: 0.72rem;
  color: var(--pv-gold);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 40%, transparent);
  border-radius: 50%;
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
}

/* 档案页现实资产 */
.pv-profile-money { display: flex; gap: 0.7rem; margin-top: 0.5rem; }
.pv-profile-money-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0.5rem 0.9rem;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 25%, transparent);
  border-radius: 9px;
}
.pv-profile-money-item.clickable { cursor: pointer; transition: all 0.25s; border-color: rgba(159, 227, 192, 0.35); }
.pv-profile-money-item.clickable:hover { border-color: rgba(159, 227, 192, 0.7); background: rgba(159, 227, 192, 0.07); }
.pv-profile-money-label { font-size: 0.6rem; color: rgba(255, 255, 255, 0.5); letter-spacing: 1px; }
.pv-profile-money-num { font-size: 1.05rem; font-weight: 800; color: #9fe3c0; }
.pv-modal-sm { width: 360px; }

/* 本周报告 */
.pv-weekly-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; }
.pv-weekly-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 0.5rem 0.3rem;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 8px;
}
.pv-weekly-num { font-size: 1.15rem; font-weight: 800; color: #f0e6cf; }
.pv-weekly-label { font-size: 0.58rem; color: rgba(255, 255, 255, 0.45); }

/* 到期提醒 */
.pv-due-list { display: flex; flex-direction: column; gap: 0.4rem; max-height: 220px; overflow-y: auto; }
.pv-due-item {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.035);
  border-left: 2px solid rgba(255, 179, 0, 0.5);
  cursor: pointer;
  transition: background 0.2s;
}
.pv-due-item:hover { background: rgba(255, 179, 0, 0.07); }
.pv-due-tag {
  flex-shrink: 0;
  font-size: 0.58rem;
  padding: 1px 7px;
  border-radius: 4px;
  color: #ffb300;
  border: 1px solid rgba(255, 179, 0, 0.45);
}
.pv-due-tag.overdue { color: #ff6b6b; border-color: rgba(255, 107, 107, 0.5); background: rgba(255, 107, 107, 0.1); }
.pv-due-title { flex: 1; min-width: 0; font-size: 0.74rem; color: #f0e6cf; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pv-due-time { flex-shrink: 0; font-size: 0.6rem; color: rgba(255, 255, 255, 0.45); }

/* 称号选择弹窗 */
.pv-titles-hint { margin: 0 0 0.4rem; font-size: 0.66rem; color: var(--miya-text-dim); }
.pv-titles-list { display: flex; flex-direction: column; gap: 0.4rem; max-height: 46vh; overflow-y: auto; }

/* 单人世界地图 */
.pv-world { background: radial-gradient(ellipse at 18% 18%, rgba(201, 172, 103, 0.12), transparent 48%), rgba(7, 8, 12, 0.86); }
.pv-world-wrap { width: min(1180px, 90%); padding: 5rem 0 4rem; margin: 0 auto; }
.pv-shop-wrap { width: min(1180px, 90%); padding: 5rem 0 4rem; margin: 0 auto; }
.pv-world-head { display: flex; justify-content: space-between; gap: 2rem; align-items: flex-end; margin-bottom: 1.5rem; }
.pv-world-head h2 { margin: 0.25rem 0 0.5rem; color: #f0e6cf; font-size: clamp(1.5rem, 3vw, 2.4rem); letter-spacing: 0.08em; }
.pv-world-head p:not(.pv-story-en) { max-width: 640px; margin: 0; color: rgba(255, 255, 255, 0.58); line-height: 1.7; font-size: 0.8rem; }
.pv-world-count { flex-shrink: 0; color: var(--pv-gold); font-size: 0.75rem; letter-spacing: 0.08em; }
.pv-world-atmosphere { display: flex; gap: 1.2rem; flex-wrap: wrap; margin-bottom: 0.9rem; color: rgba(255, 255, 255, 0.62); font-size: 0.7rem; }
.pv-world-event { display: flex; align-items: center; gap: 0.9rem; margin-bottom: 1rem; padding: 0.9rem 1rem; border: 1px solid color-mix(in srgb, var(--world-color) 42%, transparent); background: linear-gradient(100deg, color-mix(in srgb, var(--world-color) 14%, transparent), rgba(255, 255, 255, 0.02)); }
.pv-world-event-icon { color: var(--world-color); font-size: 1.8rem; }
.pv-world-event-copy { flex: 1; min-width: 0; }
.pv-world-event-copy strong { display: block; color: #f0e6cf; font-size: 0.85rem; }
.pv-world-event-copy span { color: var(--world-color); font-size: 0.62rem; }
.pv-world-event-copy p { margin: 0.25rem 0 0; color: rgba(255, 255, 255, 0.55); font-size: 0.7rem; line-height: 1.5; }
.pv-world-event-btn { flex-shrink: 0; color: var(--world-color); border-color: color-mix(in srgb, var(--world-color) 55%, transparent); background: color-mix(in srgb, var(--world-color) 10%, transparent); }
.pv-world-event-status { flex-shrink: 0; color: var(--world-color); font-size: 0.65rem; border: 1px solid color-mix(in srgb, var(--world-color) 38%, transparent); padding: 0.35rem 0.5rem; }
.pv-world-shop { margin-bottom: 1rem; padding: 0.9rem 1rem; border: 1px solid rgba(240, 163, 91, 0.32); background: linear-gradient(120deg, rgba(240, 163, 91, 0.11), rgba(255, 255, 255, 0.02)); }
.pv-world-shop-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; margin-bottom: 0.75rem; }
.pv-world-shop-head strong { display: block; color: #f0e6cf; font-size: 0.82rem; }
.pv-world-shop-head span { color: rgba(255, 255, 255, 0.48); font-size: 0.62rem; }
.pv-world-shop-currency { color: #f0a35b !important; }
.pv-miya-shop { border-color: color-mix(in srgb, var(--pv-gold) 34%, transparent); background: linear-gradient(120deg, color-mix(in srgb, var(--pv-gold) 9%, transparent), rgba(255, 255, 255, 0.02)); }
.pv-miya-shop .pv-world-shop-currency { color: var(--pv-gold-light) !important; }
.pv-world-shop-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.6rem; }
.pv-world-shop-item { min-width: 0; padding: 0.7rem; border: 1px solid rgba(255, 255, 255, 0.1); background: rgba(0, 0, 0, 0.24); }
.pv-world-shop-item-kind { color: #f0a35b; font-size: 0.58rem; }
.pv-world-shop-item h4 { margin: 0.35rem 0 0.25rem; color: #f0e6cf; font-size: 0.76rem; }
.pv-world-shop-item p { min-height: 2.6em; margin: 0; color: rgba(255, 255, 255, 0.5); font-size: 0.63rem; line-height: 1.5; }
.pv-world-shop-foot { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; margin-top: 0.65rem; color: #ffd54f; font-size: 0.68rem; }
.pv-world-shop-foot button { padding: 0.28rem 0.5rem; font-size: 0.62rem; }
.pv-world-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0.8rem; }
.pv-world-region { min-height: 290px; display: flex; flex-direction: column; padding: 1rem; border: 1px solid color-mix(in srgb, var(--world-color) 38%, transparent); background: linear-gradient(160deg, color-mix(in srgb, var(--world-color) 12%, transparent), rgba(255, 255, 255, 0.025)); background-size: cover; background-position: center; box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06); }
.pv-world-region.has-photo { text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5); }
.pv-world-region-top { display: flex; justify-content: space-between; align-items: center; }
.pv-world-icon { color: var(--world-color); font-size: 1.8rem; }
.pv-world-level { color: rgba(255, 255, 255, 0.48); font-size: 0.62rem; }
.pv-world-region h3 { margin: 1rem 0 0.15rem; color: #f0e6cf; font-size: 1rem; }
.pv-world-subtitle { color: var(--world-color); font-size: 0.65rem; letter-spacing: 0.06em; }
.pv-world-region p { flex: 1; margin: 0.8rem 0; color: rgba(255, 255, 255, 0.54); font-size: 0.72rem; line-height: 1.65; }
/* 区域卡片 Markdown 描述 (与剧情板块同款渲染效果) */
.pv-world-region-desc { flex: 1; margin: 0.8rem 0; overflow-y: auto; scrollbar-width: thin; }
.pv-world-region-desc :deep(p) { margin: 0 0 0.45rem; color: rgba(255, 255, 255, 0.54); font-size: 0.72rem; line-height: 1.65; }
.pv-world-region-desc :deep(strong) { color: rgba(255, 255, 255, 0.78); }
.pv-world-region-desc :deep(ul), .pv-world-region-desc :deep(ol) { margin: 0.35rem 0; padding-left: 1.1rem; color: rgba(255, 255, 255, 0.54); font-size: 0.72rem; line-height: 1.65; }
.pv-world-region-desc :deep(h1), .pv-world-region-desc :deep(h2), .pv-world-region-desc :deep(h3), .pv-world-region-desc :deep(h4) { margin: 0.55rem 0 0.3rem; color: #f0e6cf; font-size: 0.8rem; }
.pv-world-region-desc :deep(blockquote) { margin: 0.4rem 0; padding: 0.25rem 0.7rem; border-left: 2px solid var(--world-color); color: rgba(255, 255, 255, 0.6); font-size: 0.72rem; }
.pv-world-region-desc :deep(code) { padding: 0.05rem 0.3rem; border-radius: 3px; background: rgba(255, 255, 255, 0.08); font-size: 0.68rem; }
.pv-world-region-top-actions { display: flex; align-items: center; gap: 0.4rem; }
.pv-world-edit-btn { padding: 0.15rem 0.5rem; font-size: 0.6rem; }
.pv-world-edit-form { flex: 1; display: flex; flex-direction: column; gap: 0.45rem; margin: 0.7rem 0; }
.pv-world-edit-input { padding: 0.4rem 0.55rem; border: 1px solid color-mix(in srgb, var(--world-color) 45%, transparent); background: rgba(0, 0, 0, 0.35); color: #f0e6cf; font-size: 0.75rem; }
.pv-world-edit-input:focus { outline: none; border-color: var(--world-color); }
.pv-world-edit-textarea { flex: 1; min-height: 76px; padding: 0.45rem 0.55rem; border: 1px solid color-mix(in srgb, var(--world-color) 45%, transparent); background: rgba(0, 0, 0, 0.35); color: rgba(255, 255, 255, 0.8); font-size: 0.72rem; line-height: 1.6; resize: vertical; }
.pv-world-edit-textarea:focus { outline: none; border-color: var(--world-color); }
.pv-world-edit-actions { display: flex; gap: 0.5rem; }
.pv-world-progress { height: 4px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.pv-world-progress span { display: block; height: 100%; background: var(--world-color); transition: width 0.35s ease; }
.pv-world-meta { display: flex; justify-content: space-between; margin: 0.4rem 0 0.75rem; color: rgba(255, 255, 255, 0.45); font-size: 0.62rem; }
.pv-world-resonance { margin: 0.2rem 0 0.7rem; color: rgba(255, 255, 255, 0.58); font-size: 0.6rem; }
.pv-world-resonance > div:first-child { display: flex; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.3rem; }
.pv-world-resonance-bar { height: 3px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.pv-world-resonance-bar span { display: block; height: 100%; background: var(--pv-gold); transition: width 0.35s ease; }
.pv-world-conditions { display: flex; flex-direction: column; gap: 0.2rem; margin-bottom: 0.6rem; color: rgba(255, 255, 255, 0.42); font-size: 0.58rem; }
.pv-world-conditions span.available { color: var(--pv-gold-light); }
.pv-world-photo-btn { display: block; margin-bottom: 0.45rem; padding: 0.34rem 0.55rem; border: 1px dashed color-mix(in srgb, var(--world-color) 45%, transparent); color: rgba(255, 255, 255, 0.56); font-size: 0.61rem; text-align: center; cursor: pointer; }
.pv-world-photo-btn:hover { color: var(--world-color); background: color-mix(in srgb, var(--world-color) 10%, transparent); }
.pv-world-photo-btn input { display: none; }
.pv-world-explore { width: 100%; border-color: color-mix(in srgb, var(--world-color) 55%, transparent); color: var(--world-color); background: color-mix(in srgb, var(--world-color) 10%, transparent); }
.pv-world-explore:hover:not(:disabled) { background: color-mix(in srgb, var(--world-color) 22%, transparent); }
.pv-world-explore:disabled { opacity: 0.45; cursor: not-allowed; }
.pv-world-commission { width: 100%; margin-top: 0.45rem; padding: 0.38rem 0.55rem; color: rgba(255, 255, 255, 0.62); font-size: 0.62rem; }
.pv-world-message { margin-top: 1rem; padding: 0.75rem 1rem; border-left: 2px solid var(--pv-gold); background: rgba(201, 172, 103, 0.08); color: #f0e6cf; font-size: 0.78rem; }
.pv-world-companion { display: flex; gap: 0.7rem; margin-top: 0.65rem; padding: 0.8rem 1rem; border: 1px solid color-mix(in srgb, var(--pv-gold) 28%, transparent); background: color-mix(in srgb, var(--pv-gold) 6%, transparent); }
.pv-world-companion-mark { color: var(--pv-gold); font-size: 1.25rem; }
.pv-world-companion-label { color: var(--pv-gold-light); font-size: 0.65rem; }
.pv-world-companion p { margin: 0.25rem 0 0; color: rgba(255, 255, 255, 0.68); font-size: 0.72rem; line-height: 1.6; }
.pv-world-choice { margin-top: 0.65rem; padding: 0.8rem 1rem; border: 1px solid rgba(201, 172, 103, 0.25); background: rgba(201, 172, 103, 0.05); }
.pv-world-choice-title { color: var(--pv-gold-light); font-size: 0.68rem; margin-bottom: 0.55rem; }
.pv-world-choice-buttons { display: flex; gap: 0.45rem; flex-wrap: wrap; }
.pv-world-choice-buttons button { padding: 0.35rem 0.6rem; font-size: 0.62rem; }
.pv-world-log { margin-top: 1.5rem; border-top: 1px solid rgba(255, 255, 255, 0.1); }
.pv-world-log-head { display: flex; justify-content: space-between; padding: 0.75rem 0; color: var(--pv-gold); font-size: 0.72rem; }
.pv-world-log-head span:last-child { color: rgba(255, 255, 255, 0.38); font-size: 0.62rem; }
.pv-world-log-item { display: flex; align-items: center; gap: 0.55rem; padding: 0.6rem 0.45rem; border-top: 1px solid rgba(255, 255, 255, 0.09); font-size: 0.7rem; border-radius: 6px; transition: background 0.25s, color 0.25s; }
.pv-world-log-item:hover { background: color-mix(in srgb, var(--pv-gold) 7%, transparent); color: var(--pv-gold-light); }
/* 归档内补选同行决定 */
.pv-world-log-choice { padding: 0.6rem 0 0.2rem; border-top: 1px dashed color-mix(in srgb, var(--pv-gold) 30%, transparent); display: flex; flex-direction: column; gap: 0.45rem; }
.pv-world-log-choice-label { font-size: 0.66rem; color: var(--pv-gold-light); }
.pv-world-log-mark { color: var(--pv-gold); }
.pv-world-log-title { flex: 1; color: #f0e6cf; }
.pv-world-log-reward { color: rgba(255, 255, 255, 0.42); font-size: 0.62rem; }
@media (max-width: 1100px) { .pv-world-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 1100px) { .pv-world-shop-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 700px) { .pv-world-wrap, .pv-shop-wrap { width: 92%; padding: 3rem 0; } .pv-world-head { display: block; } .pv-world-count { margin-top: 0.8rem; } .pv-world-grid { grid-template-columns: 1fr; } .pv-world-region { min-height: 230px; } .pv-world-event { align-items: flex-start; flex-wrap: wrap; } .pv-world-event-btn { margin-left: 2.7rem; } .pv-world-shop-head { display: block; } .pv-world-shop-currency { display: block; margin-top: 0.35rem; } .pv-world-shop-grid { grid-template-columns: 1fr; } }
.pv-title-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.7rem;
  border-radius: 9px;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: all 0.2s;
}
.pv-title-item:hover { border-color: color-mix(in srgb, var(--pv-gold) 50%, transparent); background: color-mix(in srgb, var(--pv-gold) 7%, transparent); }
.pv-title-item.equipped {
  border-color: color-mix(in srgb, var(--pv-gold) 70%, transparent);
  background: color-mix(in srgb, var(--pv-gold) 12%, transparent);
  box-shadow: 0 0 12px color-mix(in srgb, var(--pv-gold) 20%, transparent);
}
.pv-title-item-icon { font-size: 0.95rem; color: var(--pv-gold); }
.pv-title-item-name { flex: 1; font-size: 0.8rem; color: #f0e6cf; }
.pv-title-item-tag { font-size: 0.58rem; color: rgba(255, 255, 255, 0.4); padding: 1px 7px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.15); }
.pv-title-item-tag.unlocked { color: var(--pv-gold); border-color: color-mix(in srgb, var(--pv-gold) 40%, transparent); }

/* ── 档案侧边栏 ── */
.pv-drawer-mask {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.45);
  display: flex; justify-content: flex-end; z-index: 900;
}
.pv-drawer {
  width: 400px; max-width: 92vw; height: 100%;
  background: #10141a;
  border-left: 1px solid color-mix(in srgb, var(--pv-gold) 30%, transparent);
  display: flex; flex-direction: column;
  box-shadow: -8px 0 30px rgba(0, 0, 0, 0.5);
}
.pv-drawer-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.7rem 1rem;
  border-bottom: 1px solid color-mix(in srgb, var(--pv-gold) 18%, transparent);
}
.pv-drawer-head-label { font-size: 0.8rem; font-weight: 700; color: var(--pv-gold); letter-spacing: 2px; }
.pv-drawer-close {
  width: 28px; height: 28px; border-radius: 7px; cursor: pointer;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: var(--miya-text); font-size: 0.8rem;
}
.pv-drawer-cover { position: relative; height: 200px; overflow: hidden; background: rgba(255, 255, 255, 0.04); }
.pv-drawer-cover-img { width: 100%; height: 100%; object-fit: cover; }
.pv-drawer-cover-ph { width: 100%; height: 100%; display: grid; place-items: center; font-size: 3.4rem; color: #fff; }
.pv-drawer-cover-char .pv-drawer-cover-ph { font-size: 4rem; }
.pv-drawer-rarity { position: absolute; top: 10px; left: 10px; padding: 3px 10px; border-radius: 5px; font-size: 0.66rem; color: #fff; }
.pv-drawer-body { flex: 1; overflow-y: auto; padding: 1rem 1.1rem; display: flex; flex-direction: column; gap: 0.5rem; }
.pv-drawer-title { font-size: 1.15rem; font-weight: 800; }
.pv-drawer-nick { font-size: 0.72rem; color: var(--miya-text-dim); margin-left: 6px; font-weight: 400; }
.pv-drawer-sub { display: flex; align-items: center; gap: 0.6rem; font-size: 0.7rem; color: var(--miya-chat-ai); }
.pv-drawer-qty { color: var(--miya-text-dim); }
.pv-drawer-birthday { font-size: 0.7rem; color: var(--miya-text-dim); }
/* 好感度变动日志 */
.pv-aff-logs { display: flex; flex-direction: column; gap: 2px; max-height: 180px; overflow-y: auto; }
.pv-aff-log { display: flex; align-items: center; gap: 0.5rem; font-size: 0.66rem; padding: 2px 0; }
.pv-aff-log-delta { flex-shrink: 0; min-width: 34px; font-weight: 700; }
.pv-aff-log-delta.up { color: #81c784; }
.pv-aff-log-delta.down { color: #ff6b6b; }
.pv-aff-log-reason { flex: 1; min-width: 0; color: var(--miya-text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pv-aff-log-time { flex-shrink: 0; font-size: 0.58rem; color: rgba(255, 255, 255, 0.3); }
.pv-drawer-section {
  margin-top: 0.6rem; font-size: 0.78rem; font-weight: 700; color: var(--pv-gold);
  border-top: 1px dashed color-mix(in srgb, var(--pv-gold) 25%, transparent);
  padding-top: 0.6rem;
}
.pv-drawer-brief { margin: 0; font-size: 0.78rem; color: var(--miya-text-dim); line-height: 1.6; }
.pv-drawer-expand { align-self: flex-start; }
.pv-drawer-md {
  font-size: 0.8rem; line-height: 1.7;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px; padding: 0.8rem 1rem;
  max-height: 340px; overflow-y: auto;
}
.pv-drawer-md :deep(p) { margin: 0.4rem 0; }
.pv-drawer-md :deep(h1), .pv-drawer-md :deep(h2), .pv-drawer-md :deep(h3) { margin: 0.6rem 0 0.3rem; }
.pv-drawer-md :deep(ul), .pv-drawer-md :deep(ol) { padding-left: 1.4rem; margin: 0.4rem 0; }
.pv-drawer-md :deep(code) { background: rgba(255, 255, 255, 0.08); padding: 1px 5px; border-radius: 4px; font-size: 0.8em; }
.pv-drawer-md :deep(blockquote) { border-left: 3px solid var(--pv-gold); margin: 0.4rem 0; padding-left: 0.8rem; color: var(--miya-text-dim); }
.drawer-enter-active, .drawer-leave-active { transition: all 0.25s ease; }
.drawer-enter-from .pv-drawer, .drawer-leave-to .pv-drawer { transform: translateX(100%); }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }

/* ── 弹窗 ── */
.pv-modal-mask {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.6); display: grid; place-items: center; z-index: 1000; backdrop-filter: blur(3px);
  animation: pv-fade-in 0.22s ease both;
}
.pv-modal { width: 480px; max-width: 94vw; max-height: 88vh; overflow-y: auto; background: #14181f; border: 1px solid color-mix(in srgb, var(--pv-gold) 30%, transparent); border-radius: 12px; padding: 1.2rem; display: flex; flex-direction: column; gap: 0.4rem; animation: pv-modal-pop 0.32s cubic-bezier(0.22, 1, 0.36, 1) both; }
@keyframes pv-fade-in { from { opacity: 0; } }
@keyframes pv-modal-pop {
  from { opacity: 0; transform: translateY(16px) scale(0.97); }
  to { opacity: 1; transform: none; }
}
.pv-modal h3 { margin: 0 0 0.4rem; font-size: 1rem; }
.pv-modal label { font-size: 0.7rem; color: var(--miya-text-dim); margin-top: 0.3rem; }
.pv-modal input, .pv-modal textarea {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px; padding: 0.45rem 0.6rem;
  color: var(--miya-text); font-size: 0.8rem; outline: none;
}
.pv-md-editor { resize: vertical; min-height: 120px; font-family: 'Cascadia Code', Consolas, monospace; line-height: 1.5; }
.pv-modal-upload { display: flex; align-items: center; gap: 0.6rem; }
.pv-modal-preview { width: 64px; height: 64px; object-fit: cover; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); }
.pv-upload-btn { display: inline-block; cursor: pointer; }
.pv-modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.8rem; }
.pv-bio-preview { margin-top: 0.2rem; }

/* ── 加载失败横幅 ── */
.pv-load-error { gap: 0.6rem; display: flex; flex-direction: column; align-items: center; }
.pv-load-error-title { font-size: 0.95rem; color: #ff8f8f; letter-spacing: 1px; }
.pv-load-error-sub { font-size: 0.72rem; color: rgba(255, 255, 255, 0.5); }

/* ── 档案页地球币记账小按钮 ── */
.pv-ledger-btn {
  margin-left: 6px;
  padding: 1px 8px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.58rem;
  color: #9fe3c0;
  background: rgba(159, 227, 192, 0.08);
  border: 1px solid rgba(159, 227, 192, 0.4);
  transition: all 0.25s;
}
.pv-ledger-btn:hover { border-color: rgba(159, 227, 192, 0.8); background: rgba(159, 227, 192, 0.16); }

/* ── 每周纪行 (v17) ── */
.pv-bp-points { display: flex; align-items: baseline; gap: 0.55rem; }
.pv-bp-points-num { font-family: 'mc-gamefont', serif; font-size: 2.2rem; color: var(--pv-gold); }
.pv-bp-points-label { font-size: 0.72rem; color: rgba(255, 255, 255, 0.55); }
.pv-bp-points-next { margin-left: auto; font-size: 0.66rem; color: color-mix(in srgb, var(--pv-gold) 80%, transparent); }
.pv-bp-bar { height: 8px; border-radius: 4px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.pv-bp-bar-fill { height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--pv-gold), var(--pv-gold-light)); transition: width 0.6s; }
.pv-bp-bar-fill.memory { background: linear-gradient(90deg, #7c4dff, var(--pv-gold-light)); }
.pv-bp-tiers { display: flex; gap: 5px; overflow-x: auto; padding-bottom: 2px; }
.pv-bp-tier {
  flex: 1; min-width: 58px;
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  padding: 0.4rem 0.25rem;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.09);
  font-size: 0.6rem;
}
.pv-bp-tier.claimed { border-color: color-mix(in srgb, var(--pv-gold) 30%, transparent); opacity: 0.55; }
.pv-bp-tier.claimable {
  border-color: var(--pv-gold);
  background: color-mix(in srgb, var(--pv-gold) 14%, transparent);
  box-shadow: 0 0 12px color-mix(in srgb, var(--pv-gold) 22%, transparent);
}
.pv-bp-tier.locked { opacity: 0.6; }
.pv-bp-tier-no { font-family: 'mc-gamefont', serif; font-size: 0.78rem; color: var(--pv-gold); }
.pv-bp-tier-reward { color: #ffd54f; font-size: 0.58rem; }
.pv-bp-tier-state { font-size: 0.54rem; color: rgba(255, 255, 255, 0.45); }
.pv-bp-claim-btn {
  padding: 2px 10px; border-radius: 10px; cursor: pointer;
  font-size: 0.58rem; font-weight: 700;
  color: #1a1206;
  background: linear-gradient(135deg, var(--pv-gold-light), var(--pv-gold));
  border: none;
}
.pv-bp-claim-btn:disabled { filter: grayscale(0.6); cursor: not-allowed; }
.pv-bp-breakdown { display: flex; flex-wrap: wrap; gap: 5px; }

/* ── 周挑战 (v17) ── */
.pv-wc-stars { display: flex; align-items: baseline; gap: 0.6rem; }
.pv-wc-stars-label { font-family: 'mc-gamefont', serif; font-size: 2.2rem; color: var(--pv-gold); letter-spacing: 6px; text-shadow: 0 0 18px color-mix(in srgb, var(--pv-gold) 35%, transparent); }
.pv-wc-stars-sub { font-size: 0.7rem; color: rgba(255, 255, 255, 0.5); }
.pv-wc-desc { margin: 0; font-size: 0.72rem; color: rgba(255, 255, 255, 0.55); line-height: 1.6; }
.pv-wc-progress { display: flex; flex-direction: column; gap: 4px; }
.pv-wc-progress-label { font-size: 0.68rem; color: rgba(255, 255, 255, 0.6); }
.pv-wc-suggestions { margin: 0; padding: 0 0 0 1.05rem; display: flex; flex-direction: column; gap: 3px; font-size: 0.68rem; color: color-mix(in srgb, var(--pv-gold) 82%, white); }

/* ── 动态流评论按钮 ── */
.pv-feed-side { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; flex-shrink: 0; }
.pv-feed-comment-btn {
  padding: 2px 8px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.56rem;
  color: color-mix(in srgb, var(--pv-gold) 85%, white);
  background: color-mix(in srgb, var(--pv-gold) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 35%, transparent);
  transition: all 0.25s;
}
.pv-feed-comment-btn:hover { background: color-mix(in srgb, var(--pv-gold) 18%, transparent); border-color: color-mix(in srgb, var(--pv-gold) 70%, transparent); }

/* ── 回忆卡池 (v17) ── */
.pv-memory-shop .pv-world-shop-currency { color: var(--pv-gold-light) !important; }
.pv-memory-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.7rem; margin-bottom: 0.65rem; }
.pv-memory-stat { display: flex; flex-direction: column; gap: 4px; }
.pv-memory-stat-label { color: rgba(255, 255, 255, 0.55); font-size: 0.62rem; }
.pv-memory-stat-num { color: var(--pv-gold); font-size: 1rem; font-weight: 800; }
.pv-memory-actions { display: flex; gap: 0.6rem; }
.pv-memory-actions button { min-width: 130px; }
.pv-memory-records { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-top: 0.65rem; }
.pv-memory-records-label { color: rgba(255, 255, 255, 0.4); font-size: 0.58rem; }
.pv-memory-record {
  font-size: 0.6rem; padding: 2px 9px; border-radius: 10px;
  color: rgba(255, 255, 255, 0.62);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid;
}
@media (max-width: 700px) { .pv-memory-stats { grid-template-columns: 1fr; } }

/* ── 回忆抽取结果弹窗 (v17) ── */
.pv-pull-modal { width: 640px; }
.pv-pull-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 0.55rem; }
.pv-pull-card {
  position: relative;
  display: flex; flex-direction: column; gap: 4px;
  padding: 0.6rem 0.65rem 0.55rem;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid;
  border-radius: 9px;
  overflow: hidden;
}
.pv-pull-rarity { align-self: flex-start; padding: 1px 8px; border-radius: 4px; font-size: 0.58rem; color: #fff; }
.pv-pull-new {
  position: absolute; top: 7px; right: 7px;
  padding: 1px 7px; border-radius: 4px;
  font-size: 0.56rem; font-weight: 800; color: #1a1206;
  background: linear-gradient(135deg, var(--pv-gold-light), var(--pv-gold));
}
.pv-pull-title { font-size: 0.8rem; font-weight: 700; color: #f0e6cf; }
.pv-pull-text { margin: 0; font-size: 0.64rem; color: rgba(255, 255, 255, 0.5); line-height: 1.5; }
.pv-pull-refund { align-self: flex-start; font-size: 0.58rem; color: #ffd54f; }

/* ── 动态评论输入 ── */
.pv-comment-editor { resize: vertical; min-height: 88px; }

/* ── 服务券 (v18): 抽屉使用按钮 + 弥娅回应卡 ── */
.pv-drawer-ticket {
  align-self: stretch;
  text-align: center;
  box-shadow: 0 0 14px color-mix(in srgb, var(--pv-gold) 25%, transparent);
}
.pv-ticket-card {
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
  padding: 0.8rem 1rem;
  background: linear-gradient(135deg, color-mix(in srgb, var(--pv-gold) 14%, transparent), rgba(0, 0, 0, 0.55));
  border: 1px solid color-mix(in srgb, var(--pv-gold) 40%, transparent);
  border-left: 3px solid var(--pv-gold);
  border-radius: 8px;
}
.pv-ticket-mood { font-size: 1.4rem; line-height: 1.1; }
.pv-ticket-body { flex: 1; min-width: 0; }
.pv-ticket-label { display: block; font-size: 0.6rem; letter-spacing: 2px; color: var(--pv-gold); }
.pv-ticket-text {
  margin: 4px 0 0;
  font-size: 0.8rem;
  color: #f0e6cf;
  line-height: 1.7;
  white-space: pre-wrap;
}

/* ── toast ── */
.pv-toast {
  position: fixed; bottom: 3rem; left: 50%; transform: translateX(-50%);
  padding: 0.6rem 1.2rem;
  background: rgba(13, 17, 23, 0.95);
  border: 1px solid color-mix(in srgb, var(--pv-gold) 50%, transparent);
  border-radius: 8px;
  color: var(--miya-text); font-size: 0.8rem;
  z-index: 2000;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}
.toast-enter-active, .toast-leave-active { transition: all 0.3s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(-50%) translateY(12px); }

/* 移动端：将桌面导航压缩成可横向滑动的双层导航，内容不再被顶栏遮挡。 */
@media (max-width: 900px) {
  .pv-nav { height: 92px; padding-top: 8px; justify-content: flex-end; }
  .pv-nav-logo { left: 10px; top: 9px; }
  .pv-nav-logo-text { display: none; }
  .pv-nav-center {
    position: absolute;
    top: 48px;
    left: 8px;
    right: 8px;
    gap: 18px;
    overflow-x: auto;
    justify-content: flex-start;
    padding: 5px 10px 8px;
    scrollbar-width: none;
    background: rgba(5, 7, 11, .58);
    border-top: 1px solid color-mix(in srgb, var(--pv-gold) 20%, transparent);
    border-bottom: 1px solid color-mix(in srgb, var(--pv-gold) 18%, transparent);
  }
  .pv-nav-center::-webkit-scrollbar { display: none; }
  .pv-nav-center a { flex: 0 0 auto; font-size: .7rem; letter-spacing: 1px; }
  .pv-nav-more {
    position: sticky;
    right: 0;
    z-index: 2;
    flex: 0 0 auto;
    padding-inline: 10px 6px;
    font-size: .7rem;
    letter-spacing: 1px;
    background: linear-gradient(90deg, rgba(5, 7, 11, 0), rgba(5, 7, 11, .96) 30%);
  }
  .pv-nav-more-menu { top: 34px; right: 0; }
  .pv-nav-side { top: 8px; right: 8px; gap: 4px; }
  .pv-nav-id, .pv-nav-coin.earth { display: none; }
  .pv-nav-coin { padding: 3px 7px; font-size: .62rem; }
  .pv-section { align-items: flex-start; padding-top: 104px; padding-bottom: 72px; }
  .pv-home-body { width: 100%; box-sizing: border-box; margin-top: 0; padding: 1rem .75rem 2rem; }
  .pv-home-en { font-size: .62rem; letter-spacing: .34em; }
  .pv-home-title { font-size: 3rem; letter-spacing: .08em; }
  .pv-home-welcome { max-width: 100%; text-align: center; line-height: 1.65; font-size: .75rem; letter-spacing: 1px; }
  .pv-home-note, .pv-life-hub, .pv-degraded, .pv-today-action { width: 100%; box-sizing: border-box; }
  .pv-home-note-text { white-space: normal; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
  .pv-home-menu { width: 100%; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .55rem; }
  .pv-home-card { width: auto; padding: .72rem .4rem; }
  .pv-home-checkin { right: 8px; top: auto; bottom: 70px; transform: none; }
  .pv-board-wrap, .pv-story-wrap, .pv-book, .pv-profile-wrap, .pv-stats-wrap { width: 92%; }
  .pv-board-wrap, .pv-story-wrap { display: block; }
  .pv-board-right { margin-top: 1rem; }
  .pv-quest-show { min-height: 0; padding: 1.25rem; }
  .pv-quest-show-title { font-size: 1.35rem; }
  .pv-board-tabs { flex-wrap: wrap; gap: .55rem .9rem; }
  .pv-board-type-filter { width: 100%; margin-left: 0; gap: .45rem; overflow-x: auto; }
  .pv-story-left, .pv-story-right { height: auto; }
  .pv-story-router { height: 360px; }
  .pv-story-card.side { display: none; }
  .pv-story-mode { position: static; width: 92%; margin: 0 auto .7rem; justify-content: flex-end; }
  .pv-book { height: auto; display: block; }
  .pv-book-spine { display: none; }
  .pv-book-page { min-height: 300px; }
  .pv-book-page:first-child, .pv-book-page:last-child { border-radius: 10px; }
  .pv-book-content { margin-top: .7rem; }
  .pv-profile-hero { align-items: flex-start; flex-wrap: wrap; }
  .pv-profile-avatar { width: 78px; height: 78px; font-size: 2rem; }
  .pv-profile-name { font-size: 1.7rem; letter-spacing: 2px; }
  .pv-profile-edit { width: 100%; }
  .pv-profile-attrs { grid-template-columns: 1fr; }
  .pv-stats-grid { grid-template-columns: 1fr; }
}

@media (max-width: 520px) {
  .pv-nav { height: 100px; }
  .pv-nav-center { top: 52px; gap: 10px; }
  .pv-section { padding-top: 112px; }
  .pv-home-title { font-size: 2.55rem; }
  .pv-home-menu { grid-template-columns: 1fr 1fr; }
  .pv-today-action { align-items: flex-start; }
  .pv-today-action-btn { align-self: center; padding-inline: .45rem; }
  .pv-quest-show-meta { grid-template-columns: 1fr; gap: .45rem; }
  .pv-quest-show-actions { flex-wrap: wrap; }
  .pv-story-router { height: 300px; }
  .pv-story-arrow { width: 32px; height: 32px; }
}

/* ── Miya OS skin: the default Earth Online palette follows the main shell ── */
.pv.miya-skin {
  --pv-gold: var(--miya-accent-soft);
  --pv-gold-light: var(--miya-accent-bright);
  --pv-gold-deep: #4f9fa5;
  --pv-panel: rgba(12, 20, 31, 0.82);
  --pv-panel-strong: rgba(17, 28, 42, 0.94);
  background: var(--miya-bg-void);
}
.pv.miya-skin .pv-banner {
  height: 18%;
  background: linear-gradient(rgba(7, 11, 18, 0.96), rgba(7, 11, 18, 0.02));
}
.pv.miya-skin .pv-nav {
  height: 62px;
  padding-top: 14px;
  border-bottom: 1px solid var(--miya-line-soft);
  background: rgba(7, 11, 18, 0.7);
  backdrop-filter: blur(18px);
}
.pv.miya-skin .pv-nav-logo-glyph,
.pv.miya-skin .pv-nav-avatar {
  color: #071018;
  background: linear-gradient(135deg, var(--miya-accent-bright), var(--miya-accent-soft));
  box-shadow: 0 0 18px rgba(120, 207, 209, 0.18);
}
.pv.miya-skin .pv-nav-logo-text,
.pv.miya-skin .pv-nav-center a:hover,
.pv.miya-skin .pv-nav-center a.active,
.pv.miya-skin .pv-nav-more:hover,
.pv.miya-skin .pv-nav-more.active {
  color: var(--miya-accent-bright);
  text-shadow: 0 0 14px rgba(120, 207, 209, 0.18);
}
.pv.miya-skin .nv-deco::before,
.pv.miya-skin .nv-deco::after { border-color: var(--miya-accent-soft); }
.pv.miya-skin .pv-nav-center a { color: var(--miya-text-muted); }
.pv.miya-skin .pv-nav-name,
.pv.miya-skin .pv-home-title,
.pv.miya-skin .pv-items-title,
.pv.miya-skin .pv-profile-name,
.pv.miya-skin .pv-story-cur-title,
.pv.miya-skin .pv-world-head h2,
.pv.miya-skin .pv-pull-title,
.pv.miya-skin .pv-ticket-text { color: var(--miya-text-strong); }
.pv.miya-skin .pv-stage { scrollbar-color: rgba(120, 207, 209, 0.44) transparent; }
.pv.miya-skin .pv-section {
  background-color: rgba(7, 11, 18, 0.72);
}
.pv.miya-skin .pv-section:not(.pv-home) {
  background-image: linear-gradient(180deg, rgba(11, 18, 28, 0.5), rgba(7, 11, 18, 0.88));
}
.pv.miya-skin .pv-home-veil {
  background:
    radial-gradient(ellipse at 50% 28%, rgba(120, 207, 209, 0.1), transparent 58%),
    linear-gradient(180deg, rgba(7, 11, 18, 0.25), rgba(7, 11, 18, 0.93));
}
.pv.miya-skin .pv-home-title {
  text-shadow: 0 0 34px rgba(120, 207, 209, 0.2);
}
.pv.miya-skin .pv-board-wrap,
.pv.miya-skin .pv-quest-show,
.pv.miya-skin .pv-stats-card,
.pv.miya-skin .pv-profile-attrs,
.pv.miya-skin .pv-profile-bio,
.pv.miya-skin .pv-home-note,
.pv.miya-skin .pv-home-card,
.pv.miya-skin .pv-wall-card,
.pv.miya-skin .pv-char-card {
  background-color: var(--pv-panel);
  border-color: var(--miya-line);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.22);
}
.pv.miya-skin .pv-home-card:hover,
.pv.miya-skin .pv-wall-card:hover,
.pv.miya-skin .pv-char-card:hover,
.pv.miya-skin .pv-board-item:hover,
.pv.miya-skin .pv-board-item.active {
  border-color: var(--miya-line-strong);
  background-color: rgba(120, 207, 209, 0.08);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.28), inset 2px 0 rgba(162, 245, 238, 0.55);
}
.pv.miya-skin .pv-home-card-name,
.pv.miya-skin .pv-home-welcome,
.pv.miya-skin .pv-home-note-text,
.pv.miya-skin .pv-quest-show-title,
.pv.miya-skin .pv-wall-name,
.pv.miya-skin .pv-char-card-name { color: var(--miya-text-strong); }
.pv.miya-skin .pv-btn-primary,
.pv.miya-skin .pv-btn-accept {
  color: #071018;
  background: linear-gradient(135deg, var(--miya-accent-bright), var(--miya-accent-soft));
  box-shadow: 0 8px 20px rgba(120, 207, 209, 0.16);
}
.pv.miya-skin .pv-btn-ghost {
  color: var(--miya-text-body);
  background: rgba(120, 207, 209, 0.06);
  border-color: var(--miya-line);
}
.pv.miya-skin .pv-btn-ghost:hover,
.pv.miya-skin .pv-btn-primary:hover,
.pv.miya-skin .pv-btn-accept:hover { border-color: var(--miya-line-strong); filter: brightness(1.08); }
.pv.miya-skin .pv-line { background: linear-gradient(90deg, var(--miya-accent-soft), var(--miya-line-soft)); }
.pv.miya-skin .pv-currency,
.pv.miya-skin .pv-chip,
.pv.miya-skin .pv-filter-chip.active,
.pv.miya-skin .pv-nav-coin.miya {
  color: var(--miya-accent-bright);
  border-color: rgba(120, 207, 209, 0.34);
  background: rgba(120, 207, 209, 0.09);
}
.pv.miya-skin .pv-home-checkin {
  border-color: rgba(120, 207, 209, 0.4);
  background: rgba(12, 20, 31, 0.82);
}
.pv.miya-skin .pv-home-checkin:hover { background: rgba(120, 207, 209, 0.12); }
.pv.miya-skin .pv-home-checkin-main { color: var(--miya-text-strong); }
.pv.miya-skin .pv-home-checkin-sub { color: var(--miya-accent-soft); }
.pv.miya-skin .pv-profile-avatar { box-shadow: 0 0 28px rgba(120, 207, 209, 0.18); }
.pv.miya-skin .pv-wall-cover,
.pv.miya-skin .pv-char-card-cover { background: rgba(120, 207, 209, 0.08); }

@media (max-width: 900px) {
  .pv.miya-skin .pv-nav { background: rgba(7, 11, 18, 0.88); }
  .pv.miya-skin .pv-nav-center {
    background: rgba(12, 20, 31, 0.9);
    border-color: var(--miya-line-soft);
  }
}

/* ── Earth Command UI · Miya OS 同源现实指挥舱 ── */
.pv {
  --earth-life: var(--miya-life, #d8bd82);
  --earth-cyan: var(--pv-gold-light);
  --earth-line: color-mix(in srgb, var(--pv-gold) 28%, transparent);
  --earth-panel: rgba(8, 16, 25, 0.76);
  background: #050a10;
}
.pv::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background:
    linear-gradient(90deg, transparent 0 79px, color-mix(in srgb, var(--pv-gold) 4%, transparent) 80px),
    linear-gradient(transparent 0 79px, color-mix(in srgb, var(--pv-gold) 3%, transparent) 80px);
  background-size: 80px 80px;
  mask-image: linear-gradient(to bottom, black, transparent 76%);
}
.pv-nav {
  height: 58px;
  align-items: center;
  padding: 0 18px;
  background: rgba(5, 10, 16, 0.8);
  border-bottom: 1px solid var(--earth-line);
  backdrop-filter: blur(18px) saturate(1.2);
}
.pv-nav::after {
  content: '';
  position: absolute;
  right: 0;
  bottom: -1px;
  width: 18%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--earth-cyan));
  box-shadow: 0 0 12px color-mix(in srgb, var(--pv-gold) 45%, transparent);
}
.pv-nav-logo { top: 13px; }
.pv-nav-logo-glyph {
  width: 29px;
  height: 29px;
  clip-path: polygon(0 0, 78% 0, 100% 22%, 100% 100%, 22% 100%, 0 78%);
  color: #041014;
}
.pv-nav-logo-text { font-family: 'Noto Sans SC', sans-serif; font-size: .82rem; letter-spacing: 1px; }
.pv-nav-center { gap: 4px; padding: 3px; border: 1px solid var(--miya-line-soft); background: rgba(120, 207, 209, 0.025); }
.pv-nav-center a, .pv-nav-more { padding: 7px 13px; font-family: 'Noto Sans SC', sans-serif; font-size: .7rem; letter-spacing: 0; }
.pv-nav-center a.active, .pv-nav-more.active { background: color-mix(in srgb, var(--pv-gold) 12%, transparent); }
.nv-deco { display: none; }
.pv-nav-side { top: 13px; }
.pv-nav-avatar { border-radius: 3px; }
.pv-nav-coin { border-radius: 3px; }
.pv-section { padding-top: 58px; }

.pv-home { overflow: hidden; align-items: stretch; }
.pv-home-bg {
  inset: 0 0 0 42%;
  background-position: center 34%;
  filter: saturate(.84) contrast(1.05) brightness(.58);
  transform: scale(1.03);
  opacity: .78;
  mask-image: linear-gradient(90deg, transparent 0, rgba(0,0,0,.72) 24%, black 58%);
}
.pv-home-veil {
  background:
    linear-gradient(90deg, rgba(5, 10, 16, .98) 0%, rgba(5, 10, 16, .86) 39%, rgba(5, 10, 16, .22) 72%, rgba(5, 10, 16, .62) 100%),
    linear-gradient(180deg, rgba(5,10,16,.14), rgba(5,10,16,.94));
}
.pv-command-deck {
  position: relative;
  z-index: 3;
  width: min(1180px, calc(100% - 48px));
  min-height: calc(100vh - 210px);
  margin: 0 auto;
  padding: clamp(1.2rem, 2.5vh, 2rem) 0 3.2rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: clamp(.8rem, 1.5vh, 1.15rem);
}
.pv-command-copy { align-self: flex-start; }
.pv-command-copy .pv-home-en { margin-bottom: .35rem; color: color-mix(in srgb, var(--earth-cyan) 70%, transparent); font-family: 'Noto Sans SC', sans-serif; font-size: .62rem; letter-spacing: .32em; }
.pv-command-copy .pv-home-title { font-size: clamp(2.7rem, 5.7vw, 4.8rem); letter-spacing: .08em; line-height: 1.05; color: var(--miya-text-strong); background: none; -webkit-text-fill-color: currentColor; text-shadow: 0 0 28px color-mix(in srgb, var(--pv-gold) 18%, transparent); }
.pv-command-copy .pv-home-welcome { margin: .45rem 0 0; text-align: left; color: var(--miya-text-muted); font-size: .75rem; letter-spacing: 1px; }
.pv-home-rule { width: min(520px, 70vw); margin-top: .75rem; display: flex; align-items: center; gap: .55rem; color: color-mix(in srgb, var(--earth-cyan) 60%, transparent); font-size: .48rem; letter-spacing: .18em; }
.pv-home-rule span { flex: 1; height: 1px; background: linear-gradient(90deg, var(--earth-line), transparent); }
.pv-home-rule span:last-child { background: linear-gradient(90deg, transparent, var(--earth-line)); }

.pv-command-grid { display: grid; grid-template-columns: minmax(210px, .78fr) minmax(360px, 1.55fr) minmax(220px, .82fr); gap: .75rem; align-items: stretch; }
.pv-command-panel {
  position: relative;
  min-width: 0;
  padding: .85rem;
  background: linear-gradient(145deg, color-mix(in srgb, var(--pv-gold) 6%, transparent), var(--earth-panel));
  border: 1px solid var(--earth-line);
  box-shadow: 0 16px 42px rgba(0, 0, 0, .3);
  backdrop-filter: blur(18px) saturate(1.16);
  clip-path: polygon(0 0, calc(100% - 11px) 0, 100% 11px, 100% 100%, 11px 100%, 0 calc(100% - 11px));
}
.pv-command-panel::before { content: ''; position: absolute; left: 0; top: 0; width: 42px; height: 2px; background: var(--earth-cyan); box-shadow: 0 0 12px color-mix(in srgb, var(--pv-gold) 45%, transparent); }
.pv-panel-kicker { display: flex; justify-content: space-between; gap: 1rem; color: var(--earth-cyan); font-size: .52rem; letter-spacing: .14em; }
.pv-panel-kicker span { color: var(--miya-text-faint); letter-spacing: .06em; }
.pv-player-identity { display: flex; align-items: center; gap: .75rem; margin-top: .9rem; }
.pv-command-avatar { width: 52px; height: 52px; flex: 0 0 auto; padding: 0; display: grid; place-items: center; overflow: hidden; border: 1px solid var(--miya-line-strong); color: #041014; background: linear-gradient(135deg, var(--earth-cyan), var(--pv-gold)); cursor: pointer; clip-path: polygon(0 0, 78% 0, 100% 22%, 100% 100%, 0 100%); }
.pv-command-avatar img { width: 100%; height: 100%; object-fit: cover; }
.pv-player-identity strong, .pv-player-identity small { display: block; }
.pv-player-identity strong { color: var(--miya-text-strong); font-size: 1rem; }
.pv-player-identity small { margin-top: .16rem; color: var(--miya-text-muted); font-size: .58rem; }
.pv-command-xp { margin-top: .75rem; }
.pv-command-xp > div { display: flex; justify-content: space-between; color: var(--miya-text-muted); font-size: .56rem; }
.pv-command-xp b { color: var(--earth-cyan); font-weight: 600; }
.pv-command-xp > i, .pv-command-attrs i { display: block; overflow: hidden; height: 3px; margin-top: .35rem; background: rgba(255,255,255,.08); }
.pv-command-xp em, .pv-command-attrs em { display: block; height: 100%; background: linear-gradient(90deg, var(--pv-gold), var(--earth-cyan)); box-shadow: 0 0 8px color-mix(in srgb, var(--pv-gold) 50%, transparent); }
.pv-command-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-top: .7rem; }
.pv-command-stats > div, .pv-command-stats button { min-width: 0; padding: .5rem; text-align: left; color: inherit; background: rgba(255,255,255,.025); border: 1px solid var(--miya-line-soft); }
.pv-command-stats button { cursor: pointer; }
.pv-command-stats b, .pv-command-stats span { display: block; }
.pv-command-stats b { color: var(--miya-text-strong); font-size: .72rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pv-command-stats span { margin-top: .12rem; color: var(--miya-text-faint); font-size: .5rem; }
.pv-command-attrs { display: grid; gap: .35rem; margin-top: .65rem; }
.pv-command-attrs > div { display: grid; grid-template-columns: 38px 1fr 24px; gap: .4rem; align-items: center; color: var(--miya-text-muted); font-size: .54rem; }
.pv-command-attrs i { margin: 0; }
.pv-command-attrs b { color: var(--miya-text-body); text-align: right; }

.pv-mission-panel { padding: 1rem 1.1rem; }
.pv-mission-focus { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: .9rem; min-height: 118px; margin-top: .7rem; padding: .85rem; background: linear-gradient(100deg, color-mix(in srgb, var(--pv-gold) 10%, transparent), rgba(5,10,16,.64)); border-left: 2px solid var(--earth-cyan); }
.pv-mission-mark { color: var(--earth-cyan); font-size: 1.65rem; }
.pv-mission-focus small { color: var(--earth-cyan); font-size: .5rem; letter-spacing: .18em; }
.pv-mission-focus h2 { margin: .28rem 0 0; color: var(--miya-text-strong); font-size: 1.12rem; letter-spacing: 0; }
.pv-mission-focus p { margin: .28rem 0 0; max-width: 440px; color: var(--miya-text-muted); font-size: .66rem; line-height: 1.5; }
.pv-command-primary { min-width: 92px; padding: .5rem .72rem; border: 1px solid var(--earth-cyan); color: #041014; background: linear-gradient(135deg, var(--earth-cyan), var(--pv-gold)); font-weight: 700; font-size: .65rem; cursor: pointer; clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%); }
.pv-mission-counts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; margin-top: .55rem; }
.pv-mission-counts span { padding: .42rem .5rem; color: var(--miya-text-faint); background: rgba(255,255,255,.022); border: 1px solid var(--miya-line-soft); font-size: .53rem; }
.pv-mission-counts b { margin-right: .2rem; color: var(--earth-cyan); font-size: .78rem; }
.pv-command-note { width: 100%; margin-top: .55rem; padding: .5rem .65rem; display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: .65rem; text-align: left; color: inherit; background: transparent; border: 1px solid var(--miya-line-soft); cursor: pointer; }
.pv-command-note:hover { border-color: var(--miya-line-strong); background: color-mix(in srgb, var(--pv-gold) 6%, transparent); }
.pv-command-note > span { color: var(--earth-life); font-size: 1rem; }
.pv-command-note small { color: var(--earth-life); font-size: .5rem; letter-spacing: .08em; }
.pv-command-note p { margin: .16rem 0 0; color: var(--miya-text-muted); font-size: .6rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pv-command-note > b { color: var(--earth-cyan); font-size: .7rem; }

.pv-reality-status { display: grid; gap: .35rem; margin-top: .8rem; color: var(--miya-success); font-size: .56rem; line-height: 1.4; }
.pv-reality-status .warning { color: var(--miya-warning); }
.pv-reality-status .quiet { color: var(--miya-text-faint); }
.pv-reality-weather { display: flex; align-items: center; gap: .65rem; margin-top: .75rem; padding: .7rem 0; border-block: 1px solid var(--miya-line-soft); }
.pv-reality-weather > strong { color: var(--earth-cyan); font-size: 1.8rem; font-weight: 400; }
.pv-reality-weather b, .pv-reality-weather span { display: block; }
.pv-reality-weather b { color: var(--miya-text-strong); font-size: .78rem; }
.pv-reality-weather span { margin-top: .12rem; color: var(--miya-text-muted); font-size: .56rem; }
.pv-reality-checkin { margin-top: .7rem; }
.pv-reality-checkin > div { display: flex; justify-content: space-between; color: var(--miya-text-faint); font-size: .5rem; }
.pv-reality-checkin > div b { color: var(--earth-cyan); }
.pv-reality-checkin small { display: block; margin-top: .25rem; color: var(--miya-text-muted); font-size: .56rem; }
.pv-reality-checkin button { width: 100%; margin-top: .55rem; padding: .42rem; border: 1px solid var(--earth-line); color: var(--earth-cyan); background: color-mix(in srgb, var(--pv-gold) 6%, transparent); font-size: .58rem; cursor: pointer; }

.pv-command-menu { width: 100%; display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin: 0; }
.pv-command-menu .pv-home-card { position: relative; width: auto; min-height: 52px; padding: .55rem .7rem; align-items: flex-start; justify-content: center; border-radius: 0; background: rgba(7, 15, 24, .72); clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%); }
.pv-command-menu .pv-home-card:hover { transform: translateY(-2px); box-shadow: inset 2px 0 var(--earth-cyan), 0 8px 18px rgba(0,0,0,.25); }
.pv-command-menu .pv-home-card-en { font-family: 'Noto Sans SC', sans-serif; font-size: .46rem; letter-spacing: .12em; }
.pv-command-menu .pv-home-card-name { font-size: .72rem; }
.pv-command-menu-arrow { position: absolute; right: .6rem; top: 50%; transform: translateY(-50%); color: var(--miya-text-faint); font-size: .58rem; }
.pv-command-menu .pv-home-card:hover .pv-command-menu-arrow { color: var(--earth-cyan); }
.pv-command-deck > .pv-degraded { width: 100%; margin: 0; }
.pv-home-checkin { display: none; }
.pv-home-scroll { color: var(--miya-text-faint); font-size: .5rem; letter-spacing: .18em; }

/* 高频板块继承指挥舱的硬朗轮廓，图片展示保持原有内容和比例。 */
.pv-board-wrap, .pv-quest-show, .pv-stats-card, .pv-world-region, .pv-world-event, .pv-world-shop, .pv-profile-attrs, .pv-profile-bio {
  border-radius: 0;
  border-color: var(--earth-line);
  background-color: rgba(8, 16, 25, .76);
}
.pv-btn-primary { color: #041014; background: linear-gradient(135deg, var(--earth-cyan), var(--pv-gold)); }

.pv-board, .pv-items, .pv-chars, .pv-story, .pv-profile, .pv-stats, .pv-world, .pv-shop {
  background:
    linear-gradient(90deg, rgba(5, 10, 16, .86), rgba(5, 10, 16, .56)),
    repeating-linear-gradient(90deg, transparent 0 119px, rgba(120, 207, 209, .025) 120px),
    repeating-linear-gradient(0deg, transparent 0 79px, rgba(120, 207, 209, .018) 80px);
}
.pv-board-title, .pv-items-title, .pv-world-head h2, .pv-profile-name, .pv-story-cur-title { color: var(--miya-text-strong); text-shadow: 0 0 18px color-mix(in srgb, var(--pv-gold) 16%, transparent); }
.pv-board-en, .pv-items-en, .pv-story-en, .pv-story-en, .pv-world-head .pv-story-en { color: var(--earth-cyan); }
.pv-board-item { border-color: var(--miya-line-soft); background: rgba(7, 15, 24, .62); }
.pv-board-item.active { border-color: var(--miya-line-strong); box-shadow: inset 2px 0 var(--earth-cyan), 0 8px 22px rgba(0,0,0,.2); }
.pv-board-item-title { color: var(--miya-text-body); }
.pv-board-item.active .pv-board-item-title { color: var(--miya-text-strong); }
.pv-quest-show { box-shadow: 0 18px 42px rgba(0,0,0,.28); }
.pv-quest-show-type { background: color-mix(in srgb, var(--pv-gold) 8%, transparent); }
.pv-wall-card, .pv-char-card { border-radius: 0; border-color: var(--miya-line); background: rgba(7, 15, 24, .72); }
.pv-wall-card:hover, .pv-char-card:hover { border-color: var(--miya-line-strong); box-shadow: inset 2px 0 var(--earth-cyan), 0 14px 28px rgba(0,0,0,.24); }
.pv-wall-name, .pv-char-card-name { color: var(--miya-text-strong); }
.pv-world-region { clip-path: polygon(0 0, calc(100% - 13px) 0, 100% 13px, 100% 100%, 13px 100%, 0 calc(100% - 13px)); }
.pv-world-region::before { opacity: .45; }
.pv-world-region:hover { border-color: color-mix(in srgb, var(--world-color) 70%, transparent); box-shadow: inset 2px 0 var(--world-color), 0 18px 34px rgba(0,0,0,.28); }
.pv-world-region.locked { filter: saturate(.35); opacity: .68; }
.pv-world-region.locked:hover { filter: saturate(.55); opacity: .82; }
.pv-world-region h3 { color: var(--miya-text-strong); }
.pv-world-event { border-radius: 0; }
.pv-stats-card-head h3 { color: var(--miya-text-strong); }
.pv-story-mode { padding: 3px; border: 1px solid var(--miya-line); background: rgba(5, 10, 16, .86); }
.pv-story-mode-btn { border-radius: 0; font-size: .62rem; }
.pv-story-mode-btn.active { color: #041014; background: linear-gradient(135deg, var(--earth-cyan), var(--pv-gold)); }
.pv-story-archive, .pv-story-card.main, .pv-book-page { border-radius: 0; border-color: var(--earth-line); box-shadow: 0 18px 46px rgba(0,0,0,.28); }
.pv-story-card.main { border-width: 1px 1px 2px; border-bottom-color: var(--earth-cyan); }
.pv-story-card.side { border-radius: 0; }
.pv-story-card-title { color: var(--miya-text-strong); }
.pv-profile-hero { border-bottom: 1px solid var(--miya-line); }
.pv-profile-avatar { border-radius: 0; clip-path: polygon(0 0, 80% 0, 100% 20%, 100% 100%, 0 100%); border: 1px solid var(--miya-line-strong); }
.pv-profile-money-item, .pv-profile-career, .pv-profile-attrs, .pv-profile-bio { border-radius: 0; border-color: var(--miya-line); background: rgba(8,16,25,.72); }
.pv-profile-money-num, .pv-career-num { color: var(--earth-cyan); }
.pv-profile-attr.low .pv-attr-fill { background: var(--miya-danger); }

@media (min-width: 1101px) {
  .pv-world-grid {
    position: relative;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    grid-template-rows: repeat(3, minmax(150px, 1fr));
    gap: .55rem;
    min-height: 520px;
    padding: .65rem;
    border: 1px solid var(--miya-line);
    background:
      radial-gradient(circle at 50% 48%, color-mix(in srgb, var(--pv-gold) 10%, transparent), transparent 45%),
      linear-gradient(135deg, rgba(8, 22, 30, .86), rgba(5, 10, 16, .92));
  }
  .pv-world-grid::before {
    content: 'REALITY ATLAS / 05 REGIONS';
    position: absolute;
    top: .85rem;
    right: 1rem;
    color: var(--miya-text-faint);
    font-size: .48rem;
    letter-spacing: .15em;
    pointer-events: none;
  }
  .pv-world-region { min-height: 0; padding: .9rem; }
  .pv-world-region:nth-child(1) { grid-column: 1 / span 5; grid-row: 1 / span 2; }
  .pv-world-region:nth-child(2) { grid-column: 6 / span 4; grid-row: 1; }
  .pv-world-region:nth-child(3) { grid-column: 10 / span 3; grid-row: 1 / span 2; }
  .pv-world-region:nth-child(4) { grid-column: 4 / span 4; grid-row: 3; }
  .pv-world-region:nth-child(5) { grid-column: 8 / span 4; grid-row: 3; }
  .pv-world-region:nth-child(1) .pv-world-icon, .pv-world-region:nth-child(3) .pv-world-icon { font-size: 2rem; }
}

@media (max-width: 1100px) {
  .pv-command-deck { width: min(960px, calc(100% - 28px)); justify-content: flex-start; padding-top: 1.2rem; }
  .pv-command-grid { grid-template-columns: 220px minmax(360px, 1fr); }
  .pv-reality-panel { grid-column: 1 / -1; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: .8rem; align-items: center; }
  .pv-reality-status, .pv-reality-weather, .pv-reality-checkin { margin: 0; }
  .pv-reality-weather { padding: 0 .8rem; border-block: 0; border-inline: 1px solid var(--miya-line-soft); }
}
@media (max-width: 760px) {
  .pv-nav { height: 96px; align-items: flex-start; padding-top: 8px; }
  .pv-nav-center { top: 48px; left: 8px; right: 8px; position: absolute; overflow-x: auto; justify-content: flex-start; }
  .pv-nav-center a, .pv-nav-more { flex: 0 0 auto; }
  .pv-section { padding-top: 100px; }
  .pv-home { overflow-y: auto; }
  .pv-home-bg { inset: 0; opacity: .42; mask-image: linear-gradient(180deg, black, transparent 72%); }
  .pv-command-deck { width: calc(100% - 22px); min-height: auto; padding: 1rem 0 4.5rem; }
  .pv-command-copy { text-align: left; }
  .pv-command-copy .pv-home-title { font-size: 2.4rem; }
  .pv-home-rule { width: 100%; }
  .pv-command-grid { grid-template-columns: 1fr; }
  .pv-reality-panel { grid-column: auto; display: block; }
  .pv-reality-status, .pv-reality-weather, .pv-reality-checkin { margin-top: .7rem; }
  .pv-reality-weather { padding: .65rem 0; border-block: 1px solid var(--miya-line-soft); border-inline: 0; }
  .pv-command-menu { grid-template-columns: repeat(2, 1fr); }
  .pv-mission-focus { grid-template-columns: auto 1fr; }
  .pv-mission-focus .pv-command-primary { grid-column: 2; justify-self: start; }
}

/* ── v3 Earth Command: 委托与世界稳定布局 ── */
.pv-board,
.pv-world {
  align-items: flex-start;
  overflow-x: hidden;
  overflow-y: auto;
}
.pv-board-wrap {
  width: min(1180px, calc(100% - 48px));
  min-height: 0;
  margin: 0 auto;
  padding: clamp(1.15rem, 3vh, 2.25rem) 0 4.5rem;
  display: grid;
  grid-template-columns: minmax(280px, .88fr) minmax(0, 1.32fr);
  gap: 1rem;
  align-items: start;
}
.pv-board-left {
  min-width: 0;
  padding: .8rem .85rem .65rem;
  border: 1px solid var(--earth-line);
  background: linear-gradient(145deg, rgba(12, 28, 38, .84), rgba(7, 15, 24, .72));
  box-shadow: 0 16px 36px rgba(0, 0, 0, .22);
  clip-path: polygon(0 0, calc(100% - 9px) 0, 100% 9px, 100% 100%, 9px 100%, 0 calc(100% - 9px));
}
.pv-board-head { padding: .1rem .15rem 0; }
.pv-board-title { font-size: clamp(2rem, 4vw, 2.8rem); color: var(--miya-text-strong); }
.pv-board-en { color: var(--earth-cyan); letter-spacing: .25em; }
.pv-board-tabs { gap: .65rem 1rem; flex-wrap: wrap; }
.pv-board-tabs > a { font-family: 'Noto Sans SC', sans-serif; font-size: .68rem; color: var(--miya-text-muted); }
.pv-board-type-filter { gap: .25rem; flex-wrap: wrap; }
.pv-board-type-filter a { padding: .18rem .42rem; font-size: .57rem; border-radius: 0; }
.pv-board-list {
  min-height: 120px;
  max-height: min(53vh, 510px);
  overflow-y: auto;
  padding: .35rem .1rem 0;
  scrollbar-gutter: stable;
}
.pv-board-item {
  min-height: 47px;
  padding: .64rem .5rem;
  border: 1px solid transparent;
  border-bottom-color: var(--miya-line-soft);
  background: rgba(4, 12, 20, .42);
}
.pv-board-item + .pv-board-item { margin-top: .18rem; }
.pv-board-item-title { line-height: 1.35; }
.pv-board-history { margin-top: .55rem; border-top-color: var(--miya-line-soft); }
.pv-board-history-toggle { padding: .6rem .2rem .2rem; color: var(--miya-text-muted); }
.pv-board-right {
  min-width: 0;
  display: block;
  align-self: start;
}
.pv-quest-show {
  min-height: 0;
  padding: clamp(1.1rem, 2.6vw, 2rem);
  gap: .72rem;
  border-left: 2px solid var(--earth-cyan);
  clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 14px 100%, 0 calc(100% - 14px));
}
.pv-quest-show-title { font-size: clamp(1.35rem, 2.3vw, 1.9rem); }
.pv-quest-show-desc { max-width: 62ch; }
.pv-quest-show-meta { gap: .55rem 1rem; }
.pv-quest-show-cell { gap: .8rem; min-width: 0; }
.pv-quest-show-cell .v { text-align: right; overflow-wrap: anywhere; }
.pv-quest-subtasks { border-radius: 0; border-color: var(--miya-line); }
.pv-quest-show-actions { flex-wrap: wrap; }
.pv-empty { border: 1px dashed var(--miya-line-soft); background: rgba(7, 15, 24, .38); }

.pv-world-wrap {
  width: min(1180px, calc(100% - 48px));
  min-height: 0;
  margin: 0 auto;
  padding: clamp(1.1rem, 3vh, 2.25rem) 0 5rem;
}
.pv-world-head {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: end;
  margin-bottom: .8rem;
  padding: .8rem 1rem .9rem;
  border: 1px solid var(--earth-line);
  border-left: 2px solid var(--earth-cyan);
  background: linear-gradient(135deg, rgba(12, 28, 38, .76), rgba(7, 15, 24, .56));
  clip-path: polygon(0 0, calc(100% - 11px) 0, 100% 11px, 100% 100%, 0 100%);
}
.pv-world-head h2 { margin-top: .22rem; font-size: clamp(1.55rem, 3.2vw, 2.45rem); }
.pv-world-head p:not(.pv-story-en) { max-width: 64ch; font-size: .72rem; }
.pv-world-count { align-self: center; padding: .45rem .65rem; border: 1px solid var(--miya-line); color: var(--earth-cyan); background: rgba(120, 207, 209, .06); font-size: .62rem; }
.pv-world-atmosphere {
  display: flex;
  align-items: center;
  gap: .45rem;
  margin-bottom: .7rem;
  padding: .45rem .55rem;
  border: 1px solid var(--miya-line-soft);
  background: rgba(5, 13, 21, .7);
  font-size: .59rem;
}
.pv-world-atmosphere > span { padding-right: .55rem; border-right: 1px solid var(--miya-line-soft); }
.pv-world-atmosphere > span:last-of-type { border-right: 0; }
.pv-world-refresh { padding: .3rem .5rem; border-radius: 0; font-size: .57rem; }
.pv-world-grid {
  gap: .65rem;
  padding: .6rem;
  border: 1px solid var(--miya-line);
  background: linear-gradient(135deg, rgba(8, 22, 30, .72), rgba(5, 10, 16, .88));
}
.pv-world-region {
  min-height: 290px;
  padding: .9rem;
  overflow: hidden;
  border-color: color-mix(in srgb, var(--world-color) 48%, var(--miya-line));
  background-color: rgba(8, 16, 25, .82);
}
.pv-world-region.has-photo { background-position: center; }
.pv-world-region-desc { max-height: 8.4em; }
.pv-world-region-desc :deep(p) { color: var(--miya-text-muted); }
.pv-world-meta { color: var(--miya-text-muted); }
.pv-world-message, .pv-world-companion, .pv-world-choice { border-radius: 0; border-color: var(--miya-line); }
.pv-world-log { border-top-color: var(--miya-line); }

@media (max-width: 900px) {
  .pv-board-wrap {
    width: calc(100% - 24px);
    padding: 1rem 0 4.6rem;
    grid-template-columns: 1fr;
    gap: .75rem;
  }
  .pv-board-left { padding: .7rem .65rem .55rem; }
  .pv-board-list { max-height: min(42vh, 360px); }
  .pv-board-right { margin-top: 0; }
  .pv-quest-show { padding: 1rem; }
  .pv-quest-show-meta { grid-template-columns: 1fr; }
  .pv-world-wrap { width: calc(100% - 24px); padding: 1rem 0 4.8rem; }
  .pv-world-head { display: grid; grid-template-columns: 1fr; gap: .55rem; padding: .75rem; }
  .pv-world-head h2 { font-size: 1.55rem; }
  .pv-world-count { justify-self: start; margin-top: 0; }
  .pv-world-atmosphere { display: grid; grid-template-columns: 1fr 1fr; gap: .35rem; align-items: stretch; }
  .pv-world-atmosphere > span { border-right: 0; padding: .25rem .35rem; border-bottom: 1px solid var(--miya-line-soft); }
  .pv-world-refresh { width: 100%; }
  .pv-world-grid { grid-template-columns: 1fr; padding: .45rem; }
  .pv-world-grid::before { display: none; }
  .pv-world-region,
  .pv-world-region:nth-child(n) { min-height: 300px; grid-column: auto; grid-row: auto; }
  .pv-world-region-desc { max-height: none; }
  .pv-world-photo-btn, .pv-world-explore, .pv-world-commission { min-height: 36px; }
}

@media (max-width: 520px) {
  .pv-board-title { font-size: 2rem; }
  .pv-board-tabs { gap: .45rem .72rem; }
  .pv-board-type-filter { overflow: visible; }
  .pv-board-item { min-height: 45px; padding-inline: .4rem; gap: .5rem; }
  .pv-board-item-title { font-size: .68rem; }
  .pv-world-head p:not(.pv-story-en) { line-height: 1.55; }
  .pv-world-atmosphere { grid-template-columns: 1fr; }
  .pv-world-atmosphere > span { border-bottom: 0; }
  .pv-world-region { min-height: 320px; }
}

/* ── v2 command deck: 主视觉 + 今日行动 + 紧凑 HUD ── */
.pv-home .pv-command-deck {
  width: min(1120px, calc(100% - 72px));
  min-height: calc(100vh - 132px);
  padding: .95rem 0 2.6rem;
  gap: .7rem;
  justify-content: center;
}
.pv-home .pv-command-copy { max-width: 680px; }
.pv-home .pv-command-copy .pv-home-title { font-size: clamp(2.9rem, 5vw, 4.1rem); }
.pv-home .pv-command-copy .pv-home-welcome { max-width: 520px; }
.pv-home-feature {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: .7rem;
  align-items: start;
}
.pv-home-player,
.pv-home-action,
.pv-home-status-block {
  position: relative;
  min-width: 0;
  border: 1px solid var(--earth-line);
  background: linear-gradient(145deg, color-mix(in srgb, var(--pv-gold) 7%, transparent), rgba(8, 16, 25, .82));
  box-shadow: 0 16px 38px rgba(0, 0, 0, .24);
  backdrop-filter: blur(18px) saturate(1.14);
  clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 10px 100%, 0 calc(100% - 10px));
}
.pv-home-player { padding: .8rem; display: grid; grid-template-columns: auto 1fr; column-gap: .7rem; align-content: start; }
.pv-home-player .pv-panel-kicker { grid-column: 1 / -1; }
.pv-home-portrait {
  width: 82px;
  height: 106px;
  margin-top: .72rem;
  padding: 0;
  overflow: hidden;
  display: grid;
  place-items: center;
  border: 1px solid var(--miya-line-strong);
  background: linear-gradient(145deg, var(--earth-cyan), var(--pv-gold));
  color: #041014;
  cursor: pointer;
  clip-path: polygon(0 0, 82% 0, 100% 18%, 100% 100%, 0 100%);
}
.pv-home-portrait img { width: 100%; height: 100%; object-fit: cover; }
.pv-home-portrait span { font-size: 2rem; font-weight: 800; }
.pv-home-player-copy { min-width: 0; align-self: end; padding-bottom: .25rem; }
.pv-home-player-copy strong,
.pv-home-player-copy small { display: block; }
.pv-home-player-copy strong { color: var(--miya-text-strong); font-size: 1rem; }
.pv-home-player-copy small { margin-top: .25rem; color: var(--miya-text-muted); font-size: .56rem; line-height: 1.45; }
.pv-home-xp { grid-column: 1 / -1; margin-top: .7rem; }
.pv-home-xp > div { display: flex; justify-content: space-between; color: var(--miya-text-muted); font-size: .55rem; }
.pv-home-xp b { color: var(--earth-cyan); font-weight: 600; }
.pv-home-xp > i { display: block; height: 3px; margin-top: .35rem; overflow: hidden; background: rgba(255,255,255,.08); }
.pv-home-xp em { display: block; height: 100%; background: linear-gradient(90deg, var(--pv-gold), var(--earth-cyan)); box-shadow: 0 0 8px color-mix(in srgb, var(--pv-gold) 50%, transparent); }
.pv-home-action { padding: .95rem 1.05rem .8rem; }
.pv-home-action-main {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: .85rem;
  min-height: 78px;
  margin-top: .65rem;
  padding: .85rem .9rem;
  border-left: 2px solid var(--earth-cyan);
  background: linear-gradient(100deg, color-mix(in srgb, var(--pv-gold) 11%, transparent), rgba(5, 10, 16, .62));
}
.pv-home-action-main small { color: var(--earth-cyan); font-size: .5rem; letter-spacing: .16em; }
.pv-home-action-main h2 { margin: .28rem 0 0; color: var(--miya-text-strong); font-size: 1.15rem; }
.pv-home-action-main p { margin: .3rem 0 0; color: var(--miya-text-muted); font-size: .66rem; line-height: 1.5; }
.pv-home-action .pv-command-note { min-height: 40px; max-height: 42px; margin-top: .35rem; padding: .32rem .5rem; overflow: hidden; }
.pv-home-action .pv-command-note p { font-size: .56rem; }
.pv-home-status { display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; }
.pv-home-status-block { padding: .38rem .7rem; clip-path: none; }
.pv-home-status-label { color: var(--earth-cyan); font-size: .5rem; letter-spacing: .16em; }
.pv-home-status-values { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .4rem; margin-top: .45rem; }
.pv-home-status-values > div,
.pv-home-status-values > button { min-width: 0; padding: .28rem .4rem; text-align: left; border: 1px solid var(--miya-line-soft); background: rgba(255,255,255,.025); color: inherit; }
.pv-home-status-values > button { cursor: pointer; }
.pv-home-status-values b,
.pv-home-status-values span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pv-home-status-values b { color: var(--miya-text-strong); font-size: .7rem; }
.pv-home-status-values span { margin-top: .14rem; color: var(--miya-text-faint); font-size: .48rem; }
.pv-home-reality-copy { display: flex; align-items: center; gap: .7rem; min-width: 0; margin-top: .45rem; color: var(--miya-text-muted); font-size: .56rem; white-space: nowrap; }
.pv-home-reality-copy span { overflow: hidden; text-overflow: ellipsis; }
.pv-home-reality-copy span:first-child { color: var(--miya-success); }
.pv-home-reality-copy .warning { color: var(--miya-warning); }
.pv-home-reality-copy .done { color: var(--earth-cyan); }
.pv-home-reality-copy button { flex: 0 0 auto; padding: .28rem .55rem; border: 1px solid var(--earth-line); color: var(--earth-cyan); background: color-mix(in srgb, var(--pv-gold) 6%, transparent); font-size: .52rem; cursor: pointer; }
.pv-home .pv-command-menu { margin-top: .05rem; }
.pv-home .pv-command-menu .pv-home-card { min-height: 48px; }
.pv-home .pv-degraded { margin-top: -.15rem; }

@media (max-width: 760px) {
  .pv-home .pv-command-deck { width: calc(100% - 22px); min-height: auto; padding: 1rem 0 3.8rem; gap: .7rem; justify-content: flex-start; }
  .pv-home .pv-command-copy .pv-home-title { font-size: 2.35rem; }
  .pv-home-feature { grid-template-columns: 1fr; }
  .pv-home-player { grid-template-columns: auto 1fr; }
  .pv-home-portrait { width: 68px; height: 86px; }
  .pv-home-action { padding: .8rem; }
  .pv-home-action-main { grid-template-columns: auto minmax(0, 1fr); min-height: 0; padding: .7rem; }
  .pv-home-action-main .pv-command-primary { grid-column: 2; justify-self: start; }
  .pv-home-action-main h2 { font-size: .95rem; }
  .pv-home-status { grid-template-columns: 1fr; }
  .pv-home-status-values { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .pv-home-reality-copy { flex-wrap: wrap; white-space: normal; }
  .pv-home-reality-copy button { margin-left: auto; }
}
/* ── final responsive corrections (must remain last in cascade) ── */
.pv-board { align-items: flex-start; overflow: auto; }
.pv-board-wrap { display: grid; grid-template-columns: minmax(280px, .88fr) minmax(0, 1.32fr); align-items: start; min-height: 0; }
.pv-board-right { align-items: flex-start; justify-content: stretch; }
.pv-world { align-items: flex-start; overflow: auto; }
.pv-world-wrap { min-height: 0; }
@media (max-width: 900px) {
  .pv-board-wrap { width: calc(100% - 24px); display: grid; grid-template-columns: 1fr; gap: .75rem; }
  .pv-board-right { margin-top: 0; display: block; }
  .pv-world-wrap { width: calc(100% - 24px); padding: 1rem 0 4.8rem; }
  .pv-world-head { display: grid; grid-template-columns: 1fr; }
  .pv-world-grid { grid-template-columns: 1fr; }
  .pv-world-region, .pv-world-region:nth-child(n) { min-height: 300px; grid-column: auto; grid-row: auto; }
}
@media (max-width: 520px) {
  .pv-board-wrap { width: calc(100% - 20px); }
  .pv-world-wrap { width: calc(100% - 20px); }
  .pv-world-atmosphere { grid-template-columns: 1fr; }
}

/* ── Miya shell integration: cyan signal, warm life accent, full-bleed stage ── */
.pv {
  background: transparent;
  color: var(--miya-text-body);
}
.pv::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  opacity: .34;
  background:
    linear-gradient(90deg, rgba(120, 207, 209, .035) 1px, transparent 1px),
    linear-gradient(rgba(120, 207, 209, .024) 1px, transparent 1px);
  background-size: 96px 96px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, .95), transparent 82%);
}
.pv-banner { height: 30%; background: linear-gradient(180deg, rgba(4, 10, 16, .86), transparent); }
.pv-nav {
  height: 58px;
  padding-top: 9px;
  border-bottom: 1px solid rgba(162, 245, 238, .1);
  background: linear-gradient(180deg, rgba(5, 10, 16, .62), rgba(5, 10, 16, .14));
  backdrop-filter: blur(10px);
}
.pv-nav-logo-glyph {
  color: #041014;
  background: linear-gradient(135deg, var(--earth-accent-light), var(--earth-accent));
  box-shadow: 0 0 18px color-mix(in srgb, var(--earth-accent) 20%, transparent);
}
.pv-nav-logo-text { color: var(--earth-accent-light); text-shadow: 0 0 14px color-mix(in srgb, var(--earth-accent) 38%, transparent); }
.pv-nav-center { gap: 18px; }
.pv-nav-center a, .pv-nav-more { color: var(--miya-text-muted); font-family: 'Noto Sans SC', sans-serif; font-size: .66rem; letter-spacing: .12em; }
.pv-nav-center a:hover, .pv-nav-center a.active, .pv-nav-more:hover, .pv-nav-more.active { color: var(--earth-accent-light); }
.nv-deco::before { border-top-color: var(--earth-accent); border-left-color: color-mix(in srgb, var(--earth-accent) 55%, transparent); border-right-color: color-mix(in srgb, var(--earth-accent) 55%, transparent); }
.nv-deco::after { border-bottom-color: var(--earth-accent); }
.pv-nav-avatar { border-color: color-mix(in srgb, var(--earth-accent) 60%, transparent); background: linear-gradient(135deg, var(--earth-accent-light), var(--earth-accent)); }
.pv-nav-name { color: var(--miya-text-strong); }
.pv-nav-level, .pv-nav-coin { color: var(--earth-accent-light); }
.pv-nav-coin { border-color: color-mix(in srgb, var(--earth-accent) 35%, transparent); background: color-mix(in srgb, var(--earth-accent) 8%, transparent); }
.pv-home-bg { filter: blur(7px) brightness(.54) saturate(1.08); }
.pv-home-veil {
  background:
    linear-gradient(90deg, rgba(5, 10, 16, .78), rgba(5, 10, 16, .2) 58%, rgba(5, 10, 16, .62)),
    linear-gradient(180deg, rgba(5, 10, 16, .18), rgba(5, 10, 16, .92));
}
.pv-home-title {
  background: linear-gradient(180deg, #f5fbfb 16%, var(--earth-accent-light) 82%);
  -webkit-background-clip: text;
  background-clip: text;
  text-shadow: 0 0 36px color-mix(in srgb, var(--earth-accent) 32%, transparent);
}
.pv-home-en, .pv-home-card-en, .pv-panel-kicker, .pv-home-status-label { color: var(--earth-accent-light); }
.pv-home-rule span { background: linear-gradient(90deg, transparent, var(--earth-accent), transparent); }
.pv-home-player, .pv-home-action, .pv-home-status-block {
  border-color: rgba(162, 245, 238, .17);
  background: linear-gradient(145deg, rgba(16, 36, 45, .56), rgba(7, 15, 24, .78));
  box-shadow: 0 18px 42px rgba(0, 0, 0, .3), inset 0 1px rgba(255, 255, 255, .04);
}
.pv-home-status {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: stretch;
}
.pv-home-status-block {
  min-height: 74px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.pv-home-status-world {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(120deg, rgba(120, 207, 209, .1), transparent 52%),
    linear-gradient(145deg, rgba(16, 36, 45, .62), rgba(7, 15, 24, .8));
}
.pv-home-status-world::after {
  content: '';
  position: absolute;
  right: -16px;
  bottom: -26px;
  width: 92px;
  height: 92px;
  border: 1px solid rgba(162, 245, 238, .18);
  border-radius: 50%;
  box-shadow: 0 0 0 10px rgba(162, 245, 238, .035), 0 0 0 20px rgba(162, 245, 238, .02);
  pointer-events: none;
}
.pv-world-signal-main {
  display: flex;
  align-items: baseline;
  gap: .45rem;
  margin-top: .42rem;
}
.pv-world-signal-main strong {
  color: var(--miya-text-strong);
  font-size: 1.25rem;
  line-height: 1;
  letter-spacing: .02em;
}
.pv-world-signal-main small {
  color: var(--earth-accent-light);
  font-size: .68rem;
  font-weight: 500;
}
.pv-world-signal-main span {
  color: var(--miya-text-muted);
  font-size: .56rem;
}
.pv-world-signal-link {
  align-self: flex-start;
  margin-top: .48rem;
  padding: .22rem 0;
  border: 0;
  border-bottom: 1px solid rgba(162, 245, 238, .28);
  color: var(--earth-accent-light);
  background: transparent;
  font-size: .55rem;
  cursor: pointer;
  transition: color .2s ease, border-color .2s ease;
}
.pv-world-signal-link b { margin-left: .22rem; font-size: .7rem; }
.pv-world-signal-link:hover { color: #fff; border-bottom-color: var(--earth-accent-light); }
.pv-home-action-main { border-left-color: var(--earth-accent); background: linear-gradient(100deg, color-mix(in srgb, var(--earth-accent) 12%, transparent), rgba(5, 10, 16, .6)); }
.pv-mission-mark, .pv-home-xp b, .pv-mission-counts b, .pv-home-reality-copy .done { color: var(--earth-accent-light); }
.pv-command-primary, .pv-btn-primary, .pv-btn-accept { color: #041014; background: linear-gradient(135deg, var(--earth-accent-light), var(--earth-accent)); }
.pv-command-menu .pv-home-card:hover { box-shadow: inset 2px 0 var(--earth-accent), 0 8px 18px rgba(0, 0, 0, .25); }
.pv-home-card-name, .pv-home-action-main h2 { color: var(--miya-text-strong); }
.pv-home-scroll { color: color-mix(in srgb, var(--earth-accent-light) 55%, transparent); }

@media (max-width: 760px) {
  .pv-nav { background: linear-gradient(180deg, rgba(5, 10, 16, .82), rgba(5, 10, 16, .28)); }
  .pv-nav-logo { left: 10px; }
  .pv-nav-side { right: 9px; }
  .pv-nav-center { gap: 10px; }
  .pv-nav-center a, .pv-nav-more { padding-inline: 5px; font-size: .6rem; letter-spacing: .06em; }
  .pv-home-bg { filter: blur(5px) brightness(.48) saturate(1.05); }
  .pv-home-title { text-shadow: 0 0 22px color-mix(in srgb, var(--earth-accent) 30%, transparent); }
  .pv-home-status-block { min-height: 0; }
  .pv-world-signal-main { margin-top: .36rem; }
  .pv-home-status { grid-template-columns: 1fr; }
}

/* ── v4 exploration HUD: world atlas + quest board ── */
.pv-board,
.pv-world {
  background:
    linear-gradient(90deg, rgba(5, 10, 16, .88), rgba(5, 10, 16, .58)),
    repeating-linear-gradient(90deg, transparent 0 119px, rgba(120, 207, 209, .026) 120px),
    repeating-linear-gradient(0deg, transparent 0 79px, rgba(120, 207, 209, .018) 80px);
}
.pv-board-wrap { gap: 1.15rem; }
.pv-board-left {
  position: relative;
  overflow: hidden;
}
.pv-board-left::before {
  content: 'MIYA / QUEST DISPATCH';
  position: absolute;
  top: .72rem;
  right: .9rem;
  color: var(--miya-text-faint);
  font-size: .45rem;
  letter-spacing: .16em;
  pointer-events: none;
}
.pv-board-title { letter-spacing: .16em; }
.pv-board-tabs { border-bottom: 1px solid var(--miya-line-soft); }
.pv-board-tabs > a.active { color: var(--earth-accent-light); }
.pv-tab-underline { background: var(--earth-accent-light); box-shadow: 0 0 9px rgba(162, 245, 238, .35); }
.pv-board-type-filter a.active { color: var(--earth-accent-light); border-color: rgba(162, 245, 238, .42); background: rgba(120, 207, 209, .07); }
.pv-board-list::-webkit-scrollbar { width: 4px; }
.pv-board-list::-webkit-scrollbar-thumb { background: rgba(162, 245, 238, .28); }
.pv-board-item { min-height: 52px; }
.pv-board-item.active { background: linear-gradient(90deg, rgba(120, 207, 209, .13), rgba(120, 207, 209, .025)); }
.pv-board-item-underline { background: var(--earth-accent-light); box-shadow: 0 0 10px rgba(162, 245, 238, .3); }
.pv-board-right { position: relative; }
.pv-quest-show {
  position: relative;
  overflow: hidden;
  border-left: 2px solid var(--earth-accent);
  clip-path: polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 0 100%);
  background:
    linear-gradient(145deg, rgba(18, 40, 49, .64), rgba(5, 12, 20, .88)),
    repeating-linear-gradient(135deg, transparent 0 18px, rgba(162, 245, 238, .025) 19px 20px);
}
.pv-quest-show::after {
  content: 'FIELD DIRECTIVE / LIVE';
  position: absolute;
  right: 1rem;
  bottom: .78rem;
  color: rgba(162, 245, 238, .38);
  font-size: .45rem;
  letter-spacing: .16em;
  pointer-events: none;
}
.pv-quest-show-type { color: var(--earth-accent-light) !important; border-color: rgba(162, 245, 238, .5) !important; background: rgba(120, 207, 209, .08); }
.pv-quest-show-title { color: var(--miya-text-strong); letter-spacing: .06em; }
.pv-quest-subtasks { border-color: var(--miya-line); background: rgba(5, 12, 20, .56); }

.pv-world-wrap { padding-top: clamp(1.15rem, 3vh, 2.25rem); }
.pv-world-head {
  position: relative;
  padding: 1rem 1.1rem;
  border: 1px solid var(--miya-line);
  border-left: 2px solid var(--earth-accent);
  background: linear-gradient(120deg, rgba(16, 36, 45, .66), rgba(7, 15, 24, .72));
  clip-path: polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%);
}
.pv-world-head h2 { letter-spacing: .1em; }
.pv-world-count {
  padding: .48rem .65rem;
  border: 1px solid rgba(162, 245, 238, .28);
  color: var(--earth-accent-light);
  background: rgba(120, 207, 209, .06);
  font-size: .62rem;
}
.pv-world-atmosphere {
  align-items: center;
  gap: .55rem 1rem;
  padding: .55rem .7rem;
  border-inline: 1px solid var(--miya-line-soft);
  border-bottom: 1px solid var(--miya-line-soft);
  background: rgba(7, 15, 24, .58);
}
.pv-world-grid { box-shadow: inset 0 1px rgba(162, 245, 238, .06), 0 18px 42px rgba(0, 0, 0, .22); }
.pv-world-region {
  position: relative;
  transition: transform .24s ease, border-color .24s ease, box-shadow .24s ease;
}
.pv-world-region::after {
  content: '';
  position: absolute;
  top: .55rem;
  right: .55rem;
  width: 16px;
  height: 16px;
  border-top: 1px solid color-mix(in srgb, var(--world-color) 62%, transparent);
  border-right: 1px solid color-mix(in srgb, var(--world-color) 62%, transparent);
  opacity: .6;
  pointer-events: none;
}
.pv-world-region:hover { transform: translateY(-2px); }
.pv-world-region.locked::after { opacity: .28; }
.pv-world-region h3 { letter-spacing: .06em; }
.pv-world-progress { background: rgba(162, 245, 238, .1); }
.pv-world-resonance-bar { background: rgba(162, 245, 238, .08); }
.pv-world-message, .pv-world-companion, .pv-world-choice { border-radius: 0; border-left: 2px solid var(--earth-accent); background: rgba(120, 207, 209, .07); }

@media (max-width: 900px) {
  .pv-quest-show { min-height: 320px; }
  .pv-world-head { padding: .85rem; }
  .pv-world-grid { box-shadow: 0 14px 32px rgba(0, 0, 0, .22); }
}
@media (max-width: 760px) {
  .pv-board-left::before { display: none; }
  .pv-quest-show::after { right: .7rem; bottom: .6rem; }
  .pv-world-head { clip-path: none; }
  .pv-world-count { display: inline-block; margin-top: .55rem; }
  .pv-world-atmosphere { border-inline: 0; }
}

/* ── v5 command hierarchy: five clear destinations, one primary action ── */
.pv-nav-center {
  gap: 3px;
  padding: 3px;
  border-color: rgba(162, 245, 238, .11);
  background: rgba(5, 13, 21, .58);
  backdrop-filter: blur(14px);
}
.pv-nav-center a {
  min-width: 68px;
  justify-content: center;
  color: var(--miya-text-muted);
}
.pv-nav-center a.active {
  color: var(--earth-accent-light);
  background: linear-gradient(180deg, rgba(120, 207, 209, .13), rgba(120, 207, 209, .035));
  box-shadow: inset 0 -2px var(--earth-accent-light);
}
.pv-home .pv-command-deck {
  width: min(1120px, calc(100% - 56px));
  gap: .58rem;
}
.pv-command-copy .pv-home-title {
  max-width: 720px;
}
.pv-home-feature {
  grid-template-columns: 216px minmax(0, 1fr);
}
.pv-home-player {
  padding: .72rem;
}
.pv-home-action {
  padding: .82rem .92rem .72rem;
}
.pv-home-action-main {
  min-height: 72px;
  margin-top: .55rem;
  padding: .72rem .82rem;
}
.pv-home-action-main h2 {
  font-size: 1.05rem;
}
.pv-home-status {
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr) minmax(176px, .58fr);
  gap: 5px;
}
.pv-home-status-block {
  min-height: 64px;
}
.pv-home-status-values {
  gap: 3px;
}
.pv-home-reality-copy {
  gap: .45rem;
}
.pv-command-menu .pv-home-card {
  min-height: 44px;
}

@media (max-width: 900px) {
  .pv-home-status { grid-template-columns: 1fr 1fr; }
  .pv-home-status-world { grid-column: 1 / -1; }
}

@media (max-width: 760px) {
  .pv-nav { height: 86px; padding-inline: 8px; }
  .pv-nav-logo { top: 8px; left: 8px; }
  .pv-nav-logo-text, .pv-nav-id { display: none; }
  .pv-nav-side { top: 8px; right: 8px; gap: 4px; }
  .pv-nav-avatar { width: 28px; height: 28px; }
  .pv-nav-coins { display: flex; gap: 3px; }
  .pv-nav-coin { padding: 3px 6px; font-size: .58rem; }
  .pv-nav-coin.earth { display: none; }
  .pv-nav-care { width: 28px; height: 28px; }
  .pv-nav-center {
    top: 42px;
    left: 7px;
    right: 7px;
    gap: 1px;
    overflow: hidden;
  }
  .pv-nav-center a {
    flex: 1 1 20%;
    min-width: 0;
    padding: 7px 3px;
    font-size: .58rem;
    letter-spacing: 0;
    white-space: nowrap;
  }
  .pv-context-nav {
    top: 86px;
    left: 8px;
    right: 8px;
    transform: none;
    justify-content: flex-start;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .pv-context-nav::-webkit-scrollbar { display: none; }
  .pv-context-label { padding-inline: .35rem .5rem; }
  .pv-context-item { padding-inline: 9px; }
  .pv-context-item small { display: none; }
  .pv-section { padding-top: 90px; }
  .pv-stage.has-context-nav .pv-section { padding-top: 122px; }
  .pv-home .pv-command-deck {
    width: calc(100% - 14px);
    padding-top: .75rem;
    gap: .55rem;
  }
  .pv-home .pv-command-copy .pv-home-title { font-size: 2.1rem; }
  .pv-command-copy .pv-home-en { font-size: .5rem; letter-spacing: .2em; }
  .pv-home-rule { margin-top: .55rem; }
  .pv-home-feature { grid-template-columns: 1fr; gap: .55rem; }
  .pv-home-player {
    grid-template-columns: 58px 1fr;
    column-gap: .6rem;
  }
  .pv-home-portrait { width: 58px; height: 72px; margin-top: .55rem; }
  .pv-home-action { order: -1; }
  .pv-home-action-main { grid-template-columns: auto minmax(0, 1fr); }
  .pv-home-action-main .pv-command-primary { grid-column: 2; }
  .pv-home-status { grid-template-columns: 1fr; gap: 5px; }
  .pv-home-status-world { grid-column: auto; }
  .pv-home-status-values { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .pv-home-reality-copy { align-items: flex-start; }
  .pv-command-menu { grid-template-columns: repeat(2, 1fr); }
  .pv-command-menu .pv-home-card { min-height: 46px; }
}

@media (max-width: 420px) {
  .pv-home-status-values { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .pv-home-action-main { gap: .58rem; }
  .pv-home-action-main h2 { font-size: .92rem; }
}

/* ── v6 player HUD polish: information hierarchy over decoration ── */
.pv-nav-id { min-width: 82px; }
.pv-nav-xp { display: block; width: 100%; height: 2px; margin-top: 4px; overflow: hidden; background: rgba(162, 245, 238, .12); }
.pv-nav-xp em { display: block; height: 100%; background: var(--earth-accent-light); box-shadow: 0 0 8px rgba(162, 245, 238, .5); }
.pv-nav-coin { white-space: nowrap; }

.pv-board-tabs > a { display: inline-flex; align-items: center; gap: .28rem; }
.pv-tab-count { min-width: 1.1em; padding: .08rem .3rem; border: 1px solid var(--miya-line-soft); color: var(--miya-text-muted); font: 600 .62rem/1.2 'Noto Sans SC', sans-serif; text-align: center; }
.pv-board-tabs > a.active .pv-tab-count { color: var(--earth-accent-light); border-color: rgba(162, 245, 238, .32); background: rgba(120, 207, 209, .08); }
.pv-board-item-meta { display: inline-flex; align-items: center; gap: .42rem; flex: 0 0 auto; color: var(--earth-life); font-size: .58rem; letter-spacing: .08em; }
.pv-board-item-meta small { padding-left: .42rem; border-left: 1px solid var(--miya-line-soft); color: var(--miya-text-muted); font-size: .58rem; letter-spacing: 0; }
.pv-board-item.active .pv-board-item-meta { color: var(--earth-accent-light); }
.pv-quest-show-kicker { display: flex; justify-content: space-between; align-items: center; gap: 1rem; margin: -.25rem 0 -.1rem; color: var(--miya-text-faint); font-size: .5rem; letter-spacing: .16em; }
.pv-quest-show-kicker b { padding: .18rem .42rem; border: 1px solid var(--miya-line); color: var(--miya-text-muted); font-size: .5rem; font-weight: 600; letter-spacing: .08em; }
.pv-quest-show-kicker b.status-pending, .pv-quest-show-kicker b.status-ongoing { color: var(--earth-accent-light); border-color: rgba(162, 245, 238, .3); }
.pv-quest-show-kicker b.status-completed { color: var(--miya-success); }
.pv-quest-show-kicker b.status-failed { color: var(--miya-danger); }
.pv-quest-more { position: relative; }
.pv-quest-more-toggle { min-width: 76px; }
.pv-quest-more-menu { position: absolute; right: 0; bottom: calc(100% + .45rem); z-index: 3; display: flex; flex-direction: column; min-width: 128px; padding: .28rem; border: 1px solid var(--miya-line-strong); background: rgba(8, 16, 25, .98); box-shadow: 0 10px 24px rgba(0, 0, 0, .38); }
.pv-quest-more-menu button { width: 100%; padding: .42rem .55rem; border: 0; text-align: left; }
.pv-quest-more-menu button:hover { background: rgba(120, 207, 209, .1); }

.pv-world-region { min-height: 320px; padding: 1.05rem; background-color: rgba(8, 16, 25, .78); cursor: pointer; }
.pv-world-region::before { content: ''; position: absolute; inset: 0; pointer-events: none; background: linear-gradient(180deg, rgba(5, 10, 16, .04) 22%, rgba(5, 10, 16, .68) 100%); }
.pv-world-region > * { position: relative; z-index: 1; }
.pv-world-region-top-actions { gap: .55rem; }
.pv-world-state { padding: .18rem .36rem; border: 1px solid rgba(162, 245, 238, .28); color: var(--earth-accent-light); font-size: .48rem; letter-spacing: .12em; }
.pv-world-state.complete { color: var(--miya-success); border-color: rgba(114, 214, 177, .34); }
.pv-world-state.locked { color: var(--miya-text-faint); border-color: var(--miya-line-soft); }
.pv-world-region.locked { filter: saturate(.6); }
.pv-world-region.locked h3, .pv-world-region.locked .pv-world-subtitle { color: var(--miya-text-muted); }
.pv-world-region h3 { margin-top: 1.15rem; font-size: 1.12rem; }
.pv-world-region-desc { flex: 0 0 5.15em; max-height: 5.15em; margin: .7rem 0 .95rem; overflow: hidden; }
.pv-world-explore { margin-top: .2rem; min-height: 38px; font-weight: 700; letter-spacing: .06em; }
.pv-world-commission { min-height: 32px; }
.pv-region-drawer-icon { display: grid; place-items: center; height: 100%; color: var(--world-color); font-size: 4rem; text-shadow: 0 0 24px color-mix(in srgb, var(--world-color) 60%, transparent); }
.pv-drawer-cover-region { background-size: cover; background-position: center; }
.pv-drawer-region-state { position: absolute; right: .8rem; bottom: .7rem; padding: .24rem .45rem; border: 1px solid rgba(162, 245, 238, .3); color: var(--earth-accent-light); font-size: .52rem; letter-spacing: .14em; }
.pv-drawer-region-state.complete { color: var(--miya-success); border-color: rgba(114, 214, 177, .34); }
.pv-drawer-region-state.locked { color: var(--miya-text-faint); border-color: var(--miya-line-soft); }
.pv-region-drawer-progress { display: flex; flex-direction: column; gap: .4rem; margin-top: .45rem; }
.pv-region-drawer-progress > div { display: flex; justify-content: space-between; color: var(--miya-text-muted); font-size: .65rem; }
.pv-region-drawer-progress b { color: var(--earth-accent-light); font-weight: 600; }
.pv-region-drawer-progress > i { display: block; height: 4px; overflow: hidden; background: rgba(255, 255, 255, .08); }
.pv-region-drawer-progress em { display: block; height: 100%; background: linear-gradient(90deg, var(--earth-accent), var(--earth-accent-light)); }
.pv-region-drawer-resonance { margin-top: .35rem; }
.pv-region-drawer-conditions { margin-top: .25rem; }
.pv-region-drawer-actions { display: flex; gap: .55rem; margin-top: .55rem; }
.pv-region-drawer-actions button { flex: 1; min-height: 36px; }
.pv-drawer-profile-mark { padding: .95rem 1.1rem .7rem; color: var(--miya-text-faint); font: .55rem/1 'JetBrains Mono', monospace; letter-spacing: .18em; border-bottom: 1px solid var(--miya-line-soft); }
.pv-drawer-profile-body label { margin-top: .35rem; color: var(--miya-text-muted); font-size: .68rem; }
.pv-drawer-input { width: 100%; box-sizing: border-box; padding: .48rem .6rem; border: 1px solid var(--miya-line); background: rgba(255, 255, 255, .05); color: var(--miya-text); font: inherit; outline: none; }
.pv-drawer-profile-body textarea { width: 100%; box-sizing: border-box; padding: .55rem .6rem; border: 1px solid var(--miya-line); background: rgba(255, 255, 255, .05); color: var(--miya-text); outline: none; }
.pv-drawer-input:focus, .pv-drawer-profile-body .pv-md-editor:focus { border-color: var(--earth-accent); }
.pv-drawer-profile-body .pv-md-editor { min-height: 150px; }

@media (max-width: 760px) {
  .pv-nav-xp { display: none; }
  .pv-board-item-meta { display: none; }
  .pv-world-region { min-height: 290px; }
  .pv-region-drawer-actions { flex-direction: column; }
}

/* ── world atlas order: equal cards, predictable scanning ── */
.pv-world-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-auto-rows: minmax(304px, auto);
  align-items: stretch;
}
.pv-world-region {
  min-height: 304px;
  height: 100%;
  box-sizing: border-box;
  padding: 1.1rem;
}
.pv-world-region:nth-child(n) { grid-column: auto; grid-row: auto; }
.pv-world-region-top { min-height: 34px; }
.pv-world-region-top-actions { align-self: flex-start; flex-wrap: wrap; justify-content: flex-end; }
.pv-world-region h3 { min-height: 1.35em; margin-top: 1rem; }
.pv-world-subtitle { min-height: 1.25em; }
.pv-world-region-desc :deep(p), .pv-world-region-desc :deep(ul), .pv-world-region-desc :deep(ol) { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; }
.pv-world-explore { margin-top: auto; }
.pv-world-commission { flex-shrink: 0; }

@media (max-width: 900px) {
  .pv-world-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); grid-auto-rows: minmax(300px, auto); }
}
@media (max-width: 760px) {
  .pv-world-grid { grid-template-columns: 1fr; grid-auto-rows: auto; }
  .pv-world-region { min-height: 290px; height: auto; }
}

</style>
