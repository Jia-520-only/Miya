<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EarthAPI, {
  type EarthEarningActionDraft,
  type EarthEarningGuidance,
  type EarthEarningOpportunity,
  type EarthEarningPlanStep,
  type EarthEarningPreferences,
  type EarthEarningRoute,
  type EarthEarningSource,
} from '@/api/earth'

type WorkspaceTab = 'today' | 'radar' | 'workbench' | 'review' | 'settings'

const tabs: Array<{ id: WorkspaceTab, label: string, glyph: string }> = [
  { id: 'today', label: '今日', glyph: '◆' },
  { id: 'radar', label: '机会', glyph: '◇' },
  { id: 'workbench', label: '执行', glyph: '▣' },
  { id: 'review', label: '复盘', glyph: '◎' },
  { id: 'settings', label: '设置', glyph: '⚙' },
]

const modelOptions = [
  ['skill_service', '技能接单'],
  ['digital_product', '数字产品'],
  ['resale', '二手交易'],
  ['content', '内容创作'],
  ['knowledge_help', '知识咨询'],
  ['automation_tool', '自动化工具'],
  ['local_service', '本地服务'],
] as const

const actionTypeLabels: Record<EarthEarningActionDraft['action_type'], string> = {
  proposal: '提案', publish: '发布', contact: '联系', upload: '上传', accept_order: '接单',
}
const actionStatusLabels: Record<EarthEarningActionDraft['status'], string> = {
  draft: '草稿', pending: '待确认', approved: '已批准', revoked: '已撤销', expired: '已过期',
}

const data = ref<EarthEarningGuidance | null>(null)
const sources = ref<EarthEarningSource[]>([])
const activeTab = ref<WorkspaceTab>('today')
const loading = ref(false)
const workingKey = ref('')
const message = ref('')
const goalAmount = ref(250)
const opportunityFilter = ref<'all' | EarthEarningOpportunity['status']>('all')
const newStepPlanId = ref<number | null>(null)
const newStepTitle = ref('')

const prefsForm = ref({
  skills: '', sellable_assets: '', preferred_kinds: '', accepted_models: modelOptions.map(([key]) => key) as string[],
  weekly_hours: 14, target_amount: 250, min_hourly_rate: 0,
  risk_tolerance: 'low' as EarthEarningPreferences['risk_tolerance'], constraints: '', primary_route: '',
})
const sourceForm = ref({ name: '', url: '' })
const opportunityForm = ref({
  title: '', source: '', url: '', kind: '技能服务', description: '', income_min: 0, income_max: 0,
  hours: 0, risk: 'unknown', confidence: 'unknown', verification_status: 'unverified', deadline: '', requirements: '',
})
const planForm = ref({ title: '', goal_amount: 100, target_date: '', notes: '' })
const incomeForm = ref<{ amount: number, cost: number, hours: number, note: string, opportunity_id: number | null }>({ amount: 0, cost: 0, hours: 0, note: '', opportunity_id: null })
const actionForm = ref<{
  action_type: EarthEarningActionDraft['action_type'], offer_id: number | null, opportunity_id: number | null,
  target: string, title: string, content: string, amount: number,
}>({ action_type: 'proposal', offer_id: null, opportunity_id: null, target: '', title: '', content: '', amount: 299 })

const visibleOpportunities = computed(() => {
  const items = data.value?.opportunities || []
  return opportunityFilter.value === 'all' ? items : items.filter(item => item.status === opportunityFilter.value)
})
const activePlans = computed(() => (data.value?.plans || []).filter(plan => plan.status === 'active'))
const focusPlan = computed(() => data.value?.focus_plan || activePlans.value[0] || null)

function csv(values: string[]) {
  return values.join(', ')
}

function csvValues(value: string) {
  return value.split(/[,，\n]/).map(item => item.trim()).filter(Boolean)
}

function setMessage(value: string) {
  message.value = value
  window.setTimeout(() => {
    if (message.value === value) message.value = ''
  }, 5000)
}

async function load() {
  loading.value = true
  try {
    const [guidance, sourceList] = await Promise.all([EarthAPI.earningGuidance(), EarthAPI.earningSources()])
    data.value = guidance
    sources.value = sourceList
    const prefs = guidance.preferences
    prefsForm.value = {
      skills: csv(prefs.skills || []), sellable_assets: csv(prefs.sellable_assets || []),
      preferred_kinds: csv(prefs.preferred_kinds || []),
      accepted_models: prefs.accepted_models?.length ? [...prefs.accepted_models] : modelOptions.map(([key]) => key),
      weekly_hours: prefs.weekly_hours ?? 14, target_amount: prefs.target_amount || 250,
      min_hourly_rate: prefs.min_hourly_rate ?? 0, risk_tolerance: prefs.risk_tolerance || 'low',
      constraints: prefs.constraints || '', primary_route: prefs.primary_route || '',
    }
    goalAmount.value = prefs.target_amount || 250
  }
  catch (error: any) {
    setMessage(error?.response?.data?.detail || '收益中枢暂时无法连接')
  }
  finally {
    loading.value = false
  }
}

function toggleModel(key: string) {
  const selected = prefsForm.value.accepted_models
  prefsForm.value.accepted_models = selected.includes(key) ? selected.filter(item => item !== key) : [...selected, key]
}

async function savePreferences(stayOnSettings = false) {
  workingKey.value = 'preferences'
  try {
    await EarthAPI.updateEarningPreferences({
      ...prefsForm.value,
      skills: csvValues(prefsForm.value.skills),
      sellable_assets: csvValues(prefsForm.value.sellable_assets),
      preferred_kinds: csvValues(prefsForm.value.preferred_kinds),
    })
    await load()
    setMessage('赚钱档案已保存，弥娅重新排好了推荐路线')
    if (!stayOnSettings) activeTab.value = 'today'
  }
  catch (error: any) { setMessage(error?.response?.data?.detail || '档案保存失败') }
  finally { workingKey.value = '' }
}

async function startSprint(route: EarthEarningRoute) {
  workingKey.value = `route-${route.key}`
  try {
    const result = await EarthAPI.createEarningSprint({ route_key: route.key, goal_amount: goalAmount.value })
    await load()
    activeTab.value = 'workbench'
    setMessage(result.created ? `「${route.name}」7 天实验已建立，第一步也放进委托板了` : `「${route.name}」实验已经在进行中`)
  }
  catch (error: any) { setMessage(error?.response?.data?.detail || '建立实验失败') }
  finally { workingKey.value = '' }
}

async function startFirstIncomeExperiment() {
  workingKey.value = 'first-income'
  try {
    const result = await EarthAPI.startFirstIncomeExperiment({ weekly_hours: 14, target_amount: 250 })
    await load()
    activeTab.value = 'workbench'
    setMessage(`首单实验已建立：${result.offer.title}，报价 ¥${result.offer.price}`)
  }
  catch (error: any) { setMessage(error?.response?.data?.detail || '首单实验初始化失败') }
  finally { workingKey.value = '' }
}

async function addActionDraft() {
  if (!actionForm.value.title.trim() || !actionForm.value.content.trim()) return
  workingKey.value = 'action-create'
  try {
    await EarthAPI.addEarningAction(actionForm.value)
    actionForm.value = { action_type: 'proposal', offer_id: null, opportunity_id: null, target: '', title: '', content: '', amount: 299 }
    await load()
    setMessage('外部动作草稿已保存；目前没有批准、发送或执行')
  }
  catch (error: any) { setMessage(error?.response?.data?.detail || '审批草稿创建失败') }
  finally { workingKey.value = '' }
}

async function submitAction(action: EarthEarningActionDraft) {
  try { await EarthAPI.submitEarningAction(action.id); await load(); setMessage('草稿已提交，等待你逐次确认') }
  catch (error: any) { setMessage(error?.response?.data?.detail || '草稿提交失败') }
}

async function approveAction(action: EarthEarningActionDraft) {
  if (!action.content_hash) return
  try { await EarthAPI.approveEarningAction(action.id, action.content_hash); await load(); setMessage('已批准当前版本 30 分钟；批准不等于发送') }
  catch (error: any) { setMessage(error?.response?.data?.detail || '批准失败，请刷新后重新核对') }
}

async function revokeAction(action: EarthEarningActionDraft) {
  try { await EarthAPI.revokeEarningAction(action.id); await load(); setMessage('批准或申请已撤销') }
  catch (error: any) { setMessage(error?.response?.data?.detail || '撤销失败') }
}

async function updateStatus(item: EarthEarningOpportunity, status: EarthEarningOpportunity['status']) {
  try { await EarthAPI.updateEarningOpportunity(item.id, { status }); await load() }
  catch (error: any) { setMessage(error?.response?.data?.detail || '状态更新失败') }
}

async function updateVerification(item: EarthEarningOpportunity, verification_status: EarthEarningOpportunity['verification_status']) {
  try {
    await EarthAPI.updateEarningOpportunity(item.id, { verification_status, last_checked_at: new Date().toISOString() })
    await load()
    setMessage(verification_status === 'verified' ? '已标记为核验通过' : '已记录核验结果')
  }
  catch (error: any) { setMessage(error?.response?.data?.detail || '核验状态更新失败') }
}

async function convertToQuest(item: EarthEarningOpportunity) {
  if (item.quest_id) return
  try { await EarthAPI.convertEarningOpportunityToQuest(item.id); await load(); setMessage(`「${item.title}」已放入委托板`) }
  catch (error: any) { setMessage(error?.response?.data?.detail || '转换委托失败') }
}

async function addOpportunity() {
  if (!opportunityForm.value.title.trim()) return
  try {
    await EarthAPI.addEarningOpportunity(opportunityForm.value as Partial<EarthEarningOpportunity>)
    opportunityForm.value = { title: '', source: '', url: '', kind: '技能服务', description: '', income_min: 0, income_max: 0, hours: 0, risk: 'unknown', confidence: 'unknown', verification_status: 'unverified', deadline: '', requirements: '' }
    await load(); setMessage('情报已进入待核验队列')
  }
  catch (error: any) { setMessage(error?.response?.data?.detail || '收录失败') }
}

async function addPlan() {
  if (!planForm.value.title.trim()) return
  try {
    await EarthAPI.addEarningPlan(planForm.value)
    planForm.value = { title: '', goal_amount: 100, target_date: '', notes: '' }
    await load(); setMessage('自定义收益计划已建立')
  }
  catch (error: any) { setMessage(error?.response?.data?.detail || '计划建立失败') }
}

async function addStep(planId: number) {
  if (!newStepTitle.value.trim()) return
  try {
    await EarthAPI.addEarningPlanStep(planId, { title: newStepTitle.value.trim() })
    newStepTitle.value = ''; newStepPlanId.value = null; await load()
  }
  catch (error: any) { setMessage(error?.response?.data?.detail || '阶段添加失败') }
}

async function toggleStep(step: EarthEarningPlanStep) {
  try { await EarthAPI.updateEarningPlanStep(step.id, { status: step.status === 'done' ? 'pending' : 'done' }); await load() }
  catch (error: any) { setMessage(error?.response?.data?.detail || '阶段更新失败') }
}

async function convertStep(step: EarthEarningPlanStep) {
  if (step.quest_id) return
  try { await EarthAPI.convertEarningPlanStepToQuest(step.id); await load(); setMessage(`「${step.title}」已放入委托板`) }
  catch (error: any) { setMessage(error?.response?.data?.detail || '阶段转委托失败') }
}

async function recordIncome() {
  try {
    await EarthAPI.recordIncome(incomeForm.value)
    incomeForm.value = { amount: 0, cost: 0, hours: 0, note: '', opportunity_id: null }
    await load(); setMessage('真实收入、成本和耗时已记入复盘')
  }
  catch (error: any) { setMessage(error?.response?.data?.detail || '收入记录失败') }
}

async function addSource() {
  if (!sourceForm.value.url.trim()) return
  try { await EarthAPI.addEarningSource(sourceForm.value); sourceForm.value = { name: '', url: '' }; await load(); setMessage('公开信息源已保存') }
  catch (error: any) { setMessage(error?.response?.data?.detail || '信息源保存失败') }
}

async function syncSources() {
  workingKey.value = 'sync'
  try {
    const result = await EarthAPI.syncEarningSources()
    await load(); setMessage(`同步完成：新增 ${result.created_count} 条，跳过 ${result.skipped} 条${result.errors.length ? `，失败 ${result.errors.length} 个来源` : ''}`)
  }
  catch (error: any) { setMessage(error?.response?.data?.detail || '公开信息同步失败') }
  finally { workingKey.value = '' }
}

async function toggleSource(source: EarthEarningSource) {
  try { await EarthAPI.updateEarningSource(source.id, { enabled: !Boolean(source.enabled) }); await load() }
  catch (error: any) { setMessage(error?.response?.data?.detail || '信息源状态更新失败') }
}

async function deleteSource(source: EarthEarningSource) {
  try { await EarthAPI.deleteEarningSource(source.id); await load(); setMessage(`已移除信息源「${source.name}」`) }
  catch (error: any) { setMessage(error?.response?.data?.detail || '信息源移除失败') }
}

onMounted(load)
</script>

<template>
  <div class="earning-view">
    <header class="earning-header">
      <div class="title-block">
        <span class="eyebrow">EARTH ONLINE / INCOME LAB</span>
        <div class="title-line"><h1>收益中枢</h1><span class="assist-state"><i /> 弥娅辅助已接入</span></div>
        <p>{{ data?.brief || '把能做的事变成一次可验证的收入实验。' }}</p>
      </div>
      <button class="icon-button" type="button" title="刷新收益数据" :disabled="loading" @click="load">↻</button>
    </header>

    <nav class="workspace-tabs" aria-label="收益工作区">
      <button v-for="tab in tabs" :key="tab.id" type="button" :class="{ active: activeTab === tab.id }" @click="activeTab = tab.id">
        <span>{{ tab.glyph }}</span>{{ tab.label }}
        <b v-if="tab.id === 'radar' && data?.pipeline?.inbox">{{ data.pipeline.inbox }}</b>
      </button>
    </nav>

    <div v-if="message" class="notice" role="status">{{ message }}<button type="button" aria-label="关闭提示" @click="message = ''">×</button></div>

    <main class="workspace">
      <template v-if="activeTab === 'today'">
        <section class="metrics" aria-label="收益概览">
          <div><span>真实净收入</span><strong>¥{{ data?.totals.net_income?.toFixed(2) || '0.00' }}</strong></div>
          <div><span>实际时薪</span><strong>¥{{ data?.totals.effective_hourly_rate?.toFixed(2) || '0.00' }}</strong></div>
          <div><span>进行中实验</span><strong>{{ data?.totals.active_plan_count || 0 }}</strong></div>
          <div><span>已尝试 / 已成交</span><strong>{{ data?.pipeline?.applied || 0 }} / {{ data?.pipeline?.won || 0 }}</strong></div>
        </section>

        <section v-if="!data?.profile_ready" class="onboarding-band">
          <div class="onboarding-copy">
            <span class="section-kicker">STEP 01 · 建立赚钱档案</span>
            <h2>先让弥娅知道，你手里有什么</h2>
            <p>不用先确定职业方向。写下会做的事、可出售的资源和现实限制，系统会从所有可接受路线里挑低成本实验。</p>
          </div>
          <form class="profile-form" @submit.prevent="savePreferences(false)">
            <label><span>能直接使用的技能</span><input v-model="prefsForm.skills" placeholder="例如：Python、写作、剪辑、摄影、英语"></label>
            <label><span>可出售或可复用的资源</span><input v-model="prefsForm.sellable_assets" placeholder="例如：闲置数码、模板、行业经验、作品集"></label>
            <div class="form-row">
              <label><span>每周可投入</span><div class="input-unit"><input v-model.number="prefsForm.weekly_hours" type="number" min="0.5" step="0.5"><em>小时</em></div></label>
              <label><span>第一阶段目标</span><div class="input-unit"><input v-model.number="prefsForm.target_amount" type="number" min="1" step="10"><em>元</em></div></label>
            </div>
            <label><span>暂时不能接受的限制</span><input v-model="prefsForm.constraints" placeholder="例如：不露脸、不垫资、只做线上、晚上有空"></label>
            <button class="primary-button" :disabled="workingKey === 'preferences'">{{ workingKey === 'preferences' ? '正在建立档案…' : '保存档案并生成路线' }}</button>
          </form>
        </section>

        <template v-else>
          <section class="today-layout">
            <div class="focus-panel">
              <div class="panel-heading"><div><span class="section-kicker">NEXT ACTION</span><h2>今天只推进这一件事</h2></div><span v-if="focusPlan" class="plan-tag">{{ focusPlan.route_key ? '7 天实验' : '收益计划' }}</span></div>
              <template v-if="data?.next_action">
                <div class="next-action"><span class="action-index">01</span><div><strong>{{ data.next_action.title }}</strong><p>{{ data.next_action.description || '完成这一小步，再决定下一步。' }}</p></div></div>
                <div v-if="focusPlan" class="focus-progress"><span><i :style="{ width: `${focusPlan.progress_percent || 0}%` }" /></span><small>{{ focusPlan.completed_steps || 0 }}/{{ focusPlan.steps?.length || 0 }} · 截止 {{ focusPlan.target_date || '未设置' }}</small></div>
                <button class="secondary-button" :disabled="!!data.next_action.quest_id" @click="convertStep(data.next_action)">{{ data.next_action.quest_id ? '已同步到委托板' : '放入地球 Online 委托板' }}</button>
              </template>
              <div v-else class="empty-state"><b>现在没有待执行步骤</b><p>从右侧选择一条路线，弥娅会把第一步放进委托板。</p></div>
            </div>

            <aside class="miya-brief">
              <span class="miya-mark">M</span>
              <div><span class="section-kicker">MIYA BRIEF</span><h2>弥娅的判断</h2><p>{{ data?.brief }}</p></div>
            </aside>
          </section>

          <section class="route-section">
            <div class="section-heading"><div><span class="section-kicker">LOW-COST EXPERIMENTS</span><h2>推荐的第一笔收入路线</h2></div><div class="heading-actions"><label class="goal-control">本轮目标 <span>¥</span><input v-model.number="goalAmount" type="number" min="201" step="10"></label><button class="primary-button" :disabled="workingKey === 'first-income'" @click="startFirstIncomeExperiment">{{ workingKey === 'first-income' ? '初始化中…' : '启动 ¥250+ 首单实验' }}</button></div></div>
            <div class="route-grid">
              <article v-for="route in data?.routes?.slice(0, 4)" :key="route.key" class="route-card">
                <div class="route-top"><span class="route-icon">{{ route.icon }}</span><span class="fit-score">匹配 {{ route.fit_score }}</span></div>
                <h3>{{ route.name }}</h3><p>{{ route.summary }}</p>
                <dl><div><dt>首笔周期</dt><dd>{{ route.first_revenue_days }}</dd></div><div><dt>启动成本</dt><dd>{{ route.cash_cost }}</dd></div></dl>
                <small>{{ route.fit_reasons.join(' · ') }}</small>
                <button class="route-button" :disabled="workingKey === `route-${route.key}`" @click="startSprint(route)">{{ workingKey === `route-${route.key}` ? '正在创建…' : '开始 7 天实验' }}</button>
              </article>
            </div>
          </section>
        </template>
      </template>

      <template v-else-if="activeTab === 'radar'">
        <section class="section-heading radar-heading"><div><span class="section-kicker">OPPORTUNITY PIPELINE</span><h2>机会雷达</h2><p>公开信息先进入待核验队列，确认关键条件后再投入时间。</p></div><div class="heading-actions"><select v-model="opportunityFilter"><option value="all">全部状态</option><option value="inbox">待评估</option><option value="shortlisted">候选</option><option value="applied">已尝试</option><option value="won">已成交</option><option value="closed">已关闭</option></select><button class="secondary-button" @click="syncSources">{{ workingKey === 'sync' ? '同步中…' : '同步信息源' }}</button></div></section>
        <section class="pipeline-strip"><div v-for="(label, key) in { inbox: '待评估', shortlisted: '候选', applied: '已尝试', won: '已成交', closed: '已关闭' }" :key="key"><strong>{{ data?.pipeline?.[key as keyof typeof data.pipeline] || 0 }}</strong><span>{{ label }}</span></div></section>
        <div v-if="visibleOpportunities.length" class="opportunity-list">
          <article v-for="item in visibleOpportunities" :key="item.id" class="opportunity-row">
            <div class="opportunity-score"><strong>{{ Math.round(item.fit_score || 0) }}</strong><span>匹配</span></div>
            <div class="opportunity-main"><div class="opportunity-title"><h3>{{ item.title }}</h3><span :class="`verification ${item.verification_status || 'unverified'}`">{{ { unverified: '待核验', checking: '核验中', verified: '已核验', rejected: '未通过' }[item.verification_status || 'unverified'] }}</span></div><p>{{ item.description || '暂无描述，建议先打开来源核对需求和付款条件。' }}</p><small>{{ item.source || '手动收录' }} · {{ item.kind }} · 预估 ¥{{ item.income_min }}-{{ item.income_max }} · {{ item.hours || '?' }}h<span v-if="item.deadline"> · 截止 {{ item.deadline }}</span></small><div class="reason-line">{{ item.fit_reasons?.join(' · ') }}</div></div>
            <div class="opportunity-actions"><a v-if="item.url" :href="item.url" target="_blank" rel="noopener noreferrer">查看来源</a><select :value="item.verification_status || 'unverified'" @change="updateVerification(item, ($event.target as HTMLSelectElement).value as EarthEarningOpportunity['verification_status'])"><option value="unverified">待核验</option><option value="checking">核验中</option><option value="verified">核验通过</option><option value="rejected">核验未通过</option></select><select :value="item.status" @change="updateStatus(item, ($event.target as HTMLSelectElement).value as EarthEarningOpportunity['status'])"><option value="inbox">待评估</option><option value="shortlisted">候选</option><option value="applied">已尝试</option><option value="won">已成交</option><option value="closed">已关闭</option></select><button class="text-button" :disabled="!!item.quest_id" @click="convertToQuest(item)">{{ item.quest_id ? '已在委托板' : '转为委托' }}</button></div>
          </article>
        </div>
        <div v-else class="large-empty"><span>◇</span><h3>还没有符合当前筛选的机会</h3><p>可以同步公开信息源，也可以把看到的真实需求手动放进待核验队列。</p></div>
        <details class="utility-drawer"><summary>手动收录一条机会</summary><form class="drawer-form" @submit.prevent="addOpportunity"><div class="form-row"><label><span>机会标题</span><input v-model="opportunityForm.title" required></label><label><span>类型</span><input v-model="opportunityForm.kind"></label></div><div class="form-row"><label><span>来源名称</span><input v-model="opportunityForm.source"></label><label><span>公开链接</span><input v-model="opportunityForm.url" type="url"></label></div><label><span>描述</span><textarea v-model="opportunityForm.description"></textarea></label><label><span>准入条件</span><textarea v-model="opportunityForm.requirements"></textarea></label><div class="form-row compact"><label><span>最低收益</span><input v-model.number="opportunityForm.income_min" type="number" min="0"></label><label><span>最高收益</span><input v-model.number="opportunityForm.income_max" type="number" min="0"></label><label><span>预计小时</span><input v-model.number="opportunityForm.hours" type="number" min="0" step="0.5"></label><label><span>截止日期</span><input v-model="opportunityForm.deadline" type="date"></label></div><button class="primary-button">放入待核验队列</button></form></details>
      </template>

      <template v-else-if="activeTab === 'workbench'">
        <section class="section-heading"><div><span class="section-kicker">EXECUTION WORKBENCH</span><h2>执行工坊</h2><p>计划是收入实验，委托板负责每天执行；对外动作进入审批箱，不会自动发送。</p></div><button class="primary-button" :disabled="workingKey === 'first-income'" @click="startFirstIncomeExperiment">{{ workingKey === 'first-income' ? '初始化中…' : '启动首单实验' }}</button></section>
        <section class="offer-section">
          <div class="subsection-heading"><div><span class="section-kicker">SELLABLE OFFER</span><h3>可售服务</h3></div><span>{{ data?.totals.active_offer_count || 0 }} 个启用</span></div>
          <div v-if="data?.offers?.length" class="offer-grid">
            <article v-for="offer in data.offers" :key="offer.id" class="offer-card">
              <header><div><span>{{ offer.status }} · {{ offer.delivery_days }} 天交付</span><h3>{{ offer.title }}</h3></div><strong>¥{{ offer.price }}</strong></header>
              <p>{{ offer.problem }}</p><dl><div><dt>交付</dt><dd>{{ offer.deliverables }}</dd></div><div><dt>边界</dt><dd>{{ offer.scope }}</dd></div></dl><small>成本估计 ¥{{ offer.cost_estimate }} · {{ offer.revisions }} 次修改</small>
            </article>
          </div>
          <div v-else class="empty-state"><b>还没有可售服务</b><p>启动首单实验会建立一张 ¥299 的 48 小时自动化微服务卡。</p></div>
        </section>
        <div v-if="data?.plans?.length" class="plan-list">
          <article v-for="plan in data.plans" :key="plan.id" class="plan-panel" :class="{ muted: plan.status !== 'active' }">
            <header><div><span>{{ plan.is_sprint ? '7 天实验' : '自定义计划' }} · {{ plan.status }}</span><h3>{{ plan.title }}</h3><p>{{ plan.notes }}</p></div><div class="plan-goal"><strong>¥{{ plan.goal_amount }}</strong><span>目标 · {{ plan.target_date || '无截止日期' }}</span></div></header>
            <div class="plan-progress"><i :style="{ width: `${plan.progress_percent || 0}%` }" /></div>
            <div class="step-list"><div v-for="(step, index) in plan.steps" :key="step.id" class="step-row"><button class="step-check" :class="{ done: step.status === 'done' }" :aria-label="step.status === 'done' ? '标记未完成' : '标记完成'" @click="toggleStep(step)">{{ step.status === 'done' ? '✓' : index + 1 }}</button><div><strong :class="{ crossed: step.status === 'done' }">{{ step.title }}</strong><p>{{ step.description }}</p></div><button class="text-button" :disabled="!!step.quest_id" @click="convertStep(step)">{{ step.quest_id ? '委托已同步' : '转为委托' }}</button></div></div>
            <form v-if="newStepPlanId === plan.id" class="inline-form" @submit.prevent="addStep(plan.id)"><input v-model="newStepTitle" placeholder="新增一个可完成的小步骤" autofocus><button>添加</button><button type="button" @click="newStepPlanId = null">取消</button></form><button v-else class="add-link" @click="newStepPlanId = plan.id; newStepTitle = ''">＋ 添加阶段</button>
          </article>
        </div>
        <div v-else class="large-empty"><span>▣</span><h3>还没有执行中的实验</h3><p>回到“今日”选择一条推荐路线，第一步会自动出现在这里和委托板。</p><button class="secondary-button" @click="activeTab = 'today'">查看推荐路线</button></div>
        <section class="approval-section">
          <div class="subsection-heading"><div><span class="section-kicker">HUMAN APPROVAL</span><h3>外部动作审批箱</h3></div><span>{{ data?.totals.pending_approval_count || 0 }} 个待确认</span></div>
          <p class="boundary-note">批准只绑定当前内容 30 分钟，且不等于发送。系统不会执行付款、转账、提现、退款，也不会自动输入验证码或支付密码。</p>
          <div v-if="data?.action_drafts?.length" class="approval-list">
            <article v-for="action in data.action_drafts" :key="action.id" class="approval-row">
              <div class="approval-main"><header><span :class="`approval-status ${action.status}`">{{ actionStatusLabels[action.status] }}</span><strong>{{ action.title }}</strong><small>{{ actionTypeLabels[action.action_type] }} · {{ action.target || '未指定对象' }}</small></header><p>{{ action.content }}</p><code v-if="action.content_hash">{{ action.content_hash }}</code></div>
              <div class="approval-actions"><button v-if="['draft', 'revoked', 'expired'].includes(action.status)" class="secondary-button" @click="submitAction(action)">提交确认</button><button v-if="action.status === 'pending'" class="primary-button" @click="approveAction(action)">批准当前版本</button><button v-if="['pending', 'approved'].includes(action.status)" class="text-button danger" @click="revokeAction(action)">撤销</button></div>
            </article>
          </div>
          <div v-else class="empty-state"><b>审批箱为空</b><p>弥娅可以起草提案和联系内容，但只有你能逐次批准。</p></div>
        </section>
        <details class="utility-drawer"><summary>准备一份外部动作草稿</summary><form class="drawer-form" @submit.prevent="addActionDraft"><div class="form-row"><label><span>动作类型</span><select v-model="actionForm.action_type"><option value="proposal">提案</option><option value="publish">发布</option><option value="contact">联系</option><option value="upload">上传</option><option value="accept_order">接单</option></select></label><label><span>关联服务</span><select v-model.number="actionForm.offer_id"><option :value="null">不关联</option><option v-for="offer in data?.offers" :key="offer.id" :value="offer.id">{{ offer.title }}</option></select></label><label><span>报价</span><div class="input-unit"><input v-model.number="actionForm.amount" type="number" min="0"><em>元</em></div></label></div><label><span>目标对象或页面</span><input v-model="actionForm.target" placeholder="公开需求链接、客户名称或平台页面"></label><label><span>标题</span><input v-model="actionForm.title" required></label><label><span>完整内容</span><textarea v-model="actionForm.content" required></textarea></label><button class="primary-button" :disabled="workingKey === 'action-create'">保存为草稿</button></form></details>
        <details class="utility-drawer"><summary>建立自定义收益计划</summary><form class="drawer-form" @submit.prevent="addPlan"><label><span>计划名称</span><input v-model="planForm.title" required></label><div class="form-row"><label><span>目标金额</span><input v-model.number="planForm.goal_amount" type="number" min="0"></label><label><span>目标日期</span><input v-model="planForm.target_date" type="date"></label></div><label><span>说明</span><textarea v-model="planForm.notes"></textarea></label><button class="primary-button">建立计划</button></form></details>
      </template>

      <template v-else-if="activeTab === 'review'">
        <section class="section-heading"><div><span class="section-kicker">REAL RESULTS</span><h2>收益复盘</h2><p>只记录真实到账、真实成本和实际投入时间，让下一轮推荐越来越准确。</p></div></section>
        <section class="review-layout"><form class="income-form" @submit.prevent="recordIncome"><h3>记录一笔真实收入</h3><div class="money-input"><span>¥</span><input v-model.number="incomeForm.amount" type="number" min="0.01" step="0.01" placeholder="0.00" required></div><div class="form-row"><label><span>直接成本</span><input v-model.number="incomeForm.cost" type="number" min="0" step="0.01"></label><label><span>实际耗时</span><div class="input-unit"><input v-model.number="incomeForm.hours" type="number" min="0" step="0.25"><em>小时</em></div></label></div><label><span>关联机会</span><select v-model.number="incomeForm.opportunity_id"><option :value="null">不关联机会</option><option v-for="item in data?.opportunities" :key="item.id" :value="item.id">{{ item.title }}</option></select></label><label><span>备注</span><input v-model="incomeForm.note" placeholder="平台、项目、客户或到账方式"></label><button class="primary-button">记入真实收益</button></form><div class="result-ledger"><header><h3>最近记录</h3><span>净收入 = 收入 - 直接成本</span></header><div v-if="data?.income_records?.length"><div v-for="record in data.income_records" :key="record.id" class="ledger-row"><div><strong>¥{{ (record.amount - record.cost).toFixed(2) }}</strong><span>净收入</span></div><p>{{ record.note || '未填写备注' }}</p><small>{{ record.recorded_at?.slice(0, 10) }} · {{ record.hours }}h · 成本 ¥{{ record.cost }}</small></div></div><div v-else class="empty-state"><b>还没有真实收入记录</b><p>第一次到账后再来这里。零收入不需要为了“完成任务”而记录。</p></div></div></section>
      </template>

      <template v-else>
        <section class="section-heading"><div><span class="section-kicker">PROFILE & SOURCES</span><h2>档案与信息源</h2><p>这些设置决定弥娅如何筛选机会，不会触发任何外部操作。</p></div></section>
        <section class="settings-layout"><form class="settings-panel" @submit.prevent="savePreferences(true)"><h3>赚钱档案</h3><label><span>技能</span><input v-model="prefsForm.skills" placeholder="用逗号分隔"></label><label><span>可出售资源</span><input v-model="prefsForm.sellable_assets" placeholder="闲置物品、作品、模板、经验"></label><div class="model-selector"><span>可接受路线</span><button v-for="([key, label]) in modelOptions" :key="key" type="button" :class="{ selected: prefsForm.accepted_models.includes(key) }" @click="toggleModel(key)">{{ prefsForm.accepted_models.includes(key) ? '✓ ' : '' }}{{ label }}</button></div><div class="form-row"><label><span>每周时间</span><div class="input-unit"><input v-model.number="prefsForm.weekly_hours" type="number" min="0" step="0.5"><em>小时</em></div></label><label><span>阶段目标</span><div class="input-unit"><input v-model.number="prefsForm.target_amount" type="number" min="1" step="10"><em>元</em></div></label></div><div class="form-row"><label><span>最低期望时薪</span><input v-model.number="prefsForm.min_hourly_rate" type="number" min="0"></label><label><span>风险偏好</span><select v-model="prefsForm.risk_tolerance"><option value="low">低风险优先</option><option value="medium">可接受中风险</option><option value="high">愿意承担高风险</option></select></label></div><label><span>现实限制</span><textarea v-model="prefsForm.constraints"></textarea></label><button class="primary-button" :disabled="workingKey === 'preferences'">保存档案</button></form><div class="settings-panel"><div class="source-title"><div><h3>公开信息源</h3><p>仅支持 RSS / Atom；同步后仍需核验关键条件。</p></div><button class="secondary-button" :disabled="workingKey === 'sync'" @click="syncSources">同步全部</button></div><form class="source-form" @submit.prevent="addSource"><input v-model="sourceForm.name" placeholder="来源名称"><input v-model="sourceForm.url" type="url" placeholder="https://example.com/feed.xml" required><button>添加</button></form><div v-if="sources.length" class="source-list"><div v-for="source in sources" :key="source.id" class="source-row"><i :class="{ off: !Boolean(source.enabled) }" /><div><strong>{{ source.name }}</strong><span>{{ source.last_error || source.url }}</span></div><button @click="toggleSource(source)">{{ Boolean(source.enabled) ? '暂停' : '启用' }}</button><button class="danger" @click="deleteSource(source)">移除</button></div></div><div v-else class="empty-state"><b>还没有公开信息源</b><p>初版不会替你登录或抓取受限平台；可以先用手动情报和推荐路线开始。</p></div></div></section>
        <section class="automation-boundary"><div><span>弥娅可以自动</span><p>{{ data?.automation?.automatic?.join(' · ') }}</p></div><div><span>必须由你确认</span><p>{{ data?.automation?.requires_confirmation?.join(' · ') }}</p></div><div><span>永久禁止自动化</span><p>{{ data?.automation?.blocked?.join(' · ') }}</p></div></section>
      </template>
    </main>

    <footer>{{ data?.boundary || '建议不保证收益；任何外部操作都应由你确认。' }}</footer>
  </div>
</template>

<style scoped>
.earning-view{--gold:#e8d5a3;--green:#9fe3c0;--red:#e59393;--line:rgba(162,245,238,.14);height:100%;overflow:auto;box-sizing:border-box;color:var(--miya-text,#eef5f4);background:rgba(5,12,18,.95);letter-spacing:0}.earning-header{max-width:1240px;margin:auto;padding:1.55rem 1.4rem 1rem;display:flex;align-items:flex-start;justify-content:space-between;gap:1rem}.eyebrow,.section-kicker{font-size:.6rem;color:var(--earth-accent-light,#a2f5ee);letter-spacing:.12em}.title-line{display:flex;align-items:center;gap:.9rem}.title-line h1{margin:.22rem 0;font-size:1.65rem;font-weight:560;letter-spacing:0}.title-block p{margin:0;color:rgba(238,245,244,.58);font-size:.78rem}.assist-state{font-size:.62rem;color:var(--green);display:flex;align-items:center;gap:.35rem}.assist-state i{width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green)}button,input,select,textarea{font:inherit;letter-spacing:0}.icon-button{width:34px;height:34px;padding:0;border:1px solid var(--line);background:rgba(120,207,209,.06);color:var(--earth-accent-light,#a2f5ee);cursor:pointer}.workspace-tabs{position:sticky;top:0;z-index:20;display:flex;max-width:1240px;margin:auto;padding:0 1.4rem;border-bottom:1px solid var(--line);background:rgba(5,12,18,.94);backdrop-filter:blur(14px)}.workspace-tabs button{position:relative;height:42px;padding:0 1rem;border:0;background:transparent;color:rgba(238,245,244,.5);cursor:pointer;font-size:.72rem}.workspace-tabs button span{margin-right:.35rem}.workspace-tabs button b{margin-left:.35rem;padding:.08rem .28rem;border-radius:8px;background:rgba(229,147,147,.14);color:var(--red);font-size:.55rem}.workspace-tabs button.active{color:var(--earth-accent-light,#a2f5ee)}.workspace-tabs button.active::after{content:'';position:absolute;left:.7rem;right:.7rem;bottom:-1px;height:2px;background:var(--earth-accent-light,#a2f5ee)}.notice{position:sticky;top:48px;z-index:19;max-width:1180px;margin:.7rem auto 0;padding:.58rem .75rem;display:flex;justify-content:space-between;border:1px solid rgba(232,213,163,.25);background:rgba(32,30,23,.96);color:var(--gold);font-size:.7rem}.notice button{border:0;background:transparent;color:inherit;cursor:pointer}.workspace{max-width:1240px;margin:auto;padding:1rem 1.4rem 2.5rem;box-sizing:border-box}.metrics{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);background:rgba(9,20,28,.58)}.metrics div{padding:.85rem 1rem;border-right:1px solid var(--line)}.metrics div:last-child{border-right:0}.metrics span,.plan-goal span{display:block;color:rgba(238,245,244,.45);font-size:.62rem}.metrics strong{display:block;margin-top:.22rem;font-size:1.25rem;color:var(--gold);font-weight:560}.onboarding-band{margin-top:1rem;display:grid;grid-template-columns:minmax(260px,.8fr) minmax(360px,1.2fr);gap:2rem;padding:1.5rem;border:1px solid var(--line);background:rgba(9,20,28,.62)}.onboarding-copy h2,.section-heading h2,.panel-heading h2,.miya-brief h2,.route-section h2{margin:.28rem 0;font-size:1.05rem;font-weight:560}.onboarding-copy p,.section-heading p{max-width:480px;margin:.5rem 0;color:rgba(238,245,244,.58);font-size:.74rem;line-height:1.65}.profile-form,.drawer-form,.settings-panel,.income-form{display:flex;flex-direction:column;gap:.7rem}label>span,.model-selector>span{display:block;margin-bottom:.3rem;color:rgba(238,245,244,.55);font-size:.62rem}input,select,textarea{width:100%;box-sizing:border-box;border:1px solid rgba(162,245,238,.18);border-radius:2px;background:rgba(0,0,0,.24);color:inherit;padding:.58rem .65rem;font-size:.72rem;outline:none}input:focus,select:focus,textarea:focus{border-color:rgba(162,245,238,.52)}textarea{min-height:72px;resize:vertical}.form-row{display:flex;gap:.65rem}.form-row>label{flex:1;min-width:0}.form-row.compact>label{min-width:110px}.input-unit{position:relative}.input-unit input{padding-right:3rem}.input-unit em{position:absolute;right:.65rem;top:50%;transform:translateY(-50%);font-size:.6rem;color:rgba(238,245,244,.4);font-style:normal}.primary-button,.secondary-button,.route-button{border:1px solid rgba(162,245,238,.38);background:rgba(120,207,209,.13);color:var(--earth-accent-light,#a2f5ee);padding:.62rem .85rem;cursor:pointer;font-size:.7rem}.primary-button{background:var(--earth-accent-deep,#4f9fa5);color:#061015;border-color:transparent;font-weight:650}.primary-button:disabled,.secondary-button:disabled,.route-button:disabled,.text-button:disabled{opacity:.45;cursor:default}.today-layout{display:grid;grid-template-columns:1.5fr .75fr;gap:.8rem;margin-top:.8rem}.focus-panel,.miya-brief,.route-card,.plan-panel,.income-form,.result-ledger,.settings-panel{border:1px solid var(--line);background:rgba(9,20,28,.58)}.focus-panel{padding:1rem}.panel-heading,.section-heading{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start}.plan-tag{padding:.24rem .45rem;border:1px solid rgba(232,213,163,.24);color:var(--gold);font-size:.58rem}.next-action{display:flex;gap:.8rem;margin:1rem 0;padding:.9rem 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.action-index{font-size:1.25rem;color:rgba(162,245,238,.35)}.next-action strong{font-size:.9rem}.next-action p,.miya-brief p,.route-card p,.step-row p,.plan-panel header p{margin:.3rem 0 0;color:rgba(238,245,244,.55);font-size:.7rem;line-height:1.55}.focus-progress{display:flex;align-items:center;gap:.8rem;margin-bottom:.8rem}.focus-progress>span{flex:1;height:3px;background:rgba(162,245,238,.1)}.focus-progress i,.plan-progress i{display:block;height:100%;background:var(--gold)}.focus-progress small{font-size:.58rem;color:rgba(238,245,244,.4)}.miya-brief{display:flex;gap:.8rem;padding:1rem;border-left:2px solid var(--earth-accent-light,#a2f5ee)}.miya-mark{display:grid;place-items:center;flex:0 0 30px;height:30px;border:1px solid rgba(162,245,238,.4);color:var(--earth-accent-light,#a2f5ee);font-size:.75rem}.route-section{margin-top:1.25rem}.section-heading{margin-bottom:.75rem}.goal-control{display:flex;align-items:center;gap:.25rem;color:rgba(238,245,244,.5);font-size:.65rem}.goal-control span{color:var(--gold)}.goal-control input{width:72px;padding:.35rem}.route-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.65rem}.route-card{display:flex;flex-direction:column;min-height:255px;padding:.9rem}.route-top{display:flex;align-items:center;justify-content:space-between}.route-icon{font-size:1.15rem;color:var(--earth-accent-light,#a2f5ee)}.fit-score{font-size:.58rem;color:var(--green)}.route-card h3{margin:.6rem 0 .15rem;font-size:.88rem}.route-card dl{display:flex;margin:.8rem 0}.route-card dl div{flex:1}.route-card dt{font-size:.55rem;color:rgba(238,245,244,.38)}.route-card dd{margin:.16rem 0 0;font-size:.65rem;color:var(--gold)}.route-card small{display:block;margin-bottom:.8rem;color:rgba(159,227,192,.72);font-size:.58rem;line-height:1.45}.route-button{margin-top:auto}.radar-heading{align-items:center}.heading-actions{display:flex;gap:.5rem}.heading-actions select{width:auto;min-width:110px}.pipeline-strip{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid var(--line);margin-bottom:.8rem}.pipeline-strip div{padding:.65rem;text-align:center;border-right:1px solid var(--line)}.pipeline-strip div:last-child{border-right:0}.pipeline-strip strong{display:block;color:var(--gold)}.pipeline-strip span{font-size:.58rem;color:rgba(238,245,244,.45)}.opportunity-list{border-top:1px solid var(--line)}.opportunity-row{display:grid;grid-template-columns:58px minmax(0,1fr) 130px;gap:.85rem;padding:.9rem .4rem;border-bottom:1px solid var(--line)}.opportunity-score{text-align:center}.opportunity-score strong{display:block;color:var(--gold);font-size:1.15rem}.opportunity-score span{font-size:.55rem;color:rgba(238,245,244,.38)}.opportunity-title{display:flex;align-items:center;gap:.55rem}.opportunity-title h3{margin:0;font-size:.82rem}.verification{padding:.15rem .38rem;border:1px solid rgba(238,245,244,.14);font-size:.55rem;color:rgba(238,245,244,.5)}.verification.verified{color:var(--green);border-color:rgba(159,227,192,.3)}.verification.rejected{color:var(--red)}.opportunity-main p{margin:.35rem 0;color:rgba(238,245,244,.58);font-size:.68rem;line-height:1.5}.opportunity-main small{color:rgba(238,245,244,.4);font-size:.58rem}.reason-line{margin-top:.28rem;color:rgba(159,227,192,.72);font-size:.58rem}.opportunity-actions{display:flex;flex-direction:column;gap:.32rem;align-items:stretch}.opportunity-actions a,.text-button{border:0;background:transparent;color:var(--earth-accent-light,#a2f5ee);font-size:.6rem;text-decoration:none;cursor:pointer;padding:.25rem;text-align:center}.opportunity-actions select{padding:.35rem;font-size:.6rem}.large-empty{padding:3rem 1rem;text-align:center;border:1px solid var(--line);color:rgba(238,245,244,.48)}.large-empty>span{font-size:1.5rem;color:rgba(162,245,238,.45)}.large-empty h3{margin:.6rem 0 .2rem;font-size:.88rem;color:rgba(238,245,244,.8)}.large-empty p,.empty-state p{margin:.3rem 0 .8rem;font-size:.68rem}.utility-drawer{margin-top:.8rem;border:1px solid var(--line);background:rgba(9,20,28,.4)}.utility-drawer summary{padding:.75rem .9rem;color:rgba(162,245,238,.72);font-size:.68rem;cursor:pointer}.drawer-form{padding:0 .9rem .9rem}.plan-list{display:flex;flex-direction:column;gap:.7rem}.plan-panel{padding:1rem}.plan-panel.muted{opacity:.55}.plan-panel header{display:flex;justify-content:space-between;gap:1rem}.plan-panel header>div:first-child{min-width:0}.plan-panel header span{font-size:.56rem;color:rgba(162,245,238,.62)}.plan-panel h3{margin:.25rem 0;font-size:.92rem}.plan-goal{text-align:right;white-space:nowrap}.plan-goal strong{display:block;color:var(--gold);font-size:1.1rem}.plan-progress{height:3px;margin:.8rem 0;background:rgba(162,245,238,.1)}.step-row{display:grid;grid-template-columns:26px minmax(0,1fr) 90px;align-items:center;gap:.65rem;padding:.55rem 0;border-top:1px solid rgba(162,245,238,.08)}.step-check{width:25px;height:25px;padding:0;border:1px solid rgba(162,245,238,.22);border-radius:50%;background:transparent;color:rgba(162,245,238,.7);font-size:.6rem;cursor:pointer}.step-check.done{background:rgba(159,227,192,.13);color:var(--green)}.step-row strong{font-size:.72rem}.step-row p{margin:.15rem 0}.crossed{text-decoration:line-through;color:rgba(238,245,244,.38)}.inline-form{display:flex;gap:.4rem;margin-top:.6rem}.inline-form input{flex:1}.inline-form button,.add-link,.source-row button,.source-form button{border:0;background:transparent;color:var(--earth-accent-light,#a2f5ee);font-size:.62rem;cursor:pointer}.add-link{padding:.6rem 0}.review-layout,.settings-layout{display:grid;grid-template-columns:.8fr 1.2fr;gap:.8rem}.income-form,.result-ledger,.settings-panel{padding:1rem}.income-form h3,.result-ledger h3,.settings-panel h3{margin:0 0 .8rem;font-size:.86rem}.money-input{position:relative}.money-input span{position:absolute;left:.8rem;top:50%;transform:translateY(-50%);color:var(--gold)}.money-input input{padding-left:1.8rem;font-size:1.25rem;color:var(--gold)}.result-ledger header,.source-title{display:flex;justify-content:space-between;align-items:flex-start}.result-ledger header>span,.source-title p{font-size:.58rem;color:rgba(238,245,244,.38)}.ledger-row{display:grid;grid-template-columns:100px minmax(0,1fr) auto;gap:.7rem;align-items:center;padding:.7rem 0;border-top:1px solid var(--line)}.ledger-row strong{display:block;color:var(--gold)}.ledger-row span,.ledger-row small{font-size:.57rem;color:rgba(238,245,244,.4)}.ledger-row p{font-size:.68rem}.empty-state{padding:1.2rem 0;color:rgba(238,245,244,.48)}.empty-state b{font-size:.72rem;color:rgba(238,245,244,.72)}.model-selector button{margin:0 .35rem .35rem 0;padding:.4rem .55rem;border:1px solid rgba(162,245,238,.14);background:transparent;color:rgba(238,245,244,.55);font-size:.62rem;cursor:pointer}.model-selector button.selected{border-color:rgba(159,227,192,.34);color:var(--green);background:rgba(159,227,192,.06)}.source-title h3{margin-bottom:.2rem}.source-title p{margin:0}.source-form{display:grid;grid-template-columns:.7fr 1.3fr auto;gap:.4rem;margin:.8rem 0}.source-form button{padding:0 .55rem;border:1px solid rgba(162,245,238,.22)}.source-row{display:grid;grid-template-columns:8px minmax(0,1fr) auto auto;gap:.5rem;align-items:center;padding:.55rem 0;border-top:1px solid var(--line)}.source-row i{width:6px;height:6px;border-radius:50%;background:var(--green)}.source-row i.off{background:rgba(238,245,244,.3)}.source-row strong,.source-row span{display:block}.source-row strong{font-size:.68rem}.source-row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.56rem;color:rgba(238,245,244,.38)}.source-row .danger{color:var(--red)}.automation-boundary{display:grid;grid-template-columns:1fr 1fr;margin-top:.8rem;border:1px solid var(--line)}.automation-boundary div{padding:.8rem}.automation-boundary div+div{border-left:1px solid var(--line)}.automation-boundary span{font-size:.6rem;color:var(--earth-accent-light,#a2f5ee)}.automation-boundary p{margin:.3rem 0;font-size:.65rem;color:rgba(238,245,244,.52);line-height:1.5}footer{max-width:1212px;margin:auto;padding:0 1.4rem 1.2rem;color:rgba(238,245,244,.32);font-size:.58rem}
.offer-section,.approval-section{margin:0 0 .9rem}.subsection-heading{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:.55rem}.subsection-heading h3{margin:.2rem 0 0;font-size:.9rem}.subsection-heading>span{font-size:.58rem;color:rgba(238,245,244,.42)}.offer-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem}.offer-card{border:1px solid var(--line);background:rgba(9,20,28,.58);padding:.9rem}.offer-card header{display:flex;justify-content:space-between;gap:1rem}.offer-card header span,.offer-card small{font-size:.56rem;color:rgba(238,245,244,.42)}.offer-card h3{margin:.2rem 0;font-size:.88rem}.offer-card header strong{color:var(--gold);font-size:1.15rem}.offer-card>p{font-size:.68rem;color:rgba(238,245,244,.58);line-height:1.5}.offer-card dl{margin:.7rem 0}.offer-card dt{font-size:.56rem;color:var(--earth-accent-light,#a2f5ee)}.offer-card dd{margin:.18rem 0 .55rem;font-size:.65rem;color:rgba(238,245,244,.55);line-height:1.5}.approval-section{margin-top:1.2rem}.boundary-note{padding:.65rem .75rem;border-left:2px solid var(--gold);background:rgba(232,213,163,.06);color:rgba(238,245,244,.62);font-size:.65rem;line-height:1.55}.approval-list{border-top:1px solid var(--line)}.approval-row{display:grid;grid-template-columns:minmax(0,1fr) 145px;gap:.8rem;padding:.8rem .25rem;border-bottom:1px solid var(--line)}.approval-main header{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}.approval-main header strong{font-size:.75rem}.approval-main header small{color:rgba(238,245,244,.4);font-size:.56rem}.approval-main p{white-space:pre-wrap;margin:.45rem 0;color:rgba(238,245,244,.62);font-size:.66rem;line-height:1.55}.approval-main code{display:block;overflow:hidden;text-overflow:ellipsis;color:rgba(162,245,238,.5);font-size:.55rem}.approval-status{padding:.15rem .35rem;border:1px solid rgba(238,245,244,.16);font-size:.55rem}.approval-status.pending{color:var(--gold);border-color:rgba(232,213,163,.35)}.approval-status.approved{color:var(--green);border-color:rgba(159,227,192,.35)}.approval-status.revoked,.approval-status.expired{color:var(--red)}.approval-actions{display:flex;flex-direction:column;justify-content:center;gap:.35rem}.text-button.danger{color:var(--red)}.automation-boundary{grid-template-columns:repeat(3,1fr)}
@media(max-width:980px){.route-grid{grid-template-columns:repeat(2,1fr)}.today-layout,.review-layout,.settings-layout{grid-template-columns:1fr}.onboarding-band{grid-template-columns:1fr}.opportunity-row{grid-template-columns:48px minmax(0,1fr)}.opportunity-actions{grid-column:2;flex-direction:row;flex-wrap:wrap}.opportunity-actions select{width:auto}.ledger-row{grid-template-columns:90px 1fr}.ledger-row small{grid-column:2}.automation-boundary{grid-template-columns:1fr}.automation-boundary div+div{border-left:0;border-top:1px solid var(--line)}}
@media(max-width:700px){.earning-header{padding:1rem .8rem .7rem}.workspace{padding:.8rem .8rem 2rem}.workspace-tabs{padding:0 .35rem}.workspace-tabs button{flex:1;padding:0 .2rem}.workspace-tabs button span{display:none}.metrics{grid-template-columns:1fr 1fr}.metrics div:nth-child(2){border-right:0}.metrics div:nth-child(-n+2){border-bottom:1px solid var(--line)}.route-grid,.offer-grid{grid-template-columns:1fr}.form-row{flex-wrap:wrap}.form-row>label{min-width:140px}.section-heading,.radar-heading{flex-direction:column}.heading-actions{width:100%;flex-wrap:wrap}.heading-actions select,.heading-actions button{flex:1}.pipeline-strip{grid-template-columns:repeat(5,minmax(56px,1fr));overflow:auto}.plan-panel header{flex-direction:column}.plan-goal{text-align:left}.step-row{grid-template-columns:26px minmax(0,1fr)}.step-row>.text-button{grid-column:2;text-align:left;padding-left:0}.source-form{grid-template-columns:1fr}.approval-row{grid-template-columns:1fr}.approval-actions{flex-direction:row;flex-wrap:wrap;justify-content:flex-start}.title-line{align-items:flex-start;flex-direction:column;gap:.15rem}.assist-state{margin-bottom:.3rem}}
</style>
