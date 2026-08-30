<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import EarthAPI, {
  type EarthAchievement,
  type EarthCharacter,
  type EarthCommemoration,
  type EarthItem,
  type EarthMiyaNote,
  type EarthMiyaShopItemInput,
  type EarthMiyaShopManagedItem,
  type EarthPlayer,
  type EarthQuest,
  type EarthStory,
  type EarthTemplates,
  type EarthRealContext,
  type EarthWorldCustomEvent,
  type EarthWorldEventArea,
  type EarthWorldRegion,
} from '@/api/earth'
import FieldsEditor from './FieldsEditor.vue'
import Markdown from '@/components/Markdown.vue'

const activeTab = ref<'items' | 'quests' | 'characters' | 'story' | 'notes' | 'world' | 'achievements' | 'data'>('items')
const loading = ref(false)
const loadError = ref('')
const player = ref<EarthPlayer | null>(null)
const items = ref<EarthItem[]>([])
const quests = ref<EarthQuest[]>([])
const characters = ref<EarthCharacter[]>([])
const stories = ref<EarthStory[]>([])
const questHistory = ref<EarthQuest[]>([])
const templates = ref<EarthTemplates | null>(null)
const notes = ref<EarthMiyaNote[]>([])
const toast = ref('')
const worldRegions = ref<EarthWorldRegion[]>([])
const worldEvents = ref<EarthWorldCustomEvent[]>([])
const realContext = ref<EarthRealContext | null>(null)
const realSettings = reactive({ enabled: true, city: '', refresh_minutes: 30, allow_precise_location: false, weather_api_key_masked: '' })
const weatherApiKey = ref('')
const worldRegionForm = reactive({ key: '', name: '', subtitle: '', description: '', icon: '◇', color: '#c9ac67', level_req: 1, latitude: '' as string | number, longitude: '' as string | number, geofence_radius: 0 })
const worldEventForm = reactive({ region_key: '', title: '', text: '', kind: 'story', reward_currency: 10, reward_exp: 15 })
const worldBusy = ref(false)

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
const STATUS_LABELS: Record<string, string> = {
  pending: '待开始', ongoing: '进行中', completed: '已完成', failed: '失败', cancelled: '已取消',
}
const RELATIONSHIP_LABELS: Record<string, string> = {
  family: '家人', friend: '朋友', colleague: '同事', partner: '恋人', other: '其他',
}
const EVENT_TYPE_LABELS: Record<string, string> = {
  life: '生活', achievement: '成就', quest: '任务', character: '人物',
}

const TABS = [
  ['items', '背包'],
  ['quests', '任务'],
  ['characters', '角色'],
  ['story', '剧情'],
  ['notes', '弥娅寄语'],
  ['world', '世界管理'],
  ['achievements', '成就'],
  ['data', '数据'],
] as const
const TAB_GROUPS = [
  { id: 'content', label: '内容管理', en: 'CONTENT', tabs: TABS.slice(0, 5) },
  { id: 'world', label: '世界管理', en: 'WORLD', tabs: TABS.slice(5, 6) },
  { id: 'system', label: '系统设置', en: 'SYSTEM', tabs: TABS.slice(6) },
] as const

function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => (toast.value = ''), 2600)
}

async function loadPlayer() { player.value = await EarthAPI.getPlayer() }
async function loadItems() { items.value = await EarthAPI.listItems() }
async function loadQuests() { quests.value = await EarthAPI.listQuests(); questHistory.value = await EarthAPI.questHistory(30) }
async function loadCharacters() { characters.value = await EarthAPI.listCharacters() }
async function loadStories() { stories.value = await EarthAPI.listStory() }
async function loadTemplates() { templates.value = await EarthAPI.getTemplates() }
async function loadNotes() { notes.value = await EarthAPI.listNotes(100) }
async function loadWorldAdmin() {
  const [world, settings, context, events, areas, miyaShopManaged, commemorationsList] = await Promise.all([EarthAPI.world(), EarthAPI.realContextSettings(), EarthAPI.realContext(), EarthAPI.listWorldEvents(), EarthAPI.listEventAreas(), EarthAPI.listMiyaShopManaged(), EarthAPI.listCommemorations()])
  worldRegions.value = world.regions || []
  Object.assign(realSettings, settings)
  realContext.value = context
  worldEvents.value = events || []
  eventAreas.value = areas || []
  miyaShopItems.value = miyaShopManaged || []
  commemorations.value = commemorationsList || []
  if (!worldEventForm.region_key && worldRegions.value[0]) worldEventForm.region_key = worldRegions.value[0].key
}

function editWorldRegion(region: EarthWorldRegion) {
  Object.assign(worldRegionForm, {
    key: region.key, name: region.name, subtitle: region.subtitle, description: region.description, icon: region.icon, color: region.color, level_req: region.level_req,
    // 地理围栏: 坐标/半径按当前区域值回填
    latitude: region.latitude ?? '', longitude: region.longitude ?? '', geofence_radius: region.geofence_radius || 0,
  })
}
function selectWorldRegion(e: Event) {
  const key = (e.target as HTMLSelectElement).value
  const region = worldRegions.value.find(item => item.key === key)
  if (region) editWorldRegion(region)
}
async function saveWorldRegion() {
  if (!worldRegionForm.key || worldBusy.value) return
  worldBusy.value = true
  try {
    // 地理围栏: 半径 0 或坐标留空表示关闭围栏
    const lat = String(worldRegionForm.latitude).trim()
    const lng = String(worldRegionForm.longitude).trim()
    const radius = Number(worldRegionForm.geofence_radius) || 0
    const fenceEnabled = radius > 0 && lat !== '' && lng !== ''
    await EarthAPI.updateWorldRegion(worldRegionForm.key, {
      ...worldRegionForm,
      latitude: fenceEnabled ? Number(lat) : null,
      longitude: fenceEnabled ? Number(lng) : null,
      geofence_radius: fenceEnabled ? radius : 0,
    })
    await loadWorldAdmin()
    showToast(fenceEnabled ? `区域已保存，地理围栏 ${radius} 米已启用` : '区域已保存，地理围栏已关闭')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '区域保存失败')
  }
  finally { worldBusy.value = false }
}
async function saveRealSettings() {
  if (worldBusy.value) return
  worldBusy.value = true
  try {
    if (weatherApiKey.value.trim()) {
      await EarthAPI.updateWeatherApiKey(weatherApiKey.value.trim())
      weatherApiKey.value = ''
    }
    await EarthAPI.updateRealContextSettings({ ...realSettings, allow_precise_location: false })
    const context = await EarthAPI.refreshRealContext()
    realContext.value = context
    showToast(context.source_status === 'ok' ? `现实天气已同步：${context.city}` : `现实天气未同步：${context.source_status}`)
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '现实数据保存失败')
  }
  finally { worldBusy.value = false }
}
async function addWorldEvent() {
  if (!worldEventForm.region_key || !worldEventForm.title.trim() || !worldEventForm.text.trim() || worldBusy.value) return
  worldBusy.value = true
  try {
    await EarthAPI.createWorldEvent({ ...worldEventForm })
    worldEventForm.title = ''; worldEventForm.text = ''
    await loadWorldAdmin()
    showToast('自定义世界事件已添加')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '世界事件添加失败')
  }
  finally { worldBusy.value = false }
}
async function removeWorldEvent(event: EarthWorldCustomEvent) {
  if (!confirm(`删除「${event.title}」？`)) return
  if (worldBusy.value) return
  worldBusy.value = true
  try {
    await EarthAPI.deleteWorldEvent(event.id)
    await loadWorldAdmin()
    showToast('世界事件已删除')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '世界事件删除失败')
  }
  finally { worldBusy.value = false }
}
async function onPickWorldRegionImage(region: EarthWorldRegion, e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || worldBusy.value) return
  worldBusy.value = true
  try {
    await EarthAPI.uploadWorldRegionImage(region.key, file)
    await loadWorldAdmin()
    showToast(`已更新「${region.name}」照片`)
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '区域照片上传失败')
  }
  finally { worldBusy.value = false }
}

// ── 限时活动管理 (内置活动只读，自定义活动可增改删 + 商品管理) ──
const eventAreas = ref<EarthWorldEventArea[]>([])
const eventAreaForm = reactive({
  key: '', name: '', subtitle: '', description: '', icon: '✦', color: '#c9ac67',
  start: '', end: '', reward_currency: 10, reward_exp: 15, active: true,
})
const editingEventArea = ref<EarthWorldEventArea | null>(null)
const eventItemForm = reactive({ key: '', name: '', description: '', cost: 10, limit: 1, kind: 'collectible', requires_discoveries: 0 })
const eventItemTarget = ref('')
const eventAreaShopItems = ref<Array<{ key: string, name: string, description: string, cost: number, limit: number, kind: string, requires_discoveries?: number }>>([])
// 拉取指定活动的现有商品列表
async function reloadEventAreaShop(areaKey: string) {
  eventAreaShopItems.value = []
  try {
    const shop = await EarthAPI.worldEventShop(areaKey)
    eventAreaShopItems.value = shop.items || []
  }
  catch { /* 内置活动无商店时静默 */ }
}
// 展开/收起某个活动的商品管理面板
function manageEventAreaItems(area: EarthWorldEventArea) {
  if (eventItemTarget.value === area.key) {
    eventItemTarget.value = ''
    eventAreaShopItems.value = []
    return
  }
  eventItemTarget.value = area.key
  reloadEventAreaShop(area.key)
}
function resetEventAreaForm() {
  Object.assign(eventAreaForm, { key: '', name: '', subtitle: '', description: '', icon: '✦', color: '#c9ac67', start: '', end: '', reward_currency: 10, reward_exp: 15, active: true })
  editingEventArea.value = null
}
function editEventArea(area: EarthWorldEventArea) {
  editingEventArea.value = area
  Object.assign(eventAreaForm, {
    key: area.key, name: area.name, subtitle: area.subtitle, description: area.description,
    icon: area.icon, color: area.color, start: area.start, end: area.end,
    reward_currency: area.reward_currency, reward_exp: area.reward_exp, active: !!area.active,
  })
}
async function submitEventArea() {
  if (worldBusy.value) return
  if (!eventAreaForm.key.trim() || !eventAreaForm.name.trim() || !eventAreaForm.start || !eventAreaForm.end) {
    showToast('活动需要 key / 名称 / 起止日期')
    return
  }
  worldBusy.value = true
  try {
    const payload = { ...eventAreaForm, key: eventAreaForm.key.trim(), name: eventAreaForm.name.trim() }
    const isEditing = !!editingEventArea.value
    const editingKey = editingEventArea.value?.key || ''
    if (isEditing)
      await EarthAPI.updateEventArea(editingKey, payload)
    else
      await EarthAPI.createEventArea(payload)
    resetEventAreaForm()
    await loadWorldAdmin()
    showToast(isEditing ? '自定义活动已更新' : '自定义活动已创建')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '活动保存失败')
  }
  finally { worldBusy.value = false }
}
async function removeEventArea(area: EarthWorldEventArea) {
  if (!confirm(`删除自定义活动「${area.name}」？`)) return
  worldBusy.value = true
  try {
    await EarthAPI.deleteEventArea(area.key)
    if (editingEventArea.value?.key === area.key) resetEventAreaForm()
    await loadWorldAdmin()
    showToast('自定义活动已删除')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '活动删除失败')
  }
  finally { worldBusy.value = false }
}
async function addEventShopItem() {
  if (worldBusy.value) return
  if (!eventItemTarget.value || !eventItemForm.key.trim() || !eventItemForm.name.trim()) {
    showToast('请先选择活动，并填写商品 key / 名称')
    return
  }
  worldBusy.value = true
  try {
    await EarthAPI.createEventShopItem(eventItemTarget.value, { ...eventItemForm, key: eventItemForm.key.trim(), name: eventItemForm.name.trim() })
    eventItemForm.key = ''; eventItemForm.name = ''; eventItemForm.description = ''
    await loadWorldAdmin()
    if (eventItemTarget.value)
      await reloadEventAreaShop(eventItemTarget.value)
    showToast('活动商品已添加')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '商品添加失败')
  }
  finally { worldBusy.value = false }
}
async function removeEventShopItem(areaKey: string, itemKey: string) {
  if (!confirm(`删除商品「${itemKey}」？`)) return
  worldBusy.value = true
  try {
    await EarthAPI.deleteEventShopItem(areaKey, itemKey)
    await loadWorldAdmin()
    await reloadEventAreaShop(areaKey)
    showToast('活动商品已删除')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '商品删除失败')
  }
  finally { worldBusy.value = false }
}
async function toggleEventAreaActive(area: EarthWorldEventArea) {
  if (!area.is_custom || worldBusy.value) return
  worldBusy.value = true
  try {
    await EarthAPI.updateEventArea(area.key, { active: !area.active })
    await loadWorldAdmin()
    showToast(area.active ? '活动已下架' : '活动已上架')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '活动状态更新失败')
  }
  finally { worldBusy.value = false }
}

// ── 弥娅商城 · 货架管理 (内置商品只读，自定义商品可增改删 / 上下架) ──
const miyaShopItems = ref<EarthMiyaShopManagedItem[]>([])
const editingMiyaShopItem = ref<EarthMiyaShopManagedItem | null>(null)
const miyaShopBusy = ref(false)
const miyaShopForm = reactive({
  key: '', name: '', description: '', cost: 12, limit: 1, kind: 'interaction',
  interaction: '', story_title: '', story_content: '', title_award: '',
})
const MIYA_SHOP_KIND_LABELS: Record<string, string> = {
  interaction: '亲昵互动', story: '短篇剧情', title: '专属称号', boost: '现实辅助', collectible: '纪念物',
}
function resetMiyaShopForm() {
  Object.assign(miyaShopForm, {
    key: '', name: '', description: '', cost: 12, limit: 1, kind: 'interaction',
    interaction: '', story_title: '', story_content: '', title_award: '',
  })
  editingMiyaShopItem.value = null
}
function editMiyaShopItem(item: EarthMiyaShopManagedItem) {
  editingMiyaShopItem.value = item
  Object.assign(miyaShopForm, {
    key: item.key, name: item.name, description: item.description || '',
    cost: item.cost ?? 0, limit: item.limit ?? 1, kind: item.kind || 'interaction',
    interaction: item.interaction || '', story_title: item.story_title || '',
    story_content: item.story_content || '', title_award: item.title_award || '',
  })
}
async function submitMiyaShopItem() {
  if (miyaShopBusy.value) return
  if (!miyaShopForm.key.trim() || !miyaShopForm.name.trim()) {
    showToast('商品需要 key / 名称')
    return
  }
  miyaShopBusy.value = true
  try {
    const kind = miyaShopForm.kind
    // 只提交当前类型对应的专属字段；boost 固定生效 commission_resonance
    const payload: EarthMiyaShopItemInput = {
      key: miyaShopForm.key.trim(),
      name: miyaShopForm.name.trim(),
      description: miyaShopForm.description,
      cost: Math.max(0, Number(miyaShopForm.cost) || 0),
      limit: Math.max(1, Number(miyaShopForm.limit) || 1),
      kind,
      interaction: kind === 'interaction' ? miyaShopForm.interaction : '',
      story_title: kind === 'story' ? miyaShopForm.story_title : '',
      story_content: kind === 'story' ? miyaShopForm.story_content : '',
      title_award: kind === 'title' ? miyaShopForm.title_award : '',
      boost: kind === 'boost' ? 'commission_resonance' : '',
    }
    const isEditing = !!editingMiyaShopItem.value
    const editingKey = editingMiyaShopItem.value?.key || ''
    if (isEditing)
      await EarthAPI.updateMiyaShopItem(editingKey, payload)
    else
      await EarthAPI.createMiyaShopItem(payload)
    resetMiyaShopForm()
    await loadWorldAdmin()
    showToast(isEditing ? '自定义商品已更新' : '新商品已上架')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '商品保存失败')
  }
  finally { miyaShopBusy.value = false }
}
async function toggleMiyaShopItemActive(item: EarthMiyaShopManagedItem) {
  if (!item.is_custom || miyaShopBusy.value) return
  miyaShopBusy.value = true
  try {
    await EarthAPI.updateMiyaShopItem(item.key, { active: !item.active })
    await loadWorldAdmin()
    showToast(item.active ? '商品已下架' : '商品已上架')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '上下架失败')
  }
  finally { miyaShopBusy.value = false }
}
async function removeMiyaShopItem(item: EarthMiyaShopManagedItem) {
  if (!confirm(`删除自定义商品「${item.name}」？`)) return
  miyaShopBusy.value = true
  try {
    await EarthAPI.deleteMiyaShopItem(item.key)
    if (editingMiyaShopItem.value?.key === item.key) resetMiyaShopForm()
    await loadWorldAdmin()
    showToast('自定义商品已删除')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '商品删除失败')
  }
  finally { miyaShopBusy.value = false }
}

// ── 成就管理 (v17 tab) ──
const achievements = ref<EarthAchievement[]>([])
const achBusy = ref(false)
const showAchievementModal = ref(false)
const achievementForm = reactive({ key: '', title: '', description: '', icon: '✦', category: 'quest', target: 1, reward_currency: 10, reward_exp: 15, title_award: '' })
async function loadAchievements() { achievements.value = await EarthAPI.listAchievements() }
async function refreshAchievementList() {
  if (achBusy.value) return
  achBusy.value = true
  try {
    const res = await EarthAPI.refreshAchievements()
    await loadAchievements()
    showToast(res.newly_unlocked?.length ? `成就已刷新，新解锁 ${res.newly_unlocked.length} 个` : '成就已刷新，暂无新解锁～')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '成就刷新失败')
  }
  finally { achBusy.value = false }
}
function openNewAchievement() {
  Object.assign(achievementForm, { key: '', title: '', description: '', icon: '✦', category: 'quest', target: 1, reward_currency: 10, reward_exp: 15, title_award: '' })
  showAchievementModal.value = true
}
async function submitAchievement() {
  if (achBusy.value) return
  if (!achievementForm.key.trim() || !achievementForm.title.trim()) {
    showToast('自定义成就需要 key / 标题')
    return
  }
  achBusy.value = true
  try {
    await EarthAPI.addAchievement({
      key: achievementForm.key.trim(),
      title: achievementForm.title.trim(),
      description: achievementForm.description,
      icon: achievementForm.icon,
      category: achievementForm.category,
      target: Math.max(1, Number(achievementForm.target) || 1),
      reward_currency: Math.max(0, Number(achievementForm.reward_currency) || 0),
      reward_exp: Math.max(0, Number(achievementForm.reward_exp) || 0),
      title_award: achievementForm.title_award.trim(),
    })
    showAchievementModal.value = false
    await loadAchievements()
    showToast(`自定义成就「${achievementForm.title}」已创建`)
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '成就创建失败')
  }
  finally { achBusy.value = false }
}
async function setAchievementProgress(a: EarthAchievement) {
  const input = window.prompt(`设置「${a.title}」的进度 (0-${a.target})`, String(a.progress))
  if (input === null) return
  const progress = Number(input)
  if (Number.isNaN(progress) || progress < 0) {
    showToast('请输入有效的进度数字～')
    return
  }
  try {
    const res = await EarthAPI.setAchievementProgress(a.key, Math.round(progress))
    await loadAchievements()
    showToast(res.achievement?.unlocked_at ? `进度已更新，成就「${a.title}」已解锁！✦` : `「${a.title}」进度已更新为 ${Math.round(progress)}`)
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '进度更新失败')
  }
}

// ── 玩家卡快捷操作 (+经验 / +弥娅币 / 地球币记账) ──
async function quickAddExp() {
  const input = window.prompt('增加多少经验？(负数为扣除)', '50')
  if (input === null) return
  const amount = Number(input)
  if (!amount || Number.isNaN(amount)) {
    showToast('请输入有效的数字～')
    return
  }
  try {
    await EarthAPI.addExp(amount)
    await loadPlayer()
    showToast(`经验 ${amount > 0 ? '+' : ''}${amount} 已到账～`)
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '经验调整失败')
  }
}
async function quickAddCurrency() {
  const input = window.prompt('增加多少弥娅币？(负数为扣除)', '20')
  if (input === null) return
  const amount = Number(input)
  if (!amount || Number.isNaN(amount)) {
    showToast('请输入有效的数字～')
    return
  }
  try {
    await EarthAPI.addCurrency(amount)
    await loadPlayer()
    showToast(`弥娅币 ${amount > 0 ? '+' : ''}${amount} 已到账～`)
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '弥娅币调整失败')
  }
}
// 地球币记账 (与前台记账同一接口)
const showAdminLedgerModal = ref(false)
const adminLedgerBusy = ref(false)
const adminLedgerForm = reactive({ amount: 0, reason: '' })
function openAdminLedger() {
  Object.assign(adminLedgerForm, { amount: 0, reason: '' })
  showAdminLedgerModal.value = true
}
async function submitAdminLedger() {
  if (adminLedgerBusy.value) return
  const amount = Number(adminLedgerForm.amount)
  if (!amount || Number.isNaN(amount)) {
    showToast('金额不能为 0，正数记收入、负数记支出哦～')
    return
  }
  adminLedgerBusy.value = true
  try {
    const res = await EarthAPI.adjustEarthCurrency(amount, adminLedgerForm.reason.trim() || (amount > 0 ? '现实收入' : '现实支出'))
    showAdminLedgerModal.value = false
    await loadPlayer()
    showToast(`已记账 ${amount > 0 ? '+' : ''}${amount} 元 · 余额 ¥${res.balance.toFixed(2)}`)
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '记账失败')
  }
  finally { adminLedgerBusy.value = false }
}

// ── 纪念日 (v17 世界管理小节) ──
const commemorations = ref<EarthCommemoration[]>([])
const COMMEMORATION_DATE_RE = /^\d{2}-\d{2}$/
const commemorationForm = reactive({ key: '', name: '', date: '', lead_days: 3, description: '', icon: '✦' })
const commemorationBusy = ref(false)
function commemorationPhaseLabel(c: EarthCommemoration): string {
  if (!c.enabled) return '已停用'
  if (c.phase === 'today') return '今天'
  if (c.phase === 'upcoming') return '临近'
  if (c.phase === 'later') return `还有 ${c.days_until} 天`
  return '日期无效'
}
async function addCommemorationRow() {
  if (commemorationBusy.value) return
  if (!commemorationForm.key.trim() || !commemorationForm.name.trim() || !COMMEMORATION_DATE_RE.test(commemorationForm.date.trim())) {
    showToast('纪念日需要 key / 名称 / 日期 (格式 MM-DD)')
    return
  }
  commemorationBusy.value = true
  try {
    await EarthAPI.addCommemoration({
      key: commemorationForm.key.trim(),
      name: commemorationForm.name.trim(),
      date: commemorationForm.date.trim(),
      description: commemorationForm.description.trim(),
      icon: commemorationForm.icon.trim() || '✦',
      lead_days: Math.max(0, Number(commemorationForm.lead_days) || 0),
    })
    Object.assign(commemorationForm, { key: '', name: '', date: '', lead_days: 3, description: '', icon: '✦' })
    await loadWorldAdmin()
    showToast('纪念日已添加，弥娅会提前提醒你的～')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '纪念日添加失败')
  }
  finally { commemorationBusy.value = false }
}
async function removeCommemoration(c: EarthCommemoration) {
  if (!confirm(`删除纪念日「${c.name}」？`)) return
  commemorationBusy.value = true
  try {
    await EarthAPI.deleteCommemoration(c.key)
    await loadWorldAdmin()
    showToast('纪念日已删除')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '纪念日删除失败')
  }
  finally { commemorationBusy.value = false }
}

// ── 生成今日日常委托 (v17 任务工具栏) ──
const dailyBusy = ref(false)
async function generateDaily() {
  if (dailyBusy.value) return
  dailyBusy.value = true
  try {
    const res = await EarthAPI.generateDailyCommissions()
    await loadQuests()
    showToast(res.created ? `今日日常已生成：${res.created} 个新委托✦` : '今天的日常委托已经在任务板上啦～')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '日常生成失败')
  }
  finally { dailyBusy.value = false }
}

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    await Promise.all([loadPlayer(), loadItems(), loadQuests(), loadCharacters(), loadStories(), loadTemplates(), loadNotes(), loadWorldAdmin(), loadAchievements()])
  }
  catch (e: any) {
    loadError.value = e?.response?.data?.detail || e?.message || '网络或服务异常'
  }
  finally {
    loading.value = false
  }
}

onMounted(loadAll)

// ── 弥娅寄语 ──
const noteForm = reactive({ content: '', mood: 'neutral', pinned: false })
const noteBusy = ref(false)
const MOOD_LABELS: Record<string, string> = {
  neutral: '✦ 平静', happy: '✧ 开心', caring: '❦ 关心', excited: '✸ 兴奋', proud: '✪ 骄傲', sleepy: '☾ 困倦', sad: '❋ 难过',
}
async function publishNote() {
  if (!noteForm.content.trim()) {
    showToast('寄语内容不能为空～')
    return
  }
  if (noteBusy.value)
    return
  noteBusy.value = true
  try {
    await EarthAPI.addNote({ ...noteForm, content: noteForm.content.trim() })
    noteForm.content = ''
    noteForm.pinned = false
    showToast('寄语已发布，佳会在地球online 首页看到它～')
    await loadNotes()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '寄语发布失败')
  }
  finally {
    noteBusy.value = false
  }
}
async function togglePin(n: EarthMiyaNote) {
  try {
    await EarthAPI.pinNote(n.id, !n.pinned)
    await loadNotes()
    showToast(n.pinned ? '寄语已取消置顶' : '寄语已置顶')
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '寄语置顶状态更新失败')
  }
}
async function removeNote(n: EarthMiyaNote) {
  if (!confirm('删除这条寄语？'))
    return
  try {
    await EarthAPI.deleteNote(n.id)
    showToast('寄语已删除')
    await loadNotes()
  }
  catch (e: any) {
    showToast(e?.response?.data?.detail || '寄语删除失败')
  }
}

const expPercent = computed(() => {
  if (!player.value)
    return 0
  const spentExp = (player.value.level - 1) * player.value.level / 2 * 100
  const current = player.value.exp - spentExp
  return Math.min(100, Math.round((current / (player.value.level * 100)) * 100))
})

// ── 好感度阶段 ──
function affinityLevel(affinity: number) {
  const levels = templates.value?.affinity_levels || []
  return levels.find(l => affinity >= l.min && affinity <= l.max) || { label: '未知', color: '#9e9e9e' }
}

// ── 字段 chips ──
function fieldChips(fields: Record<string, any> | undefined, limit = 4): Array<[string, any]> {
  if (!fields)
    return []
  return Object.entries(fields).slice(0, limit)
}

// ── 弹窗状态 ──
const showItemModal = ref(false)
const showQuestModal = ref(false)
const showCharacterModal = ref(false)
const showStoryModal = ref(false)
const showAffinityModal = ref(false)
const showPlayerModal = ref(false)
const editingItem = ref<EarthItem | null>(null)
const editingQuest = ref<EarthQuest | null>(null)
const editingCharacter = ref<EarthCharacter | null>(null)
const affinityTarget = ref<EarthCharacter | null>(null)

// ── 玩家卡 ──
const playerForm = reactive({ name: '玩家', title: '', avatar_path: '', bio: '', attrs: [] as Array<{ key: string, label: string, value: number, max: number }>, earth_currency: 0 })
function openPlayerModal() {
  const p = player.value
  if (!p)
    return
  Object.assign(playerForm, {
    name: p.name || '玩家',
    title: p.title || '',
    avatar_path: p.avatar_path || '',
    bio: p.bio || '',
    attrs: JSON.parse(JSON.stringify(p.attrs || [])),
    earth_currency: p.earth_currency ?? 0,
  })
  showPlayerModal.value = true
}
async function savePlayer() {
  await EarthAPI.updatePlayer({
    name: playerForm.name.trim() || '玩家',
    title: playerForm.title,
    avatar_path: playerForm.avatar_path,
    bio: playerForm.bio,
    attrs: playerForm.attrs,
    earth_currency: Math.max(0, playerForm.earth_currency),
  })
  showPlayerModal.value = false
  showToast('玩家卡已更新')
  await loadPlayer()
}
async function onPickPlayerAvatar(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file)
    return
  const res = await EarthAPI.uploadImage(file)
  playerForm.avatar_path = res.image_path
  input.value = ''
  showToast('头像已上传～')
}
function addAttr() {
  playerForm.attrs.push({ key: `attr${playerForm.attrs.length + 1}`, label: '', value: 50, max: 100 })
}
function removeAttr(index: number) {
  playerForm.attrs.splice(index, 1)
}

// ── 背包 ──
const itemForm = reactive({ name: '', category: 'digital', rarity: 'common', quantity: 1, description: '', image_path: '', markdown: '', fields: {} as Record<string, any> })
const itemTemplateFields = computed(() => templates.value?.items[itemForm.category]?.fields || [])
function openNewItem() {
  editingItem.value = null
  Object.assign(itemForm, { name: '', category: 'digital', rarity: 'common', quantity: 1, description: '', image_path: '', markdown: '', fields: {} })
  showItemModal.value = true
}
function openEditItem(item: EarthItem) {
  editingItem.value = item
  Object.assign(itemForm, {
    name: item.name, category: item.category, rarity: item.rarity,
    quantity: item.quantity, description: item.description, image_path: item.image_path || '',
    markdown: item.markdown || '',
    fields: JSON.parse(JSON.stringify(item.fields || {})),
  })
  showItemModal.value = true
}
async function saveItem() {
  if (!itemForm.name.trim())
    return
  if (editingItem.value)
    await EarthAPI.updateItem(editingItem.value.id, { ...itemForm })
  else
    await EarthAPI.createItem({ ...itemForm })
  showToast(editingItem.value ? '物品已更新' : `已将「${itemForm.name}」收入背包`)
  showItemModal.value = false
  await loadItems()
}
async function removeItem(item: EarthItem) {
  if (!confirm(`确认移除「${item.name}」？`))
    return
  await EarthAPI.deleteItem(item.id)
  showToast('物品已移除')
  await loadItems()
}
async function onPickImage(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file)
    return
  const res = await EarthAPI.uploadImage(file, editingItem.value?.id)
  if (editingItem.value) {
    itemForm.image_path = res.image_path
    await loadItems()
  }
  else {
    itemForm.image_path = res.image_path
  }
  input.value = ''
  showToast('图片已上传～')
}

// ── 任务 ──
const questForm = reactive({
  title: '', description: '', quest_type: 'branch', must_complete: false,
  reward_currency: 10, reward_exp: 15, penalty_currency: 20, deadline: '',
  fields: {} as Record<string, any>, difficulty: 1,
  subtasks: [] as Array<{ text: string, done: number | boolean }>,
  recurring: '',
})
const RECURRING_LABELS: Record<string, string> = {
  '': '一次性', daily: '每天循环 (喝水/睡觉等)', weekly: '每周循环',
}
const questTemplateId = ref('custom')
const questTemplateFields = computed(() => templates.value?.quests.find(q => q.id === questTemplateId.value)?.fields || [])
function applyQuestTemplate() {
  const tpl = templates.value?.quests.find(q => q.id === questTemplateId.value)
  if (!tpl)
    return
  questForm.reward_currency = tpl.reward_currency
  questForm.reward_exp = tpl.reward_exp
  questForm.penalty_currency = tpl.penalty_currency
  questForm.difficulty = tpl.difficulty || 1
}
function openNewQuest() {
  editingQuest.value = null
  questTemplateId.value = 'custom'
  Object.assign(questForm, {
    title: '', description: '', quest_type: 'branch', must_complete: false,
    reward_currency: 10, reward_exp: 15, penalty_currency: 20, deadline: '', fields: {}, difficulty: 1,
    subtasks: [], recurring: '',
  })
  showQuestModal.value = true
}
function openEditQuest(q: EarthQuest) {
  editingQuest.value = q
  Object.assign(questForm, {
    title: q.title, description: q.description, quest_type: q.quest_type, must_complete: q.must_complete,
    reward_currency: q.reward_currency, reward_exp: q.reward_exp, penalty_currency: q.penalty_currency,
    deadline: q.deadline, fields: q.fields || {}, difficulty: q.difficulty || 1,
    subtasks: (q.subtasks || []).map(s => ({ text: s.text, done: !!s.done })),
    recurring: q.recurring || '',
  })
  showQuestModal.value = true
}
function addSubtask() {
  questForm.subtasks.push({ text: '', done: false })
}
function removeSubtask(i: number) {
  questForm.subtasks.splice(i, 1)
}
async function saveQuest() {
  if (!questForm.title.trim())
    return
  const subtasks = questForm.subtasks
    .map(s => ({ text: s.text.trim(), done: !!s.done }))
    .filter(s => s.text)
  const payload = { ...questForm, subtasks }
  if (editingQuest.value)
    await EarthAPI.updateQuest(editingQuest.value.id, payload)
  else
    await EarthAPI.createQuest({ ...payload, source: 'manual' })
  showToast(`任务已${editingQuest.value ? '更新' : '发布'}: 「${questForm.title}」`)
  showQuestModal.value = false
  await Promise.all([loadQuests(), loadPlayer()])
}
async function completeQuest(q: EarthQuest) {
  const res = await EarthAPI.completeQuest(q.id)
  player.value = res.player
  showToast(`任务完成！+${res.reward.currency} 弥娅币, +${res.reward.exp} 经验`)
  await loadQuests()
}
async function cancelQuest(q: EarthQuest) {
  if (!confirm(`取消任务「${q.title}」？(无惩罚)`))
    return
  await EarthAPI.cancelQuest(q.id)
  showToast('任务已取消')
  await loadQuests()
}
async function failQuest(q: EarthQuest) {
  if (!confirm(`标记「${q.title}」为失败？将扣除 ${q.penalty_currency} 弥娅币`))
    return
  const res = await EarthAPI.failQuest(q.id)
  player.value = res.player
  showToast('任务失败，弥娅币已扣除')
  await loadQuests()
}
async function checkOverdue() {
  const res = await EarthAPI.checkOverdue()
  showToast(res.failed ? `${res.failed} 个逾期任务已失败` : '没有逾期任务～')
  await Promise.all([loadQuests(), loadPlayer()])
}

// ── 角色 ──
const characterForm = reactive({ name: '', nickname: '', relationship: 'friend', affinity: 0, notes: '', birthday: '', avatar_path: '', markdown: '', fields: {} as Record<string, any> })
const characterTemplateFields = computed(() => templates.value?.characters[characterForm.relationship]?.fields || [])
function openNewCharacter() {
  editingCharacter.value = null
  Object.assign(characterForm, { name: '', nickname: '', relationship: 'friend', affinity: 0, notes: '', birthday: '', avatar_path: '', markdown: '', fields: {} })
  showCharacterModal.value = true
}
function openEditCharacter(c: EarthCharacter) {
  editingCharacter.value = c
  Object.assign(characterForm, {
    name: c.name, nickname: c.nickname, relationship: c.relationship,
    affinity: c.affinity, notes: c.notes, birthday: c.birthday,
    avatar_path: c.avatar_path || '', markdown: c.markdown || '',
    fields: JSON.parse(JSON.stringify(c.fields || {})),
  })
  showCharacterModal.value = true
}
async function saveCharacter() {
  if (!characterForm.name.trim())
    return
  if (editingCharacter.value)
    await EarthAPI.updateCharacter(editingCharacter.value.id, { ...characterForm })
  else
    await EarthAPI.createCharacter({ ...characterForm })
  showToast(`角色「${characterForm.name}」已${editingCharacter.value ? '更新' : '加入图鉴'}`)
  showCharacterModal.value = false
  await loadCharacters()
}
async function removeCharacter(c: EarthCharacter) {
  if (!confirm(`确认移除角色「${c.name}」？`))
    return
  await EarthAPI.deleteCharacter(c.id)
  showToast('角色已移除')
  await loadCharacters()
}
async function onPickAvatar(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file)
    return
  const res = await EarthAPI.uploadImage(file)
  characterForm.avatar_path = res.image_path
  input.value = ''
  showToast('头像已上传～')
}
const affinityForm = reactive({ delta: 5, reason: '' })
function openAffinity(c: EarthCharacter) {
  affinityTarget.value = c
  affinityForm.delta = 5
  affinityForm.reason = ''
  showAffinityModal.value = true
}
async function saveAffinity() {
  if (!affinityTarget.value)
    return
  await EarthAPI.addAffinity(affinityTarget.value.id, Number(affinityForm.delta), affinityForm.reason)
  showToast(`「${affinityTarget.value.name}」好感度已更新`)
  showAffinityModal.value = false
  await loadCharacters()
}

// ── 剧情 ──
const storyForm = reactive({ title: '', content: '', event_type: 'life', character_id: '', happened_at: '', fields: {} as Record<string, any>, image_path: '' })
const editingStory = ref<EarthStory | null>(null)
function openNewStory() {
  editingStory.value = null
  Object.assign(storyForm, { title: '', content: '', event_type: 'life', character_id: '', happened_at: '', fields: {}, image_path: '' })
  showStoryModal.value = true
}
function openEditStory(s: EarthStory) {
  editingStory.value = s
  Object.assign(storyForm, {
    title: s.title,
    content: s.content,
    event_type: s.event_type,
    character_id: s.character_id ? String(s.character_id) : '',
    happened_at: s.happened_at || '',
    fields: s.fields || {},
    image_path: s.image_path || '',
  })
  showStoryModal.value = true
}
async function saveStory() {
  if (!storyForm.title.trim())
    return
  const wasEditing = !!editingStory.value
  const payload = {
    title: storyForm.title,
    content: storyForm.content,
    event_type: storyForm.event_type,
    character_id: storyForm.character_id ? Number(storyForm.character_id) : undefined,
    happened_at: storyForm.happened_at,
    fields: storyForm.fields,
    image_path: storyForm.image_path,
  }
  if (editingStory.value)
    await EarthAPI.updateStory(editingStory.value.id, payload)
  else
    await EarthAPI.createStory(payload)
  showStoryModal.value = false
  Object.assign(storyForm, { title: '', content: '', event_type: 'life', character_id: '', happened_at: '', fields: {}, image_path: '' })
  editingStory.value = null
  showToast(wasEditing ? '剧情已更新' : '剧情已记录')
  await loadStories()
}
async function onPickStoryImage(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file)
    return
  const res = await EarthAPI.uploadImage(file)
  storyForm.image_path = res.image_path
  input.value = ''
  showToast('剧情图片已上传～')
}
async function removeStory(s: EarthStory) {
  if (!confirm(`删除剧情「${s.title}」？`))
    return
  await EarthAPI.deleteStory(s.id)
  showToast('剧情已删除')
  await loadStories()
}

// ── 数据页 (JSON 可视化) ──
const jsonText = ref('')
const templatesText = ref('')
const jsonBusy = ref(false)

async function loadJsonText() {
  jsonBusy.value = true
  try {
    const data = await EarthAPI.exportJson()
    jsonText.value = JSON.stringify(data, null, 2)
    showToast('已从服务器读取最新数据')
  }
  finally {
    jsonBusy.value = false
  }
}
function formatJson() {
  try {
    jsonText.value = JSON.stringify(JSON.parse(jsonText.value), null, 2)
    showToast('已格式化')
  }
  catch (e) {
    showToast(`JSON 格式错误: ${(e as Error).message}`)
  }
}
async function saveJsonText() {
  try {
    const data = JSON.parse(jsonText.value)
    if (!confirm('保存会用此 JSON 覆盖全部数据（数据库会先自动备份），确认？'))
      return
    await EarthAPI.importJson(data)
    showToast('数据已导入保存')
    await loadAll()
  }
  catch (e) {
    showToast(`JSON 格式错误: ${(e as Error).message}`)
  }
}
function downloadJson() {
  const blob = new Blob([jsonText.value], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'earthonline.json'
  a.click()
  URL.revokeObjectURL(a.href)
}
async function loadTemplatesText() {
  const data = await EarthAPI.getTemplates()
  templatesText.value = JSON.stringify(data, null, 2)
  showToast('已读取模板')
}
async function saveTemplatesText() {
  try {
    const data = JSON.parse(templatesText.value)
    await EarthAPI.saveTemplates(data)
    templates.value = data
    showToast('模板已保存')
  }
  catch (e) {
    showToast(`JSON 格式错误: ${(e as Error).message}`)
  }
}

function formatDate(iso: string): string {
  if (!iso)
    return ''
  return iso.replace('T', ' ').slice(0, 16)
}

function questStars(difficulty: number): string {
  const d = Math.max(1, Math.min(5, difficulty || 1))
  return '★'.repeat(d) + '☆'.repeat(5 - d)
}
</script>

<template>
  <div class="earth-online">
    <!-- 开拓者角色卡 -->
    <header class="player-card">
      <div class="player-left">
        <div class="player-avatar">
          <img v-if="player?.avatar_path" :src="EarthAPI.imageUrl(player.avatar_path)" class="player-avatar-img" />
          <template v-else>地</template>
        </div>
        <div class="player-info">
          <div class="player-title">
            <span class="player-name">{{ player?.name || '玩家' }}</span>
            <span v-if="player?.title" class="player-subtitle">{{ player.title }}</span>
            <span class="player-level">Lv.{{ player?.level ?? 1 }}</span>
          </div>
          <div class="exp-bar"><div class="exp-fill" :style="{ width: `${expPercent}%` }" /></div>
          <div class="exp-label">开拓经验 {{ player?.exp ?? 0 }}</div>
        </div>
      </div>
      <div class="player-right">
        <div class="player-attrs">
          <div v-for="attr in (player?.attrs || []).slice(0, 4)" :key="attr.key" class="attr-row">
            <span class="attr-label">{{ attr.label || attr.key }}</span>
            <div class="attr-bar"><div class="attr-fill" :style="{ width: `${Math.min(100, (attr.value / (attr.max || 100)) * 100)}%` }" /></div>
            <span class="attr-value">{{ attr.value }}</span>
          </div>
        </div>
        <div class="player-stats">
          <div class="stat-item"><span class="stat-icon">◆</span><span class="stat-value">{{ player?.miya_currency ?? player?.currency ?? 0 }}</span><span class="stat-label">弥娅币</span></div>
          <div class="stat-item"><span class="stat-icon">✓</span><span class="stat-value">{{ player?.total_completed ?? 0 }}</span><span class="stat-label">完成任务</span></div>
          <div class="stat-item"><span class="stat-icon">✕</span><span class="stat-value">{{ player?.total_failed ?? 0 }}</span><span class="stat-label">失败任务</span></div>
        </div>
        <div class="player-quick-actions">
          <button class="btn-sm" title="调整玩家经验" @click="quickAddExp">+经验</button>
          <button class="btn-sm" title="调整弥娅币" @click="quickAddCurrency">+弥娅币</button>
          <button class="btn-sm" title="记一笔现实收入/支出" @click="openAdminLedger">地球币记账</button>
        </div>
        <button class="btn-ghost btn-edit-card" @click="openPlayerModal">✎ 编辑玩家卡</button>
      </div>
    </header>

    <nav class="earth-tabs" aria-label="地球online管理模块">
      <div v-for="group in TAB_GROUPS" :key="group.id" class="earth-tab-group">
        <span class="earth-tab-group-label"><b>{{ group.label }}</b><small>{{ group.en }}</small></span>
        <div class="earth-tab-group-items">
          <button
            v-for="t in group.tabs"
            :key="t[0]"
            class="earth-tab"
            :class="{ active: activeTab === t[0] }"
            @click="activeTab = t[0]"
          >
            {{ t[1] }}
          </button>
        </div>
      </div>
    </nav>

    <main class="earth-body">
      <div v-if="loading" class="loading">加载中…</div>
      <div v-else-if="loadError" class="load-error" role="alert">
        <strong>数据加载失败</strong>
        <span>{{ loadError }}</span>
        <button class="btn-primary" type="button" @click="loadAll">点击重试</button>
      </div>

      <!-- 背包 -->
      <section v-else-if="activeTab === 'items'" class="earth-panel">
        <div class="panel-head">
          <h3>我的背包 <small>({{ items.length }})</small></h3>
          <button class="btn-primary" @click="openNewItem">+ 新增物品</button>
        </div>
        <div v-if="items.length === 0" class="empty">背包还是空的呢，亲爱的，拍张照记录点什么吧～</div>
        <div v-else class="item-grid">
          <div v-for="item in items" :key="item.id" class="item-card" :style="{ borderColor: RARITY_COLORS[item.rarity] || '#888' }">
            <div class="item-img-wrap">
              <img v-if="item.image_path" :src="EarthAPI.imageUrl(item.image_path)" class="item-img" />
              <div v-else class="item-img item-img-ph">{{ item.name[0] }}</div>
              <span class="item-rarity" :style="{ background: RARITY_COLORS[item.rarity] || '#888' }">{{ RARITY_LABELS[item.rarity] || item.rarity }}</span>
              <span v-if="item.quantity > 1" class="item-qty">×{{ item.quantity }}</span>
            </div>
            <div class="item-body">
              <div class="item-name">{{ item.name }}</div>
              <div class="item-cat">{{ CATEGORY_LABELS[item.category] || item.category }}</div>
              <p v-if="item.description" class="item-desc">{{ item.description }}</p>
              <div v-if="fieldChips(item.fields).length" class="chip-row">
                <span v-for="[k, v] in fieldChips(item.fields)" :key="k" class="chip">{{ k }}: {{ v }}</span>
              </div>
            </div>
            <div class="item-actions">
              <button class="btn-sm" @click="openEditItem(item)">编辑</button>
              <button class="btn-sm btn-danger" @click="removeItem(item)">移除</button>
            </div>
          </div>
        </div>
      </section>

      <!-- 任务 -->
      <section v-else-if="activeTab === 'quests'" class="earth-panel">
        <div class="panel-head">
          <h3>任务委托 <small>(进行中 {{ quests.filter(q => ['pending', 'ongoing'].includes(q.status)).length }})</small></h3>
          <div class="head-actions">
            <button class="btn-ghost" :disabled="dailyBusy" @click="generateDaily">✦ 生成今日日常</button>
            <button class="btn-ghost" @click="checkOverdue">检查逾期</button>
            <button class="btn-primary" @click="openNewQuest">+ 新任务</button>
          </div>
        </div>
        <div v-if="quests.length === 0" class="empty">还没有任务，让弥娅给你安排一个吧～</div>
        <div v-else class="quest-list">
          <div v-for="q in quests" :key="q.id" class="quest-card" :class="q.status">
            <div class="quest-head">
              <span class="quest-type">{{ QUEST_TYPE_LABELS[q.quest_type] || q.quest_type }}</span>
              <span class="quest-badge" :class="q.must_complete ? 'badge-must' : 'badge-opt'">{{ q.must_complete ? '必须' : '可选' }}</span>
              <span v-if="q.source === 'miya'" class="quest-source">弥娅安排</span>
              <span class="quest-status">{{ STATUS_LABELS[q.status] || q.status }}</span>
            </div>
            <div class="quest-title">{{ q.title }}</div>
            <p v-if="q.description" class="quest-desc">{{ q.description }}</p>
            <div v-if="fieldChips(q.fields).length" class="chip-row">
              <span v-for="[k, v] in fieldChips(q.fields)" :key="k" class="chip">{{ k }}: {{ v }}</span>
            </div>
            <div v-if="(q.subtasks || []).length" class="chip-row">
              <span class="chip subtask-chip">
                进度 {{ (q.subtasks || []).filter(s => s.done).length }}/{{ (q.subtasks || []).length }}
              </span>
              <span
                v-for="(sub, i) in (q.subtasks || []).slice(0, 3)"
                :key="i"
                class="chip subtask-chip"
                :class="{ done: sub.done }"
              >
                {{ sub.done ? '◉' : '○' }} {{ sub.text }}
              </span>
              <span v-if="(q.subtasks || []).length > 3" class="chip">…</span>
            </div>
            <div class="quest-meta">
              <span class="meta-stars" :style="{ color: '#ffb300' }">{{ questStars(q.difficulty) }}</span>
              <span v-if="q.recurring === 'daily' || q.recurring === 'weekly'" class="meta-recurring">↻ {{ RECURRING_LABELS[q.recurring] }}</span>
              <span class="meta-reward">+{{ q.reward_currency }} 弥娅币</span>
              <span class="meta-reward">+{{ q.reward_exp }} 经验</span>
              <span v-if="q.penalty_currency" class="meta-penalty">鸽: -{{ q.penalty_currency }} 弥娅币</span>
              <span v-if="q.deadline" class="meta-deadline">截止 {{ formatDate(q.deadline) }}</span>
            </div>
            <div v-if="['pending', 'ongoing'].includes(q.status)" class="quest-actions">
              <button class="btn-sm btn-primary" @click="completeQuest(q)">✓ 完成</button>
              <button class="btn-sm" @click="cancelQuest(q)">取消</button>
              <button class="btn-sm btn-danger" @click="failQuest(q)">失败</button>
              <button class="btn-sm" @click="openEditQuest(q)">✎ 编辑</button>
            </div>
            <div v-else class="quest-actions">
              <button class="btn-sm" @click="openEditQuest(q)">✎ 编辑</button>
            </div>
          </div>
        </div>
        <div v-if="questHistory.length" class="history-block">
          <h4>任务历史</h4>
          <div v-for="h in questHistory" :key="h.id" class="history-item">
            <span class="h-status" :class="h.status">{{ STATUS_LABELS[h.status] || h.status }}</span>
            <span class="h-title">{{ h.title }}</span>
            <span class="h-time">{{ formatDate(h.completed_at || '') }}</span>
          </div>
        </div>
      </section>

      <!-- 角色 -->
      <section v-else-if="activeTab === 'characters'" class="earth-panel">
        <div class="panel-head">
          <h3>角色图鉴 <small>({{ characters.length }})</small></h3>
          <button class="btn-primary" @click="openNewCharacter">+ 新增角色</button>
        </div>
        <div v-if="characters.length === 0" class="empty">图鉴里还没有角色，先记录一位重要的人吧～</div>
        <div v-else class="character-grid">
          <div v-for="c in characters" :key="c.id" class="character-card">
            <div class="char-top">
              <div class="char-avatar" :style="!c.avatar_path ? { background: `hsl(${(c.id * 47) % 360}, 60%, 40%)` } : {}">
                <img v-if="c.avatar_path" :src="EarthAPI.imageUrl(c.avatar_path)" class="char-avatar-img" />
                <template v-else>{{ c.name[0] }}</template>
              </div>
              <div class="char-info">
                <div class="char-name">{{ c.name }}<span v-if="c.nickname" class="char-nick">{{ c.nickname }}</span></div>
                <div class="char-rel">{{ RELATIONSHIP_LABELS[c.relationship] || c.relationship }} · <span :style="{ color: affinityLevel(c.affinity).color }">{{ affinityLevel(c.affinity).label }}</span></div>
              </div>
              <span class="affinity-num">{{ c.affinity }}</span>
            </div>
            <div class="affinity-bar"><div class="affinity-fill" :style="{ width: `${c.affinity}%` }" /></div>
            <p v-if="c.notes" class="char-notes">{{ c.notes }}</p>
            <div v-if="fieldChips(c.fields).length" class="chip-row">
              <span v-for="[k, v] in fieldChips(c.fields)" :key="k" class="chip">{{ k }}: {{ v }}</span>
            </div>
            <div class="char-actions">
              <button class="btn-sm btn-primary" @click="openAffinity(c)">好感度 +/−</button>
              <button class="btn-sm" @click="openEditCharacter(c)">编辑</button>
              <button class="btn-sm btn-danger" @click="removeCharacter(c)">删除</button>
            </div>
          </div>
        </div>
      </section>

      <!-- 剧情 -->
      <section v-else-if="activeTab === 'story'" class="earth-panel">
        <div class="panel-head">
          <h3>人生剧情 <small>({{ stories.length }})</small></h3>
          <button class="btn-primary" @click="openNewStory">+ 记录剧情</button>
        </div>
        <div v-if="stories.length === 0" class="empty">还没有剧情记录，亲爱的，今天有什么故事想告诉我吗？</div>
        <div v-else class="story-timeline">
          <div v-for="s in stories" :key="s.id" class="story-item">
            <div class="story-dot" />
            <div class="story-card">
              <div class="story-head">
                <span class="story-type">{{ EVENT_TYPE_LABELS[s.event_type] || s.event_type }}</span>
                <span class="story-time">{{ formatDate(s.happened_at) }}</span>
              </div>
              <div class="story-title">{{ s.title }}</div>
              <p v-if="s.content" class="story-content">{{ s.content }}</p>
              <div class="story-actions">
                <button class="btn-sm" @click="openEditStory(s)">✎ 编辑</button>
                <button class="btn-sm btn-danger" @click="removeStory(s)">删除</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 弥娅寄语 -->
      <section v-else-if="activeTab === 'notes'" class="earth-panel">
        <div class="panel-head">
          <h3>弥娅寄语 <small>前台首页公告栏 ({{ notes.length }})</small></h3>
        </div>
        <div class="note-publish">
          <div class="note-publish-row">
            <textarea v-model="noteForm.content" class="note-editor" placeholder="写一条给佳的寄语吧，会显示在地球online 前台首页哦～ (支持 Markdown)" />
          </div>
          <div class="note-publish-foot">
            <select v-model="noteForm.mood" class="note-mood-select">
              <option v-for="(label, key) in MOOD_LABELS" :key="key" :value="key">{{ label }}</option>
            </select>
            <label class="checkbox-row"><input v-model="noteForm.pinned" type="checkbox" />置顶到首页</label>
            <button class="btn-primary" :disabled="noteBusy" @click="publishNote">✉ 发布寄语</button>
          </div>
        </div>
        <div v-if="notes.length === 0" class="empty">还没有寄语，弥娅快给佳写一条吧～</div>
        <div v-else class="note-list">
          <div v-for="n in notes" :key="n.id" class="note-card" :class="{ pinned: n.pinned }">
            <span class="note-mood">{{ MOOD_LABELS[n.mood]?.split(' ')[0] || '✦' }}</span>
            <div class="note-body">
              <div class="note-content"><Markdown :source="n.content" /></div>
              <div class="note-meta">
                <span v-if="n.pinned" class="note-pin-tag">📌 置顶</span>
                <span>{{ formatDate(n.created_at) }}</span>
              </div>
            </div>
            <div class="note-actions">
              <button class="btn-sm" @click="togglePin(n)">{{ n.pinned ? '取消置顶' : '置顶' }}</button>
              <button class="btn-sm btn-danger" @click="removeNote(n)">删除</button>
            </div>
          </div>
        </div>
      </section>

      <!-- 世界管理 -->
      <section v-else-if="activeTab === 'world'" class="earth-panel">
        <div class="panel-head">
          <h3>地球online 世界管理 <small>现实连接、区域照片与自定义发现</small></h3>
          <button class="btn-primary" :disabled="worldBusy" @click="loadWorldAdmin">↻ 刷新</button>
        </div>
        <div class="world-admin-grid">
          <div class="world-admin-card">
            <h4>现实天气连接</h4>
            <label class="checkbox-row"><input v-model="realSettings.enabled" type="checkbox" />启用现实数据</label>
            <label>城市（只保存城市名，不读取 GPS）</label>
            <input v-model="realSettings.city" placeholder="例如：北京 / 上海 / 杭州" />
            <label>刷新间隔（分钟）</label>
            <input v-model.number="realSettings.refresh_minutes" type="number" min="5" max="1440" />
            <div class="world-admin-status">{{ realContext?.source_status === 'ok' ? `已同步：${realContext.city} · ${realContext.weather} · ${realContext.temperature ?? '未知'}°C` : `当前状态：${realContext?.source_status || '未同步'}` }}</div>
            <label>心知天气 API Key <small>当前：{{ realSettings.weather_api_key_masked || '未配置' }}</small></label>
            <input v-model="weatherApiKey" type="password" placeholder="留空表示不修改" autocomplete="off" />
            <button class="btn-primary" :disabled="worldBusy" @click="saveRealSettings">保存并刷新现实</button>
          </div>
          <div class="world-admin-card">
            <h4>区域编辑</h4>
            <select @change="selectWorldRegion">
              <option value="">选择一个区域</option>
              <option v-for="region in worldRegions" :key="region.key" :value="region.key">{{ region.name }}</option>
            </select>
            <template v-if="worldRegionForm.key">
              <label>名称</label><input v-model="worldRegionForm.name" />
              <label>副标题</label><input v-model="worldRegionForm.subtitle" />
              <label>描述</label><textarea v-model="worldRegionForm.description" />
              <div class="modal-row"><div><label>图标</label><input v-model="worldRegionForm.icon" /></div><div><label>等级</label><input v-model.number="worldRegionForm.level_req" type="number" min="1" /></div></div>
              <label>主题色</label><input v-model="worldRegionForm.color" type="color" />
              <label>地理围栏 <small>坐标与半径 (米) 都设置后启用；半径 0 或坐标留空表示关闭</small></label>
              <div class="modal-row">
                <div><label>纬度 latitude</label><input v-model="worldRegionForm.latitude" placeholder="如 30.2741" /></div>
                <div><label>经度 longitude</label><input v-model="worldRegionForm.longitude" placeholder="如 120.1551" /></div>
              </div>
              <label>围栏半径 (米，0 = 关闭)</label>
              <input v-model.number="worldRegionForm.geofence_radius" type="number" min="0" />
              <button class="btn-primary" :disabled="worldBusy" @click="saveWorldRegion">保存区域</button>
            </template>
          </div>
        </div>
        <div class="world-admin-card">
          <h4>区域现实照片</h4>
          <div class="world-admin-region-list">
            <div v-for="region in worldRegions" :key="region.key" class="world-admin-region">
              <span class="world-admin-region-name">{{ region.name }}</span>
              <span class="world-admin-region-photo">{{ region.image_path ? '已绑定照片' : '尚未绑定' }}</span>
              <label class="btn-sm upload-btn">选择照片<input type="file" accept="image/*" hidden @change="onPickWorldRegionImage(region, $event)" /></label>
            </div>
          </div>
        </div>
        <div class="world-admin-card">
          <h4>新增自定义发现</h4>
          <div class="modal-row"><div><label>区域</label><select v-model="worldEventForm.region_key"><option v-for="region in worldRegions" :key="region.key" :value="region.key">{{ region.name }}</option></select></div><div><label>类型</label><select v-model="worldEventForm.kind"><option value="story">剧情</option><option value="chest">宝箱</option><option value="hidden">隐藏</option></select></div></div>
          <label>标题</label><input v-model="worldEventForm.title" placeholder="例如：窗边的新光" />
          <label>发现内容</label><textarea v-model="worldEventForm.text" placeholder="这条发现对应你现实里的什么事情？" />
          <div class="modal-row"><div><label>弥娅币</label><input v-model.number="worldEventForm.reward_currency" type="number" min="0" /></div><div><label>经验</label><input v-model.number="worldEventForm.reward_exp" type="number" min="0" /></div></div>
          <button class="btn-primary" :disabled="worldBusy" @click="addWorldEvent">添加发现</button>
          <div v-if="worldEvents.length" class="world-event-list"><div v-for="event in worldEvents" :key="event.id" class="world-event-row"><span>{{ event.title }}</span><small>{{ worldRegions.find(r => r.key === event.region_key)?.name || event.region_key }} · +{{ event.reward_currency }} ◆</small><button class="btn-sm btn-danger" @click="removeWorldEvent(event)">删除</button></div></div>
        </div>

        <!-- 限时活动管理 -->
        <div class="world-admin-card">
          <h4>限时活动管理 <small>内置活动不可修改；自定义活动可编辑 / 删除并管理商品</small></h4>
          <div v-if="eventAreas.length" class="event-area-list">
            <div v-for="area in eventAreas" :key="area.key" class="event-area-row">
              <span class="event-area-icon" :style="{ color: area.color }">{{ area.icon }}</span>
              <div class="event-area-info">
                <strong>{{ area.name }} <small v-if="!area.is_custom" class="event-area-tag builtin">内置</small><small v-else-if="area.running" class="event-area-tag running">进行中</small></strong>
                <small>{{ area.start }} ~ {{ area.end }} · +{{ area.reward_currency }} ◆ / +{{ area.reward_exp }} EXP</small>
              </div>
              <div class="event-area-actions">
                <button v-if="area.is_custom" class="btn-sm" :disabled="worldBusy" @click="editEventArea(area)">{{ editingEventArea?.key === area.key ? '编辑中' : '编辑' }}</button>
                <button v-if="area.is_custom" class="btn-sm" :disabled="worldBusy" @click="toggleEventAreaActive(area)">{{ area.active ? '下架' : '上架' }}</button>
                <button v-if="area.is_custom" class="btn-sm btn-danger" :disabled="worldBusy" @click="removeEventArea(area)">删除</button>
                <button class="btn-sm" @click="manageEventAreaItems(area)">{{ eventItemTarget === area.key ? '收起商品' : '管理商品' }}</button>
              </div>
            </div>
          </div>
          <p v-else class="data-hint">还没有任何限时活动。</p>
          <!-- 活动商品管理 (展开) -->
          <template v-if="eventItemTarget">
            <label>为「{{ eventAreas.find(a => a.key === eventItemTarget)?.name || eventItemTarget }}」添加商品 <small>仅自定义活动可添加</small></label>
            <div class="modal-row">
              <div><label>key</label><input v-model="eventItemForm.key" placeholder="如 memory_badge" /></div>
              <div><label>名称</label><input v-model="eventItemForm.name" placeholder="商品名称" /></div>
            </div>
            <label>描述</label><input v-model="eventItemForm.description" placeholder="商品说明" />
            <div class="modal-row">
              <div><label>价格 (弥娅币)</label><input v-model.number="eventItemForm.cost" type="number" min="0" /></div>
              <div><label>限购</label><input v-model.number="eventItemForm.limit" type="number" min="1" /></div>
              <div><label>类型</label><select v-model="eventItemForm.kind"><option value="collectible">纪念物</option><option value="title">称号</option><option value="story">剧情</option><option value="badge">徽章</option></select></div>
              <div><label>需发现数</label><input v-model.number="eventItemForm.requires_discoveries" type="number" min="0" /></div>
            </div>
            <button class="btn-primary" :disabled="worldBusy" @click="addEventShopItem">添加商品</button>
            <div v-if="eventAreaShopItems.length" class="world-event-list">
              <div v-for="item in eventAreaShopItems" :key="item.key" class="world-event-row">
                <span>{{ item.name }}</span>
                <small>◆{{ item.cost }} · {{ item.kind }}</small>
                <button class="btn-sm btn-danger" :disabled="worldBusy" @click="removeEventShopItem(eventItemTarget, item.key)">删除</button>
              </div>
            </div>
            <p v-else class="data-hint">该活动当前没有自定义商品（内置活动的商品为内置定义）。</p>
          </template>
          <!-- 新建 / 编辑自定义活动表单 -->
          <label>{{ editingEventArea ? `编辑自定义活动「${editingEventArea.name}」` : '新建自定义活动' }}</label>
          <div class="modal-row">
            <div><label>key</label><input v-model="eventAreaForm.key" placeholder="如 summer_2026" :disabled="!!editingEventArea" /></div>
            <div><label>名称</label><input v-model="eventAreaForm.name" placeholder="活动名称" /></div>
          </div>
          <div class="modal-row">
            <div><label>副标题</label><input v-model="eventAreaForm.subtitle" /></div>
            <div><label>图标</label><input v-model="eventAreaForm.icon" /></div>
            <div><label>主题色</label><input v-model="eventAreaForm.color" type="color" /></div>
          </div>
          <label>描述</label><textarea v-model="eventAreaForm.description" />
          <div class="modal-row">
            <div><label>开始日期</label><input v-model="eventAreaForm.start" type="date" /></div>
            <div><label>结束日期</label><input v-model="eventAreaForm.end" type="date" /></div>
            <div><label>弥娅币</label><input v-model.number="eventAreaForm.reward_currency" type="number" min="0" /></div>
            <div><label>经验</label><input v-model.number="eventAreaForm.reward_exp" type="number" min="0" /></div>
          </div>
          <label class="checkbox-row"><input v-model="eventAreaForm.active" type="checkbox" />上架中</label>
          <div class="event-area-form-actions">
            <button class="btn-primary" :disabled="worldBusy" @click="submitEventArea">{{ editingEventArea ? '保存活动' : '创建活动' }}</button>
            <button v-if="editingEventArea" class="btn-ghost" :disabled="worldBusy" @click="resetEventAreaForm">取消编辑</button>
          </div>
        </div>

        <!-- 弥娅商城 · 货架管理 -->
        <div class="world-admin-card">
          <h4>弥娅商城 · 货架管理 <small>内置商品不可修改；自定义商品可编辑 / 上下架 / 删除</small></h4>
          <div v-if="miyaShopItems.length" class="event-area-list">
            <div v-for="item in miyaShopItems" :key="item.key" class="event-area-row">
              <span class="event-area-icon" :style="{ color: '#c9ac67' }">◆</span>
              <div class="event-area-info">
                <strong>
                  {{ item.name }}
                  <small v-if="item.builtin" class="event-area-tag builtin">内置</small>
                  <small v-else class="event-area-tag" :class="item.active ? 'running' : 'builtin'">{{ item.active ? '上架' : '已下架' }}</small>
                </strong>
                <small>◆{{ item.cost }} · 限购 {{ item.limit }} · {{ MIYA_SHOP_KIND_LABELS[item.kind] || item.kind }}</small>
              </div>
              <div class="event-area-actions">
                <button v-if="item.is_custom" class="btn-sm" :disabled="miyaShopBusy" @click="editMiyaShopItem(item)">{{ editingMiyaShopItem?.key === item.key ? '编辑中' : '编辑' }}</button>
                <button v-if="item.is_custom" class="btn-sm" :disabled="miyaShopBusy" @click="toggleMiyaShopItemActive(item)">{{ item.active ? '下架' : '上架' }}</button>
                <button v-if="item.is_custom" class="btn-sm btn-danger" :disabled="miyaShopBusy" @click="removeMiyaShopItem(item)">删除</button>
              </div>
            </div>
          </div>
          <p v-else class="data-hint">货架还没有任何商品。</p>
          <!-- 上架新商品 / 编辑自定义商品 (复用同一表单，编辑时 key 只读) -->
          <label>{{ editingMiyaShopItem ? `编辑自定义商品「${editingMiyaShopItem.name}」` : '上架新商品' }}</label>
          <div class="modal-row">
            <div><label>key</label><input v-model="miyaShopForm.key" placeholder="如 miya_morning_call" :disabled="!!editingMiyaShopItem" /></div>
            <div><label>名称</label><input v-model="miyaShopForm.name" placeholder="商品名称" /></div>
          </div>
          <label>描述</label><input v-model="miyaShopForm.description" placeholder="货架上的商品说明" />
          <div class="modal-row">
            <div><label>价格 (弥娅币)</label><input v-model.number="miyaShopForm.cost" type="number" min="0" /></div>
            <div><label>限购</label><input v-model.number="miyaShopForm.limit" type="number" min="1" /></div>
            <div>
              <label>类型</label>
              <select v-model="miyaShopForm.kind">
                <option v-for="(label, key) in MIYA_SHOP_KIND_LABELS" :key="key" :value="key">{{ label }}</option>
              </select>
            </div>
          </div>
          <!-- 按类型显示专属字段 -->
          <template v-if="miyaShopForm.kind === 'interaction'">
            <label>亲昵互动文案 <small>兑换后弥娅会对佳说的话</small></label>
            <textarea v-model="miyaShopForm.interaction" placeholder="今天辛苦了。靠近一点，让我把声音放轻…" />
          </template>
          <template v-else-if="miyaShopForm.kind === 'story'">
            <label>剧情标题</label>
            <input v-model="miyaShopForm.story_title" placeholder="短篇剧情标题" />
            <label>剧情内容</label>
            <textarea v-model="miyaShopForm.story_content" placeholder="一段可以在现实里慢慢完成的剧情…" />
          </template>
          <template v-else-if="miyaShopForm.kind === 'title'">
            <label>专属称号 <small>兑换后解锁并写入玩家档案</small></label>
            <input v-model="miyaShopForm.title_award" placeholder="如 弥娅的心上人" />
          </template>
          <template v-else-if="miyaShopForm.kind === 'boost'">
            <div class="world-admin-status">现实辅助固定生效：下一次区域委托获得额外共鸣奖励 (commission_resonance)，无需额外填写内容。</div>
          </template>
          <div class="event-area-form-actions">
            <button class="btn-primary" :disabled="miyaShopBusy" @click="submitMiyaShopItem">{{ editingMiyaShopItem ? '保存商品' : '上架商品' }}</button>
            <button v-if="editingMiyaShopItem" class="btn-ghost" :disabled="miyaShopBusy" @click="resetMiyaShopForm">取消编辑</button>
          </div>
        </div>

        <!-- 纪念日 (v17) -->
        <div class="world-admin-card">
          <h4>纪念日 <small>重要的日子交给弥娅，到了会提前提醒并送上寄语</small></h4>
          <div v-if="commemorations.length" class="event-area-list">
            <div v-for="c in commemorations" :key="c.key" class="event-area-row">
              <span class="event-area-icon" :style="{ color: '#c9ac67' }">{{ c.icon || '✦' }}</span>
              <div class="event-area-info">
                <strong>
                  {{ c.name }}
                  <small class="event-area-tag" :class="{ running: c.enabled && c.phase === 'today', builtin: !c.enabled }">{{ commemorationPhaseLabel(c) }}</small>
                </strong>
                <small>
                  {{ c.date }}<template v-if="c.next_date"> · 下次 {{ c.next_date }}</template> · 提前 {{ c.lead_days }} 天提醒<template v-if="c.description"> · {{ c.description }}</template>
                </small>
              </div>
              <div class="event-area-actions">
                <button class="btn-sm btn-danger" :disabled="commemorationBusy" @click="removeCommemoration(c)">删除</button>
              </div>
            </div>
          </div>
          <p v-else class="data-hint">还没有纪念日，把重要的日子交给弥娅记着吧。</p>
          <label>新增纪念日 <small>日期格式 MM-DD，每年重复</small></label>
          <div class="modal-row">
            <div><label>key</label><input v-model="commemorationForm.key" placeholder="如 anniversary_0520" /></div>
            <div><label>名称</label><input v-model="commemorationForm.name" placeholder="如 佳的生日" /></div>
            <div><label>日期 (MM-DD)</label><input v-model="commemorationForm.date" placeholder="05-20" maxlength="5" /></div>
          </div>
          <div class="modal-row">
            <div><label>图标</label><input v-model="commemorationForm.icon" placeholder="✦" /></div>
            <div><label>提前提醒 (天)</label><input v-model.number="commemorationForm.lead_days" type="number" min="0" max="30" /></div>
          </div>
          <label>描述 (可选)</label>
          <input v-model="commemorationForm.description" placeholder="这一天对你们意味着什么" />
          <div class="event-area-form-actions">
            <button class="btn-primary" :disabled="commemorationBusy" @click="addCommemorationRow">添加纪念日</button>
          </div>
        </div>
      </section>

      <!-- 成就 (v17) -->
      <section v-else-if="activeTab === 'achievements'" class="earth-panel">
        <div class="panel-head">
          <h3>成就管理 <small>({{ achievements.length }} 项 · 已解锁 {{ achievements.filter(a => a.unlocked_at).length }})</small></h3>
          <div class="head-actions">
            <button class="btn-ghost" :disabled="achBusy" @click="refreshAchievementList">↻ 刷新成就</button>
            <button class="btn-primary" @click="openNewAchievement">+ 新建自定义成就</button>
          </div>
        </div>
        <div v-if="achievements.length === 0" class="empty">还没有成就，点右上角新建一个吧～</div>
        <div v-else class="ach-admin-list">
          <div v-for="a in achievements" :key="a.id" class="ach-admin-row" :class="{ unlocked: !!a.unlocked_at }">
            <span class="ach-admin-icon">{{ a.icon || '✦' }}</span>
            <div class="ach-admin-info">
              <strong>
                {{ a.title }}
                <small v-if="a.hidden" class="ach-admin-tag hidden">隐藏</small>
                <small v-if="a.unlocked_at" class="ach-admin-tag unlocked">已解锁 {{ formatDate(a.unlocked_at) }}</small>
              </strong>
              <small>{{ a.description }}</small>
              <div class="ach-admin-bar"><div class="ach-admin-fill" :style="{ width: `${Math.min(100, Math.round((a.progress / Math.max(1, a.target)) * 100))}%` }" /></div>
            </div>
            <div class="ach-admin-meta">
              <span class="ach-admin-progress">{{ a.progress }}/{{ a.target }}</span>
              <span class="ach-admin-rewards">◆{{ a.reward_currency ?? 0 }} · EXP{{ a.reward_exp ?? 0 }}<template v-if="a.title_award"> · 称号「{{ a.title_award }}」</template></span>
              <button class="btn-sm btn-primary" :disabled="achBusy" @click="setAchievementProgress(a)">设置进度</button>
            </div>
          </div>
        </div>
      </section>

      <!-- 数据 JSON -->
      <section v-else class="earth-panel">
        <div class="panel-head">
          <h3>数据 JSON <small>记事本模式</small></h3>
          <div class="head-actions">
            <button class="btn-ghost" @click="loadJsonText">从服务器读取</button>
            <button class="btn-ghost" @click="formatJson">格式化</button>
            <button class="btn-ghost" @click="downloadJson">下载文件</button>
            <button class="btn-primary" @click="saveJsonText">保存到服务器</button>
          </div>
        </div>
        <p class="data-hint">镜像文件: data/earthonline/earthonline.json — 你可以直接编辑 JSON 后点「保存到服务器」（自动备份数据库），也可以在外面打开这个文件手写参数。</p>
        <textarea v-model="jsonText" class="json-editor" spellcheck="false" placeholder="点击「从服务器读取」加载数据…" />

        <div class="panel-head" style="margin-top: 1rem;">
          <h3>模板库 <small>templates.json</small></h3>
          <div class="head-actions">
            <button class="btn-ghost" @click="loadTemplatesText">读取模板</button>
            <button class="btn-primary" @click="saveTemplatesText">保存模板</button>
          </div>
        </div>
        <p class="data-hint">自定义物品/角色/任务模板：新增物品时按分类显示预设字段，角色按关系显示预设字段，任务可选用预设模板。</p>
        <textarea v-model="templatesText" class="json-editor json-editor-sm" spellcheck="false" placeholder="点击「读取模板」加载…" />
      </section>
    </main>

    <!-- 弹窗：开拓者角色卡 -->
    <div v-if="showPlayerModal" class="modal-mask" @click.self="showPlayerModal = false">
      <div class="modal">
        <h3>玩家卡</h3>
        <label>姓名</label>
        <input v-model="playerForm.name" placeholder="你的名字" />
        <label>称号</label>
        <input v-model="playerForm.title" placeholder="如 地球online 玩家" />
        <label>简介 (支持 Markdown)</label>
        <textarea v-model="playerForm.bio" placeholder="用 Markdown 写一段自我介绍…" />
        <label>头像</label>
        <div class="modal-upload">
          <img v-if="playerForm.avatar_path" :src="EarthAPI.imageUrl(playerForm.avatar_path)" class="modal-preview" />
          <label class="btn-ghost upload-btn">选择照片<input type="file" accept="image/*" hidden @change="onPickPlayerAvatar" /></label>
        </div>
        <label>现实资产 / 地球币 (元) <small class="label-hint">佳自己记录的现实货币，完成任务后自行更新</small></label>
        <input v-model.number="playerForm.earth_currency" type="number" min="0" step="0.01" />
        <label>自定义属性</label>
        <div class="attr-editor">
          <div v-for="(attr, i) in playerForm.attrs" :key="i" class="attr-editor-row">
            <input v-model="attr.label" placeholder="属性名" class="attr-editor-label" />
            <input v-model="attr.key" placeholder="key" class="attr-editor-key" />
            <input v-model.number="attr.value" type="number" placeholder="值" class="attr-editor-num" />
            <span class="attr-slash">/</span>
            <input v-model.number="attr.max" type="number" placeholder="上限" class="attr-editor-num" />
            <button class="btn-sm btn-danger" @click="removeAttr(i)">×</button>
          </div>
          <button class="btn-sm" @click="addAttr">+ 添加属性</button>
        </div>
        <div class="modal-actions">
          <button class="btn-ghost" @click="showPlayerModal = false">取消</button>
          <button class="btn-primary" @click="savePlayer">保存</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：物品 -->
    <div v-if="showItemModal" class="modal-mask" @click.self="showItemModal = false">
      <div class="modal">
        <h3>{{ editingItem ? '编辑物品' : '新增物品' }}</h3>
        <label>名称</label>
        <input v-model="itemForm.name" placeholder="物品名称" />
        <label>分类 (决定模板字段)</label>
        <select v-model="itemForm.category">
          <option v-for="(label, key) in CATEGORY_LABELS" :key="key" :value="key">{{ label }}</option>
        </select>
        <label>稀有度</label>
        <select v-model="itemForm.rarity">
          <option v-for="(label, key) in RARITY_LABELS" :key="key" :value="key">{{ label }}</option>
        </select>
        <label>数量</label>
        <input v-model.number="itemForm.quantity" type="number" min="1" />
        <label>描述</label>
        <textarea v-model="itemForm.description" placeholder="这件物品对你的意义…" />
        <label>图片</label>
        <div class="modal-upload">
          <img v-if="itemForm.image_path" :src="EarthAPI.imageUrl(itemForm.image_path)" class="modal-preview" />
          <label class="btn-ghost upload-btn">选择照片<input type="file" accept="image/*" hidden @change="onPickImage" /></label>
        </div>
        <label>详细档案 (Markdown)</label>
        <textarea v-model="itemForm.markdown" class="md-editor" placeholder="# 档案标题&#10;&#10;- 参数一&#10;- 参数二&#10;&#10;> 一句话说明" />
        <template v-if="itemForm.markdown">
          <label>档案预览</label>
          <div class="md-preview"><Markdown :source="itemForm.markdown" /></div>
        </template>
        <label v-if="itemTemplateFields.length">{{ templates?.items[itemForm.category]?.label }}模板参数</label>
        <FieldsEditor v-model="itemForm.fields" :template-fields="itemTemplateFields" />
        <div class="modal-actions">
          <button class="btn-ghost" @click="showItemModal = false">取消</button>
          <button class="btn-primary" @click="saveItem">保存</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：任务 -->
    <div v-if="showQuestModal" class="modal-mask" @click.self="showQuestModal = false">
      <div class="modal">
        <h3>{{ editingQuest ? '编辑任务' : '新任务' }}</h3>
        <label>标题</label>
        <input v-model="questForm.title" placeholder="任务标题" />
        <label>描述</label>
        <textarea v-model="questForm.description" placeholder="任务详情…" />
        <label>任务模板</label>
        <select v-model="questTemplateId" @change="applyQuestTemplate">
          <option value="custom">自定义</option>
          <option v-for="tpl in (templates?.quests || [])" :key="tpl.id" :value="tpl.id">{{ tpl.label }}</option>
        </select>
        <label>类型</label>
        <select v-model="questForm.quest_type">
          <option value="main">主线</option>
          <option value="branch">支线</option>
          <option value="daily">日常</option>
          <option value="optional">可选</option>
        </select>
        <label>难度星级</label>
        <select v-model.number="questForm.difficulty">
          <option :value="1">★ 简单</option>
          <option :value="2">★★ 普通</option>
          <option :value="3">★★★ 困难</option>
          <option :value="4">★★★★ 挑战</option>
          <option :value="5">★★★★★ 地狱</option>
        </select>
        <label>循环类型 <small class="label-hint">(完成后自动重置，适合喝水/睡觉等日常习惯)</small></label>
        <select v-model="questForm.recurring">
          <option v-for="(label, key) in RECURRING_LABELS" :key="key" :value="key">{{ label }}</option>
        </select>
        <label class="checkbox-row"><input v-model="questForm.must_complete" type="checkbox" />必须任务（失败会惩罚）</label>
        <div class="modal-row">
          <div><label>奖励(币)</label><input v-model.number="questForm.reward_currency" type="number" min="0" /></div>
          <div><label>奖励(经验)</label><input v-model.number="questForm.reward_exp" type="number" min="0" /></div>
          <div><label>鸽惩罚(币)</label><input v-model.number="questForm.penalty_currency" type="number" min="0" /></div>
        </div>
        <label>截止时间</label>
        <input v-model="questForm.deadline" type="datetime-local" />
        <label>子任务清单 <small class="label-hint">(全部勾选完成后任务才能提交)</small></label>
        <div class="subtask-editor">
          <div v-for="(sub, i) in questForm.subtasks" :key="i" class="subtask-row">
            <input type="checkbox" v-model="sub.done" class="subtask-check" />
            <input v-model="sub.text" placeholder="子任务描述，如：写第一章草稿" class="subtask-input" />
            <button class="btn-sm btn-danger" @click="removeSubtask(i)">×</button>
          </div>
          <button class="btn-sm" @click="addSubtask">+ 添加子任务</button>
        </div>
        <label v-if="questTemplateFields.length">模板参数</label>
        <FieldsEditor v-model="questForm.fields" :template-fields="questTemplateFields" />
        <div class="modal-actions">
          <button class="btn-ghost" @click="showQuestModal = false">取消</button>
          <button class="btn-primary" @click="saveQuest">{{ editingQuest ? '保存' : '发布' }}</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：角色 -->
    <div v-if="showCharacterModal" class="modal-mask" @click.self="showCharacterModal = false">
      <div class="modal">
        <h3>{{ editingCharacter ? '编辑角色' : '新增角色' }}</h3>
        <label>姓名</label>
        <input v-model="characterForm.name" placeholder="现实中的人物" />
        <label>昵称</label>
        <input v-model="characterForm.nickname" placeholder="昵称/称呼" />
        <label>关系 (决定模板字段)</label>
        <select v-model="characterForm.relationship">
          <option v-for="(label, key) in RELATIONSHIP_LABELS" :key="key" :value="key">{{ label }}</option>
        </select>
        <label>初始好感度 (0-100)</label>
        <input v-model.number="characterForm.affinity" type="number" min="0" max="100" />
        <label>备注</label>
        <textarea v-model="characterForm.notes" placeholder="关于这位的备注…" />
        <label>生日</label>
        <input v-model="characterForm.birthday" type="date" />
        <label>头像照片</label>
        <div class="modal-upload">
          <img v-if="characterForm.avatar_path" :src="EarthAPI.imageUrl(characterForm.avatar_path)" class="modal-preview" />
          <label class="btn-ghost upload-btn">选择照片<input type="file" accept="image/*" hidden @change="onPickAvatar" /></label>
        </div>
        <label>详细档案 (Markdown)</label>
        <textarea v-model="characterForm.markdown" class="md-editor" placeholder="# 关于 TA&#10;&#10;- 性格特点&#10;- 重要的事&#10;&#10;> 一段话记录" />
        <template v-if="characterForm.markdown">
          <label>档案预览</label>
          <div class="md-preview"><Markdown :source="characterForm.markdown" /></div>
        </template>
        <label v-if="characterTemplateFields.length">{{ templates?.characters[characterForm.relationship]?.label }}模板参数</label>
        <FieldsEditor v-model="characterForm.fields" :template-fields="characterTemplateFields" />
        <div class="modal-actions">
          <button class="btn-ghost" @click="showCharacterModal = false">取消</button>
          <button class="btn-primary" @click="saveCharacter">保存</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：好感度 -->
    <div v-if="showAffinityModal && affinityTarget" class="modal-mask" @click.self="showAffinityModal = false">
      <div class="modal modal-sm">
        <h3>「{{ affinityTarget.name }}」好感度 <span :style="{ color: affinityLevel(affinityTarget.affinity).color }">({{ affinityLevel(affinityTarget.affinity).label }})</span></h3>
        <label>变动值 (负数为降低)</label>
        <input v-model.number="affinityForm.delta" type="number" />
        <label>原因</label>
        <input v-model="affinityForm.reason" placeholder="比如：一起吃了顿饭" />
        <div class="modal-actions">
          <button class="btn-ghost" @click="showAffinityModal = false">取消</button>
          <button class="btn-primary" @click="saveAffinity">确认</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：剧情 -->
    <div v-if="showStoryModal" class="modal-mask" @click.self="showStoryModal = false">
      <div class="modal">
        <h3>{{ editingStory ? '编辑剧情' : '记录剧情' }}</h3>
        <label>标题</label>
        <input v-model="storyForm.title" placeholder="事件的标题" />
        <label>内容</label>
        <textarea v-model="storyForm.content" placeholder="这一天发生了什么…" />
        <label>类型</label>
        <select v-model="storyForm.event_type">
          <option v-for="(label, key) in EVENT_TYPE_LABELS" :key="key" :value="key">{{ label }}</option>
        </select>
        <label>关联角色</label>
        <select v-model="storyForm.character_id">
          <option value="">无</option>
          <option v-for="c in characters" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
        <label>发生时间</label>
        <input v-model="storyForm.happened_at" type="datetime-local" />
        <label>剧情图片</label>
        <div class="modal-upload">
          <img v-if="storyForm.image_path" :src="EarthAPI.imageUrl(storyForm.image_path)" class="modal-preview" />
          <label class="btn-ghost upload-btn">选择照片<input type="file" accept="image/*" hidden @change="onPickStoryImage" /></label>
        </div>
        <label>自定义参数</label>
        <FieldsEditor v-model="storyForm.fields" :template-fields="[]" />
        <div class="modal-actions">
          <button class="btn-ghost" @click="showStoryModal = false">取消</button>
          <button class="btn-primary" @click="saveStory">{{ editingStory ? '保存' : '记录' }}</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：新建自定义成就 (v17) -->
    <div v-if="showAchievementModal" class="modal-mask" @click.self="showAchievementModal = false">
      <div class="modal modal-sm">
        <h3>新建自定义成就</h3>
        <label>key</label>
        <input v-model="achievementForm.key" placeholder="如 first_memory_pull" />
        <label>标题</label>
        <input v-model="achievementForm.title" placeholder="成就标题" />
        <label>描述</label>
        <input v-model="achievementForm.description" placeholder="达成条件说明" />
        <div class="modal-row">
          <div><label>图标</label><input v-model="achievementForm.icon" placeholder="✦" /></div>
          <div><label>目标值</label><input v-model.number="achievementForm.target" type="number" min="1" /></div>
        </div>
        <div class="modal-row">
          <div><label>奖励弥娅币</label><input v-model.number="achievementForm.reward_currency" type="number" min="0" /></div>
          <div><label>奖励经验</label><input v-model.number="achievementForm.reward_exp" type="number" min="0" /></div>
        </div>
        <label>奖励称号 (可选)</label>
        <input v-model="achievementForm.title_award" placeholder="如 回忆收藏家" />
        <div class="modal-actions">
          <button class="btn-ghost" :disabled="achBusy" @click="showAchievementModal = false">取消</button>
          <button class="btn-primary" :disabled="achBusy" @click="submitAchievement">创建</button>
        </div>
      </div>
    </div>

    <!-- 弹窗：地球币记账 (v17) -->
    <div v-if="showAdminLedgerModal" class="modal-mask" @click.self="showAdminLedgerModal = false">
      <div class="modal modal-sm">
        <h3>地球币记账</h3>
        <label>金额 (元, 正数收入 / 负数支出)</label>
        <input v-model.number="adminLedgerForm.amount" type="number" step="0.01" placeholder="如 100 或 -35.5" />
        <label>备注</label>
        <input v-model="adminLedgerForm.reason" placeholder="比如：发工资 / 买菜" maxlength="40" />
        <div class="modal-actions">
          <button class="btn-ghost" :disabled="adminLedgerBusy" @click="showAdminLedgerModal = false">取消</button>
          <button class="btn-primary" :disabled="adminLedgerBusy" @click="submitAdminLedger">记一笔</button>
        </div>
      </div>
    </div>

    <Transition name="toast">
      <div v-if="toast" class="earth-toast">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.earth-online {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  height: 100%;
  min-height: 0;
  color: var(--miya-text);
}

/* 玩家卡 (鎏金风格, 与前台统一) */
.player-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.2rem;
  padding: 0.85rem 1rem;
  background: linear-gradient(110deg, rgba(201, 172, 103, 0.13), rgba(23, 32, 42, 0.86));
  border: 1px solid rgba(201, 172, 103, 0.26);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}
.player-left { display: flex; align-items: center; gap: 1rem; min-width: 220px; }
.player-avatar {
  width: 54px; height: 54px; border-radius: 12px;
  display: grid; place-items: center; overflow: hidden;
  font-size: 1.6rem; font-weight: 700;
  background: linear-gradient(135deg, #e8d5a3, #c9ac67);
  box-shadow: 0 0 18px rgba(201, 172, 103, 0.4);
}
.player-avatar-img { width: 100%; height: 100%; object-fit: cover; }
.player-info { min-width: 200px; }
.player-title { display: flex; align-items: baseline; gap: 0.6rem; }
.player-name { font-size: 1.1rem; font-weight: 700; }
.player-subtitle { font-size: 0.7rem; color: var(--miya-text-dim); }
.player-level { color: #c9ac67; font-size: 0.85rem; font-weight: 700; }
.exp-bar { height: 8px; margin-top: 0.4rem; border-radius: 4px; background: rgba(255, 255, 255, 0.12); overflow: hidden; }
.exp-fill { height: 100%; border-radius: 4px; background: linear-gradient(90deg, #c9ac67, #e8d5a3); transition: width 0.5s ease; }
.exp-label { font-size: 0.68rem; color: var(--miya-text-dim); margin-top: 0.25rem; }
.player-right { flex: 1; display: grid; grid-template-columns: minmax(160px, 1fr) auto minmax(165px, auto) auto; align-items: center; gap: 1rem; }
.player-attrs { display: flex; flex-direction: column; gap: 3px; min-width: 150px; }
.attr-row { display: flex; align-items: center; gap: 0.4rem; font-size: 0.62rem; }
.attr-label { color: var(--miya-text-dim); width: 44px; text-align: right; flex-shrink: 0; }
.attr-bar { flex: 1; height: 5px; border-radius: 3px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
.attr-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, #ffb300, #ff6b6b); }
.attr-value { color: #ffd54f; width: 20px; }
.player-stats { display: flex; gap: 1.2rem; }
.stat-item { display: flex; flex-direction: column; align-items: center; }
.stat-icon { font-size: 1.1rem; }
.stat-value { font-size: 1.15rem; font-weight: 700; }
.stat-label { font-size: 0.62rem; color: var(--miya-text-dim); }
.btn-edit-card { white-space: nowrap; }
/* 玩家卡快捷操作 (+经验 / +弥娅币 / 地球币记账) */
.player-quick-actions { display: flex; gap: 0.35rem; flex-wrap: wrap; justify-content: flex-end; }

/* 成就管理 (v17) */
.ach-admin-list { display: flex; flex-direction: column; gap: 0.5rem; }
.ach-admin-row {
  display: flex; align-items: center; gap: 0.7rem;
  padding: 0.6rem 0.7rem;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid color-mix(in srgb, var(--miya-border) 12%, transparent);
  border-radius: 10px;
}
.ach-admin-row.unlocked { border-color: rgba(201, 172, 103, 0.45); background: rgba(201, 172, 103, 0.07); }
.ach-admin-icon { font-size: 1.35rem; flex-shrink: 0; }
.ach-admin-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.ach-admin-info strong { font-size: 0.85rem; color: var(--miya-text); }
.ach-admin-info > small { font-size: 0.66rem; color: var(--miya-text-dim); }
.ach-admin-tag { margin-left: 6px; padding: 0 6px; border-radius: 8px; font-size: 0.56rem; }
.ach-admin-tag.unlocked { color: #c9ac67; border: 1px solid rgba(201, 172, 103, 0.4); }
.ach-admin-tag.hidden { color: #9e9e9e; border: 1px solid rgba(158, 158, 158, 0.4); }
.ach-admin-bar { height: 5px; border-radius: 3px; background: rgba(255, 255, 255, 0.09); overflow: hidden; margin-top: 3px; }
.ach-admin-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, #c9ac67, #e8d5a3); transition: width 0.4s; }
.ach-admin-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; flex-shrink: 0; }
.ach-admin-progress { font-size: 0.78rem; font-weight: 700; color: #ffd54f; }
.ach-admin-rewards { font-size: 0.6rem; color: var(--miya-text-dim); }

/* Tab */
.earth-tabs { display: flex; flex-wrap: wrap; gap: .75rem; align-items: stretch; }
.earth-tab-group {
  display: flex;
  align-items: stretch;
  gap: .35rem;
  padding: .25rem .35rem .25rem .55rem;
  border-left: 1px solid color-mix(in srgb, var(--miya-border) 18%, transparent);
  background: rgba(5, 13, 21, .28);
}
.earth-tab-group-label {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 3.6rem;
  color: var(--miya-text-faint);
  line-height: 1.1;
}
.earth-tab-group-label b { font-size: .58rem; font-weight: 600; letter-spacing: .08em; }
.earth-tab-group-label small { margin-top: .18rem; color: color-mix(in srgb, var(--earth-accent-light, var(--miya-accent-bright)) 58%, transparent); font: .42rem/1 'JetBrains Mono', monospace; letter-spacing: .1em; }
.earth-tab-group-items { display: flex; gap: .25rem; }
.earth-tab {
  padding: 0.48rem .85rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid color-mix(in srgb, var(--miya-border) 12%, transparent);
  border-radius: 0;
  color: var(--miya-text-dim);
  cursor: pointer;
  transition: all 0.3s;
}
.earth-tab:hover { color: var(--miya-text); }
.earth-tab.active {
  color: var(--earth-accent-light, var(--miya-accent-bright));
  font-weight: 700;
  background: color-mix(in srgb, var(--earth-accent, var(--miya-accent-soft)) 12%, transparent);
  border-color: color-mix(in srgb, var(--earth-accent-light, var(--miya-accent-bright)) 52%, transparent);
}

/* Body */
.earth-body { flex: 1; min-height: 0; overflow-y: auto; }
.earth-panel { display: flex; flex-direction: column; gap: 0.8rem; }
.loading { padding: 2rem; text-align: center; color: var(--miya-text-dim); }
.load-error {
  display: grid;
  justify-items: center;
  gap: 0.55rem;
  padding: 2.4rem 1.2rem;
  text-align: center;
  color: var(--miya-text-dim);
}
.load-error strong { color: #f0e6cf; font-size: 0.95rem; }
.load-error span { max-width: 560px; font-size: 0.74rem; line-height: 1.5; color: #e6bd78; }
.empty { padding: 2.5rem; text-align: center; color: var(--miya-text-dim); }
.panel-head { display: flex; justify-content: space-between; align-items: center; }
.panel-head h3 { margin: 0; font-size: 1rem; }
.panel-head h3 small { color: var(--miya-text-dim); font-weight: 400; }
.head-actions { display: flex; gap: 0.5rem; }
.world-admin-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.8rem; }
.world-admin-card { display: flex; flex-direction: column; gap: 0.45rem; padding: 0.9rem; background: rgba(0, 0, 0, 0.25); border: 1px solid rgba(201, 172, 103, 0.22); border-radius: 10px; }
.world-admin-card h4 { margin: 0 0 0.2rem; color: #e8d5a3; font-size: 0.86rem; }
.world-admin-card label { color: var(--miya-text-dim); font-size: 0.68rem; }
.world-admin-card input, .world-admin-card select, .world-admin-card textarea { background: rgba(255,255,255,0.06); border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent); border-radius: 6px; color: var(--miya-text); padding: 0.42rem 0.55rem; font-size: 0.78rem; }
.world-admin-card textarea { min-height: 70px; resize: vertical; }
.world-admin-status { padding: 0.55rem; color: #c9e9c0; background: rgba(129, 199, 132, 0.08); border: 1px solid rgba(129, 199, 132, 0.2); font-size: 0.68rem; }
.world-admin-region-list, .world-event-list { display: flex; flex-direction: column; gap: 0.45rem; }
.world-admin-region, .world-event-row { display: flex; align-items: center; gap: 0.55rem; padding: 0.5rem; background: rgba(255,255,255,0.04); border-radius: 6px; font-size: 0.72rem; }
.world-admin-region-name, .world-event-row span { flex: 1; }
.world-admin-region-photo, .world-event-row small { color: var(--miya-text-dim); font-size: 0.64rem; }
/* 限时活动管理 */
.event-area-list { display: flex; flex-direction: column; gap: 0.4rem; }
.event-area-row { display: flex; align-items: center; gap: 0.6rem; padding: 0.5rem; background: rgba(255,255,255,0.04); border-radius: 6px; font-size: 0.72rem; }
.event-area-icon { flex-shrink: 0; font-size: 1rem; }
.event-area-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.event-area-info small { color: var(--miya-text-dim); font-size: 0.62rem; }
.event-area-tag { margin-left: 6px; padding: 0 6px; border-radius: 8px; font-size: 0.56rem; }
.event-area-tag.builtin { color: #9e9e9e; border: 1px solid rgba(158,158,158,0.4); }
.event-area-tag.running { color: #81c784; border: 1px solid rgba(129,199,132,0.4); }
.event-area-actions { display: flex; gap: 0.35rem; flex-wrap: wrap; }
.event-area-form-actions { display: flex; gap: 0.5rem; margin-top: 0.4rem; }
@media (max-width: 800px) { .world-admin-grid { grid-template-columns: 1fr; } }
@media (max-width: 1080px) {
  .player-card { align-items: flex-start; flex-direction: column; }
  .player-right { width: 100%; grid-template-columns: minmax(160px, 1fr) auto; }
  .player-quick-actions { justify-content: flex-start; }
}
@media (max-width: 620px) {
  .player-left { min-width: 0; }
  .player-right { grid-template-columns: 1fr; gap: .7rem; }
  .player-stats { justify-content: flex-start; }
  .btn-edit-card { width: 100%; }
}

/* chips */
.chip-row { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.chip {
  font-size: 0.6rem; padding: 1px 7px; border-radius: 10px;
  background: rgba(201, 172, 103, 0.1); border: 1px solid rgba(201, 172, 103, 0.28);
  color: var(--miya-text-dim);
}

/* 按钮 */
.btn-primary {
  padding: 0.42rem 0.9rem; border: none; border-radius: 6px;
  background: linear-gradient(135deg, #c9ac67, #7c4dff);
  color: #fff; cursor: pointer; font-size: 0.8rem;
  transition: filter 0.2s;
}
.btn-primary:hover { filter: brightness(1.15); }
.btn-ghost {
  padding: 0.42rem 0.9rem; border-radius: 6px; cursor: pointer; font-size: 0.8rem;
  background: rgba(255, 255, 255, 0.06); border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent);
  color: var(--miya-text);
}
.btn-sm {
  padding: 0.28rem 0.6rem; font-size: 0.72rem; border-radius: 5px; cursor: pointer;
  background: rgba(255, 255, 255, 0.07); border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent);
  color: var(--miya-text);
}
.btn-danger { color: #ff6b6b; border-color: rgba(255, 107, 107, 0.3); }
.btn-danger:hover { background: rgba(255, 107, 107, 0.15); }

/* 背包 */
.item-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 0.8rem; }
.item-card {
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid;
  border-radius: 10px; overflow: hidden;
  transition: transform 0.25s, box-shadow 0.25s;
  display: flex; flex-direction: column;
}
.item-card:hover { transform: translateY(-3px); box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45); }
.item-img-wrap { position: relative; height: 120px; overflow: hidden; }
.item-img { width: 100%; height: 100%; object-fit: cover; }
.item-img-ph { display: grid; place-items: center; font-size: 2.2rem; background: rgba(255, 255, 255, 0.05); color: var(--miya-text-dim); }
.item-rarity { position: absolute; top: 6px; left: 6px; padding: 2px 8px; border-radius: 4px; font-size: 0.62rem; color: #fff; }
.item-qty { position: absolute; bottom: 6px; right: 6px; padding: 1px 6px; background: rgba(0, 0, 0, 0.7); border-radius: 4px; font-size: 0.72rem; }
.item-body { padding: 0.5rem 0.6rem; flex: 1; }
.item-name { font-size: 0.85rem; font-weight: 600; }
.item-cat { font-size: 0.62rem; color: var(--miya-text-dim); margin-top: 2px; }
.item-desc { font-size: 0.68rem; color: var(--miya-text-dim); margin: 4px 0 0; line-height: 1.4; }
.item-actions { display: flex; gap: 0.4rem; padding: 0 0.6rem 0.6rem; }

/* 任务 */
.quest-list { display: flex; flex-direction: column; gap: 0.6rem; }
.quest-card {
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid color-mix(in srgb, var(--miya-border) 12%, transparent);
  border-radius: 10px; padding: 0.8rem 1rem;
}
.quest-card.completed { opacity: 0.55; }
.quest-card.failed { border-color: rgba(255, 107, 107, 0.3); }
.quest-head { display: flex; align-items: center; gap: 0.5rem; }
.quest-type { font-size: 0.62rem; color: #c9ac67; border: 1px solid rgba(201, 172, 103, 0.4); padding: 1px 6px; border-radius: 4px; }
.quest-badge { font-size: 0.62rem; padding: 1px 6px; border-radius: 4px; }
.badge-must { background: rgba(255, 179, 0, 0.18); color: #ffb300; border: 1px solid rgba(255, 179, 0, 0.4); }
.badge-opt { background: rgba(201, 172, 103, 0.13); color: #c9ac67; border: 1px solid rgba(201, 172, 103, 0.35); }
.quest-source { font-size: 0.6rem; color: #7c4dff; border: 1px solid rgba(124, 77, 255, 0.35); padding: 1px 6px; border-radius: 4px; }
.quest-status { margin-left: auto; font-size: 0.68rem; color: var(--miya-text-dim); }
.quest-title { font-size: 0.95rem; font-weight: 600; margin-top: 0.4rem; }
.quest-desc { font-size: 0.75rem; color: var(--miya-text-dim); margin: 4px 0 0; }
.quest-meta { display: flex; gap: 0.8rem; margin-top: 0.4rem; font-size: 0.68rem; }
.meta-stars { letter-spacing: 1px; font-size: 0.66rem; }
.meta-reward { color: #ffd54f; }
.meta-penalty { color: #ff6b6b; }
.meta-deadline { color: var(--miya-text-dim); }
.meta-recurring { font-size: 0.62rem; color: #c9ac67; border: 1px solid rgba(201, 172, 103, 0.4); padding: 0 6px; border-radius: 10px; }
.quest-actions { display: flex; gap: 0.4rem; margin-top: 0.6rem; }
.history-block { margin-top: 0.6rem; padding-top: 0.6rem; border-top: 1px dashed color-mix(in srgb, var(--miya-border) 15%, transparent); }
.history-block h4 { margin: 0 0 0.4rem; font-size: 0.8rem; color: var(--miya-text-dim); }
.history-item { display: flex; gap: 0.6rem; align-items: center; font-size: 0.72rem; padding: 2px 0; }
.h-status { font-size: 0.6rem; padding: 1px 6px; border-radius: 4px; background: rgba(255, 255, 255, 0.08); }
.h-status.completed { color: #81c784; }
.h-status.failed { color: #ff6b6b; }
.h-status.cancelled { color: var(--miya-text-dim); }
.h-title { flex: 1; }
.h-time { color: var(--miya-text-dim); }

/* 角色 */
.character-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 0.8rem; }
.character-card {
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid color-mix(in srgb, var(--miya-border) 12%, transparent);
  border-radius: 10px; padding: 0.8rem;
}
.char-top { display: flex; align-items: center; gap: 0.7rem; }
.char-avatar { width: 44px; height: 44px; border-radius: 10px; display: grid; place-items: center; font-size: 1.3rem; color: #fff; overflow: hidden; }
.char-avatar-img { width: 100%; height: 100%; object-fit: cover; }
.char-info { flex: 1; min-width: 0; }
.char-name { font-size: 0.92rem; font-weight: 600; }
.char-nick { font-size: 0.62rem; color: var(--miya-text-dim); margin-left: 4px; }
.char-rel { font-size: 0.66rem; color: #c9ac67; }
.affinity-num { font-size: 1.1rem; font-weight: 700; color: #ffd54f; }
.affinity-bar { height: 7px; border-radius: 4px; background: rgba(255, 255, 255, 0.1); overflow: hidden; margin-top: 0.5rem; }
.affinity-fill { height: 100%; border-radius: 4px; background: linear-gradient(90deg, #ffb300, #ff6b6b); transition: width 0.4s; }
.char-notes { font-size: 0.7rem; color: var(--miya-text-dim); margin: 0.4rem 0 0; }
.char-actions { display: flex; gap: 0.4rem; margin-top: 0.6rem; }

/* 剧情 */
.story-timeline { position: relative; padding-left: 20px; }
.story-timeline::before { content: ''; position: absolute; left: 5px; top: 0; bottom: 0; width: 1px; background: color-mix(in srgb, var(--miya-border) 20%, transparent); }
.story-item { position: relative; margin-bottom: 0.8rem; }
.story-dot { position: absolute; left: -16px; top: 14px; width: 8px; height: 8px; border-radius: 50%; background: #c9ac67; box-shadow: 0 0 8px rgba(201, 172, 103, 0.6); }
.story-card { background: rgba(0, 0, 0, 0.35); border: 1px solid color-mix(in srgb, var(--miya-border) 12%, transparent); border-radius: 10px; padding: 0.7rem 0.9rem; }
.story-head { display: flex; justify-content: space-between; align-items: center; }
.story-type { font-size: 0.6rem; color: #c9ac67; border: 1px solid rgba(201, 172, 103, 0.4); padding: 1px 6px; border-radius: 4px; }
.story-time { font-size: 0.62rem; color: var(--miya-text-dim); }
.story-title { font-size: 0.88rem; font-weight: 600; margin-top: 0.3rem; }
.story-content { font-size: 0.74rem; color: var(--miya-text-dim); margin: 4px 0 0; line-height: 1.5; }
.story-actions { margin-top: 0.4rem; }

/* 数据页 */
.data-hint { font-size: 0.68rem; color: var(--miya-text-dim); margin: 0; line-height: 1.5; }

/* 子任务编辑器 */
.label-hint { font-weight: 400; font-size: 0.62rem; }
.subtask-editor { display: flex; flex-direction: column; gap: 0.4rem; }
.subtask-row { display: flex; align-items: center; gap: 0.45rem; }
.subtask-check { width: 16px; height: 16px; flex-shrink: 0; accent-color: #c9ac67; }
.subtask-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent);
  border-radius: 6px;
  padding: 0.4rem 0.55rem;
  color: var(--miya-text);
  font-size: 0.78rem;
  outline: none;
  min-width: 0;
}
.subtask-chip.done { color: rgba(255, 255, 255, 0.4); text-decoration: line-through; }

/* 弥娅寄语 */
.note-publish {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.7rem 0.8rem;
  background: rgba(201, 172, 103, 0.06);
  border: 1px solid rgba(201, 172, 103, 0.25);
  border-radius: 10px;
}
.note-publish-row { display: flex; }
.note-editor {
  flex: 1;
  min-height: 72px;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent);
  border-radius: 8px;
  padding: 0.6rem 0.7rem;
  color: var(--miya-text);
  font-size: 0.8rem;
  outline: none;
  resize: vertical;
}
.note-publish-foot { display: flex; align-items: center; gap: 0.8rem; }
.note-mood-select {
  background: rgba(255, 255, 255, 0.06); border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent);
  border-radius: 6px; padding: 0.35rem 0.5rem; color: var(--miya-text); font-size: 0.76rem; outline: none;
}
.note-list { display: flex; flex-direction: column; gap: 0.6rem; margin-top: 0.8rem; }
.note-card {
  display: flex;
  gap: 0.7rem;
  padding: 0.7rem 0.8rem;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid color-mix(in srgb, var(--miya-border) 12%, transparent);
  border-radius: 10px;
}
.note-card.pinned { border-color: rgba(201, 172, 103, 0.45); background: rgba(201, 172, 103, 0.07); }
.note-mood { font-size: 1.2rem; flex-shrink: 0; }
.note-body { flex: 1; min-width: 0; }
.note-content { font-size: 0.78rem; color: var(--miya-text); line-height: 1.6; }
.note-content :deep(p) { margin: 0.2rem 0; }
.note-meta { display: flex; gap: 0.6rem; margin-top: 4px; font-size: 0.62rem; color: var(--miya-text-dim); }
.note-pin-tag { color: #c9ac67; }
.note-actions { display: flex; flex-direction: column; gap: 0.35rem; flex-shrink: 0; }

.json-editor {
  width: 100%;
  min-height: 320px;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent);
  border-radius: 8px;
  padding: 0.8rem;
  color: #c9e9c0;
  font-family: 'Cascadia Code', Consolas, monospace;
  font-size: 0.74rem;
  line-height: 1.5;
  outline: none;
  resize: vertical;
}
.json-editor-sm { min-height: 180px; }

/* 属性编辑器 */
.attr-editor { display: flex; flex-direction: column; gap: 0.4rem; }
.attr-editor-row { display: flex; align-items: center; gap: 0.4rem; }
.attr-editor-label { flex: 1.4; }
.attr-editor-key { flex: 1; }
.attr-editor-num { width: 62px; }
.attr-slash { color: var(--miya-text-dim); font-size: 0.7rem; }
.attr-editor-row input {
  background: rgba(255, 255, 255, 0.06); border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent);
  border-radius: 6px; padding: 0.4rem 0.55rem; color: var(--miya-text); font-size: 0.78rem; outline: none;
  min-width: 0;
}

/* 弹窗 */
.modal-mask { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.6); display: grid; place-items: center; z-index: 1000; backdrop-filter: blur(3px); }
.modal { width: 460px; max-width: 94vw; max-height: 88vh; overflow-y: auto; background: #161d26; border: 1px solid color-mix(in srgb, var(--miya-border) 25%, transparent); border-radius: 12px; padding: 1.2rem; display: flex; flex-direction: column; gap: 0.4rem; }
.modal-sm { width: 320px; }
.modal h3 { margin: 0 0 0.4rem; font-size: 1rem; }
.modal label { font-size: 0.7rem; color: var(--miya-text-dim); margin-top: 0.3rem; }
.modal input, .modal select, .modal textarea {
  background: rgba(255, 255, 255, 0.06); border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent);
  border-radius: 6px; padding: 0.45rem 0.6rem; color: var(--miya-text); font-size: 0.8rem; outline: none;
}
.modal textarea { resize: vertical; min-height: 60px; }
.modal-row { display: flex; gap: 0.6rem; }
.modal-row > div { flex: 1; }
.checkbox-row { display: flex; align-items: center; gap: 0.4rem; margin-top: 0.5rem; }
.modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.8rem; }
.modal-upload { display: flex; align-items: center; gap: 0.6rem; }
.modal-preview { width: 64px; height: 64px; object-fit: cover; border-radius: 8px; border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent); }
.upload-btn { display: inline-block; cursor: pointer; }
.md-editor { resize: vertical; min-height: 110px; font-family: 'Cascadia Code', Consolas, monospace; line-height: 1.5; }
.md-preview {
  font-size: 0.74rem; line-height: 1.6;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid color-mix(in srgb, var(--miya-border) 15%, transparent);
  border-radius: 8px; padding: 0.6rem 0.8rem;
  max-height: 220px; overflow-y: auto;
}
.md-preview :deep(p) { margin: 0.3rem 0; }
.md-preview :deep(h1), .md-preview :deep(h2), .md-preview :deep(h3) { margin: 0.4rem 0 0.2rem; font-size: 0.95em; }
.md-preview :deep(ul), .md-preview :deep(ol) { padding-left: 1.3rem; margin: 0.3rem 0; }
.md-preview :deep(code) { background: rgba(255, 255, 255, 0.08); padding: 1px 5px; border-radius: 4px; font-size: 0.85em; }

/* Toast */
.earth-toast {
  position: fixed; bottom: 3rem; left: 50%; transform: translateX(-50%);
  padding: 0.6rem 1.2rem; background: rgba(13, 17, 23, 0.95); border: 1px solid rgba(201, 172, 103, 0.45);
  border-radius: 8px; color: var(--miya-text); font-size: 0.8rem; z-index: 2000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}
.toast-enter-active, .toast-leave-active { transition: all 0.3s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(-50%) translateY(12px); }

/* Miya OS admin skin: quiet surfaces, teal signal colour, consistent controls. */
.earth-online {
  --earth-admin-accent: var(--earth-accent, var(--miya-accent-soft));
  --earth-admin-bright: var(--earth-accent-light, var(--miya-accent-bright));
  --earth-admin-deep: var(--earth-accent-deep, #4f9fa5);
  --earth-admin-surface: rgba(12, 20, 31, 0.82);
  gap: 0.65rem;
}
.earth-online .player-card,
.earth-online .earth-panel,
.earth-online .earth-tabs {
  border-color: var(--miya-line);
}
.earth-online .player-card {
  padding: 0.75rem 0.9rem;
  background: linear-gradient(110deg, color-mix(in srgb, var(--earth-admin-accent) 10%, transparent), rgba(12, 20, 31, 0.9));
  box-shadow: var(--miya-shadow-panel);
}
.earth-online .player-avatar {
  background: linear-gradient(135deg, var(--earth-admin-bright), var(--earth-admin-accent));
  box-shadow: 0 0 18px rgba(120, 207, 209, 0.2);
}
.earth-online .player-level,
.earth-online .stat-icon,
.earth-online .stat-value,
.earth-online .panel-head h3,
.earth-online .player-name { color: var(--miya-text-strong); }
.earth-online .player-level,
.earth-online .world-admin-card h4 { color: var(--earth-admin-accent); }
.earth-online .exp-fill,
.earth-online .ach-admin-fill { background: linear-gradient(90deg, var(--earth-admin-accent), var(--earth-admin-bright)); }
.earth-online .attr-fill { background: linear-gradient(90deg, var(--miya-info), var(--earth-admin-accent)); }
.earth-online .earth-tab,
.earth-online .btn-ghost,
.earth-online .btn-sm {
  border-color: var(--miya-line);
  background: color-mix(in srgb, var(--earth-admin-accent) 4.5%, transparent);
}
.earth-online .earth-tab:hover,
.earth-online .earth-tab.active {
  color: var(--earth-admin-bright);
  border-color: var(--miya-line-strong);
  background: color-mix(in srgb, var(--earth-admin-accent) 10%, transparent);
}
.earth-online .earth-body { padding-right: 0.15rem; }
.earth-online .item-card,
.earth-online .quest-card,
.earth-online .char-card,
.earth-online .story-card,
.earth-online .note-card,
.earth-online .world-admin-card,
.earth-online .ach-admin-row {
  background: var(--earth-admin-surface);
  border-color: var(--miya-line);
  border-radius: var(--miya-radius-sm);
}
.earth-online .item-card:hover,
.earth-online .quest-card:hover,
.earth-online .char-card:hover,
.earth-online .story-card:hover,
.earth-online .note-card:hover {
  border-color: var(--miya-line-strong);
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.24);
}
.earth-online .btn-primary {
  color: #071018;
  background: linear-gradient(135deg, var(--earth-admin-bright), var(--earth-admin-accent));
  box-shadow: 0 8px 20px rgba(120, 207, 209, 0.15);
}
.earth-online .btn-primary:hover { filter: brightness(1.08); }
.earth-online input:focus,
.earth-online select:focus,
.earth-online textarea:focus,
.earth-online .json-editor:focus {
  border-color: var(--miya-accent-soft);
  box-shadow: var(--miya-shadow-focus);
}
.earth-online .chip,
.earth-online .note-publish {
  border-color: color-mix(in srgb, var(--earth-admin-accent) 28%, transparent);
  background: color-mix(in srgb, var(--earth-admin-accent) 7%, transparent);
}
.earth-online .note-card.pinned,
.earth-online .ach-admin-row.unlocked { border-color: color-mix(in srgb, var(--earth-admin-accent) 42%, transparent); background: color-mix(in srgb, var(--earth-admin-accent) 8%, transparent); }
.earth-online .modal { background: var(--miya-bg-elevated); border-color: var(--miya-line-strong); box-shadow: var(--miya-shadow-float); }
.earth-online .earth-toast { border-color: color-mix(in srgb, var(--earth-admin-accent) 45%, transparent); background: rgba(12, 20, 31, 0.96); }
.earth-online .quest-type,
.earth-online .meta-recurring,
.earth-online .char-rel,
.earth-online .story-type,
.earth-online .note-pin-tag {
  color: var(--earth-admin-accent);
  border-color: color-mix(in srgb, var(--earth-admin-accent) 42%, transparent);
}
.earth-online .badge-opt {
  background: color-mix(in srgb, var(--earth-admin-accent) 13%, transparent);
  color: var(--earth-admin-accent);
  border-color: color-mix(in srgb, var(--earth-admin-accent) 35%, transparent);
}
.earth-online .story-dot {
  background: var(--earth-admin-accent);
  box-shadow: 0 0 8px color-mix(in srgb, var(--earth-admin-accent) 60%, transparent);
}
.earth-online .subtask-check { accent-color: var(--earth-admin-accent); }
.earth-online .event-area-icon { color: var(--earth-admin-accent) !important; }
.earth-online .ach-admin-tag.unlocked { color: var(--earth-admin-accent); border-color: color-mix(in srgb, var(--earth-admin-accent) 40%, transparent); }

/* Control room pass: 后台是操作台，不再复刻玩家首页的宣传式卡片。 */
.earth-online {
  position: relative;
  padding: .75rem;
  overflow: hidden;
  background:
    linear-gradient(90deg, rgba(120, 207, 209, .025) 1px, transparent 1px),
    linear-gradient(rgba(120, 207, 209, .02) 1px, transparent 1px),
    rgba(5, 10, 16, .72);
  background-size: 72px 72px;
}
.earth-online::before {
  content: 'MIYA / EARTH ONLINE CONTROL ROOM';
  position: absolute;
  right: 1rem;
  top: .9rem;
  z-index: 1;
  color: var(--miya-text-faint);
  font-size: .48rem;
  letter-spacing: .16em;
  pointer-events: none;
}
.earth-online .player-card {
  position: relative;
  z-index: 2;
  border-radius: 0;
  clip-path: polygon(0 0, calc(100% - 14px) 0, 100% 14px, 100% 100%, 14px 100%, 0 calc(100% - 14px));
}
.earth-online .earth-tabs {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  gap: 3px;
  padding: 3px;
  overflow-x: auto;
  background: rgba(5, 10, 16, .92);
  border: 1px solid var(--miya-line);
  border-radius: 0;
  backdrop-filter: blur(16px);
}
.earth-online .earth-tab {
  flex: 0 0 auto;
  border: 0;
  border-radius: 0;
  padding: .45rem .78rem;
  color: var(--miya-text-muted);
  font-size: .7rem;
}
.earth-online .earth-tab.active { box-shadow: inset 0 -2px var(--earth-admin-bright); }
.earth-online .earth-body { position: relative; z-index: 2; padding: .25rem 0 .75rem; }
.earth-online .panel-head { align-items: flex-end; padding-bottom: .55rem; border-bottom: 1px solid var(--miya-line-soft); }
.earth-online .panel-head h3 { font-size: 1.05rem; letter-spacing: .03em; }
.earth-online .panel-head h3::before { content: '● '; color: var(--earth-admin-bright); font-size: .55em; vertical-align: .18em; }
.earth-online .item-card,
.earth-online .quest-card,
.earth-online .character-card,
.earth-online .story-card,
.earth-online .note-card,
.earth-online .world-admin-card,
.earth-online .ach-admin-row { border-radius: 0; clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%); }
.earth-online .item-card { border-top-color: var(--miya-line-strong); }
.earth-online .item-img-wrap { height: 136px; }
.earth-online .quest-card { border-left: 2px solid var(--miya-line); }
.earth-online .quest-card.ongoing { border-left-color: var(--earth-admin-bright); background: linear-gradient(90deg, rgba(120, 207, 209, .08), var(--earth-admin-surface)); }
.earth-online .quest-card.failed { border-left-color: var(--miya-danger); }
.earth-online .character-card { border-top: 2px solid var(--miya-line); }
.earth-online .story-card { border-left: 2px solid var(--earth-admin-accent); }
.earth-online .note-publish { border-radius: 0; border-left: 2px solid var(--earth-admin-accent); }
.earth-online .btn-primary, .earth-online .btn-ghost, .earth-online .btn-sm { border-radius: 2px; }
@media (max-width: 620px) {
  .earth-online { padding: .45rem; }
  .earth-online::before { display: none; }
  .earth-online .player-card { padding: .65rem; }
  .earth-online .panel-head { align-items: flex-start; flex-direction: column; gap: .5rem; }
  .earth-online .head-actions { width: 100%; flex-wrap: wrap; }
  .earth-online .head-actions > * { flex: 1; }
}

/* 控制室模式: 更高信息密度、更低装饰噪声，与玩家前台形成明确区分。 */
.earth-online {
  position: relative;
  padding: .15rem .2rem .5rem;
  background:
    linear-gradient(90deg, rgba(120, 207, 209, .018) 1px, transparent 1px),
    linear-gradient(rgba(120, 207, 209, .014) 1px, transparent 1px);
  background-size: 72px 72px;
}
.earth-online .player-card {
  padding: .65rem .8rem;
  background: linear-gradient(100deg, rgba(120, 207, 209, .08), rgba(8, 16, 25, .9) 62%);
  border-color: rgba(120, 207, 209, .2);
}
.earth-online .player-avatar { width: 48px; height: 48px; border-radius: 2px; box-shadow: 0 0 18px rgba(120, 207, 209, .18); }
.earth-online .player-name { font-size: 1rem; }
.earth-online .player-level { color: var(--earth-admin-bright); }
.earth-online .stat-value { color: var(--earth-admin-bright); }
.earth-online .earth-tabs { box-shadow: 0 10px 24px rgba(0,0,0,.18); }
.earth-online .earth-tab.active { color: var(--earth-admin-bright); background: rgba(120, 207, 209, .08); }
.earth-online .earth-tab-group { border-left-color: rgba(162, 245, 238, .12); background: rgba(5, 13, 21, .34); }
.earth-online .earth-tab-group-label b { color: var(--miya-text-body); }
.earth-online .earth-tab-group-label small { color: color-mix(in srgb, var(--earth-admin-bright) 58%, transparent); }
.earth-online .earth-tab-group-items { align-items: stretch; }
.earth-online .panel-head h3 { font-weight: 650; }
.earth-online .item-card,
.earth-online .quest-card,
.earth-online .character-card,
.earth-online .story-card,
.earth-online .note-card,
.earth-online .world-admin-card,
.earth-online .ach-admin-row { box-shadow: 0 10px 26px rgba(0,0,0,.16); }
.earth-online .item-card:hover,
.earth-online .quest-card:hover,
.earth-online .character-card:hover,
.earth-online .story-card:hover,
.earth-online .note-card:hover { transform: translateY(-1px); }
@media (max-width: 620px) {
  .earth-online { padding: .35rem .1rem .5rem; }
  .earth-online .earth-tabs { gap: .35rem; padding: 2px; }
  .earth-online .earth-tab-group { flex: 1 1 100%; min-width: max-content; padding-inline: .35rem; }
  .earth-online .earth-tab-group-label { min-width: 3.1rem; }
  .earth-online .earth-tab-group-items { flex: 1; }
  .earth-online .earth-tab { flex: 1; padding-inline: .55rem; }
}
</style>
