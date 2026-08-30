import type { MaybeRef } from 'vue'
import { apiPort, getApiPort } from '@/utils/api-port'
import { ApiClient } from './index'

export interface EarthAttr {
  key: string
  label: string
  value: number
  max: number
}

export interface EarthPlayer {
  level: number
  exp: number
  currency: number
  miya_currency?: number
  earth_currency?: number
  total_completed: number
  total_failed: number
  name?: string
  title?: string
  avatar_path?: string
  bio?: string
  attrs?: EarthAttr[]
  equipped_title?: string
  updated_at?: string
}

export interface EarthLevelUp {
  old_level: number
  new_level: number
  reward_currency: number
}

export interface EarthTitles {
  default: string
  equipped: string
  unlocked: Array<{ key: string, title: string, icon: string, unlocked_at: string }>
}

export interface EarthWeeklyReport {
  week_start: string
  quests: { completed: number, failed: number, completion_rate: number }
  checkins: number
  activities: number
  achievements: number
  affinity_changes: number
  earned: { currency: number, exp: number }
  player: EarthPlayer
}

export interface EarthLifeHub {
  as_of: string
  facts: { player: { name: string, level: number }, checkin: EarthCheckinStatus, quests: { ongoing: number, pending: number, due_soon: number }, attributes: Record<string, { value: number, max: number }>, weekly: EarthWeeklyReport, recent_activity: EarthActivity[], real_context: { enabled: boolean, city: string, source: string, source_status: string, last_synced_at: string, is_stale: boolean, precise_location_saved: boolean }, operator: { enabled: boolean, in_quiet_hours: boolean, last_cycle_at: string, next_cycle_at: string, cycles: number, last_actions: number, last_skipped: boolean, last_notification_sent: boolean } }
  observations: Array<{ key: string, text: string, evidence?: Record<string, number> }>
  recommendations: Array<{ key: string, text: string, requires_confirmation: boolean }>
  pending_confirmation: Array<{ key: string, text: string }>
  boundary: string
}

export interface EarthWorldRegion {
  id: number
  key: string
  name: string
  subtitle: string
  description: string
  icon: string
  color: string
  level_req: number
  discovered: number
  discovery_count: number
  event_total: number
  discovery_total: number
  exploration_percent: number
  image_path?: string
  last_explored_at?: string
  resonance_xp?: number
  resonance_level?: number
  resonance_next_xp?: number
  available_event_total?: number
  condition_events?: Array<{ title: string, condition_label: string, available: boolean }>
  latitude?: number | null
  longitude?: number | null
  geofence_radius?: number
}

export interface EarthWorldDiscovery {
  id?: number
  region_key: string
  event_key: string
  kind?: string
  title: string
  content: string
  reward_currency: number
  reward_exp: number
  discovered_at: string
  companion?: { speaker: string, text: string, tone: string, region: string }
  choice?: { choice: string, chosen_at: string } | null
}

export interface EarthWorldCustomEvent {
  id: number
  region_key: string
  title: string
  text: string
  kind: string
  reward_currency: number
  reward_exp: number
  active: number
  created_at: string
}

export interface EarthWorldShopItem {
  key: string
  name: string
  description: string
  cost: number
  limit: number
  kind: string
  purchased: number
  can_buy: boolean
  requires_discoveries?: number
}

export interface EarthWorldShop {
  event_key: string
  name?: string
  active: boolean
  start?: string
  end?: string
  items: EarthWorldShopItem[]
}

export interface EarthMiyaShopItem {
  key: string
  name: string
  description: string
  cost: number
  limit: number
  kind: string
  purchased: number
  can_buy: boolean
  interaction?: string
}

export interface EarthMiyaShop {
  name: string
  currency: string
  items: EarthMiyaShopItem[]
  player: EarthPlayer
}

// ── 服务券: 互动类商品兑换后存入背包 (category=collectible, fields.service_ticket=商品key)
// 使用时才真正触发互动, 由 /miya-shop/redeem 返回弥娅的回应 ──
export interface EarthRedeemResult {
  success: boolean
  name: string
  /** 弥娅口吻的互动回应文案 */
  interaction: string
  /** 背包中该服务券剩余张数 */
  remaining: number
  player: EarthPlayer
}

// 弥娅商城货架管理条目 (GET /miya-shop/manage): 内置商品 + 全部自定义商品 (含下架)
export interface EarthMiyaShopManagedItem {
  key: string
  name: string
  description: string
  cost: number
  limit: number
  kind: string
  interaction?: string
  story_title?: string
  story_content?: string
  title_award?: string
  boost?: string
  /** 上下架状态 0|1 (内置商品恒为 1) */
  active?: number
  /** 内置商品标记 (不可修改 / 删除) */
  builtin?: boolean
  /** 自定义商品标记 */
  is_custom?: boolean
}

// 上架 / 编辑自定义商品入参 (kind=boost 时 boost 固定 commission_resonance)
export interface EarthMiyaShopItemInput {
  key: string
  name: string
  description?: string
  cost?: number
  limit?: number
  kind?: string
  interaction?: string
  story_title?: string
  story_content?: string
  title_award?: string
  boost?: string
  /** 编辑 (PUT) 时可上下架 */
  active?: boolean
}

export interface EarthWorldResponse {
  regions: EarthWorldRegion[]
  discoveries: EarthWorldDiscovery[]
  /** 世界模块降级或尚未初始化时可能暂无状态。 */
  status: EarthWorldStatus | null
}

export interface EarthWorldEventArea {
  key: string
  name: string
  subtitle: string
  description: string
  icon: string
  color: string
  start: string
  end: string
  reward_currency: number
  reward_exp: number
  active: boolean
  is_custom?: boolean
  running?: boolean
}

export interface EarthWorldEventShopItemInput {
  key: string
  name: string
  description?: string
  cost?: number
  limit?: number
  kind?: string
  requires_discoveries?: number
}

export interface EarthWorldStatus {
  date: string
  time: string
  period: string
  period_icon: string
  weather: string
  weather_icon: string
  source_status?: string
  real_context?: EarthRealContext
  event_areas: EarthWorldEventArea[]
}

export interface EarthRealContext {
  captured_at: string
  last_synced_at?: string
  source: string
  source_status: string
  city: string
  latitude?: number | null
  longitude?: number | null
  weather: string
  weather_icon: string
  temperature?: number | null
  condition_code?: string
  humidity?: number | null
  wind?: string
  timezone?: string
  is_stale?: number
  settings?: Record<string, any>
}

export interface EarthItem {
  id: number
  name: string
  category: string
  rarity: string
  quantity: number
  description: string
  image_path?: string
  status: string
  markdown?: string
  fields?: Record<string, any>
  created_at?: string
}

export interface EarthQuest {
  id: number
  title: string
  description: string
  quest_type: string
  must_complete: boolean
  status: string
  reward_currency: number
  reward_exp: number
  penalty_currency: number
  deadline: string
  source: string
  difficulty: number
  fields?: Record<string, any>
  subtasks?: Array<{ text: string, done: number | boolean }>
  recurring?: string
  created_at?: string
  completed_at?: string
}

export interface EarthActivity {
  id: number
  kind: string
  icon: string
  summary: string
  detail: string
  quest_id?: number | null
  comment?: string
  created_at: string
}

export interface EarthExchangeRates {
  enabled: boolean
  usd_per_cny: number
}

export interface EarthTheme {
  version?: number
  accent: string
  accent_light: string
  accent_deep: string
  background: string
  background_opacity: number
  glass: boolean
}

export interface EarthCharacter {
  id: number
  name: string
  nickname: string
  relationship: string
  affinity: number
  avatar_path?: string
  notes: string
  birthday: string
  markdown?: string
  fields?: Record<string, any>
  created_at?: string
}

export interface EarthStory {
  id: number
  title: string
  content: string
  event_type: string
  character_id?: number | null
  item_id?: number | null
  happened_at: string
  image_path?: string
  fields?: Record<string, any>
  created_at?: string
}

export interface EarthSummary {
  player: EarthPlayer
  stats: { active_quests: number, items: number, characters: number, stories: number }
}

export interface EarthAchievement {
  id: number
  key: string
  title: string
  description: string
  icon: string
  category: string
  target: number
  progress: number
  hidden: number
  unlocked_at: string
  created_at: string
  /** 奖励字段 (v17 后端返回, 兼容旧数据全部可选) */
  reward_currency?: number
  reward_exp?: number
  title_award?: string
}

export interface EarthCheckinRecord {
  id: number
  date: string
  reward_currency: number
  reward_exp: number
  streak: number
  created_at: string
}

export interface EarthCheckinStatus {
  today: string
  checked_today: boolean
  streak: number
  total_days: number
  today_reward: EarthCheckinRecord | null
  history: EarthCheckinRecord[]
}

// ── v17: 签到睡眠反馈 ──
export interface EarthCheckinSleep {
  hours: number
  energy_bonus: number
  mood_extra: number
  note: string
}

// ── v17: 货币流水 (弥娅币/地球币/经验) ──
export interface EarthCurrencyLedgerEntry {
  id: number
  currency: 'miya' | 'earth' | 'exp'
  delta: number
  reason: string
  created_at: string
}

// ── v17: 回忆卡池 (memory) ──
export type EarthMemoryRarity = 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary'

export interface EarthMemoryPoolItem {
  key: string
  title: string
  rarity: EarthMemoryRarity
  owned: boolean
}

export interface EarthMemoryPool {
  name: string
  cost_single: number
  cost_ten: number
  pity_threshold: number
  pity: number
  weights: Record<string, number>
  total_pulls: number
  collected: number
  pool_size: number
  pool: EarthMemoryPoolItem[]
  player: EarthPlayer
}

export interface EarthMemoryPullItem {
  pool_key: string
  title: string
  text: string
  rarity: EarthMemoryRarity
  is_new: boolean
  item_id: number
  refund_currency: number
}

export interface EarthMemoryPullResult {
  success: boolean
  times: number
  cost: number
  results: EarthMemoryPullItem[]
  refund_total: number
  pity: number
  player: EarthPlayer
}

export interface EarthMemoryPullRecord {
  id: number
  pool_key: string
  title: string
  rarity: string
  is_new?: boolean
  created_at: string
  times?: number
  cost?: number
}

// ── v17: 每周纪行 (battle pass) ──
export interface EarthBattlePassTier {
  tier: number
  threshold: number
  reward_currency: number
  reached: boolean
  claimed: boolean
  claimable: boolean
}

export interface EarthBattlePassBreakdownEntry {
  count: number
  points_each: number
}

export interface EarthBattlePass {
  name: string
  week_key: string
  week_start: string
  points: number
  breakdown: Record<string, EarthBattlePassBreakdownEntry>
  tiers: EarthBattlePassTier[]
  current_tier: number
  claimable_count: number
}

// ── v17: 周挑战 ──
export interface EarthWeeklyChallenge {
  name: string
  theme: { key: string, name: string, description: string, suggestions: string[] }
  week_key: string
  goal: number
  completed_quests: number
  stars: number
  stars_label: string
  progress_percent: number
}

// ── v17: 纪念日 ──
export interface EarthCommemoration {
  id: number
  key: string
  name: string
  date: string
  description: string
  icon: string
  lead_days: number
  enabled: boolean
  days_until: number
  phase: 'today' | 'upcoming' | 'later' | 'invalid'
  next_date: string
}

export interface EarthCommemorationInput {
  key: string
  name: string
  date: string
  description?: string
  icon?: string
  lead_days?: number
}

// ── v17: 生成今日日常委托 ──
export interface EarthGeneratedDaily {
  success: boolean
  created: number
  quests: EarthQuest[]
  created_quests?: EarthQuest[]
  date: string
}

export interface EarthMiyaNote {
  id: number
  content: string
  mood: string
  pinned: number
  created_at: string
}

export interface EarthStats {
  player: EarthPlayer
  quests: {
    total: number
    status: Record<string, number>
    types: Record<string, number>
    completed: number
    failed: number
    completion_rate: number
    trend_7d: Array<{ date: string, count: number }>
  }
  items: { total: number, rarity: Record<string, number>, categories: Record<string, number> }
  characters: {
    total: number
    relationships: Record<string, number>
    affinity_ranking: Array<{ id: number, name: string, affinity: number }>
  }
  stories: { total: number, types: Record<string, number> }
  checkin: EarthCheckinStatus
  achievements: { total: number, unlocked: number, recent: EarthAchievement[] }
}

export interface EarthTemplateField {
  key: string
  label: string
  placeholder?: string
}

export interface EarthTemplates {
  items: Record<string, { label: string, fields: EarthTemplateField[] }>
  characters: Record<string, { label: string, fields: EarthTemplateField[] }>
  quests: Array<{ id: string, label: string, reward_currency: number, reward_exp: number, penalty_currency: number, difficulty: number, fields: EarthTemplateField[] }>
  affinity_levels: Array<{ min: number, max: number, label: string, color: string }>
  player_attrs?: EarthAttr[]
}

export class EarthApiClient extends ApiClient {
  constructor(port: MaybeRef<number>) {
    super(port)
    // 地球online 数据字段与后端保持一致 (snake_case)，不做 camelCase 转换：
    // 后端 store 返回 snake_case，此前全局 transformResponse 会转成 camelCase，
    // 导致前端按 reward_currency / checked_today / trend_7d 读取全部落空 (undefined)。
    this.instance.defaults.transformResponse = [
      (data: any) => {
        try {
          return JSON.parse(data)
        }
        catch {
          return data
        }
      },
    ]
  }

  // ── 玩家 ──
  async getPlayer(): Promise<EarthPlayer> {
    return this.instance.get('/api/earth/player')
  }

  async addExp(amount: number): Promise<EarthPlayer> {
    return this.instance.post('/api/earth/player/exp', { amount })
  }

  async addCurrency(amount: number): Promise<EarthPlayer> {
    return this.instance.post('/api/earth/player/currency', { amount })
  }

  async spendMiyaCoins(amount: number, reason: string): Promise<{ success: boolean, spent: number, player: EarthPlayer }> {
    return this.instance.post('/api/earth/player/spend', { amount, reason })
  }

  async summary(): Promise<EarthSummary> {
    return this.instance.get('/api/earth/summary')
  }

  async updatePlayer(data: Partial<EarthPlayer>): Promise<EarthPlayer> {
    return this.instance.put('/api/earth/player', data)
  }

  // ── JSON 可视化 (记事本模式) ──
  async exportJson(): Promise<any> {
    return this.instance.get('/api/earth/export')
  }

  async readJson(): Promise<any> {
    return this.instance.get('/api/earth/json')
  }

  async importJson(data: any): Promise<any> {
    return this.instance.post('/api/earth/import', { data })
  }

  // ── 模板库 ──
  async getTemplates(): Promise<EarthTemplates> {
    return this.instance.get('/api/earth/templates')
  }

  async saveTemplates(data: EarthTemplates): Promise<EarthTemplates> {
    return this.instance.put('/api/earth/templates', data)
  }

  // ── 通用图片上传 ──
  async uploadImage(file: File, itemId?: number): Promise<{ success: boolean, image_path: string, url: string, item?: EarthItem }> {
    const form = new FormData()
    form.append('file', file)
    if (itemId)
      form.append('item_id', String(itemId))
    return this.instance.post('/api/earth/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      transformRequest: [(d: any) => d],
      transformResponse: [(d: string) => {
        try { return JSON.parse(d) } catch { return d }
      }],
    })
  }

  // ── 背包 ──
  async listItems(category = '', status = ''): Promise<EarthItem[]> {
    return this.instance.get('/api/earth/items', { params: { category, status } })
  }

  async getItem(itemId: number): Promise<EarthItem> {
    return this.instance.get(`/api/earth/items/${itemId}`)
  }

  async createItem(data: Partial<EarthItem>): Promise<EarthItem> {
    return this.instance.post('/api/earth/items', data)
  }

  async updateItem(itemId: number, data: Partial<EarthItem>): Promise<EarthItem> {
    return this.instance.put(`/api/earth/items/${itemId}`, data)
  }

  async deleteItem(itemId: number): Promise<{ success: boolean }> {
    return this.instance.delete(`/api/earth/items/${itemId}`)
  }

  async uploadItemImage(file: File, itemId?: number): Promise<{ success: boolean, image_path: string, url: string, item?: EarthItem }> {
    const form = new FormData()
    form.append('file', file)
    if (itemId)
      form.append('item_id', String(itemId))
    return this.instance.post('/api/earth/items/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      transformRequest: [(d: any) => d],
      transformResponse: [(d: string) => {
        try { return JSON.parse(d) } catch { return d }
      }],
    })
  }

  imageUrl(path?: string): string {
    if (!path)
      return ''
    if (path.startsWith('http'))
      return path
    return `http://localhost:${getApiPort()}${path}`
  }

  // ── 任务 ──
  async listQuests(status = '', questType = ''): Promise<EarthQuest[]> {
    return this.instance.get('/api/earth/quests', { params: { status, quest_type: questType } })
  }

  async questHistory(limit = 50): Promise<EarthQuest[]> {
    return this.instance.get('/api/earth/quests/history', { params: { limit } })
  }

  async createQuest(data: Partial<EarthQuest>): Promise<EarthQuest> {
    return this.instance.post('/api/earth/quests', data)
  }

  async updateQuest(questId: number, data: Partial<EarthQuest>): Promise<EarthQuest> {
    return this.instance.put(`/api/earth/quests/${questId}`, data)
  }

  async completeQuest(questId: number): Promise<{ success: boolean, player: EarthPlayer, reward: { currency: number, exp: number }, level_up?: EarthLevelUp | null, recurring_reset?: boolean }> {
    return this.instance.post(`/api/earth/quests/${questId}/complete`)
  }

  async acceptQuest(questId: number): Promise<{ success: boolean, quest: EarthQuest }> {
    return this.instance.post(`/api/earth/quests/${questId}/accept`)
  }

  async failQuest(questId: number): Promise<{ success: boolean, player: EarthPlayer }> {
    return this.instance.post(`/api/earth/quests/${questId}/fail`)
  }

  async cancelQuest(questId: number): Promise<{ success: boolean }> {
    return this.instance.post(`/api/earth/quests/${questId}/cancel`)
  }

  async checkOverdue(): Promise<{ success: boolean, failed: number }> {
    return this.instance.post('/api/earth/quests/check-overdue')
  }

  async toggleSubtask(questId: number, index: number, done?: boolean): Promise<{ success: boolean, quest: EarthQuest, message?: string }> {
    return this.instance.post(`/api/earth/quests/${questId}/subtasks`, { index, done })
  }

  // ── 全局动态流 ──
  async activity(limit = 50, kind = ''): Promise<EarthActivity[]> {
    return this.instance.get('/api/earth/activity', { params: { limit, kind } })
  }

  async commentActivity(activityId: number, comment: string): Promise<EarthActivity> {
    return this.instance.post(`/api/earth/activity/${activityId}/comment`, { comment })
  }

  // ── 币种换算 ──
  async exchangeRates(): Promise<EarthExchangeRates> {
    return this.instance.get('/api/earth/exchange-rates')
  }

  // ── 前台主题 ──
  async getTheme(): Promise<EarthTheme> {
    return this.instance.get('/api/earth/theme')
  }

  async saveTheme(data: Partial<EarthTheme>): Promise<EarthTheme> {
    return this.instance.put('/api/earth/theme', data)
  }

  async resetTheme(): Promise<EarthTheme> {
    return this.instance.post('/api/earth/theme/reset')
  }

  // ── 剧情 ──
  async listStory(eventType = '', limit = 100): Promise<EarthStory[]> {
    return this.instance.get('/api/earth/story', { params: { event_type: eventType, limit } })
  }

  async createStory(data: Partial<EarthStory>): Promise<EarthStory> {
    return this.instance.post('/api/earth/story', data)
  }

  async updateStory(storyId: number, data: Partial<EarthStory>): Promise<EarthStory> {
    return this.instance.put(`/api/earth/story/${storyId}`, data)
  }

  async deleteStory(storyId: number): Promise<{ success: boolean }> {
    return this.instance.delete(`/api/earth/story/${storyId}`)
  }

  // ── 角色 ──
  async listCharacters(): Promise<EarthCharacter[]> {
    return this.instance.get('/api/earth/characters')
  }

  async createCharacter(data: Partial<EarthCharacter>): Promise<EarthCharacter> {
    return this.instance.post('/api/earth/characters', data)
  }

  async updateCharacter(characterId: number, data: Partial<EarthCharacter>): Promise<EarthCharacter> {
    return this.instance.put(`/api/earth/characters/${characterId}`, data)
  }

  async deleteCharacter(characterId: number): Promise<{ success: boolean }> {
    return this.instance.delete(`/api/earth/characters/${characterId}`)
  }

  async addAffinity(characterId: number, delta: number, reason: string): Promise<EarthCharacter> {
    return this.instance.post(`/api/earth/characters/${characterId}/affinity`, { delta, reason })
  }

  async affinityLogs(characterId: number, limit = 50): Promise<Array<{ id: number, delta: number, reason: string, created_at: string }>> {
    return this.instance.get(`/api/earth/characters/${characterId}/affinity-logs`, { params: { limit } })
  }

  // ── 成就 ──
  async listAchievements(): Promise<EarthAchievement[]> {
    return this.instance.get('/api/earth/achievements')
  }

  async refreshAchievements(): Promise<{ success: boolean, newly_unlocked: EarthAchievement[] }> {
    return this.instance.post('/api/earth/achievements/refresh')
  }

  // 弥娅自定义成就
  async addAchievement(data: {
    key: string
    title: string
    description?: string
    icon?: string
    category?: string
    target?: number
    reward_currency?: number
    reward_exp?: number
    title_award?: string
    hidden?: boolean
  }): Promise<{ success: boolean, achievement?: EarthAchievement, message?: string }> {
    return this.instance.post('/api/earth/achievements/custom', data)
  }

  // 手动更新成就进度 (达标自动解锁)
  async setAchievementProgress(key: string, progress: number): Promise<{ success: boolean, achievement?: EarthAchievement, message?: string }> {
    return this.instance.post('/api/earth/achievements/progress', { key, progress })
  }

  // ── 限时活动管理 (内置 + 自定义) ──
  async listEventAreas(): Promise<EarthWorldEventArea[]> {
    return this.instance.get('/api/earth/world/event-areas')
  }

  async createEventArea(data: Partial<EarthWorldEventArea>): Promise<{ success: boolean, area: EarthWorldEventArea }> {
    return this.instance.post('/api/earth/world/event-areas', data)
  }

  async updateEventArea(eventKey: string, data: Partial<EarthWorldEventArea>): Promise<{ success: boolean, area: EarthWorldEventArea }> {
    return this.instance.put(`/api/earth/world/event-areas/${encodeURIComponent(eventKey)}`, data)
  }

  async deleteEventArea(eventKey: string): Promise<{ success: boolean }> {
    return this.instance.delete(`/api/earth/world/event-areas/${encodeURIComponent(eventKey)}`)
  }

  async createEventShopItem(eventKey: string, data: Partial<EarthWorldShopItem>): Promise<{ success: boolean, item: EarthWorldShopItem }> {
    return this.instance.post(`/api/earth/world/event-areas/${encodeURIComponent(eventKey)}/items`, data)
  }

  async deleteEventShopItem(eventKey: string, itemKey: string): Promise<{ success: boolean }> {
    return this.instance.delete(`/api/earth/world/event-areas/${encodeURIComponent(eventKey)}/items/${encodeURIComponent(itemKey)}`)
  }

  // ── 每日签到 ──
  async checkinStatus(): Promise<EarthCheckinStatus> {
    return this.instance.get('/api/earth/checkin')
  }

  // v17: 可携带昨晚睡眠时长 (0-24 小时)，后端会反馈体力/心情加成
  async checkin(sleepHours?: number): Promise<{ success: boolean, message?: string, reward?: { currency: number, exp: number }, streak?: number, player?: EarthPlayer, status?: EarthCheckinStatus, level_up?: EarthLevelUp | null, sleep?: EarthCheckinSleep }> {
    return this.instance.post('/api/earth/checkin', sleepHours != null ? { sleep_hours: sleepHours } : undefined)
  }

  async checkinHistory(limit = 100): Promise<EarthCheckinRecord[]> {
    return this.instance.get('/api/earth/checkin/history', { params: { limit } })
  }

  // ── v17: 地球币记账 / 货币流水 ──
  // 现实资产记账 (amount 正数=收入, 负数=支出)
  async adjustEarthCurrency(amount: number, reason: string): Promise<{ success: boolean, amount: number, balance: number, player: EarthPlayer }> {
    return this.instance.post('/api/earth/player/earth-currency', { amount, reason })
  }

  async currencyLedger(limit = 100, currency = ''): Promise<EarthCurrencyLedgerEntry[]> {
    return this.instance.get('/api/earth/currency/ledger', { params: { limit, currency } })
  }

  // ── v17: 回忆卡池 ──
  async memoryPool(): Promise<EarthMemoryPool> {
    return this.instance.get('/api/earth/memory')
  }

  async memoryPull(times: 1 | 10): Promise<EarthMemoryPullResult> {
    return this.instance.post('/api/earth/memory/pull', { times })
  }

  async memoryPulls(limit = 50): Promise<EarthMemoryPullRecord[]> {
    return this.instance.get('/api/earth/memory/pulls', { params: { limit } })
  }

  // ── v17: 每周纪行 ──
  async battlePass(): Promise<EarthBattlePass> {
    return this.instance.get('/api/earth/battle-pass')
  }

  async claimBattlePass(tier: number): Promise<{ success: boolean, tier: number, reward_currency: number, battle_pass: EarthBattlePass }> {
    return this.instance.post(`/api/earth/battle-pass/${tier}/claim`)
  }

  // ── v17: 周挑战 ──
  async weeklyChallenge(): Promise<EarthWeeklyChallenge> {
    return this.instance.get('/api/earth/weekly-challenge')
  }

  // ── v17: 纪念日 ──
  async listCommemorations(): Promise<EarthCommemoration[]> {
    return this.instance.get('/api/earth/commemorations')
  }

  async addCommemoration(data: EarthCommemorationInput): Promise<{ success: boolean, commemoration: EarthCommemoration }> {
    return this.instance.post('/api/earth/commemorations', data)
  }

  async deleteCommemoration(key: string): Promise<{ success: boolean }> {
    return this.instance.delete(`/api/earth/commemorations/${encodeURIComponent(key)}`)
  }

  async syncCommemorations(): Promise<{ success: boolean, activated: string[], notes_sent: string[] }> {
    return this.instance.post('/api/earth/commemorations/sync')
  }

  // ── v17: 生成今日日常委托 ──
  async generateDailyCommissions(): Promise<EarthGeneratedDaily> {
    return this.instance.post('/api/earth/quests/generate-daily')
  }

  // ── 弥娅寄语 ──
  async listNotes(limit = 30): Promise<EarthMiyaNote[]> {
    return this.instance.get('/api/earth/notes', { params: { limit } })
  }

  async addNote(data: { content: string, mood?: string, pinned?: boolean }): Promise<EarthMiyaNote> {
    return this.instance.post('/api/earth/notes', data)
  }

  async pinNote(noteId: number, pinned: boolean): Promise<EarthMiyaNote> {
    return this.instance.post(`/api/earth/notes/${noteId}/pin`, { pinned })
  }

  async deleteNote(noteId: number): Promise<{ success: boolean }> {
    return this.instance.delete(`/api/earth/notes/${noteId}`)
  }

  // ── 统计数据中心 ──
  async stats(): Promise<EarthStats> {
    return this.instance.get('/api/earth/stats')
  }

  async lifeHub(): Promise<EarthLifeHub> {
    return this.instance.get('/api/earth/life-hub')
  }

  // ── 称号系统 ──
  async titles(): Promise<EarthTitles> {
    return this.instance.get('/api/earth/titles')
  }

  async equipTitle(title: string): Promise<{ success: boolean, equipped: string, titles: EarthTitles }> {
    return this.instance.post('/api/earth/titles/equip', { title })
  }

  // ── 到期提醒 ──
  async dueSoon(days = 3): Promise<EarthQuest[]> {
    return this.instance.get('/api/earth/quests/due-soon', { params: { days } })
  }

  // ── 每周报告 ──
  async weeklyReport(): Promise<EarthWeeklyReport> {
    return this.instance.get('/api/earth/weekly-report')
  }

  // ── 单人开放世界 ──
  async world(): Promise<EarthWorldResponse> {
    return this.instance.get('/api/earth/world')
  }

  async worldStatus(): Promise<EarthWorldStatus> {
    return this.instance.get('/api/earth/world/status')
  }

  async realContext(): Promise<EarthRealContext> {
    return this.instance.get('/api/earth/world/real-context')
  }

  async refreshRealContext(values: Record<string, any> = {}): Promise<EarthRealContext> {
    return this.instance.post('/api/earth/world/real-context/refresh', values)
  }

  async realContextSettings(): Promise<Record<string, any>> {
    return this.instance.get('/api/earth/world/real-context/settings')
  }

  async updateRealContextSettings(values: Record<string, any>): Promise<Record<string, any>> {
    return this.instance.put('/api/earth/world/real-context/settings', values)
  }

  async updateWeatherApiKey(apiKey: string): Promise<Record<string, any>> {
    return this.instance.put('/api/earth/world/real-context/api-key', { api_key: apiKey })
  }

  async updateWorldRegion(regionKey: string, values: Record<string, any>): Promise<EarthWorldRegion> {
    return this.instance.put(`/api/earth/world/regions/${encodeURIComponent(regionKey)}`, values)
  }

  async listWorldEvents(regionKey = ''): Promise<EarthWorldCustomEvent[]> {
    return this.instance.get('/api/earth/world/events', { params: { region_key: regionKey } })
  }

  async createWorldEvent(values: Record<string, any>): Promise<EarthWorldCustomEvent> {
    return this.instance.post('/api/earth/world/events', values)
  }

  async deleteWorldEvent(eventId: number): Promise<{ success: boolean }> {
    return this.instance.delete(`/api/earth/world/events/${eventId}`)
  }

  async worldEventShop(eventKey: string): Promise<EarthWorldShop> {
    return this.instance.get(`/api/earth/world/events/${encodeURIComponent(eventKey)}/shop`)
  }

  async buyWorldEventItem(eventKey: string, itemKey: string): Promise<{ success: boolean, item: EarthWorldShopItem, player: EarthPlayer }> {
    return this.instance.post(`/api/earth/world/events/${encodeURIComponent(eventKey)}/shop/${encodeURIComponent(itemKey)}/buy`)
  }

  async miyaShop(): Promise<EarthMiyaShop> {
    return this.instance.get('/api/earth/miya-shop')
  }

  async buyMiyaShopItem(itemKey: string): Promise<{ success: boolean, item: EarthMiyaShopItem, interaction?: string, player: EarthPlayer }> {
    return this.instance.post(`/api/earth/miya-shop/${encodeURIComponent(itemKey)}/buy`)
  }

  // 使用背包里的服务券 (item_id 优先, 也可按 item_key 兑换)
  async redeemService(itemId?: number, itemKey?: string): Promise<EarthRedeemResult> {
    const body: Record<string, any> = {}
    if (itemId != null)
      body.item_id = itemId
    if (itemKey)
      body.item_key = itemKey
    return this.instance.post('/api/earth/miya-shop/redeem', body)
  }

  // ── 弥娅商城货架管理 (内置商品只读，自定义商品可增改删 / 上下架) ──
  async listMiyaShopManaged(): Promise<EarthMiyaShopManagedItem[]> {
    return this.instance.get('/api/earth/miya-shop/manage')
  }

  async createMiyaShopItem(data: Partial<EarthMiyaShopItemInput>): Promise<{ success: boolean, item: EarthMiyaShopManagedItem }> {
    return this.instance.post('/api/earth/miya-shop/manage', data)
  }

  async updateMiyaShopItem(itemKey: string, data: Partial<EarthMiyaShopItemInput>): Promise<{ success: boolean, item: EarthMiyaShopManagedItem }> {
    return this.instance.put(`/api/earth/miya-shop/manage/${encodeURIComponent(itemKey)}`, data)
  }

  async deleteMiyaShopItem(itemKey: string): Promise<{ success: boolean }> {
    return this.instance.delete(`/api/earth/miya-shop/manage/${encodeURIComponent(itemKey)}`)
  }

  async worldDiscoveries(regionKey = '', limit = 100): Promise<EarthWorldDiscovery[]> {
    return this.instance.get('/api/earth/world/discoveries', { params: { region_key: regionKey, limit } })
  }

  async exploreWorld(regionKey: string, coords?: { latitude: number, longitude: number }): Promise<{
    success: boolean
    complete: boolean
    region: EarthWorldRegion
    discovery: EarthWorldDiscovery | null
    player: EarthPlayer
    level_up?: EarthLevelUp | null
    message?: string
    resonance?: { level: number, xp: number, level_up?: boolean }
    geofence?: { enabled: boolean, passed: boolean, distance_m?: number, radius_m?: number, message?: string }
    attrs?: Record<string, number>
  }> {
    // 区域启用地理围栏时需要携带真实坐标 (latitude/longitude)
    const body = coords ? { latitude: coords.latitude, longitude: coords.longitude } : undefined
    return this.instance.post(`/api/earth/world/${encodeURIComponent(regionKey)}/explore`, body)
  }

  async chooseWorldDiscovery(discoveryId: number, choice: 'continue' | 'record' | 'rest'): Promise<{ success: boolean, label: string, resonance?: { level: number, xp: number }, player: EarthPlayer }> {
    return this.instance.post(`/api/earth/world/discoveries/${discoveryId}/choice`, { choice })
  }

  async uploadWorldRegionImage(regionKey: string, file: File): Promise<{ success: boolean, image_path: string, region: EarthWorldRegion }> {
    const form = new FormData()
    form.append('file', file)
    return this.instance.post(`/api/earth/world/${encodeURIComponent(regionKey)}/image`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  }

  async regionCommission(regionKey: string): Promise<{ success: boolean, created: boolean, quest: EarthQuest }> {
    return this.instance.post(`/api/earth/world/${encodeURIComponent(regionKey)}/commission`)
  }
}

export default new EarthApiClient(apiPort)
