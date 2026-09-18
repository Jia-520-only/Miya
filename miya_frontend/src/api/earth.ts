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

export interface EarthEarningOpportunity {
  id: number
  title: string
  source: string
  url: string
  kind: string
  description: string
  income_min: number
  income_max: number
  hours: number
  risk: 'low' | 'medium' | 'high' | 'unknown'
  confidence: 'low' | 'medium' | 'high' | 'unknown'
  verification_status: 'unverified' | 'checking' | 'verified' | 'rejected'
  deadline?: string
  requirements?: string
  scam_flags?: string[]
  last_checked_at?: string
  status: 'inbox' | 'shortlisted' | 'applied' | 'won' | 'closed'
  quest_id?: number | null
  hourly_estimate?: number
  fit_score?: number
  fit_reasons?: string[]
  created_at?: string
  updated_at?: string
}

export interface EarthEarningPlan {
  id: number
  title: string
  goal_amount: number
  target_date: string
  status: 'active' | 'paused' | 'completed' | 'archived'
  notes: string
  route_key?: string
  is_sprint?: boolean | number
  created_at?: string
  updated_at?: string
  steps?: EarthEarningPlanStep[]
  completed_steps?: number
  progress_percent?: number
}

export interface EarthEarningPlanStep {
  id: number
  plan_id: number
  title: string
  description: string
  position: number
  status: 'pending' | 'doing' | 'done' | 'skipped'
  quest_id?: number | null
  completed_at?: string
  created_at?: string
  updated_at?: string
}

export interface EarthIncomeRecord {
  id: number
  opportunity_id?: number | null
  amount: number
  cost: number
  hours: number
  note: string
  recorded_at: string
}

export interface EarthEarningOffer {
  id: number
  title: string
  customer: string
  problem: string
  deliverables: string
  scope: string
  proof: string
  price: number
  cost_estimate: number
  delivery_days: number
  revisions: number
  route_key: string
  status: 'draft' | 'active' | 'paused' | 'retired'
  created_at?: string
  updated_at?: string
}

export interface EarthEarningActionDraft {
  id: number
  opportunity_id?: number | null
  offer_id?: number | null
  action_type: 'proposal' | 'publish' | 'contact' | 'upload' | 'accept_order'
  target: string
  title: string
  content: string
  attachments: string[]
  amount: number
  risk: 'low' | 'medium' | 'high'
  status: 'draft' | 'pending' | 'approved' | 'revoked' | 'expired'
  content_hash: string
  approved_hash: string
  submitted_at?: string
  approved_at?: string
  expires_at?: string
  revoked_at?: string
  created_at?: string
  updated_at?: string
}

export interface EarthEarningGuidance {
  opportunities: EarthEarningOpportunity[]
  plans: EarthEarningPlan[]
  income_records: EarthIncomeRecord[]
  offers: EarthEarningOffer[]
  action_drafts: EarthEarningActionDraft[]
  digital_resources: EarthDigitalResource[]
  digital_products: EarthDigitalProduct[]
  digital_orders: EarthDigitalOrder[]
  digital_deliveries: EarthDigitalDelivery[]
  routes: EarthEarningRoute[]
  profile_ready: boolean
  brief: string
  focus_plan?: EarthEarningPlan | null
  next_action?: EarthEarningPlanStep | null
  pipeline: Record<EarthEarningOpportunity['status'], number>
  totals: { net_income: number, opportunity_count: number, active_plan_count: number, active_offer_count: number, pending_approval_count: number, approved_action_count: number, approved_resource_count?: number, ready_product_count?: number, awaiting_payment_count?: number, active_delivery_count?: number, total_hours: number, effective_hourly_rate: number }
  preferences: EarthEarningPreferences
  automation: { automatic: string[], requires_confirmation: string[], blocked: string[] }
  authorization?: { policy: EarthEarningAuthorizationPolicy, audit: EarthEarningAuthorizationAudit[] }
  boundary: string
}

export interface EarthEarningPreferences {
  skills: string[]
  preferred_kinds: string[]
  accepted_models: string[]
  sellable_assets: string[]
  constraints: string
  primary_route: string
  weekly_hours: number
  target_amount: number
  min_hourly_rate: number
  risk_tolerance: 'low' | 'medium' | 'high'
  updated_at?: string
}

export interface EarthEarningAuthorizationPolicy {
  id: number
  enabled: boolean
  simulation_only: boolean
  allowed_actions: EarthEarningActionDraft['action_type'][]
  allowed_targets: string[]
  max_single_amount: number
  max_daily_actions: number
  expires_at: string
  emergency_stop: boolean
  updated_at?: string
}

export interface EarthEarningAuthorizationAudit {
  id: number
  action_type: string
  target: string
  amount: number
  decision: 'allow' | 'deny'
  reason: string
  simulation: boolean
  created_at: string
}

export interface EarthEarningRoute {
  key: string
  name: string
  icon: string
  kind: string
  summary: string
  best_for: string
  first_revenue_days: string
  cash_cost: string
  effort: string
  steps: Array<[string, string]>
  fit_score: number
  fit_reasons: string[]
  first_action: string
}

export interface EarthEarningSprintResult {
  success: boolean
  created: boolean
  plan: EarthEarningPlan
  quest?: EarthQuest | null
  route: EarthEarningRoute
}

export interface EarthEarningSource {
  id: number
  name: string
  url: string
  kind: string
  enabled: boolean | number
  last_synced_at?: string
  last_error?: string
  created_at?: string
  updated_at?: string
}

export interface EarthDigitalResource {
  id: number
  title: string
  source_url: string
  source_name: string
  license_type: 'original' | 'resale_license' | 'open_license' | 'public_domain' | 'unknown'
  rights_status: 'pending' | 'verified' | 'rejected'
  rights_note: string
  content_uri: string
  checksum: string
  version: string
  risk_flags: string[]
  status: 'candidate' | 'approved' | 'rejected' | 'archived'
  created_at?: string
  updated_at?: string
}

export interface EarthDigitalProduct {
  id: number
  title: string
  description: string
  resource_ids: number[]
  platform: 'xianyu' | 'manual'
  price: number
  cost_estimate: number
  delivery_mode: 'expiring_link' | string
  delivery_note: string
  status: 'draft' | 'ready' | 'paused' | 'retired'
  created_at?: string
  updated_at?: string
}

export interface EarthDigitalOrder {
  id: number
  product_id: number
  external_order_ref: string
  amount: number
  cost: number
  status: 'awaiting_payment' | 'paid' | 'delivered' | 'completed' | 'cancelled' | 'refund_requested' | 'refunded'
  payment_confirmed_at: string
  note: string
  product?: EarthDigitalProduct | null
  created_at?: string
  updated_at?: string
}

export interface EarthDigitalDelivery {
  id: number
  order_id: number
  token_hash: string
  expires_at: string
  max_downloads: number
  download_count: number
  status: 'active' | 'expired' | 'exhausted' | 'revoked'
  issued_at: string
  last_accessed_at: string
}

export interface EarthRealPlace {
  id: number
  place_key: string
  name: string
  subtitle?: string
  latitude?: number | null
  longitude?: number | null
  visit_count: number
  first_visited_at?: string
  last_visited_at?: string
  source?: string
  confidence?: number
  verification_status?: 'unverified' | 'confirmed' | 'observed'
  source_updated_at?: string
  accuracy_m?: number | null
  image_path?: string
  country?: string
  admin1?: string
  city?: string
  district?: string
  neighborhood?: string
  notes?: string
  display_address?: string
  provider_id?: string
  category?: string
  tags?: string[]
  favorite?: boolean
  visits?: EarthRealPlaceVisit[]
  photos?: EarthRealPlacePhoto[]
}

export interface EarthRealPlaceVisit {
  id: number
  place_key: string
  visited_at: string
  latitude?: number | null
  longitude?: number | null
  accuracy_m?: number | null
  source?: string
  confidence?: number
  verification_status?: 'unverified' | 'confirmed' | 'observed'
  provider_id?: string
  observed_at?: string
  note?: string
}

export interface EarthRealPlacePhoto {
  id: number
  place_key: string
  image_path: string
  caption?: string
  created_at?: string
}

export interface EarthMapSearchResult {
  name: string
  display_name: string
  latitude: number
  longitude: number
  address?: Record<string, string>
  provider_id?: string
  category?: string
  type?: string
  importance?: number
  distance_m?: number
  category_group?: string
  source?: string
  fetched_at?: string
  website?: string
  phone?: string
  opening_hours?: string
}

export interface EarthMapJourney {
  id: number
  title: string
  happened_at: string
  narrative: string
  source: string
  verification_status: 'unverified' | 'confirmed' | 'observed'
  recorded_at: string
  duration_seconds: number
  distance_m: number
  point_count: number
  track: Array<{ latitude: number, longitude: number, timestamp?: number }>
}

export interface EarthMapFactContext {
  generated_at: string
  truth_policy: Record<string, string>
  weather: { source: string, source_status: string, captured_at: string, is_stale: boolean, city: string, weather: string, temperature?: number | null }
  places: EarthRealPlace[]
  journeys: EarthMapJourney[]
  counts: { places: number, journeys: number, observed: number, confirmed: number, unverified: number }
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

// 上架 / 编辑自定义商品入参
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
  places?: EarthRealPlace[]
  /** 世界模块降级或尚未初始化时可能暂无状态。 */
  status: EarthWorldStatus | null
  mode?: 'real_world' | string
}

export interface EarthWorldRoute {
  success: boolean
  provider: string
  profile: 'driving' | 'walking' | 'cycling'
  distance_m: number
  duration_s: number
  geometry: { type: 'LineString', coordinates: [number, number][] }
  legs?: Array<Record<string, any>>
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
  /** 需要先记录的现实地点数量；字段名为历史兼容名。 */
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

export interface EarthWeatherForecastDay {
  date: string
  text_day: string
  text_night: string
  high?: number | null
  low?: number | null
  rainfall?: number | null
  precip?: number | null
  humidity?: number | null
  wind_direction?: string
  wind_scale?: string
}

export interface EarthWeatherQuery {
  requested_location: string
  resolved_location: { id?: string, name?: string, country?: string, path?: string, timezone?: string, timezone_offset?: string }
  city: string
  provider: string
  source: string
  source_status: string
  resolution_status: string
  captured_at: string
  served_at: string
  expires_at: string
  is_stale: boolean
  from_cache: boolean
  weather: string
  weather_icon: string
  temperature?: number | null
  humidity?: number | null
  wind?: string
  forecast_status: string
  forecast: EarthWeatherForecastDay[]
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

  // ── v18: 现实收益情报与计划 ──
  async earningGuidance(): Promise<EarthEarningGuidance> {
    return this.instance.get('/api/earth/earning/guidance')
  }

  async earningAuthorization(): Promise<EarthEarningAuthorizationPolicy> {
    return this.instance.get('/api/earth/earning/authorization')
  }

  async updateEarningAuthorization(data: Partial<EarthEarningAuthorizationPolicy>): Promise<EarthEarningAuthorizationPolicy> {
    return this.instance.put('/api/earth/earning/authorization', data)
  }

  async evaluateEarningAuthorization(data: { action_type: string, target?: string, amount?: number }): Promise<{ allowed: boolean, decision: 'allow' | 'deny', reason: string, simulation_only: boolean, action_type: string, target: string, amount: number }> {
    return this.instance.post('/api/earth/earning/authorization/evaluate', data)
  }

  async earningAuthorizationAudit(limit = 100): Promise<EarthEarningAuthorizationAudit[]> {
    return this.instance.get('/api/earth/earning/authorization/audit', { params: { limit } })
  }

  async runEarningAutomationCycle(): Promise<{
    success: boolean
    started_at: string
    finished_at: string
    sync: { created_count?: number, skipped?: number, errors?: unknown[] }
    pipeline?: { promoted?: number[], prepared?: { title?: string } | null, actions?: string[] }
    experiment?: { status?: string, quest?: { title?: string } | null }
    guidance: EarthEarningGuidance
    actions: string[]
    requires_confirmation: string[]
    blocked: string[]
    digital_product?: { success: boolean, created: boolean, product?: EarthDigitalProduct, action?: EarthEarningActionDraft }
  }> {
    return this.instance.post('/api/earth/earning/automation/run')
  }

  async digitalResources(params?: { status?: string, rights_status?: string }): Promise<EarthDigitalResource[]> {
    return this.instance.get('/api/earth/earning/digital-resources', { params })
  }

  async addDigitalResource(data: Partial<EarthDigitalResource>): Promise<EarthDigitalResource> {
    return this.instance.post('/api/earth/earning/digital-resources', data)
  }

  async updateDigitalResource(id: number, data: Partial<EarthDigitalResource>): Promise<EarthDigitalResource> {
    return this.instance.put(`/api/earth/earning/digital-resources/${id}`, data)
  }

  async digitalProducts(status = ''): Promise<EarthDigitalProduct[]> {
    return this.instance.get('/api/earth/earning/digital-products', { params: status ? { status } : undefined })
  }

  async addDigitalProduct(data: Partial<EarthDigitalProduct>): Promise<EarthDigitalProduct> {
    return this.instance.post('/api/earth/earning/digital-products', data)
  }

  async prepareXianyuListing(id: number): Promise<{ success: boolean, created: boolean, product: EarthDigitalProduct, action?: EarthEarningActionDraft, message?: string }> {
    return this.instance.post(`/api/earth/earning/digital-products/${id}/prepare-xianyu`)
  }

  async digitalOrders(status = ''): Promise<EarthDigitalOrder[]> {
    return this.instance.get('/api/earth/earning/digital-orders', { params: status ? { status } : undefined })
  }

  async addDigitalOrder(data: { product_id: number, external_order_ref?: string, amount?: number, cost?: number, note?: string }): Promise<EarthDigitalOrder> {
    return this.instance.post('/api/earth/earning/digital-orders', data)
  }

  async confirmDigitalOrderPayment(id: number, confirmation: string): Promise<EarthDigitalOrder> {
    return this.instance.post(`/api/earth/earning/digital-orders/${id}/confirm-payment`, { confirmation })
  }

  async digitalDeliveries(orderId?: number): Promise<EarthDigitalDelivery[]> {
    return this.instance.get('/api/earth/earning/digital-deliveries', { params: orderId ? { order_id: orderId } : undefined })
  }

  async issueDigitalDelivery(id: number, expiresHours = 72, maxDownloads = 3): Promise<{ success: boolean, delivery_id: number, order_id: number, token: string, expires_at: string, max_downloads: number, resource_manifest: Array<{ id: number, title: string, content_uri: string, checksum: string, version: string }>, warning: string }> {
    return this.instance.post(`/api/earth/earning/digital-orders/${id}/deliveries`, { expires_hours: expiresHours, max_downloads: maxDownloads })
  }

  async redeemDigitalDelivery(token: string): Promise<{ success: boolean, order_id: number, product: EarthDigitalProduct, remaining_downloads: number, resources: Array<{ title: string, content_uri: string, checksum: string, version: string }> }> {
    return this.instance.post('/api/earth/earning/digital-deliveries/redeem', { token })
  }

  async revokeDigitalDelivery(id: number): Promise<{ success: boolean, delivery_id: number, status: string }> {
    return this.instance.post(`/api/earth/earning/digital-deliveries/${id}/revoke`)
  }

  async earningRoutes(): Promise<EarthEarningRoute[]> {
    return this.instance.get('/api/earth/earning/routes')
  }

  async createEarningSprint(data: { route_key: string, goal_amount?: number, target_date?: string }): Promise<EarthEarningSprintResult> {
    return this.instance.post('/api/earth/earning/sprints', data)
  }

  async startFirstIncomeExperiment(data: { weekly_hours?: number, target_amount?: number, price?: number, cost_estimate?: number } = {}): Promise<{ success: boolean, preferences: EarthEarningPreferences, offer: EarthEarningOffer, sprint: EarthEarningSprintResult }> {
    return this.instance.post('/api/earth/earning/first-income-experiment', data)
  }

  async earningOffers(status = ''): Promise<EarthEarningOffer[]> {
    return this.instance.get('/api/earth/earning/offers', { params: status ? { status } : undefined })
  }

  async addEarningOffer(data: Partial<EarthEarningOffer>): Promise<EarthEarningOffer> {
    return this.instance.post('/api/earth/earning/offers', data)
  }

  async updateEarningOffer(id: number, data: Partial<EarthEarningOffer>): Promise<EarthEarningOffer> {
    return this.instance.put(`/api/earth/earning/offers/${id}`, data)
  }

  async earningActions(status = ''): Promise<EarthEarningActionDraft[]> {
    return this.instance.get('/api/earth/earning/actions', { params: status ? { status } : undefined })
  }

  async addEarningAction(data: Partial<EarthEarningActionDraft>): Promise<EarthEarningActionDraft> {
    return this.instance.post('/api/earth/earning/actions', data)
  }

  async updateEarningAction(id: number, data: Partial<EarthEarningActionDraft>): Promise<EarthEarningActionDraft> {
    return this.instance.put(`/api/earth/earning/actions/${id}`, data)
  }

  async submitEarningAction(id: number): Promise<EarthEarningActionDraft> {
    return this.instance.post(`/api/earth/earning/actions/${id}/submit`)
  }

  async approveEarningAction(id: number, contentHash: string): Promise<EarthEarningActionDraft> {
    return this.instance.post(`/api/earth/earning/actions/${id}/approve`, { content_hash: contentHash })
  }

  async revokeEarningAction(id: number): Promise<EarthEarningActionDraft> {
    return this.instance.post(`/api/earth/earning/actions/${id}/revoke`)
  }

  async earningPreferences(): Promise<EarthEarningPreferences> {
    return this.instance.get('/api/earth/earning/preferences')
  }

  async updateEarningPreferences(data: Partial<EarthEarningPreferences>): Promise<EarthEarningPreferences> {
    return this.instance.put('/api/earth/earning/preferences', data)
  }

  async earningOpportunities(params?: { status?: string, kind?: string, limit?: number }): Promise<EarthEarningOpportunity[]> {
    return this.instance.get('/api/earth/earning/opportunities', { params })
  }

  async earningSources(): Promise<EarthEarningSource[]> {
    return this.instance.get('/api/earth/earning/sources')
  }

  async addEarningSource(data: { name?: string, url: string, kind?: string, enabled?: boolean }): Promise<EarthEarningSource> {
    return this.instance.post('/api/earth/earning/sources', data)
  }

  async updateEarningSource(id: number, data: Partial<EarthEarningSource>): Promise<EarthEarningSource> {
    return this.instance.put(`/api/earth/earning/sources/${id}`, data)
  }

  async deleteEarningSource(id: number): Promise<{ success: boolean }> {
    return this.instance.delete(`/api/earth/earning/sources/${id}`)
  }

  async syncEarningSources(sourceId?: number): Promise<{ success: boolean, created: Array<{ id: number, title: string, source: string }>, created_count: number, skipped: number, errors: Array<{ source: string, error: string }> }> {
    return this.instance.post('/api/earth/earning/sync', undefined, { params: sourceId ? { source_id: sourceId } : undefined })
  }

  async addEarningOpportunity(data: Partial<EarthEarningOpportunity>): Promise<EarthEarningOpportunity> {
    return this.instance.post('/api/earth/earning/opportunities', data)
  }

  async updateEarningOpportunity(id: number, data: Partial<EarthEarningOpportunity>): Promise<EarthEarningOpportunity> {
    return this.instance.put(`/api/earth/earning/opportunities/${id}`, data)
  }

  async convertEarningOpportunityToQuest(id: number, data?: { title?: string, deadline?: string, difficulty?: number, reward_exp?: number }): Promise<{ success: boolean, quest: EarthQuest, opportunity: EarthEarningOpportunity }> {
    return this.instance.post(`/api/earth/earning/opportunities/${id}/to-quest`, data || {})
  }

  async earningPlans(status = ''): Promise<EarthEarningPlan[]> {
    return this.instance.get('/api/earth/earning/plans', { params: status ? { status } : undefined })
  }

  async addEarningPlan(data: Partial<EarthEarningPlan>): Promise<EarthEarningPlan> {
    return this.instance.post('/api/earth/earning/plans', data)
  }

  async addEarningPlanStep(planId: number, data: Partial<EarthEarningPlanStep>): Promise<EarthEarningPlanStep> {
    return this.instance.post(`/api/earth/earning/plans/${planId}/steps`, data)
  }

  async updateEarningPlanStep(id: number, data: Partial<EarthEarningPlanStep>): Promise<EarthEarningPlanStep> {
    return this.instance.put(`/api/earth/earning/plan-steps/${id}`, data)
  }

  async convertEarningPlanStepToQuest(id: number): Promise<{ success: boolean, step: EarthEarningPlanStep, quest: EarthQuest }> {
    return this.instance.post(`/api/earth/earning/plan-steps/${id}/to-quest`)
  }

  async incomeRecords(limit = 100): Promise<EarthIncomeRecord[]> {
    return this.instance.get('/api/earth/earning/records', { params: { limit } })
  }

  async recordIncome(data: Partial<EarthIncomeRecord>): Promise<{ success: boolean, record: EarthIncomeRecord, player: EarthPlayer }> {
    return this.instance.post('/api/earth/earning/records', data)
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

  async listRealPlaces(limit = 200): Promise<EarthRealPlace[]> {
    return this.instance.get('/api/earth/world/places', { params: { limit } })
  }

  async geocodeWorldPlace(query: string): Promise<{ success: boolean, query: string, latitude: number, longitude: number, address?: Record<string, string> }> {
    return this.instance.get('/api/earth/world/geocode', { params: { query } })
  }

  async searchWorldPlaces(query: string, limit = 6): Promise<{ success: boolean, query: string, results: EarthMapSearchResult[] }> {
    return this.instance.get('/api/earth/world/search', { params: { query, limit } })
  }

  async nearbyWorldPlaces(latitude: number, longitude: number, radiusM = 1500, limit = 40): Promise<{ success: boolean, center: { latitude: number, longitude: number }, radius_m: number, results: EarthMapSearchResult[], source: string }> {
    return this.instance.get('/api/earth/world/nearby', { params: { latitude, longitude, radius_m: radiusM, limit } })
  }

  async mapFacts(placeLimit = 20, journeyLimit = 10): Promise<EarthMapFactContext> {
    return this.instance.get('/api/earth/world/facts', { params: { place_limit: placeLimit, journey_limit: journeyLimit } })
  }

  async listWorldJourneys(limit = 50): Promise<EarthMapJourney[]> {
    return this.instance.get('/api/earth/world/journeys', { params: { limit } })
  }

  async reverseGeocodeWorldPlace(latitude: number, longitude: number): Promise<EarthMapSearchResult & { success: boolean }> {
    return this.instance.get('/api/earth/world/reverse-geocode', { params: { latitude, longitude } })
  }

  async worldRoute(values: { profile: 'driving' | 'walking' | 'cycling', coordinates: [number, number][] }): Promise<EarthWorldRoute> {
    return this.instance.post('/api/earth/world/route', values)
  }

  async recordPlaceVisit(values: { name: string, latitude?: number | null, longitude?: number | null, accuracy_m?: number | null, note?: string, visited_at?: string, observed_at?: string, source?: string, confidence?: number, verification_status?: 'unverified' | 'confirmed' | 'observed', place_key?: string, provider_id?: string, display_address?: string, category?: string }): Promise<{ success: boolean, place: EarthRealPlace }> {
    return this.instance.post('/api/earth/world/places/visits', values)
  }

  async getRealPlace(placeKey: string): Promise<EarthRealPlace> {
    return this.instance.get(`/api/earth/world/places/${encodeURIComponent(placeKey)}`)
  }

  async updateRealPlace(placeKey: string, values: Partial<EarthRealPlace>): Promise<{ success: boolean, place: EarthRealPlace }> {
    return this.instance.put(`/api/earth/world/places/${encodeURIComponent(placeKey)}`, values)
  }

  async deleteRealPlace(placeKey: string): Promise<{ success: boolean }> {
    return this.instance.delete(`/api/earth/world/places/${encodeURIComponent(placeKey)}`)
  }

  async uploadRealPlaceImage(placeKey: string, file: File): Promise<{ success: boolean, image_path: string, place: EarthRealPlace }> {
    const form = new FormData(); form.append('file', file)
    return this.instance.post(`/api/earth/world/places/${encodeURIComponent(placeKey)}/image`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
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

  async queryWeather(location: string, includeForecast = true, forecastDays = 3): Promise<EarthWeatherQuery> {
    return this.instance.post('/api/earth/world/weather/query', {
      location,
      include_forecast: includeForecast,
      forecast_days: forecastDays,
    })
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

}

export default new EarthApiClient(apiPort)
