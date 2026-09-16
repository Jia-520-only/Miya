<script setup lang="ts">
import { onMounted, ref } from 'vue'
import EarthAPI, { type EarthEarningGuidance, type EarthEarningOpportunity, type EarthEarningPlanStep, type EarthEarningSource, type EarthEarningPreferences } from '@/api/earth'

const data = ref<EarthEarningGuidance | null>(null)
const sources = ref<EarthEarningSource[]>([])
const loading = ref(false)
const message = ref('')
const form = ref({ title: '', source: '', url: '', kind: '技能服务', description: '', income_min: 0, income_max: 0, hours: 0, risk: 'unknown', confidence: 'unknown' })
const plan = ref({ title: '', goal_amount: 0, target_date: '', notes: '' })
const income = ref<{ amount: number, cost: number, hours: number, note: string, opportunity_id: number | null }>({ amount: 0, cost: 0, hours: 0, note: '', opportunity_id: null })
const newStepPlanId = ref<number | null>(null)
const newStepTitle = ref('')
const sourceForm = ref({ name: '', url: '' })
const prefsForm = ref({ skills: '', preferred_kinds: '', weekly_hours: 5, target_amount: 500, min_hourly_rate: 0, risk_tolerance: 'low' as EarthEarningPreferences['risk_tolerance'] })

async function load() {
  loading.value = true
  try {
    [data.value, sources.value] = await Promise.all([EarthAPI.earningGuidance(), EarthAPI.earningSources()])
    const prefs = data.value.preferences
    prefsForm.value = { skills: prefs.skills.join(', '), preferred_kinds: prefs.preferred_kinds.join(', '), weekly_hours: prefs.weekly_hours, target_amount: prefs.target_amount, min_hourly_rate: prefs.min_hourly_rate, risk_tolerance: prefs.risk_tolerance }
  }
  catch (error: any) { message.value = error?.response?.data?.detail || '收益面板暂时无法连接' }
  finally { loading.value = false }
}

async function addOpportunity() {
  if (!form.value.title.trim()) return
  try { await EarthAPI.addEarningOpportunity(form.value); message.value = '已收录这条情报'; form.value = { title: '', source: '', url: '', kind: '技能服务', description: '', income_min: 0, income_max: 0, hours: 0, risk: 'unknown', confidence: 'unknown' }; await load() }
  catch (error: any) { message.value = error?.response?.data?.detail || '收录失败' }
}

async function addPlan() {
  if (!plan.value.title.trim()) return
  try { await EarthAPI.addEarningPlan(plan.value); message.value = '收益计划已建立'; plan.value = { title: '', goal_amount: 0, target_date: '', notes: '' }; await load() }
  catch (error: any) { message.value = error?.response?.data?.detail || '计划建立失败' }
}

async function recordIncome() {
  try { await EarthAPI.recordIncome(income.value); message.value = '已记录净收益并写入地球币流水'; income.value = { amount: 0, cost: 0, hours: 0, note: '', opportunity_id: null }; await load() }
  catch (error: any) { message.value = error?.response?.data?.detail || '记录失败' }
}

async function updateStatus(item: EarthEarningOpportunity, status: EarthEarningOpportunity['status']) {
  try { await EarthAPI.updateEarningOpportunity(item.id, { status }); await load() }
  catch (error: any) { message.value = error?.response?.data?.detail || '状态更新失败' }
}

async function addSource() {
  if (!sourceForm.value.url.trim()) return
  try { await EarthAPI.addEarningSource(sourceForm.value); sourceForm.value = { name: '', url: '' }; message.value = '公开信息源已保存'; await load() }
  catch (error: any) { message.value = error?.response?.data?.detail || '信息源保存失败' }
}

async function syncSources() {
  loading.value = true
  try { const result = await EarthAPI.syncEarningSources(); message.value = `同步完成：新增 ${result.created_count} 条，跳过 ${result.skipped} 条${result.errors.length ? `，失败 ${result.errors.length} 个来源` : ''}`; await load() }
  catch (error: any) { message.value = error?.response?.data?.detail || '公开信息同步失败' }
  finally { loading.value = false }
}

async function toggleSource(source: EarthEarningSource) {
  try { await EarthAPI.updateEarningSource(source.id, { enabled: !Boolean(source.enabled) }); await load() }
  catch (error: any) { message.value = error?.response?.data?.detail || '信息源状态更新失败' }
}

async function deleteSource(source: EarthEarningSource) {
  try { await EarthAPI.deleteEarningSource(source.id); message.value = `已移除信息源「${source.name}」`; await load() }
  catch (error: any) { message.value = error?.response?.data?.detail || '信息源移除失败' }
}

async function savePreferences() {
  try {
    await EarthAPI.updateEarningPreferences({ ...prefsForm.value, skills: prefsForm.value.skills.split(','), preferred_kinds: prefsForm.value.preferred_kinds.split(',') })
    message.value = '筛选偏好已保存，推荐分数已更新'
    await load()
  }
  catch (error: any) { message.value = error?.response?.data?.detail || '偏好保存失败' }
}

async function convertToQuest(item: EarthEarningOpportunity) {
  if (item.quest_id) return
  try {
    await EarthAPI.convertEarningOpportunityToQuest(item.id)
    message.value = `已将「${item.title}」放入地球online 委托板`
    await load()
  }
  catch (error: any) { message.value = error?.response?.data?.detail || '转换委托失败' }
}

async function addStep(planId: number) {
  if (!newStepTitle.value.trim()) return
  try { await EarthAPI.addEarningPlanStep(planId, { title: newStepTitle.value.trim() }); newStepTitle.value = ''; newStepPlanId.value = null; message.value = '阶段已加入计划'; await load() }
  catch (error: any) { message.value = error?.response?.data?.detail || '阶段添加失败' }
}

async function toggleStep(step: EarthEarningPlanStep) {
  try { await EarthAPI.updateEarningPlanStep(step.id, { status: step.status === 'done' ? 'pending' : 'done' }); await load() }
  catch (error: any) { message.value = error?.response?.data?.detail || '阶段更新失败' }
}

async function convertStep(step: EarthEarningPlanStep) {
  if (step.quest_id) return
  try { await EarthAPI.convertEarningPlanStepToQuest(step.id); message.value = `已将阶段「${step.title}」放入委托板`; await load() }
  catch (error: any) { message.value = error?.response?.data?.detail || '阶段转委托失败' }
}

onMounted(load)
</script>

<template>
  <div class="earning-view">
    <div class="earning-head"><div><div class="kicker">REAL-WORLD INCOME / MIYA ASSIST</div><h1>收益中枢</h1><p>把机会变成下一步行动，再用真实记录校准路线。</p></div><button class="refresh" :disabled="loading" @click="load">↻ 刷新</button></div>
    <div v-if="message" class="message">{{ message }}</div>
    <div class="summary-grid"><div><b>¥{{ data?.totals.net_income?.toFixed(2) || '0.00' }}</b><span>已记录净收益</span></div><div><b>{{ data?.totals.opportunity_count || 0 }}</b><span>情报总数</span></div><div><b>{{ data?.totals.active_plan_count || 0 }}</b><span>进行中计划</span></div></div>
    <div class="earning-grid">
      <section class="card source-card"><div class="card-head"><h2>◎ 公开信息源</h2><button class="sync-btn" :disabled="loading" @click="syncSources">{{ loading ? '同步中…' : '↻ 同步全部' }}</button></div><form class="source-form" @submit.prevent="addSource"><input v-model="sourceForm.name" placeholder="名称（可选，例如：官方公告）"><input v-model="sourceForm.url" type="url" placeholder="RSS / Atom 公开号址" required><button>添加来源</button></form><div v-if="!sources.length" class="empty">还没有来源；先添加一个公开 RSS/Atom 地址。</div><div v-for="source in sources" :key="source.id" class="source-row"><span class="source-state" :class="{ off: !Boolean(source.enabled) }">{{ Boolean(source.enabled) ? '●' : '○' }}</span><div class="source-main"><b>{{ source.name }}</b><small>{{ source.url }}</small><em v-if="source.last_error">{{ source.last_error }}</em><small v-else-if="source.last_synced_at">上次同步：{{ source.last_synced_at }}</small></div><button class="source-action" @click="toggleSource(source)">{{ Boolean(source.enabled) ? '暂停' : '启用' }}</button><button class="source-action danger" @click="deleteSource(source)">移除</button></div><p class="source-note">只读取公开内容；每个来源最多采集 30 条，按链接自动去重。</p></section>
      <section class="card preferences-card"><div class="card-head"><h2>◇ 我的筛选偏好</h2><span>只影响推荐排序</span></div><form class="form" @submit.prevent="savePreferences"><input v-model="prefsForm.skills" placeholder="你的技能，用逗号分隔：写作, 设计, 编程"><input v-model="prefsForm.preferred_kinds" placeholder="偏好类型：技能服务, 二手, 内容"><div class="row"><input v-model.number="prefsForm.weekly_hours" type="number" min="0" step="0.5" placeholder="每周可投入小时"><input v-model.number="prefsForm.target_amount" type="number" min="0" step="10" placeholder="阶段目标金额"><input v-model.number="prefsForm.min_hourly_rate" type="number" min="0" step="1" placeholder="最低时薪"></div><select v-model="prefsForm.risk_tolerance"><option value="low">低风险优先</option><option value="medium">可接受中风险</option><option value="high">愿意承担高风险</option></select><button>保存筛选偏好</button></form></section>
      <section class="card opportunities"><div class="card-head"><h2>◇ 情报站</h2><span>先核实，再行动</span></div><div v-if="!data?.opportunities.length" class="empty">还没有情报。可以先把看到的机会链接记在这里。</div><article v-for="item in data?.opportunities" :key="item.id" class="opportunity"><div class="opp-top"><h3>{{ item.title }}</h3><span class="score">{{ item.fit_score || 0 }} 分</span></div><p>{{ item.description || '暂无描述' }}</p><small>{{ item.source || '手动收录' }} · {{ item.kind }} · 预估 ¥{{ item.income_min }}-{{ item.income_max }} · {{ item.hours }}h</small><div v-if="item.fit_reasons?.length" class="fit-reasons">{{ item.fit_reasons.join(' · ') }}</div><div class="opp-foot"><span :class="`risk ${item.risk}`">风险 {{ item.risk }}</span><span>可信度 {{ item.confidence }}</span><select :value="item.status" @change="updateStatus(item, ($event.target as HTMLSelectElement).value as any)"><option value="inbox">待评估</option><option value="shortlisted">已筛选</option><option value="applied">已尝试</option><option value="won">已获得</option><option value="closed">已关闭</option></select><button class="quest-btn" :disabled="!!item.quest_id" @click="convertToQuest(item)">{{ item.quest_id ? '已在委托板' : '转为委托' }}</button></div></article></section>
      <section class="card"><div class="card-head"><h2>✦ 收益计划</h2><span>把目标拆小</span></div><form class="form" @submit.prevent="addPlan"><input v-model="plan.title" placeholder="例如：30 天获得第一笔 500 元" required><div class="row"><input v-model.number="plan.goal_amount" type="number" min="0" placeholder="目标金额"><input v-model="plan.target_date" type="date"></div><textarea v-model="plan.notes" placeholder="弥娅需要知道的限制、技能或时间"></textarea><button>建立计划</button></form><div v-for="p in data?.plans" :key="p.id" class="plan-block"><div class="plan"><b>{{ p.title }}</b><span>目标 ¥{{ p.goal_amount }} · {{ p.completed_steps || 0 }}/{{ p.steps?.length || 0 }} 阶段 · {{ p.progress_percent || 0 }}%</span></div><div class="progress"><i :style="{ width: `${p.progress_percent || 0}%` }" /></div><div v-for="step in p.steps" :key="step.id" class="step"><button class="step-check" :class="{ done: step.status === 'done' }" :aria-label="step.status === 'done' ? '标记未完成' : '标记完成'" @click="toggleStep(step)">{{ step.status === 'done' ? '✓' : '○' }}</button><span :class="{ 'step-done': step.status === 'done' }">{{ step.title }}</span><button class="step-quest" :disabled="!!step.quest_id" @click="convertStep(step)">{{ step.quest_id ? '已在委托板' : '转为委托' }}</button></div><form v-if="newStepPlanId === p.id" class="step-add" @submit.prevent="addStep(p.id)"><input v-model="newStepTitle" placeholder="下一阶段，例如：发布第一条作品" autofocus><button>添加</button><button type="button" @click="newStepPlanId = null">取消</button></form><button v-else class="add-step" @click="newStepPlanId = p.id; newStepTitle = ''">＋ 添加阶段</button></div></section>
      <section class="card"><div class="card-head"><h2>＋ 收录情报</h2><span>支持公开链接 / 手动记录</span></div><form class="form" @submit.prevent="addOpportunity"><input v-model="form.title" placeholder="机会标题" required><div class="row"><input v-model="form.source" placeholder="来源"><input v-model="form.url" placeholder="链接（可选）"></div><div class="row"><input v-model.number="form.income_min" type="number" min="0" placeholder="最低收益"><input v-model.number="form.income_max" type="number" min="0" placeholder="最高收益"><input v-model.number="form.hours" type="number" min="0" step="0.5" placeholder="预计小时"></div><textarea v-model="form.description" placeholder="描述、要求和你看到的备注"></textarea><div class="row"><select v-model="form.risk"><option value="unknown">风险未知</option><option value="low">低风险</option><option value="medium">中风险</option><option value="high">高风险</option></select><select v-model="form.confidence"><option value="unknown">可信度未知</option><option value="low">低可信</option><option value="medium">中可信</option><option value="high">高可信</option></select></div><button>收录情报</button></form></section>
      <section class="card"><div class="card-head"><h2>◆ 记录收入</h2><span>会同步到现实资产流水</span></div><form class="form" @submit.prevent="recordIncome"><div class="row"><input v-model.number="income.amount" type="number" min="0" step="0.01" placeholder="收入金额" required><input v-model.number="income.cost" type="number" min="0" step="0.01" placeholder="成本"><input v-model.number="income.hours" type="number" min="0" step="0.5" placeholder="投入小时"></div><select v-model.number="income.opportunity_id"><option :value="null">不关联情报</option><option v-for="item in data?.opportunities" :key="item.id" :value="item.id">关联：{{ item.title }}</option></select><input v-model="income.note" placeholder="备注（平台、项目、客户等）"><button>记入流水</button></form><div v-for="r in data?.income_records" :key="r.id" class="plan"><b>¥{{ (r.amount - r.cost).toFixed(2) }}</b><span>{{ r.note || '未填写备注' }} · {{ r.hours }}h</span></div></section>
    </div>
    <p class="boundary">{{ data?.boundary || '建议基于你记录的资料，不保证收益；涉及外部平台、付款或提交前需要你确认。' }}</p>
  </div>
</template>

<style scoped>
.earning-view{height:100%;overflow:auto;padding:2.2rem clamp(1rem,4vw,4rem);box-sizing:border-box;color:var(--miya-text,#eef5f4);background:linear-gradient(160deg,rgba(7,15,22,.96),rgba(9,20,28,.88));}.earning-head{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;max-width:1200px;margin:auto}.kicker{font-size:.58rem;letter-spacing:.18em;color:var(--earth-accent-light,#a2f5ee)}h1{margin:.35rem 0;font-size:2.2rem;font-weight:500}.earning-head p{margin:0;color:rgba(238,245,244,.6)}button,.refresh{border:1px solid color-mix(in srgb,var(--earth-accent-light,#a2f5ee) 48%,transparent);background:rgba(120,207,209,.1);color:var(--earth-accent-light,#a2f5ee);padding:.55rem .85rem;cursor:pointer}.quest-btn,.step-quest{padding:.25rem .45rem;font-size:.58rem;white-space:nowrap}.quest-btn:disabled,.step-quest:disabled{opacity:.5;cursor:default}.sync-btn{padding:.25rem .5rem;font-size:.62rem}.summary-grid{max-width:1200px;margin:1.5rem auto;display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem}.summary-grid div,.card{border:1px solid rgba(162,245,238,.15);background:rgba(8,18,27,.72);backdrop-filter:blur(12px)}.summary-grid div{padding:1rem}.summary-grid b{display:block;font-size:1.45rem;color:#e8d5a3}.summary-grid span,.card-head span,.plan span,.opportunity small{font-size:.65rem;color:rgba(238,245,244,.52)}.earning-grid{max-width:1200px;margin:auto;display:grid;grid-template-columns:1.25fr 1fr;gap:.8rem}.card{padding:1rem}.source-card{grid-column:1/-1}.card-head{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid rgba(162,245,238,.12);padding-bottom:.6rem;margin-bottom:.7rem}.card h2{margin:0;font-size:.95rem;font-weight:500;color:#e8d5a3}.source-form{display:flex;gap:.5rem;margin-bottom:.65rem}.source-form input{flex:1;box-sizing:border-box;border:1px solid rgba(162,245,238,.18);background:rgba(0,0,0,.22);color:inherit;padding:.55rem;font:inherit;font-size:.72rem}.source-form button{white-space:nowrap}.source-row{display:flex;align-items:center;gap:.55rem;padding:.5rem 0;border-bottom:1px solid rgba(162,245,238,.08)}.source-state{color:#9fe3c0;font-size:.7rem}.source-state.off{color:rgba(238,245,244,.35)}.source-main{flex:1;min-width:0;display:flex;flex-direction:column;gap:.1rem}.source-main b{font-size:.72rem;font-weight:500}.source-main small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:rgba(238,245,244,.45);font-size:.6rem}.source-main em{color:#e59393;font-size:.6rem;font-style:normal}.source-action{padding:.25rem .45rem;font-size:.58rem}.source-action.danger{color:#e59393}.source-note{margin:.6rem 0 0;color:rgba(238,245,244,.38);font-size:.6rem}.opportunity{padding:.7rem 0;border-bottom:1px solid rgba(162,245,238,.1)}.opp-top,.opp-foot{display:flex;align-items:center;gap:.6rem}.opp-top h3{flex:1;margin:0;font-size:.88rem;font-weight:500}.score{font-size:.65rem;color:#e8d5a3}.opportunity p{margin:.35rem 0;font-size:.74rem;color:rgba(238,245,244,.72);line-height:1.5}.fit-reasons{margin-top:.35rem;color:#9fe3c0;font-size:.6rem;line-height:1.4}.opp-foot{margin-top:.45rem;font-size:.62rem;color:rgba(238,245,244,.52)}.opp-foot select{margin-left:auto}.risk.low{color:#9fe3c0}.risk.high{color:#e59393}.form{display:flex;flex-direction:column;gap:.55rem}.form input,.form textarea,.form select,.opp-foot select,.step-add input{box-sizing:border-box;border:1px solid rgba(162,245,238,.18);background:rgba(0,0,0,.22);color:inherit;padding:.55rem;font:inherit;font-size:.72rem}.form textarea{min-height:65px;resize:vertical}.row{display:flex;gap:.5rem}.row>*{flex:1;min-width:0}.plan-block{border-bottom:1px solid rgba(162,245,238,.1);padding-bottom:.5rem;margin-bottom:.3rem}.plan{display:flex;justify-content:space-between;gap:.6rem;padding:.65rem 0;font-size:.75rem}.progress{height:3px;background:rgba(162,245,238,.12);margin-bottom:.3rem}.progress i{display:block;height:100%;background:#e8d5a3}.step{display:flex;align-items:center;gap:.45rem;padding:.32rem 0;font-size:.7rem}.step-check{padding:0;border:0;background:transparent;color:#a2f5ee;font-size:.85rem}.step-check.done{color:#9fe3c0}.step-done{text-decoration:line-through;color:rgba(238,245,244,.4)}.step-quest{margin-left:auto}.add-step{border:0;background:transparent;padding:.35rem 0;color:rgba(162,245,238,.65);font-size:.65rem}.step-add{display:flex;gap:.4rem;margin-top:.35rem}.step-add input{flex:1}.step-add button{padding:.25rem .45rem;font-size:.6rem}.empty{padding:1rem 0;color:rgba(238,245,244,.52);font-size:.75rem}.message{max-width:1200px;margin:1rem auto 0;padding:.55rem .7rem;border-left:2px solid #e8d5a3;color:#e8d5a3;font-size:.7rem}.boundary{max-width:1200px;margin:1rem auto;color:rgba(238,245,244,.4);font-size:.65rem}@media(max-width:800px){.earning-grid{grid-template-columns:1fr}.summary-grid{grid-template-columns:1fr 1fr}.summary-grid div:last-child{grid-column:1/-1}.row{flex-wrap:wrap}.row>*{min-width:30%}.source-form{flex-wrap:wrap}.source-form input{min-width:40%}.source-form button{margin-left:auto}} 
</style>
