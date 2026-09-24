<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EarthAPI, {
  type EarthDistChannel,
  type EarthDistChannelKind,
  type EarthDistMaterial,
  type EarthDistPackage,
  type EarthDistPackageStatus,
  type EarthDistPlatform,
  type EarthDistTarget,
  type EarthDistributionReport,
} from '@/api/earth'

const platformLabels: Array<[EarthDistPlatform, string]> = [
  ['xiaohongshu', '小红书'], ['zhihu', '知乎'], ['tieba', '贴吧'], ['bilibili', 'B站'], ['douyin', '抖音'],
  ['kuaishou', '快手'], ['weibo', '微博'], ['gongzhonghao', '公众号'], ['xianyu', '闲鱼'], ['other', '其他'],
]
const platformLabel = (platform: string) => platformLabels.find(([key]) => key === platform)?.[1] || platform || '未指定'

const channelKindLabels: Array<[EarthDistChannelKind, string]> = [
  ['netdisk_cps', '网盘 CPS 分佣'], ['netdisk_referral', '网盘拉新邀请'], ['direct_sale', '自有直接售卖'], ['other', '其他'],
]
const packageStatusLabels: Record<EarthDistPackageStatus, string> = { draft: '草稿', ready: '可分发', published: '已发布', retired: '已停用' }

/** 列表接口返回的对象类型；共享/发布草稿直接挂在条目上，避免模板里做可能为 undefined 的字典索引。 */
type DistPackageRow = EarthDistPackage & { draft: { shareUrl: string, sharePassword: string, shareNote: string } }
type DistMaterialRow = EarthDistMaterial & { publishDraft: string }

const report = ref<EarthDistributionReport | null>(null)
const channels = ref<EarthDistChannel[]>([])
const targets = ref<EarthDistTarget[]>([])
const packages = ref<DistPackageRow[]>([])
const materials = ref<DistMaterialRow[]>([])
const loading = ref(false)
const workingKey = ref('')
const error = ref('')
const notice = ref('')
const days = ref(30)
const materialFilter = ref<'all' | EarthDistMaterial['status']>('all')

const channelForm = ref<{ id: number | null, name: string, key: string, kind: EarthDistChannelKind, promoUrl: string, promoCode: string, settlementCycle: string, notes: string, enabled: boolean }>({
  id: null, name: '', key: '', kind: 'netdisk_cps', promoUrl: '', promoCode: '', settlementCycle: '', notes: '', enabled: true,
})
const targetForm = ref<{ platform: EarthDistPlatform, accountLabel: string, profileUrl: string, audienceNote: string, dailyPostLimit: number }>({
  platform: 'xiaohongshu', accountLabel: '', profileUrl: '', audienceNote: '', dailyPostLimit: 1,
})
const packageForm = ref<{ title: string, resourceIds: string, channelId: number | null, keywords: string, coverHint: string }>({
  title: '', resourceIds: '', channelId: null, keywords: '', coverHint: '',
})
const genForm = ref<{ packageId: number | null, targetIds: number[], variants: number, replace: boolean }>({ packageId: null, targetIds: [], variants: 1, replace: false })
const metricForm = ref<{ materialId: number | null, packageId: number | null, statDate: string, impressions: number, clicks: number, transfers: number, newUsers: number, vipOrders: number, revenue: number, cost: number, note: string }>({
  materialId: null, packageId: null, statDate: new Date().toISOString().slice(0, 10),
  impressions: 0, clicks: 0, transfers: 0, newUsers: 0, vipOrders: 0, revenue: 0, cost: 0, note: '',
})

const funnel = computed(() => report.value?.funnel || null)
const visibleMaterials = computed(() => (
  materialFilter.value === 'all' ? materials.value : materials.value.filter(item => item.status === materialFilter.value)
))
const pendingMaterials = computed(() => materials.value.filter(item => item.status === 'submitted'))

function setMessage(value: string) {
  notice.value = value
  window.setTimeout(() => { if (notice.value === value) notice.value = '' }, 6000)
}

function fail(error_: any, fallback: string) {
  error.value = error_?.response?.data?.detail || fallback
}

function csvValues(value: string) {
  return value.split(/[,，\n]/).map(item => item.trim()).filter(Boolean)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [reportData, channelList, targetList, packageList, materialList] = await Promise.all([
      EarthAPI.distributionReport(days.value),
      EarthAPI.distChannels(),
      EarthAPI.distTargets(),
      EarthAPI.distPackages(),
      EarthAPI.distMaterials({ limit: 300 }),
    ])
    report.value = reportData
    channels.value = channelList
    targets.value = targetList
    packages.value = packageList.map(item => ({
      ...item,
      draft: { shareUrl: item.shareUrl || '', sharePassword: item.sharePassword || '', shareNote: item.shareNote || '' },
    }))
    materials.value = materialList.map(item => ({ ...item, publishDraft: item.publishedUrl || '' }))
    const firstPackageId = packageList[0]?.id ?? null
    if (!genForm.value.packageId) genForm.value.packageId = firstPackageId
    if (!metricForm.value.packageId) metricForm.value.packageId = firstPackageId
  }
  catch (error_: any) {
    fail(error_, '网盘分发中枢暂时无法连接')
  }
  finally {
    loading.value = false
  }
}

async function runCycle() {
  workingKey.value = 'cycle'
  error.value = ''
  try {
    const result = await EarthAPI.runDistributionCycle()
    await load()
    setMessage(result.skipped === 'disabled'
      ? '分发巡检在配置里处于关闭状态，没有执行任何动作'
      : `分发巡检完成：新增 ${result.createdMaterials || 0} 条物料草稿，提交审批 ${result.submitted || 0} 条，审批回填 ${result.approved || 0} 条；弥娅没有登录任何平台`)
  }
  catch (error_: any) { fail(error_, '分发巡检失败') }
  finally { workingKey.value = '' }
}

function editChannel(channel: EarthDistChannel) {
  channelForm.value = {
    id: channel.id, name: channel.name, key: channel.key, kind: channel.kind,
    promoUrl: channel.promoUrl || '', promoCode: channel.promoCode || '',
    settlementCycle: channel.settlementCycle || '', notes: channel.notes || '',
    enabled: Boolean(channel.enabled),
  }
  error.value = ''
}

function resetChannelForm() {
  channelForm.value = { id: null, name: '', key: '', kind: 'netdisk_cps', promoUrl: '', promoCode: '', settlementCycle: '', notes: '', enabled: true }
}

async function saveChannel() {
  if (!channelForm.value.name.trim()) return
  workingKey.value = 'channel-save'
  error.value = ''
  try {
    await EarthAPI.upsertDistChannel({
      id: channelForm.value.id ?? undefined,
      name: channelForm.value.name.trim(),
      key: channelForm.value.key.trim() || undefined,
      kind: channelForm.value.kind,
      promoUrl: channelForm.value.promoUrl.trim(),
      promoCode: channelForm.value.promoCode.trim(),
      settlementCycle: channelForm.value.settlementCycle.trim(),
      notes: channelForm.value.notes.trim(),
      enabled: channelForm.value.enabled,
    })
    resetChannelForm()
    await load()
    setMessage('分发平台已保存（只记录公开推广链接与邀请码，不保存账号密码）')
  }
  catch (error_: any) { fail(error_, '分发平台保存失败') }
  finally { workingKey.value = '' }
}

async function toggleChannel(channel: EarthDistChannel) {
  try {
    await EarthAPI.upsertDistChannel({
      id: channel.id, name: channel.name, key: channel.key, kind: channel.kind,
      promoUrl: channel.promoUrl || '', promoCode: channel.promoCode || '',
      settlementCycle: channel.settlementCycle || '', notes: channel.notes || '',
      enabled: !channel.enabled,
    })
    await load()
  }
  catch (error_: any) { fail(error_, '平台状态更新失败') }
}

async function removeChannel(channel: EarthDistChannel) {
  if (!window.confirm(`删除分发平台「${channel.name}」？`)) return
  try { await EarthAPI.deleteDistChannel(channel.id); await load(); setMessage(`已删除分发平台「${channel.name}」`) }
  catch (error_: any) { fail(error_, '分发平台删除失败') }
}

async function addTarget() {
  if (!targetForm.value.accountLabel.trim()) return
  workingKey.value = 'target-add'
  error.value = ''
  try {
    await EarthAPI.upsertDistTarget({
      platform: targetForm.value.platform,
      accountLabel: targetForm.value.accountLabel.trim(),
      profileUrl: targetForm.value.profileUrl.trim(),
      audienceNote: targetForm.value.audienceNote.trim(),
      dailyPostLimit: Number(targetForm.value.dailyPostLimit) || 1,
    })
    targetForm.value = { platform: 'xiaohongshu', accountLabel: '', profileUrl: '', audienceNote: '', dailyPostLimit: 1 }
    await load()
    setMessage('投放位已登记；这里只填账号标识与主页，不要填密码或 Cookie')
  }
  catch (error_: any) { fail(error_, '投放位保存失败') }
  finally { workingKey.value = '' }
}

async function removeTarget(target: EarthDistTarget) {
  if (!window.confirm(`删除投放位「${platformLabel(target.platform)} · ${target.accountLabel}」？`)) return
  try { await EarthAPI.deleteDistTarget(target.id); await load() }
  catch (error_: any) { fail(error_, '投放位删除失败') }
}

async function createPackage() {
  if (!packageForm.value.title.trim()) return
  workingKey.value = 'package-add'
  error.value = ''
  try {
    await EarthAPI.createDistPackage({
      title: packageForm.value.title.trim(),
      resourceIds: csvValues(packageForm.value.resourceIds).map(Number).filter(value => Number.isFinite(value)),
      channelId: packageForm.value.channelId ?? undefined,
      keywords: csvValues(packageForm.value.keywords),
      coverHint: packageForm.value.coverHint.trim(),
    })
    packageForm.value = { title: '', resourceIds: '', channelId: null, keywords: '', coverHint: '' }
    await load()
    setMessage('资源包已组装；填好网盘分享链接后即可进入可分发状态')
  }
  catch (error_: any) { fail(error_, '资源包创建失败') }
  finally { workingKey.value = '' }
}

async function bindShare(item: DistPackageRow) {
  const draft = item.draft
  workingKey.value = `share-${item.id}`
  error.value = ''
  try {
    const result = await EarthAPI.bindDistShare(item.id, {
      shareUrl: draft.shareUrl.trim(), sharePassword: draft.sharePassword.trim(), shareNote: draft.shareNote.trim(),
    })
    await load()
    setMessage(result.warning ? `分享链接已绑定，但注意：${result.warning}` : '网盘分享链接已绑定到资源包')
  }
  catch (error_: any) { fail(error_, '分享链接绑定失败') }
  finally { workingKey.value = '' }
}

async function setPackageStatus(item: DistPackageRow, status: EarthDistPackageStatus) {
  workingKey.value = `package-${item.id}`
  error.value = ''
  try {
    await EarthAPI.updateDistPackage(item.id, { status })
    await load()
    setMessage(`资源包「${item.title}」状态已更新为 ${packageStatusLabels[status]}`)
  }
  catch (error_: any) { fail(error_, '资源包状态更新失败（多半是授权还没核验或缺少分享链接）') }
  finally { workingKey.value = '' }
}

async function removePackage(item: DistPackageRow) {
  if (!window.confirm(`删除资源包「${item.title}」？已生成的投放物料不会被自动删除。`)) return
  try { await EarthAPI.deleteDistPackage(item.id); await load() }
  catch (error_: any) { fail(error_, '资源包删除失败') }
}

function toggleGenTarget(id: number) {
  const selected = genForm.value.targetIds
  genForm.value.targetIds = selected.includes(id) ? selected.filter(item => item !== id) : [...selected, id]
}

async function generateMaterials() {
  if (!genForm.value.packageId) { error.value = '先选择一个资源包'; return }
  workingKey.value = 'material-generate'
  error.value = ''
  try {
    const result = await EarthAPI.generateDistMaterials(genForm.value.packageId, {
      targetIds: genForm.value.targetIds.length ? genForm.value.targetIds : undefined,
      variants: Number(genForm.value.variants) || 1,
      replace: genForm.value.replace,
    })
    await load()
    setMessage(`已生成 ${result.createdCount} 条物料草稿（跳过 ${result.skippedCount} 条重复）；全部是站内草稿，需要你批准后才能手动发布`)
  }
  catch (error_: any) { fail(error_, '物料生成失败（先确认资源授权与投放位）') }
  finally { workingKey.value = '' }
}

async function promote(material: DistMaterialRow) {
  workingKey.value = `promote-${material.id}`
  error.value = ''
  try {
    const result = await EarthAPI.promoteDistMaterial(material.id)
    await load()
    setMessage(`物料 #${material.id} 已提交审批，审批草稿 #${result.action?.id ?? '?'} 在「执行」页的审批箱里等你确认`)
  }
  catch (error_: any) { fail(error_, '提交审批失败（先给资源包补上承接链接）') }
  finally { workingKey.value = '' }
}

async function markPublished(material: DistMaterialRow) {
  const url = (material.publishDraft || material.publishedUrl || '').trim()
  if (url && !/^https?:\/\//i.test(url)) { error.value = '发布链接必须是 http/https 地址'; return }
  workingKey.value = `publish-${material.id}`
  error.value = ''
  try {
    await EarthAPI.markDistMaterialPublished(material.id, url)
    await load()
    setMessage('已记录为你手动发布完成；记得回填转化数据，弥娅才能判断加码还是停投')
  }
  catch (error_: any) { fail(error_, '标记已发布失败（先批准对应审批草稿）') }
  finally { workingKey.value = '' }
}

async function removeMaterial(material: DistMaterialRow) {
  if (!window.confirm(`删除投放物料 #${material.id}？`)) return
  try { await EarthAPI.deleteDistMaterial(material.id); await load() }
  catch (error_: any) { fail(error_, '物料删除失败') }
}

async function syncActions() {
  workingKey.value = 'material-sync'
  error.value = ''
  try {
    const result = await EarthAPI.syncDistMaterialActions()
    await load()
    setMessage(`审批回填完成：转已批准 ${result.approved || 0} 条，退回草稿 ${result.returned || 0} 条，跳过 ${result.skipped || 0} 条`)
  }
  catch (error_: any) { fail(error_, '审批回填失败') }
  finally { workingKey.value = '' }
}

function openMetricForm(material: DistMaterialRow) {
  metricForm.value = {
    materialId: material.id, packageId: material.packageId,
    statDate: new Date().toISOString().slice(0, 10),
    impressions: 0, clicks: 0, transfers: 0, newUsers: 0, vipOrders: 0, revenue: 0, cost: 0,
    note: `${platformLabel(material.platform)} · ${material.title.slice(0, 40)}`,
  }
  setMessage(`正在为物料 #${material.id} 回填转化数据，填完在下方提交`)
}

async function recordMetrics() {
  workingKey.value = 'metrics-add'
  error.value = ''
  try {
    const result = await EarthAPI.recordDistMetrics({
      materialId: metricForm.value.materialId ?? undefined,
      packageId: metricForm.value.packageId ?? undefined,
      statDate: metricForm.value.statDate,
      impressions: Number(metricForm.value.impressions) || 0,
      clicks: Number(metricForm.value.clicks) || 0,
      transfers: Number(metricForm.value.transfers) || 0,
      newUsers: Number(metricForm.value.newUsers) || 0,
      vipOrders: Number(metricForm.value.vipOrders) || 0,
      revenue: Number(metricForm.value.revenue) || 0,
      cost: Number(metricForm.value.cost) || 0,
      note: metricForm.value.note,
    })
    await load()
    setMessage(result.incomeRecordId
      ? `转化数据已记录，佣金同步写入现实收益流水 #${result.incomeRecordId}`
      : '转化数据已记录，复盘口径已更新')
  }
  catch (error_: any) { fail(error_, '转化数据记录失败（至少关联一个资源包或一条物料）') }
  finally { workingKey.value = '' }
}

const platformRows = computed(() => report.value?.platforms || [])

onMounted(load)
</script>

<template>
  <div class="distribution-panel">
    <section class="panel-band">
      <div>
        <span class="panel-kicker">NETDISK DISTRIBUTION HUB</span>
        <h2>网盘分发中枢</h2>
        <p>弥娅只生成投放草稿、组装资源包并做数据复盘。发布必须由你确认后在平台手动完成；弥娅不登录任何平台、不保存账号密码、不发送、不收款。</p>
      </div>
      <div class="band-actions">
        <label class="day-control">复盘窗口
          <select v-model.number="days" @change="load()">
            <option :value="7">7 天</option>
            <option :value="30">30 天</option>
            <option :value="90">90 天</option>
          </select>
        </label>
        <button class="primary-button" type="button" :disabled="workingKey === 'cycle'" @click="runCycle">{{ workingKey === 'cycle' ? '巡检中…' : '运行一次分发巡检' }}</button>
        <button class="secondary-button" type="button" :disabled="loading" @click="load">{{ loading ? '刷新中…' : '刷新' }}</button>
      </div>
    </section>

    <div v-if="error" class="error-line" role="alert">{{ error }}<button type="button" aria-label="关闭错误" @click="error = ''">×</button></div>
    <div v-if="notice" class="notice-line" role="status">{{ notice }}<button type="button" aria-label="关闭提示" @click="notice = ''">×</button></div>

    <section class="block">
      <div class="block-heading"><div><span class="panel-kicker">REVIEW</span><h3>复盘概览</h3></div><span class="count-chip">窗口 {{ report?.windowDays || days }} 天 · 数据行 {{ report?.counts.metricRows || 0 }}</span></div>
      <div v-if="funnel" class="funnel-grid">
        <div><span>曝光</span><strong>{{ funnel.impressions }}</strong></div>
        <div><span>点击</span><strong>{{ funnel.clicks }}</strong></div>
        <div><span>转存</span><strong>{{ funnel.transfers }}</strong></div>
        <div><span>拉新</span><strong>{{ funnel.newUsers }}</strong></div>
        <div><span>会员单</span><strong>{{ funnel.vipOrders }}</strong></div>
        <div><span>收入</span><strong>¥{{ funnel.revenue.toFixed(2) }}</strong></div>
        <div><span>成本</span><strong>¥{{ funnel.cost.toFixed(2) }}</strong></div>
        <div><span>净额</span><strong class="gold">¥{{ funnel.net.toFixed(2) }}</strong></div>
        <div><span>CTR</span><strong>{{ funnel.ctr }}%</strong></div>
        <div><span>转存率</span><strong>{{ funnel.transferRate }}%</strong></div>
        <div><span>拉新率</span><strong>{{ funnel.newUserRate }}%</strong></div>
        <div><span>千次曝光收入</span><strong>¥{{ funnel.revenuePer1k }}</strong></div>
      </div>
      <div v-else class="empty-line">还没有复盘数据：先绑定分享链接、生成物料并回填转化数据。</div>

      <div class="review-columns">
        <div class="review-box">
          <span class="panel-kicker">COMPLIANCE</span>
          <ul class="plain-list">
            <li v-for="line in report?.compliance || []" :key="line">◆ {{ line }}</li>
            <li v-if="!(report?.compliance || []).length">暂无合规检查结果。</li>
          </ul>
        </div>
        <div class="review-box">
          <span class="panel-kicker">SUGGESTIONS</span>
          <ul class="plain-list">
            <li v-for="line in report?.suggestions || []" :key="line">◇ {{ line }}</li>
            <li v-if="!(report?.suggestions || []).length">弥娅暂时没有额外建议。</li>
          </ul>
        </div>
      </div>

      <div v-if="platformRows.length" class="mini-table">
        <div class="mini-head"><span>平台</span><span>曝光</span><span>点击</span><span>转存</span><span>拉新</span><span>净额</span></div>
        <div v-for="row in platformRows" :key="row.platform" class="mini-row"><span>{{ platformLabel(row.platform) }}</span><span>{{ row.impressions }}</span><span>{{ row.clicks }}</span><span>{{ row.transfers }}</span><span>{{ row.newUsers }}</span><span>¥{{ row.net.toFixed(2) }}</span></div>
      </div>
      <p class="boundary-text">{{ report?.boundary || '弥娅只做到站内组装、按渠道生成草稿与数据复盘；对外发布、收款与交易仍由你逐条确认。' }}</p>
    </section>

    <section class="block">
      <div class="block-heading"><div><span class="panel-kicker">CHANNELS</span><h3>分发平台</h3></div><span class="count-chip">{{ channels.length }} 个 · 启用 {{ channels.filter(item => item.enabled).length }} 个</span></div>
      <p class="warn-text">只填公开推广链接与邀请码，<b>不要填账号密码、Cookie 或令牌</b>。弥娅不会用它们登录任何平台。</p>
      <div v-if="channels.length" class="channel-list">
        <article v-for="channel in channels" :key="channel.id" class="channel-row" :class="{ muted: !channel.enabled }">
          <div class="row-main">
            <div class="row-title"><strong>{{ channel.name }}</strong><span class="tag">{{ channelKindLabels.find(([key]) => key === channel.kind)?.[1] || channel.kind }}</span><span v-if="!channel.enabled" class="tag off">已停用</span></div>
            <div class="row-meta">
              <span>key: {{ channel.key }}</span>
              <span v-if="channel.promoCode">邀请码: {{ channel.promoCode }}</span>
              <span v-if="channel.settlementCycle">结算: {{ channel.settlementCycle }}</span>
            </div>
            <a v-if="channel.promoUrl" class="row-link" :href="channel.promoUrl" target="_blank" rel="noopener noreferrer">{{ channel.promoUrl }}</a>
            <small v-else class="row-warn">还没有推广链接，物料生成时会缺承接入口</small>
            <p v-if="channel.notes" class="row-note">{{ channel.notes }}</p>
          </div>
          <div class="row-actions">
            <label class="switch"><input type="checkbox" :checked="channel.enabled" @change="toggleChannel(channel)"><span>启用</span></label>
            <button class="text-button" type="button" @click="editChannel(channel)">编辑</button>
            <button class="text-button danger" type="button" @click="removeChannel(channel)">删除</button>
          </div>
        </article>
      </div>
      <div v-else class="empty-line">还没有分发平台。先添加一个网盘 CPS / 拉新渠道（例如百度网盘、夸克），再把资源包绑到它上面。</div>

      <form class="inline-form" @submit.prevent="saveChannel">
        <div class="form-row">
          <label><span>名称</span><input v-model="channelForm.name" placeholder="例如：百度网盘 CPS" required></label>
          <label><span>key（可留空自动生成）</span><input v-model="channelForm.key" placeholder="baidu-pan"></label>
          <label><span>类型</span>
            <select v-model="channelForm.kind">
              <option v-for="[key, label] in channelKindLabels" :key="key" :value="key">{{ label }}</option>
            </select>
          </label>
        </div>
        <div class="form-row">
          <label><span>公开推广链接</span><input v-model="channelForm.promoUrl" type="url" placeholder="https://pan.example.com/s/xxxx"></label>
          <label><span>邀请码 / 口令</span><input v-model="channelForm.promoCode" placeholder="公开邀请码，不是密码"></label>
          <label><span>结算周期</span><input v-model="channelForm.settlementCycle" placeholder="例如：次月 15 日"></label>
        </div>
        <label><span>备注</span><input v-model="channelForm.notes" placeholder="分佣比例、结算说明等（不要写账号密码）"></label>
        <div class="form-actions">
          <button class="primary-button" :disabled="workingKey === 'channel-save'">{{ channelForm.id ? '保存修改' : '新增分发平台' }}</button>
          <button v-if="channelForm.id" class="text-button" type="button" @click="resetChannelForm">取消编辑</button>
        </div>
      </form>
    </section>

    <section class="block">
      <div class="block-heading"><div><span class="panel-kicker">TARGETS</span><h3>投放位</h3></div><span class="count-chip">{{ targets.length }} 个</span></div>
      <div v-if="targets.length" class="target-list">
        <article v-for="target in targets" :key="target.id" class="target-card">
          <header><strong>{{ platformLabel(target.platform) }}</strong><span class="tag">{{ target.accountLabel }}</span><span class="tag">日发上限 {{ target.dailyPostLimit }}</span></header>
          <a v-if="target.profileUrl" class="row-link" :href="target.profileUrl" target="_blank" rel="noopener noreferrer">{{ target.profileUrl }}</a>
          <p class="row-note">{{ target.audienceNote || '还没有人群备注' }}</p>
          <button class="text-button danger" type="button" @click="removeTarget(target)">删除投放位</button>
        </article>
      </div>
      <div v-else class="empty-line">还没有投放位。登记一个账号位（只填账号标识和主页链接）后，弥娅才能按平台模板生成草稿。</div>
      <form class="inline-form" @submit.prevent="addTarget">
        <div class="form-row">
          <label><span>平台</span><select v-model="targetForm.platform"><option v-for="[key, label] in platformLabels" :key="key" :value="key">{{ label }}</option></select></label>
          <label><span>账号标识</span><input v-model="targetForm.accountLabel" placeholder="例如：小红书主号（不要填密码）" required></label>
          <label><span>日发上限</span><input v-model.number="targetForm.dailyPostLimit" type="number" min="1" max="50"></label>
        </div>
        <div class="form-row">
          <label><span>主页链接</span><input v-model="targetForm.profileUrl" type="url" placeholder="https://..."></label>
          <label><span>人群备注</span><input v-model="targetForm.audienceNote" placeholder="例如：考研学生、职场新人"></label>
        </div>
        <button class="primary-button" :disabled="workingKey === 'target-add'">{{ workingKey === 'target-add' ? '保存中…' : '登记投放位' }}</button>
      </form>
    </section>

    <section class="block">
      <div class="block-heading"><div><span class="panel-kicker">PACKAGES</span><h3>资源包</h3></div><span class="count-chip">{{ packages.length }} 个 · 可分发 {{ report?.counts.readyPackages || 0 }}</span></div>
      <div v-if="packages.length" class="package-list">
        <article v-for="item in packages" :key="item.id" class="package-card">
          <header>
            <div><strong>{{ item.title }}</strong><div class="row-meta"><span>{{ item.channelName || '未绑定分发平台' }}</span><span>{{ item.resourceCount }} 份资源</span><span class="tag" :class="`status-${item.status}`">{{ packageStatusLabels[item.status] || item.status }}</span></div></div>
            <a v-if="item.shareUrl" class="row-link" :href="item.shareUrl" target="_blank" rel="noopener noreferrer">已绑定分享链接</a>
            <small v-else class="row-warn">尚未绑定网盘分享链接</small>
          </header>
          <p v-if="item.keywords.length" class="row-note">关键词：{{ item.keywords.join('、') }}</p>
          <p v-if="item.coverHint" class="row-note">封面提示：{{ item.coverHint }}</p>
          <div class="row-actions wrap">
            <button v-if="item.status === 'draft'" class="secondary-button" type="button" :disabled="workingKey === `package-${item.id}`" @click="setPackageStatus(item, 'ready')">标记为可分发</button>
            <button v-if="item.status === 'ready'" class="text-button" type="button" :disabled="workingKey === `package-${item.id}`" @click="setPackageStatus(item, 'draft')">退回草稿</button>
            <button v-if="item.status === 'published'" class="text-button" type="button" :disabled="workingKey === `package-${item.id}`" @click="setPackageStatus(item, 'retired')">停用</button>
            <button class="text-button danger" type="button" @click="removePackage(item)">删除</button>
          </div>
          <details class="share-drawer">
            <summary>{{ item.shareUrl ? '更新分享链接' : '绑定网盘分享链接' }}</summary>
            <div class="form-row">
              <label><span>分享链接</span><input v-model="item.draft.shareUrl" type="url" placeholder="https://pan.example.com/s/xxxx"></label>
              <label><span>提取码</span><input v-model="item.draft.sharePassword" placeholder="可留空"></label>
            </div>
            <label><span>分享备注</span><input v-model="item.draft.shareNote" placeholder="例如：转存后请先看 00-说明.txt"></label>
            <button class="secondary-button" type="button" :disabled="workingKey === `share-${item.id}`" @click="bindShare(item)">{{ workingKey === `share-${item.id}` ? '绑定中…' : '保存分享链接' }}</button>
          </details>
        </article>
      </div>
      <div v-else class="empty-line">还没有资源包。先在「执行」页确认资源授权已核验、状态为可售，再在这里按 5-15 份一组组装。</div>
      <form class="inline-form" @submit.prevent="createPackage">
        <div class="form-row">
          <label><span>资源包名称</span><input v-model="packageForm.title" placeholder="例如：考研英语资料合集" required></label>
          <label><span>分发平台</span>
            <select v-model.number="packageForm.channelId">
              <option :value="null">暂不绑定</option>
              <option v-for="channel in channels" :key="channel.id" :value="channel.id">{{ channel.name }}</option>
            </select>
          </label>
        </div>
        <div class="form-row">
          <label><span>资源 ID（逗号分隔）</span><input v-model="packageForm.resourceIds" placeholder="1, 2, 3"></label>
          <label><span>关键词（逗号分隔）</span><input v-model="packageForm.keywords" placeholder="考研英语, 单词, 真题"></label>
        </div>
        <label><span>封面提示</span><input v-model="packageForm.coverHint" placeholder="例如：浅色背景 + 资料截图九宫格"></label>
        <button class="primary-button" :disabled="workingKey === 'package-add'">{{ workingKey === 'package-add' ? '组装中…' : '组装资源包' }}</button>
      </form>
    </section>

    <section class="block">
      <div class="block-heading">
        <div><span class="panel-kicker">MATERIALS</span><h3>投放物料</h3></div>
        <div class="heading-actions">
          <select v-model="materialFilter">
            <option value="all">全部状态</option>
            <option value="draft">草稿</option>
            <option value="submitted">待你批准</option>
            <option value="approved">已批准</option>
            <option value="published">已发布</option>
            <option value="retired">已停用</option>
          </select>
          <button class="secondary-button" type="button" :disabled="workingKey === 'material-sync'" @click="syncActions">{{ workingKey === 'material-sync' ? '回填中…' : '同步审批结果' }}</button>
        </div>
      </div>
      <p v-if="pendingMaterials.length" class="approval-hint">有 {{ pendingMaterials.length }} 条物料在审批箱里等你确认：批准动作在「执行」页的「外部动作审批箱」完成，批准后再到平台手动发布。</p>

      <div v-if="visibleMaterials.length" class="material-list">
        <article v-for="material in visibleMaterials" :key="material.id" class="material-row">
          <div class="material-main">
            <div class="row-title">
              <span class="tag">{{ platformLabel(material.platform) }}</span>
              <strong>{{ material.title }}</strong>
              <span class="tag" :class="`status-${material.status}`">{{ material.status === 'submitted' ? '待你批准' : material.status === 'approved' ? '已批准' : material.status === 'published' ? '已发布' : material.status === 'retired' ? '已停用' : '草稿' }}</span>
              <span class="tag variant">v{{ material.variant }}</span>
            </div>
            <div v-if="material.riskFlags.length" class="risk-line">
              <span v-for="flag in material.riskFlags" :key="flag">⚠ {{ flag }}</span>
            </div>
            <details class="body-drawer">
              <summary>查看文案</summary>
              <pre>{{ material.body }}</pre>
              <p v-if="material.cta" class="row-note">引导语：{{ material.cta }}</p>
              <p v-if="material.tags.length" class="row-note">标签：{{ material.tags.join(' ') }}</p>
            </details>
            <div v-if="material.status === 'submitted'" class="pending-line">
              待你批准{{ material.actionId ? ` #${material.actionId}` : '' }} —— 到「执行」页的审批箱批准，然后回到平台手动发布。
            </div>
            <a v-if="material.publishedUrl" class="row-link" :href="material.publishedUrl" target="_blank" rel="noopener noreferrer">{{ material.publishedUrl }}</a>
          </div>
          <div class="row-actions column">
            <button v-if="['draft', 'retired'].includes(material.status)" class="secondary-button" type="button" :disabled="workingKey === `promote-${material.id}`" @click="promote(material)">{{ workingKey === `promote-${material.id}` ? '提交中…' : '提交审批' }}</button>
            <template v-if="material.status === 'approved'">
              <input v-model="material.publishDraft" placeholder="发布后的公开链接（可留空）">
              <button class="primary-button" type="button" :disabled="workingKey === `publish-${material.id}`" @click="markPublished(material)">{{ workingKey === `publish-${material.id}` ? '记录中…' : '标记已发布' }}</button>
            </template>
            <button v-if="material.status === 'published'" class="secondary-button" type="button" @click="openMetricForm(material)">回填转化数据</button>
            <button class="text-button danger" type="button" @click="removeMaterial(material)">删除</button>
          </div>
        </article>
      </div>
      <div v-else class="empty-line">当前筛选下还没有投放物料。用下面的「按渠道生成」建立第一批草稿，或先运行一次分发巡检。</div>

      <form class="inline-form" @submit.prevent="generateMaterials">
        <div class="form-row">
          <label><span>资源包</span>
            <select v-model.number="genForm.packageId" required>
              <option :value="null">选择资源包</option>
              <option v-for="item in packages" :key="item.id" :value="item.id">{{ item.title }}</option>
            </select>
          </label>
          <label><span>版本数（1-10）</span><input v-model.number="genForm.variants" type="number" min="1" max="10"></label>
          <label class="switch inline"><input v-model="genForm.replace" type="checkbox"><span>替换已有同版本草稿</span></label>
        </div>
        <div class="target-picker">
          <span>投放位（不选则使用全部启用投放位）</span>
          <div class="picker-grid">
            <button v-for="target in targets" :key="target.id" type="button" :class="{ selected: genForm.targetIds.includes(target.id) }" @click="toggleGenTarget(target.id)">
              {{ genForm.targetIds.includes(target.id) ? '✓ ' : '' }}{{ platformLabel(target.platform) }} · {{ target.accountLabel }}
            </button>
            <span v-if="!targets.length" class="row-warn">还没有投放位，先在上方登记。</span>
          </div>
        </div>
        <button class="primary-button" :disabled="workingKey === 'material-generate'">{{ workingKey === 'material-generate' ? '生成中…' : '按渠道生成投放草稿' }}</button>
      </form>

      <form class="inline-form metric-form" @submit.prevent="recordMetrics">
        <div class="block-heading"><div><span class="panel-kicker">METRICS</span><h4>回填转化数据</h4></div><span class="count-chip">{{ metricForm.materialId ? `物料 #${metricForm.materialId}` : '只按资源包登记' }}</span></div>
        <div class="form-row">
          <label><span>关联资源包</span>
            <select v-model.number="metricForm.packageId">
              <option :value="null">不关联</option>
              <option v-for="item in packages" :key="item.id" :value="item.id">{{ item.title }}</option>
            </select>
          </label>
          <label><span>日期</span><input v-model="metricForm.statDate" type="date"></label>
          <label><span>曝光</span><input v-model.number="metricForm.impressions" type="number" min="0"></label>
          <label><span>点击</span><input v-model.number="metricForm.clicks" type="number" min="0"></label>
          <label><span>转存</span><input v-model.number="metricForm.transfers" type="number" min="0"></label>
        </div>
        <div class="form-row">
          <label><span>拉新</span><input v-model.number="metricForm.newUsers" type="number" min="0"></label>
          <label><span>会员单</span><input v-model.number="metricForm.vipOrders" type="number" min="0"></label>
          <label><span>佣金收入</span><input v-model.number="metricForm.revenue" type="number" min="0" step="0.01"></label>
          <label><span>成本</span><input v-model.number="metricForm.cost" type="number" min="0" step="0.01"></label>
        </div>
        <label><span>备注</span><input v-model="metricForm.note" placeholder="平台、活动或口径说明"></label>
        <button class="primary-button" :disabled="workingKey === 'metrics-add'">{{ workingKey === 'metrics-add' ? '记录中…' : '记录转化数据' }}</button>
      </form>
    </section>
  </div>
</template>

<style scoped>
.distribution-panel{--gold:#e8d5a3;--green:#9fe3c0;--red:#e59393;--warm:#f0b072;--line:rgba(162,245,238,.14);display:flex;flex-direction:column;gap:1rem;letter-spacing:0}
.panel-band{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;padding:1rem;border:1px solid var(--line);background:rgba(9,20,28,.58)}
.panel-band h2{margin:.28rem 0;font-size:1.05rem;font-weight:560}
.panel-band p{max-width:620px;margin:.4rem 0 0;color:rgba(238,245,244,.58);font-size:.72rem;line-height:1.6}
.panel-kicker{font-size:.6rem;color:var(--earth-accent-light,#a2f5ee);letter-spacing:.12em}
.band-actions{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.day-control{display:flex;align-items:center;gap:.35rem;color:rgba(238,245,244,.5);font-size:.62rem}
.day-control select{width:auto}
.error-line,.notice-line{display:flex;align-items:center;justify-content:space-between;gap:.6rem;padding:.55rem .7rem;font-size:.68rem}
.error-line{border:1px solid rgba(229,147,147,.35);background:rgba(60,24,24,.5);color:var(--red)}
.notice-line{border:1px solid rgba(232,213,163,.28);background:rgba(32,30,23,.6);color:var(--gold)}
.error-line button,.notice-line button{border:0;background:transparent;color:inherit;cursor:pointer}
.block{border:1px solid var(--line);background:rgba(9,20,28,.58);padding:1rem}
.block-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:.8rem;flex-wrap:wrap;margin-bottom:.7rem}
.block-heading h3{margin:.24rem 0 0;font-size:.92rem;font-weight:560}
.block-heading h4{margin:.24rem 0 0;font-size:.85rem;font-weight:560}
.count-chip{padding:.2rem .45rem;border:1px solid var(--line);color:rgba(238,245,244,.5);font-size:.58rem}
.heading-actions{display:flex;align-items:center;gap:.45rem;flex-wrap:wrap}
.heading-actions select{width:auto}
.funnel-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid var(--line);background:rgba(5,12,18,.5)}
.funnel-grid div{padding:.6rem .7rem;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.funnel-grid span{display:block;color:rgba(238,245,244,.45);font-size:.58rem}
.funnel-grid strong{display:block;margin-top:.2rem;font-size:.92rem;color:rgba(238,245,244,.9);font-weight:560}
.funnel-grid strong.gold{color:var(--gold)}
.review-columns{display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin-top:.7rem}
.review-box{border:1px solid var(--line);background:rgba(5,12,18,.42);padding:.7rem}
.plain-list{margin:.45rem 0 0;padding:0;list-style:none;display:flex;flex-direction:column;gap:.3rem}
.plain-list li{color:rgba(238,245,244,.62);font-size:.66rem;line-height:1.55}
.mini-table{margin-top:.7rem;border:1px solid var(--line)}
.mini-head,.mini-row{display:grid;grid-template-columns:1.2fr repeat(5,minmax(0,1fr));gap:.4rem;padding:.42rem .6rem;font-size:.62rem}
.mini-head{color:var(--earth-accent-light,#a2f5ee);border-bottom:1px solid var(--line)}
.mini-row{border-bottom:1px solid var(--line);color:rgba(238,245,244,.62)}
.mini-row:last-child{border-bottom:0}
.boundary-text{margin:.7rem 0 0;padding:.55rem .7rem;border-left:2px solid var(--gold);background:rgba(232,213,163,.06);color:rgba(238,245,244,.62);font-size:.64rem;line-height:1.55}
.warn-text{margin:0 0 .6rem;padding:.5rem .65rem;border-left:2px solid var(--warm);background:rgba(240,176,114,.08);color:var(--warm);font-size:.64rem;line-height:1.55}
.warn-text b{color:#ffd9b0}
.channel-list,.package-list,.material-list{display:flex;flex-direction:column;border-top:1px solid var(--line)}
.channel-row{display:grid;grid-template-columns:minmax(0,1fr) 165px;gap:.8rem;padding:.7rem .2rem;border-bottom:1px solid var(--line)}
.channel-row.muted{opacity:.55}
.row-main{min-width:0}
.row-title{display:flex;align-items:center;gap:.45rem;flex-wrap:wrap}
.row-title strong{font-size:.74rem}
.row-meta{display:flex;gap:.6rem;flex-wrap:wrap;margin-top:.28rem;color:rgba(238,245,244,.45);font-size:.58rem}
.row-link{display:block;margin-top:.28rem;color:var(--earth-accent-light,#a2f5ee);font-size:.6rem;word-break:break-all;text-decoration:none}
.row-link:hover{text-decoration:underline}
.row-warn{display:block;margin-top:.28rem;color:var(--warm);font-size:.58rem}
.row-note{margin:.28rem 0 0;color:rgba(238,245,244,.5);font-size:.62rem;line-height:1.5}
.row-actions{display:flex;align-items:center;gap:.45rem;flex-wrap:wrap;justify-content:flex-end}
.row-actions.column{flex-direction:column;align-items:stretch}
.row-actions.wrap{justify-content:flex-start;margin-top:.5rem}
.tag{padding:.16rem .38rem;border:1px solid var(--line);color:rgba(238,245,244,.62);font-size:.55rem}
.tag.off{color:var(--warm);border-color:rgba(240,176,114,.35)}
.tag.variant{color:rgba(238,245,244,.45)}
.tag.status-draft{color:rgba(238,245,244,.55)}
.tag.status-ready,.tag.status-approved{color:var(--green);border-color:rgba(159,227,192,.35)}
.tag.status-submitted{color:var(--gold);border-color:rgba(232,213,163,.35)}
.tag.status-published{color:var(--earth-accent-light,#a2f5ee);border-color:rgba(162,245,238,.35)}
.tag.status-retired{color:rgba(238,245,244,.4)}
.inline-form{margin-top:.8rem;padding-top:.8rem;border-top:1px solid var(--line);display:flex;flex-direction:column;gap:.65rem}
.form-row{display:flex;gap:.65rem;flex-wrap:wrap}
.form-row>label{flex:1;min-width:150px}
label>span{display:block;margin-bottom:.28rem;color:rgba(238,245,244,.55);font-size:.6rem}
input,select,textarea{width:100%;box-sizing:border-box;border:1px solid rgba(162,245,238,.18);border-radius:2px;background:rgba(0,0,0,.24);color:inherit;padding:.5rem .6rem;font-size:.7rem;outline:none;font:inherit;letter-spacing:0}
input:focus,select:focus{border-color:rgba(162,245,238,.52)}
.form-actions{display:flex;align-items:center;gap:.5rem}
.primary-button,.secondary-button{border:1px solid rgba(162,245,238,.38);background:rgba(120,207,209,.13);color:var(--earth-accent-light,#a2f5ee);padding:.55rem .8rem;cursor:pointer;font-size:.68rem;font:inherit;letter-spacing:0}
.primary-button{background:var(--earth-accent-deep,#4f9fa5);color:#061015;border-color:transparent;font-weight:650}
.primary-button:disabled,.secondary-button:disabled,.text-button:disabled{opacity:.45;cursor:default}
.text-button{border:0;background:transparent;color:var(--earth-accent-light,#a2f5ee);cursor:pointer;font-size:.62rem;padding:.3rem 0;font:inherit;letter-spacing:0}
.text-button.danger{color:var(--red)}
.switch{display:flex;align-items:center;gap:.4rem;color:rgba(238,245,244,.6);font-size:.62rem}
.switch.inline{flex:0 0 auto}
.switch input{width:auto}
.target-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.6rem}
.target-card{border:1px solid var(--line);background:rgba(5,12,18,.42);padding:.7rem}
.target-card header{display:flex;align-items:center;gap:.4rem;flex-wrap:wrap}
.target-card strong{font-size:.72rem}
.package-card{border-bottom:1px solid var(--line);padding:.75rem .2rem}
.package-card header{display:flex;align-items:flex-start;justify-content:space-between;gap:.8rem;flex-wrap:wrap}
.package-card header strong{font-size:.76rem}
.share-drawer{margin-top:.55rem;border-top:1px dashed var(--line);padding-top:.5rem}
.share-drawer summary{cursor:pointer;color:rgba(238,245,244,.5);font-size:.62rem}
.share-drawer .form-row{margin-top:.55rem}
.material-row{display:grid;grid-template-columns:minmax(0,1fr) 220px;gap:.8rem;padding:.75rem .2rem;border-bottom:1px solid var(--line)}
.material-main{min-width:0}
.risk-line{display:flex;flex-wrap:wrap;gap:.3rem;margin-top:.4rem}
.risk-line span{padding:.2rem .4rem;border:1px solid rgba(240,176,114,.45);background:rgba(240,176,114,.1);color:var(--warm);font-size:.57rem}
.body-drawer{margin-top:.5rem}
.body-drawer summary{cursor:pointer;color:rgba(238,245,244,.5);font-size:.62rem}
.body-drawer pre{margin:.5rem 0 0;padding:.6rem;border:1px solid var(--line);background:rgba(0,0,0,.3);color:rgba(238,245,244,.7);font-size:.62rem;line-height:1.6;white-space:pre-wrap;word-break:break-word;max-height:260px;overflow:auto}
.pending-line{margin-top:.45rem;padding:.4rem .55rem;border-left:2px solid var(--gold);background:rgba(232,213,163,.07);color:var(--gold);font-size:.62rem}
.approval-hint{margin:0 0 .6rem;padding:.5rem .65rem;border-left:2px solid var(--gold);background:rgba(232,213,163,.07);color:rgba(238,245,244,.66);font-size:.63rem;line-height:1.55}
.target-picker>span{display:block;margin-bottom:.3rem;color:rgba(238,245,244,.55);font-size:.6rem}
.picker-grid{display:flex;flex-wrap:wrap;gap:.4rem}
.picker-grid button{border:1px solid var(--line);background:rgba(120,207,209,.06);color:rgba(238,245,244,.62);padding:.38rem .6rem;cursor:pointer;font-size:.62rem;font:inherit;letter-spacing:0}
.picker-grid button.selected{border-color:rgba(162,245,238,.5);color:var(--earth-accent-light,#a2f5ee)}
.metric-form .form-row{margin-bottom:0}
.empty-line{padding:.75rem;border:1px dashed var(--line);color:rgba(238,245,244,.45);font-size:.66rem;line-height:1.6}
@media(max-width:980px){.funnel-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.review-columns{grid-template-columns:1fr}.channel-row,.material-row{grid-template-columns:1fr}.row-actions{justify-content:flex-start}.panel-band{flex-direction:column}}
@media(max-width:700px){.funnel-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.mini-head,.mini-row{grid-template-columns:1fr repeat(3,minmax(0,1fr));font-size:.55rem}.mini-head span:nth-child(3),.mini-head span:nth-child(5),.mini-row span:nth-child(3),.mini-row span:nth-child(5){display:none}}
</style>
