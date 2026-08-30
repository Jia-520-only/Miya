<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import API from '@/api/core'
import EarthAPI, { type EarthTheme } from '@/api/earth'
import MiyaButton from '@/components/ui/MiyaButton.vue'
import InputText from '@/components/ui/MiyaInputText.vue'
import Slider from '@/components/ui/MiyaSlider.vue'
import ToggleSwitch from '@/components/ui/MiyaToggleSwitch.vue'
import { audioSettings, bgmState, fetchMusicLibrary, playBgm, setBgmPlaylist } from '@/composables/useAudio'
import { COLOR_GROUPS, colorStorageKey, componentColors } from '@/composables/useComponentColors'
import { useHomeBriefing } from '@/composables/useHomeBriefing'
import { CONFIG } from '@/utils/config'
import { apiUrl } from '@/utils/api-url'
import { isLegacyBackground } from '@/utils/backgroundAssets'
import type { Live2dPackageInfo } from '@/electron'

const router = useRouter()
type TabKey = 'appearance' | 'model' | 'soul' | 'memory' | 'system' | 'audio' | 'color' | 'live2d' | 'panel'
const activeTab = ref<TabKey>('appearance')
const backendOnline = ref(false)
const musicLibrary = ref<Array<{ id: string, title: string, source: string, url: string, kind?: string, playable?: boolean }>>([])
const playableMusicLibrary = computed(() => musicLibrary.value.filter(track => track.playable !== false && track.kind !== 'material'))
const currentBgmFile = ref('')

// ── 配置面板（API Key / 人设 / 管理账号） ──
const panelApi = (path = '') => apiUrl(`/api/config/panel${path}`)
const panelLoading = ref(false)
const envGroups = ref<Array<{ group: string, effect: string, keys: Array<{ key: string, label: string, configured: boolean, masked: string, newValue: string, saving: boolean }> }>>([])
const personaList = ref<Array<{ id: string, name: string, full_name: string, description: string }>>([])
const currentPersona = ref('')
const personaSwitching = ref('')
const personaSwitchMsg = ref('')
const editingPersona = ref('')
const personaForm = ref<{ name: string, full_name: string, description: string, prompt: string }>({ name: '', full_name: '', description: '', prompt: '' })
const personaSaving = ref(false)
const personaMsg = ref('')
const adminDraft = ref<Record<string, { name: string, ids: Record<string, string> }>>({})
const adminSaving = ref(false)
const adminMsg = ref('')

async function loadPanel() {
  panelLoading.value = true
  try {
    const res = await fetch(panelApi('/overview')).then(r => r.json())
    if (res.success) {
      envGroups.value = (res.env_groups || []).map((g: any) => ({
        ...g,
        keys: (g.keys || []).map((k: any) => ({ ...k, newValue: '', saving: false })),
      }))
      personaList.value = res.personas || []
      currentPersona.value = res.current_persona || 'normal'
      const admins: Record<string, { name: string, ids: Record<string, string> }> = {}
      for (const [person, info] of Object.entries(res.superadmins || {})) {
        const ids: Record<string, string> = {}
        for (const [platform, idList] of Object.entries((info as any).ids || {}))
          ids[platform] = Array.isArray(idList) ? idList.join(', ') : String(idList)
        admins[person] = { name: (info as any).name || person, ids }
      }
      adminDraft.value = admins
    }
    await Promise.allSettled([loadModels(), loadForms()])
  }
  catch { /* 后端未启动时静默 */ }
  finally { panelLoading.value = false }
}

async function saveEnvKey(item: { key: string, newValue: string, saving: boolean, masked: string, configured: boolean }) {
  const value = item.newValue.trim()
  if (!value)
    return
  item.saving = true
  try {
    const res = await fetch(panelApi('/env'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: item.key, value }),
    }).then(r => r.json())
    if (res.success) {
      item.configured = true
      item.masked = res.masked
      item.newValue = ''
    }
    else { alert(res.detail || '保存失败') }
  }
  catch { alert('保存失败：后端未连接') }
  finally { item.saving = false }
}

async function switchPersona(id: string) {
  if (id === currentPersona.value || personaSwitching.value)
    return
  personaSwitching.value = id
  personaSwitchMsg.value = ''
  try {
    const res = await fetch(panelApi('/persona/switch'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: id }),
    }).then(r => r.json())
    if (res.success) {
      currentPersona.value = id
      personaSwitchMsg.value = res.message || '已切换'
    }
    else { personaSwitchMsg.value = res.detail || '切换失败' }
  }
  catch { personaSwitchMsg.value = '切换失败：后端未连接' }
  finally {
    personaSwitching.value = ''
    setTimeout(() => (personaSwitchMsg.value = ''), 3000)
  }
}

async function openPersonaEditor(id: string) {
  personaMsg.value = ''
  try {
    const res = await fetch(panelApi(`/personas/${encodeURIComponent(id)}`)).then(r => r.json())
    if (res.success) {
      const p = res.persona
      editingPersona.value = id
      personaForm.value = { name: p.name, full_name: p.full_name, description: p.description, prompt: p.prompt }
    }
    else { personaMsg.value = res.detail || '读取失败' }
  }
  catch { personaMsg.value = '读取失败：后端未连接' }
}

// ── 人设卡新建 / 删除 ──
const creatingPersona = ref(false)
const newPersonaForm = ref({ id: '', name: '', full_name: '', description: '', template: '' })
const personaCreating = ref(false)
const templateOptions = computed(() => [
  { id: '', label: '空白模板（_template）' },
  ...personaList.value.map(p => ({ id: p.id, label: `复制 ${p.name} (${p.id})` })),
])

async function createPersona() {
  const f = newPersonaForm.value
  if (personaCreating.value)
    return
  if (!f.id.trim() || !f.name.trim()) {
    personaMsg.value = '人设卡 ID 与名称不能为空'
    setTimeout(() => (personaMsg.value = ''), 3000)
    return
  }
  personaCreating.value = true
  personaMsg.value = ''
  try {
    const res = await fetch(panelApi('/personas'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(f),
    }).then(r => r.json())
    if (res.success) {
      personaMsg.value = res.message
      creatingPersona.value = false
      newPersonaForm.value = { id: '', name: '', full_name: '', description: '', template: '' }
      await loadPanel()
      openPersonaEditor(res.id)
    }
    else { personaMsg.value = res.detail || '创建失败' }
  }
  catch { personaMsg.value = '创建失败：后端未连接' }
  finally {
    personaCreating.value = false
    setTimeout(() => (personaMsg.value = ''), 4000)
  }
}

async function removePersona(id: string) {
  if (!confirm(`确定删除人设卡 ${id} 吗？删除前会自动备份到 config/backup/panel/。`))
    return
  personaMsg.value = ''
  try {
    const res = await fetch(panelApi(`/personas/${encodeURIComponent(id)}/delete`), { method: 'POST' }).then(r => r.json())
    personaMsg.value = res.success ? res.message : (res.detail || '删除失败')
    if (res.success) {
      if (editingPersona.value === id)
        editingPersona.value = ''
      await loadPanel()
    }
  }
  catch { personaMsg.value = '删除失败：后端未连接' }
  finally { setTimeout(() => (personaMsg.value = ''), 4000) }
}

async function savePersona() {
  if (!editingPersona.value || personaSaving.value)
    return
  personaSaving.value = true
  personaMsg.value = ''
  try {
    const res = await fetch(panelApi(`/personas/${encodeURIComponent(editingPersona.value)}`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(personaForm.value),
    }).then(r => r.json())
    personaMsg.value = res.success ? '人设卡已保存 ✓' : (res.detail || '保存失败')
    if (res.success)
      await loadPanel()
  }
  catch { personaMsg.value = '保存失败：后端未连接' }
  finally {
    personaSaving.value = false
    setTimeout(() => (personaMsg.value = ''), 3000)
  }
}

async function saveAdmins() {
  if (adminSaving.value)
    return
  adminSaving.value = true
  adminMsg.value = ''
  try {
    const superadmins: Record<string, { name: string, ids: Record<string, string> }> = {}
    for (const [person, info] of Object.entries(adminDraft.value)) {
      const ids: Record<string, string> = {}
      for (const [platform, val] of Object.entries(info.ids)) {
        if (val.trim())
          ids[platform] = val
      }
      superadmins[person] = { name: info.name, ids }
    }
    const res = await fetch(panelApi('/superadmins'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ superadmins }),
    }).then(r => r.json())
    adminMsg.value = res.success ? (res.message || '已保存') : (res.detail || '保存失败')
    if (res.success)
      await loadPanel()
  }
  catch { adminMsg.value = '保存失败：后端未连接' }
  finally {
    adminSaving.value = false
    setTimeout(() => (adminMsg.value = ''), 4000)
  }
}

const EFFECT_HINTS: Record<string, string> = {
  instant: '保存即生效',
  restart: '保存后需重启相关平台',
  hot: '保存后自动热重载',
}

// ── 模型池 ──
const ROUTE_TASKS: Array<[string, string]> = [
  ['simple_chat', '对话'],
  ['complex_reasoning', '推理'],
  ['code_analysis', '代码分析'],
  ['creative_writing', '创作'],
  ['tool_calling', '工具调用'],
  ['summarization', '摘要'],
  ['image_description', '图像'],
  ['agent_mode', 'Agent'],
  ['computer_use', '电脑操作'],
]
function normalizeRouting(source: Record<string, any> | null | undefined): Record<string, any> {
  const routing = { ...(source || {}) }
  for (const [task] of ROUTE_TASKS) {
    routing[task] = {
      primary: '@active',
      secondary: '',
      fallback: '',
      ...(routing[task] || {}),
    }
  }
  return routing
}
const modelPool = ref<{ active: string, models: any[], routing: Record<string, any> }>({
  active: '',
  models: [],
  routing: normalizeRouting({}),
})
const modelMsg = ref('')
const modelBusy = ref('')
const editingModel = ref<any>(null)
const modelSaving = ref(false)
const modelRouteOptions = computed(() => ['@active', ...modelPool.value.models.map((m: any) => m.id)])

async function loadModels() {
  try {
    const res = await fetch(panelApi('/models')).then(r => r.json())
    if (res.success) {
      modelPool.value = {
        active: res.active || '',
        models: Array.isArray(res.models) ? res.models : [],
        routing: normalizeRouting(res.routing),
      }
    }
  }
  catch { /* 后端未启动时静默 */ }
}

async function setActiveModel(id: string) {
  if (id === modelPool.value.active || modelBusy.value)
    return
  modelBusy.value = id
  modelMsg.value = ''
  try {
    const res = await fetch(panelApi('/models/active'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: id }),
    }).then(r => r.json())
    if (res.success) {
      modelPool.value.active = id
      modelMsg.value = res.message
    }
    else { modelMsg.value = res.detail || '切换失败' }
  }
  catch { modelMsg.value = '切换失败：后端未连接' }
  finally {
    modelBusy.value = ''
    setTimeout(() => (modelMsg.value = ''), 4000)
  }
}

function openModelEditor(m: any) {
  editingModel.value = m
    ? { ...m, api_key: '', isNew: false }
    : { id: '', name: '', provider: 'openai', base_url: '', env_key: '', api_key: '', api_key_masked: '', key_source: 'none', description: '', type: 'chat', disabled: false, isNew: true }
}

async function saveModel() {
  const m = editingModel.value
  if (!m || modelSaving.value)
    return
  const id = (m.id || '').trim()
  if (!id || !m.name?.trim() || !m.base_url?.trim()) {
    modelMsg.value = '模型 ID、名称与 base_url 不能为空'
    setTimeout(() => (modelMsg.value = ''), 3000)
    return
  }
  modelSaving.value = true
  modelMsg.value = ''
  try {
    const res = await fetch(panelApi(`/models/${encodeURIComponent(id)}`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: m.name, provider: m.provider, base_url: m.base_url,
        env_key: m.env_key, api_key: m.api_key || '', description: m.description, type: m.type, disabled: m.disabled,
      }),
    }).then(r => r.json())
    if (res.success) {
      modelMsg.value = res.message
      editingModel.value = null
      await loadModels()
    }
    else { modelMsg.value = res.detail || '保存失败' }
  }
  catch { modelMsg.value = '保存失败：后端未连接' }
  finally {
    modelSaving.value = false
    setTimeout(() => (modelMsg.value = ''), 4000)
  }
}

async function removeModel(id: string) {
  if (modelBusy.value)
    return
  if (!confirm(`确定删除模型 ${id} 吗？相关路由引用会一并清理。`))
    return
  modelBusy.value = id
  modelMsg.value = ''
  try {
    const res = await fetch(panelApi(`/models/${encodeURIComponent(id)}/delete`), { method: 'POST' }).then(r => r.json())
    modelMsg.value = res.success ? res.message : (res.detail || '删除失败')
    if (res.success)
      await loadModels()
  }
  catch { modelMsg.value = '删除失败：后端未连接' }
  finally {
    modelBusy.value = ''
    setTimeout(() => (modelMsg.value = ''), 4000)
  }
}

async function saveRouting() {
  if (modelBusy.value)
    return
  modelBusy.value = 'routing'
  modelMsg.value = ''
  try {
    const res = await fetch(panelApi('/models/routing'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ routing: modelPool.value.routing }),
    }).then(r => r.json())
    if (res.success) {
      modelPool.value.routing = normalizeRouting(res.routing)
      modelMsg.value = res.message
    }
    else { modelMsg.value = res.detail || '保存失败' }
  }
  catch { modelMsg.value = '保存失败：后端未连接' }
  finally {
    modelBusy.value = ''
    setTimeout(() => (modelMsg.value = ''), 4000)
  }
}

// ── 通用配置表单 ──
const genericForms = ref<Array<{ id: string, label: string, effect: string, hint: string, saving: boolean, msg: string, fields: Array<{ key: string, label: string, type: string, options?: string[], value: any, configured?: boolean }> }>>([])

async function loadForms() {
  try {
    const res = await fetch(panelApi('/forms')).then(r => r.json())
    if (res.success)
      genericForms.value = (res.forms || []).map((f: any) => ({ ...f, saving: false, msg: '' }))
  }
  catch { /* 后端未启动时静默 */ }
}

async function saveForm(form: { id: string, fields: any[], saving: boolean, msg: string }) {
  if (form.saving)
    return
  form.saving = true
  form.msg = ''
  const values: Record<string, any> = {}
  for (const f of form.fields)
    values[f.key] = f.value
  try {
    const res = await fetch(panelApi(`/forms/${encodeURIComponent(form.id)}`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ values }),
    }).then(r => r.json())
    form.msg = res.success ? (res.message + (res.updated_fields?.length ? `（${res.updated_fields.length} 项）` : '')) : (res.detail || '保存失败')
    if (res.success)
      await loadForms()
  }
  catch { form.msg = '保存失败：后端未连接' }
  finally {
    form.saving = false
    setTimeout(() => (form.msg = ''), 4000)
  }
}

// ── 实时数据 ──
const systemStatus = ref<any>(null)
const personaData = ref<any>(null)
const platformData = ref<any[]>([])
const memoryStats = ref<any>(null)
const providerList = ref<any[]>([])

// ── 配置文件编辑器 ──
const configFiles = ref<Array<{ name: string, path: string, size: number }>>([])
const editingFile = ref('')
const editingContent = ref('')
const editingSaved = ref(false)

// ── Live2D 独立窗口配置 ──
const live2dCfg = useStorage('miya-live2d-window-config', {
  bgColor: '#000000',
  bgAlpha: 0,
  windowScale: 100,
  modelScale: 100,
  alwaysOnTop: true,
  visible: true,
  clickThrough: false,
  mouseTracking: false,
  mouseIdleReturn: true,
})
// useStorage keeps older objects as-is; backfill fields introduced in upgrades.
if (live2dCfg.value.clickThrough === undefined) live2dCfg.value.clickThrough = false
if (live2dCfg.value.mouseTracking === undefined) live2dCfg.value.mouseTracking = false
if (live2dCfg.value.mouseIdleReturn === undefined) live2dCfg.value.mouseIdleReturn = true
const live2dPackages = ref<Live2dPackageInfo[]>([])
const live2dPackageBusy = ref(false)
const live2dPackageMsg = ref('')

const formatLive2dSize = (bytes: number) => bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`

async function refreshLive2dPackages() {
  live2dPackages.value = await window.live2dAPI?.listPackages?.() ?? []
}

async function importLive2dPackage() {
  live2dPackageBusy.value = true
  live2dPackageMsg.value = ''
  try {
    const item = await window.live2dAPI?.importPackage?.()
    if (item) live2dPackageMsg.value = `已导入 ${item.name}${item.active ? '，已自动启用' : ''}`
    await refreshLive2dPackages()
  }
  catch (error) { live2dPackageMsg.value = error instanceof Error ? error.message : String(error) }
  finally { live2dPackageBusy.value = false }
}

async function activateLive2dPackage(id: string) {
  live2dPackageBusy.value = true
  try {
    await window.live2dAPI?.activatePackage?.(id)
    live2dPackageMsg.value = '角色已切换，Live2D 窗口正在重新加载'
    await refreshLive2dPackages()
  }
  catch (error) { live2dPackageMsg.value = error instanceof Error ? error.message : String(error) }
  finally { live2dPackageBusy.value = false }
}

async function removeLive2dPackage(item: Live2dPackageInfo) {
  if (!confirm(`删除角色“${item.name}”？`)) return
  live2dPackageBusy.value = true
  try {
    await window.live2dAPI?.deletePackage?.(item.id)
    await refreshLive2dPackages()
  }
  catch (error) { live2dPackageMsg.value = error instanceof Error ? error.message : String(error) }
  finally { live2dPackageBusy.value = false }
}

function setLive2dBg(e?: Event) {
  if (e)
    live2dCfg.value.bgColor = (e.target as HTMLInputElement).value
  const api = window.live2dAPI
  if (!api)
    return
  const hex = live2dCfg.value.bgColor.replace('#', '')
  api.setBackground?.(`0x${hex}`, live2dCfg.value.bgAlpha)
}

let live2dScaleTimer: ReturnType<typeof setTimeout> | null = null
function setLive2dScale(immediate = false) {
  if (live2dScaleTimer) clearTimeout(live2dScaleTimer)
  const apply = async () => {
    live2dScaleTimer = null
    const applied = await window.live2dAPI?.setWindowScale?.(live2dCfg.value.windowScale)
    if (typeof applied === 'number') live2dCfg.value.windowScale = applied
  }
  if (immediate) void apply()
  else live2dScaleTimer = setTimeout(apply, 80)
}

function setLive2dAlwaysOnTop() {
  const api = window.live2dAPI
  if (api)
    api.setAlwaysOnTop(live2dCfg.value.alwaysOnTop)
}

function setLive2dModelScale() {
  window.live2dAPI?.setModelScale?.(live2dCfg.value.modelScale)
}

function setLive2dMouseTracking() {
  window.live2dAPI?.setTracking(live2dCfg.value.mouseTracking)
}

function setLive2dMouseIdleReturn() {
  window.live2dAPI?.setMouseIdleReturn(live2dCfg.value.mouseIdleReturn)
}

async function setLive2dClickThrough() {
  const api = window.live2dAPI
  if (!api) {
    live2dPackageMsg.value = '鼠标穿透仅在 Electron 桌面版中可用'
    live2dCfg.value.clickThrough = false
    return
  }
  const applied = await api.setClickThrough(live2dCfg.value.clickThrough)
  live2dPackageMsg.value = applied ? '鼠标穿透已在 Live2D 窗口生效' : (live2dCfg.value.clickThrough ? 'Live2D 窗口未就绪，穿透未生效' : '鼠标穿透已关闭')
  if (live2dCfg.value.clickThrough && !applied) live2dCfg.value.clickThrough = false
}

function enableLive2dDesktopMode() {
  live2dCfg.value.bgColor = '#000000'
  live2dCfg.value.bgAlpha = 0
  live2dCfg.value.alwaysOnTop = true
  setLive2dBg()
  setLive2dAlwaysOnTop()
}

async function setLive2dVisibility() {
  const api = window.live2dAPI
  if (api)
    await api.setVisibility(live2dCfg.value.visible)
}

function resetLive2dPos() {
  const api = window.live2dAPI
  if (api)
    api.resetPosition()
}

function resetLive2dSize() {
  live2dCfg.value.windowScale = 100
  setLive2dScale(true)
}

function resetLive2dModelSize() {
  live2dCfg.value.modelScale = 100
  setLive2dModelScale()
}

async function loadConfigFiles() {
  try {
    const res = await fetch(apiUrl('/api/desktop/files/list?path=config')).then(r => r.json())
    configFiles.value = (res.files || []).filter((f: any) => !f.is_dir && (f.name.endsWith('.json') || f.name.endsWith('.yaml') || f.name.endsWith('.yml')))
  }
  catch {}
}

async function openConfigFile(filePath: string) {
  try {
    const res = await fetch(apiUrl(`/api/desktop/files/read?path=${encodeURIComponent(filePath)}`)).then(r => r.json())
    editingFile.value = filePath
    editingContent.value = res.content || JSON.stringify(res.data || res, null, 2)
    editingSaved.value = false
  }
  catch { editingContent.value = '读取失败' }
}

async function saveConfigFile() {
  try {
    await fetch(apiUrl('/api/desktop/files/write'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: editingFile.value, content: editingContent.value }),
    })
    editingSaved.value = true
    setTimeout(() => editingSaved.value = false, 2000)
  }
  catch { alert('保存失败') }
}

onMounted(async () => {
  musicLibrary.value = await fetchMusicLibrary()
  setBgmPlaylist(playableMusicLibrary.value.map(track => ({ file: track.url, title: track.title })))
  currentBgmFile.value = playableMusicLibrary.value[0]?.id || ''
  const savedLive2dConfig = await window.live2dAPI?.getConfig?.()
  if (savedLive2dConfig) Object.assign(live2dCfg.value, savedLive2dConfig)
  loadEarthTheme()
  await refreshLive2dPackages()
  try {
    const health = await API.health()
    backendOnline.value = health.status === 'healthy'
    if (!backendOnline.value)
      return

    const [status, persona, mem, providers] = await Promise.allSettled([
      API.systemStatus(),
      API.getCurrentPersona(),
      API.getMemoryStats(),
      API.listModels().then((r: any) => (r?.models || []).map((m: any) => ({ ...m, available: m.enabled }))).catch(() => []),
    ])
    systemStatus.value = status.status === 'fulfilled' ? status.value : null
    personaData.value = persona.status === 'fulfilled' ? persona.value : null
    memoryStats.value = mem.status === 'fulfilled' ? mem.value : null
    providerList.value = providers.status === 'fulfilled' ? providers.value : []

    // 平台（WebAPI 自带的 /api/platform/stats，返回 {platforms: [{id, name, enable, status}]}）
    const plat = await fetch(apiUrl('/api/platform/stats')).then(r => r.json()).catch(() => ({}))
    platformData.value = plat.platforms || []
    loadConfigFiles()
    loadPanel()
  }
  catch {}
})

const tabs: { key: TabKey, label: string, icon: string }[] = [
  { key: 'appearance', label: '外观', icon: '✦' },
  { key: 'model', label: '模型', icon: '◈' },
  { key: 'soul', label: '灵魂', icon: '♥' },
  { key: 'memory', label: '记忆', icon: '◆' },
  { key: 'panel', label: '配置', icon: '⚙' },
  { key: 'audio', label: '声音', icon: '♪' },
  { key: 'color', label: '调色', icon: '⬡' },
  { key: 'live2d', label: 'Live2D', icon: '◉' },
  { key: 'system', label: '系统', icon: '◎' },
]

// 外观
const showStatus = useStorage('miya-show-status', true)
const perspectiveEnabled = useStorage('miya-perspective-enabled', true)
const gyroEnabled = useStorage('miya-gyro-enabled', true)
const hudOpacity = useStorage('miya-hud-opacity', 1.0)
const hudVisible = useStorage('miya-hud-visible', true)
const homeGalleryVisible = useStorage('miya-home-gallery-visible', true)
const homeGalleryImages = useStorage<string[]>('miya-home-gallery-images', [])
homeGalleryImages.value = homeGalleryImages.value.filter(image => !isLegacyBackground(image))
const homeGalleryInput = ref<HTMLInputElement>()
const homeGalleryUploading = ref(false)
const homeGalleryMessage = ref('')
const homeGalleryCaptions = useStorage<Record<string, { title: string, description: string }>>('miya-home-gallery-captions', {})
const selectedHomeGalleryImage = ref('')
const homeGalleryTitle = ref('')
const homeGalleryDescription = ref('')
const { items: homeBriefingItems, autoPlay: homeBriefingAutoPlay, intervalSeconds: homeBriefingInterval, showCaption: homeBriefingShowCaption, fallbackGreeting: homeBriefingFallbackGreeting } = useHomeBriefing()
const homeBriefingInput = ref<HTMLInputElement>()
const homeBriefingUploading = ref(false)
const homeBriefingMessage = ref('')

// 背景
const bgImage = useStorage('miya-bg-image', '')
if (isLegacyBackground(bgImage.value))
  bgImage.value = ''
const bgOpacity = useStorage('miya-bg-opacity', 0.35)
const customBackgrounds = useStorage<Array<{ path: string, name: string }>>('miya-custom-backgrounds', [])
const bgFileInput = ref<HTMLInputElement>()
const bgUploading = ref(false)
const bgMessage = ref('')

function pickBgFile() { bgFileInput.value?.click() }
async function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length || bgUploading.value)
    return
  if (files.some(file => !file.type.startsWith('image/'))) {
    bgMessage.value = '请选择图片文件'
    return
  }
  bgUploading.value = true
  bgMessage.value = ''
  try {
    const added: Array<{ path: string, name: string }> = []
    for (const file of files) {
      const result = await EarthAPI.uploadImage(file)
      if (result.image_path)
        added.push({ path: result.image_path, name: file.name })
    }
    customBackgrounds.value = [...customBackgrounds.value, ...added]
    if (added[0])
      bgImage.value = added[0].path
    bgMessage.value = added.length ? `已添加 ${added.length} 张背景，并应用第一张` : '没有可添加的图片'
  }
  catch {
    bgMessage.value = '背景添加失败，请确认桌面后端已经启动'
  }
  finally {
    bgUploading.value = false
  }
}
function selectNone() {
  bgImage.value = ''
  bgMessage.value = '已恢复默认背景'
}

function removeLegacyBackground() {
  bgImage.value = ''
  bgMessage.value = '已清除旧版自定义背景并恢复默认'
}

function selectCustomBackground(path: string) {
  bgImage.value = path
  bgMessage.value = '已应用自定义背景'
}

function removeCustomBackground(index: number) {
  const removed = customBackgrounds.value[index]
  customBackgrounds.value = customBackgrounds.value.filter((_, itemIndex) => itemIndex !== index)
  if (removed?.path === bgImage.value) {
    bgImage.value = ''
    bgMessage.value = '已移除当前背景并恢复默认'
  }
  else {
    bgMessage.value = '已从背景图库移除'
  }
}

function pickHomeGalleryImages() {
  homeGalleryInput.value?.click()
}

function homeGalleryImageUrl(path: string): string {
  return path.startsWith('/api/') ? EarthAPI.imageUrl(path) : path
}

async function onHomeGalleryFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length || homeGalleryUploading.value)
    return
  homeGalleryUploading.value = true
  homeGalleryMessage.value = ''
  try {
    const added: string[] = []
    for (const file of files) {
      const result = await EarthAPI.uploadImage(file)
      if (result.image_path)
        added.push(result.image_path)
    }
    homeGalleryImages.value = [...homeGalleryImages.value, ...added]
    homeGalleryMessage.value = added.length ? `已添加 ${added.length} 张弥娅图片` : '没有可添加的图片'
  }
  catch {
    homeGalleryMessage.value = '图片添加失败，请确认桌面后端已经启动'
  }
  finally {
    homeGalleryUploading.value = false
  }
}

function removeHomeGalleryImage(index: number) {
  const removed = homeGalleryImages.value[index]
  homeGalleryImages.value = homeGalleryImages.value.filter((_, current) => current !== index)
  if (removed && selectedHomeGalleryImage.value === removed) {
    selectedHomeGalleryImage.value = ''
    homeGalleryTitle.value = ''
    homeGalleryDescription.value = ''
  }
}

function editHomeGalleryImage(image: string) {
  selectedHomeGalleryImage.value = image
  const caption = homeGalleryCaptions.value[image]
  homeGalleryTitle.value = caption?.title || ''
  homeGalleryDescription.value = caption?.description || ''
}

function saveHomeGalleryCaption() {
  const image = selectedHomeGalleryImage.value
  if (!image)
    return
  homeGalleryCaptions.value = {
    ...homeGalleryCaptions.value,
    [image]: {
      title: homeGalleryTitle.value.trim(),
      description: homeGalleryDescription.value.trim(),
    },
  }
  homeGalleryMessage.value = '这张图片的首页文字已保存'
}

function pickHomeBriefingImages() {
  homeBriefingInput.value?.click()
}

async function onHomeBriefingFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length || homeBriefingUploading.value)
    return
  homeBriefingUploading.value = true
  homeBriefingMessage.value = ''
  try {
    const added = []
    for (const [fileIndex, file] of files.entries()) {
      const result = await EarthAPI.uploadImage(file)
      if (result.image_path) {
        added.push({
          id: `briefing-${Date.now()}-${fileIndex}`,
          image: result.image_path,
          title: file.name.replace(/\.[^.]+$/, ''),
          description: '',
        })
      }
    }
    homeBriefingItems.value = [...homeBriefingItems.value, ...added]
    homeBriefingMessage.value = added.length ? `已添加 ${added.length} 条动态简报` : '没有可添加的图片'
  }
  catch {
    homeBriefingMessage.value = '简报图片添加失败，请确认桌面后端已经启动'
  }
  finally {
    homeBriefingUploading.value = false
  }
}

function removeHomeBriefing(index: number) {
  homeBriefingItems.value = homeBriefingItems.value.filter((_, itemIndex) => itemIndex !== index)
}

function moveHomeBriefing(index: number, direction: -1 | 1) {
  const target = index + direction
  if (target < 0 || target >= homeBriefingItems.value.length)
    return
  const reordered = [...homeBriefingItems.value]
  const [item] = reordered.splice(index, 1)
  if (!item)
    return
  reordered.splice(target, 0, item)
  homeBriefingItems.value = reordered
}

// ── 辅助 ──
const modelDefaults: Record<string, string> = {
  simple_chat: '对话',
  complex_reasoning: '推理',
  code_analysis: '代码分析',
  creative_writing: '创作',
  tool_calling: '工具调用',
  summarization: '摘要',
  image_description: '图像',
  agent_mode: 'Agent',
  computer_use: '电脑操作',
}

// ── 调色 ──
function resetAllComponentColors() {
  const map: Record<string, string> = {}
  for (const g of COLOR_GROUPS) {
    for (const c of g.colors) map[colorStorageKey(g.id, c.key)] = c.default
  }
  componentColors.value = map
}
function resetComponentGroup(id: string) {
  const g = COLOR_GROUPS.find(x => x.id === id)
  if (!g)
    return
  const updated = { ...(componentColors.value as Record<string, string>) }
  for (const c of g.colors) updated[colorStorageKey(g.id, c.key)] = c.default
  componentColors.value = updated
}

// ── 地球online 主题 ──
const earthTheme = ref<EarthTheme | null>(null)
const earthThemeSaved = ref(false)
const EARTH_THEME_PRESETS: Array<[string, string, string]> = [
  ['Miya OS', '#78cfd1', '#a2f5ee'],
  ['鎏金', '#c9ac67', '#e8d5a3'],
  ['月白', '#9fb4d8', '#d3e0f5'],
  ['青碧', '#3fd0c9', '#a8f0ec'],
  ['绯樱', '#e58aa5', '#ffc9d8'],
  ['星紫', '#9d7bff', '#c9b8ff'],
  ['琥珀', '#e8a24a', '#ffd39a'],
]
async function loadEarthTheme() {
  try {
    earthTheme.value = await EarthAPI.getTheme()
    if (earthTheme.value && isLegacyBackground(earthTheme.value.background))
      earthTheme.value.background = ''
  }
  catch { /* 后端未启动时忽略 */ }
}
async function saveEarthTheme() {
  if (!earthTheme.value)
    return
  earthTheme.value = await EarthAPI.saveTheme({ ...earthTheme.value })
  earthThemeSaved.value = true
  setTimeout(() => (earthThemeSaved.value = false), 2200)
}
async function resetEarthTheme() {
  earthTheme.value = await EarthAPI.resetTheme()
  earthThemeSaved.value = true
  setTimeout(() => (earthThemeSaved.value = false), 2200)
}

function getRouteModel(key: string): string {
  // 真实路由表：primary 支持 @active（跟随激活模型）
  const route = modelPool.value.routing?.[key]
  if (!route?.primary)
    return '—'
  if (route.primary === '@active') {
    const active = modelPool.value.models.find((m: any) => m.id === modelPool.value.active)
    return active ? `${active.name}（跟随激活）` : '@active'
  }
  return route.primary
}
</script>

<template>
  <div class="config-layout">
    <!-- 侧边 Tab 栏 -->
    <aside class="config-sidebar">
      <div class="sidebar-header">
        <button class="back-btn" title="返回首页" @click="router.push('/')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
        </button>
        <span class="sidebar-title">弥娅调谐</span>
      </div>
      <nav class="sidebar-nav">
        <button
          v-for="tab in tabs" :key="tab.key"
          class="tab-btn" :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          <span class="tab-icon">{{ tab.icon }}</span>
          <span class="tab-label">{{ tab.label }}</span>
        </button>
      </nav>
      <div class="sidebar-version">
        v{{ CONFIG.system.version || '7.0' }}
      </div>
    </aside>

    <!-- 内容区 -->
    <main class="config-main">
      <!-- ═══ 外观 ═══ -->
      <div v-show="activeTab === 'appearance'" class="config-page">
        <h2>外观设置</h2>

        <div class="config-section">
          <h3>背景图片</h3>
          <p class="hint">
            背景图库仅保留你从本机添加的图片。支持一次添加多张，点击立即应用。
          </p>
          <div class="bg-grid">
            <div class="bg-thumb" :class="{ active: !bgImage }" @click="selectNone">
              <span class="bg-default">默认</span>
            </div>
            <div v-for="(background, backgroundIndex) in customBackgrounds" :key="background.path" class="bg-thumb custom-bg-thumb" :class="{ active: bgImage === background.path }" :title="background.name" @click="selectCustomBackground(background.path)">
              <img :src="homeGalleryImageUrl(background.path)" :alt="background.name">
              <button class="bg-thumb-remove" title="从图库移除" aria-label="从图库移除" @click.stop="removeCustomBackground(backgroundIndex)">×</button>
              <span>{{ background.name }}</span>
            </div>
            <div v-if="bgImage.startsWith('data:')" class="bg-thumb active custom-bg-thumb legacy-bg-thumb">
              <img :src="bgImage" alt="当前自定义背景">
              <button class="bg-thumb-remove" title="清除旧版背景" aria-label="清除旧版背景" @click.stop="removeLegacyBackground">×</button>
              <span>旧版自定义背景</span>
            </div>
          </div>
          <div class="bg-actions">
            <MiyaButton size="sm" :disabled="bgUploading" @click="pickBgFile">
              {{ bgUploading ? '正在添加…' : '+ 添加背景图片' }}
            </MiyaButton>
            <span v-if="bgMessage" class="bg-message">{{ bgMessage }}</span>
            <input ref="bgFileInput" type="file" accept="image/*" multiple class="hidden" @change="onFileChange">
          </div>
          <div class="config-item" style="margin-top:0.6rem">
            <label>不透明度</label>
            <div class="slider-row">
              <Slider v-model="bgOpacity" :min="0" :max="1" :step="0.01" /><span class="slider-val">{{ Math.round(bgOpacity * 100) }}%</span>
            </div>
          </div>
        </div>

        <div v-if="earthTheme" class="config-section earth-background-config">
          <h3 class="color-group-header">
            <span>◎ 地球 Online 背景</span>
            <span v-if="earthThemeSaved" class="saved-msg">已保存 ✓</span>
          </h3>
          <p class="hint">与首页共用个人背景图库，但可以独立选择图片和透明度。</p>
          <div class="earth-theme-walls">
            <button class="earth-theme-wall" :class="{ active: !earthTheme.background }" @click="earthTheme.background = ''">
              <span class="earth-theme-wall-none">无</span>
            </button>
            <button v-for="background in customBackgrounds" :key="background.path" class="earth-theme-wall" :class="{ active: earthTheme.background === background.path }" :title="background.name" @click="earthTheme.background = background.path">
              <span class="earth-theme-wall-img" :style="{ backgroundImage: `url(${homeGalleryImageUrl(background.path)})` }" />
            </button>
          </div>
          <p v-if="!customBackgrounds.length" class="hint">先在上方“背景图片”中添加图片，这里就会自动出现。</p>
          <div class="hud-extra-row" style="margin-top:0.6rem">
            <label class="he-label">背景透明度</label>
            <div class="he-slider">
              <Slider v-model="earthTheme.background_opacity" :min="0" :max="1" :step="0.05" />
            </div>
            <span class="he-val">{{ Math.round(earthTheme.background_opacity * 100) }}%</span>
          </div>
          <button class="action-btn" style="margin-top:0.7rem" @click="saveEarthTheme">保存地球 Online 背景</button>
        </div>

        <div class="config-section">
          <h3>界面行为</h3>
          <div class="toggle-row">
            <div><span class="model-name">首页透视</span><p class="hint">保持左右操作翼的固定空间倾斜</p></div>
            <ToggleSwitch v-model="perspectiveEnabled" />
          </div>
          <div class="toggle-row">
            <div><span class="model-name">陀螺跟随</span><p class="hint">在透视基础上跟随鼠标轻微移动</p></div>
            <ToggleSwitch v-model="gyroEnabled" />
          </div>
          <div class="toggle-row">
            <div><span class="model-name">顶部状态栏</span><p class="hint">显示弥娅形态、连接状态与时间</p></div>
            <ToggleSwitch v-model="showStatus" />
          </div>
        </div>

        <div class="config-section">
          <h3>首页弥娅美图</h3>
          <div class="config-item gallery-toggle-row">
            <div>
              <label>显示弥娅美图</label>
              <p class="hint">首页中央一次展示三张，可加入任意数量并手动轮换。</p>
            </div>
            <ToggleSwitch v-model="homeGalleryVisible" />
          </div>
          <div v-if="homeGalleryImages.length" class="miya-gallery-grid">
            <div v-for="(image, imageIndex) in homeGalleryImages" :key="`${image}-${imageIndex}`" class="miya-gallery-thumb" :class="{ selected: selectedHomeGalleryImage === image }" @click="editHomeGalleryImage(image)">
              <img :src="homeGalleryImageUrl(image)" alt="弥娅美图">
              <button title="移除这张图片" @click.stop="removeHomeGalleryImage(imageIndex)">×</button>
              <span>{{ String(imageIndex + 1).padStart(2, '0') }}</span>
            </div>
          </div>
          <div v-else class="miya-gallery-empty">还没有弥娅美图，可以从本机添加多张图片。</div>
          <div v-if="selectedHomeGalleryImage" class="miya-gallery-editor">
            <div class="config-item">
              <label>卡片标题</label>
              <InputText v-model="homeGalleryTitle" placeholder="例如：弥娅的午后" class="input-sm" />
            </div>
            <div class="config-item">
              <label>卡片说明</label>
              <textarea v-model="homeGalleryDescription" rows="3" placeholder="写一段只属于这张图片的话；留空则不显示。" />
            </div>
            <button class="action-btn" @click="saveHomeGalleryCaption">保存卡片文字</button>
          </div>
          <div class="bg-actions">
            <button class="action-btn" :disabled="homeGalleryUploading" @click="pickHomeGalleryImages">
              {{ homeGalleryUploading ? '正在添加…' : '+ 添加弥娅图片' }}
            </button>
            <input ref="homeGalleryInput" type="file" accept="image/*" multiple class="hidden" @change="onHomeGalleryFiles">
            <span v-if="homeGalleryMessage" class="gallery-message">{{ homeGalleryMessage }}</span>
          </div>
        </div>

        <div class="config-section home-briefing-config">
          <h3>动态简报 <small>首页左下角情报轮播</small></h3>
          <p class="hint">用于展示新闻、状态或纪念瞬间；与中央弥娅美图相互独立。</p>
          <div class="toggle-row">
            <div><span class="model-name">自动轮播</span><p class="hint">关闭后停留在当前简报</p></div>
            <ToggleSwitch v-model="homeBriefingAutoPlay" />
          </div>
          <div class="toggle-row">
            <div><span class="model-name">显示配字</span><p class="hint">显示图片下方的标题和说明</p></div>
            <ToggleSwitch v-model="homeBriefingShowCaption" />
          </div>
          <div class="config-item">
            <label>轮播间隔</label>
            <div class="slider-row">
              <Slider v-model="homeBriefingInterval" :min="3" :max="15" :step="1" /><span class="slider-val">{{ homeBriefingInterval }} 秒</span>
            </div>
          </div>
          <div class="config-item">
            <label>无寄语时的欢迎语</label>
            <InputText v-model="homeBriefingFallbackGreeting" maxlength="60" placeholder="佳，有什么需要帮忙的吗？" class="input-sm briefing-greeting-input" />
            <p class="hint">首页优先显示地球 Online 的置顶／最新弥娅寄语；没有寄语或接口离线时显示这里。</p>
          </div>

          <div v-if="homeBriefingItems.length" class="home-briefing-list">
            <article v-for="(item, itemIndex) in homeBriefingItems" :key="item.id" class="home-briefing-editor">
              <div class="home-briefing-preview">
                <img v-if="item.image" :src="homeGalleryImageUrl(item.image)" alt="动态简报预览">
                <span v-else>≋</span>
                <small>{{ String(itemIndex + 1).padStart(2, '0') }}</small>
              </div>
              <div class="home-briefing-fields">
                <InputText v-model="item.title" maxlength="24" placeholder="简报标题" />
                <InputText v-model="item.description" maxlength="60" placeholder="简报说明" />
              </div>
              <div class="home-briefing-actions">
                <button :disabled="itemIndex === 0" title="向前移动" @click="moveHomeBriefing(itemIndex, -1)">↑</button>
                <button :disabled="itemIndex === homeBriefingItems.length - 1" title="向后移动" @click="moveHomeBriefing(itemIndex, 1)">↓</button>
                <button class="danger" title="删除简报" @click="removeHomeBriefing(itemIndex)">×</button>
              </div>
            </article>
          </div>
          <div v-else class="miya-gallery-empty">当前没有动态简报，首页会显示科技感默认占位。</div>
          <div class="bg-actions">
            <button class="action-btn" :disabled="homeBriefingUploading" @click="pickHomeBriefingImages">
              {{ homeBriefingUploading ? '正在添加…' : '+ 添加简报图片' }}
            </button>
            <input ref="homeBriefingInput" type="file" accept="image/*" multiple class="hidden" @change="onHomeBriefingFiles">
            <span v-if="homeBriefingMessage" class="gallery-message">{{ homeBriefingMessage }}</span>
          </div>
        </div>

      </div>

      <!-- ═══ 模型 ═══ -->
      <div v-show="activeTab === 'model'" class="config-page">
        <h2>模型配置</h2>
        <div v-if="!backendOnline" class="offline-hint">
          ● 后端未连接
        </div>
        <template v-else>
          <div class="config-section">
            <h3>默认路由</h3>
            <div v-for="(label, key) in modelDefaults" :key="key" class="model-item">
              <span class="model-name">{{ label }}</span>
              <span class="model-val">{{ getRouteModel(key) }}</span>
            </div>
          </div>
          <div class="config-section">
            <h3>注册模型 ({{ providerList.length }})</h3>
            <div v-for="p in providerList.slice(0, 8)" :key="p.id || p.name" class="model-item">
              <span class="model-name">{{ p.name || p.id }}</span>
              <span class="model-val status-on">{{ p.provider || 'API' }}</span>
            </div>
          </div>
          <div class="config-section">
            <h3>协作模式</h3>
            <div class="model-item">
              <span class="model-name">单模型</span><span class="model-val">复杂度 ≤ 2</span>
            </div>
            <div class="model-item">
              <span class="model-name">链式</span><span class="model-val">复杂度 ≤ 3</span>
            </div>
            <div class="model-item">
              <span class="model-name">并行</span><span class="model-val">复杂度 ≤ 4</span>
            </div>
          </div>
        </template>
      </div>

      <!-- ═══ 灵魂 ═══ -->
      <div v-show="activeTab === 'soul'" class="config-page">
        <h2>灵魂 & 情绪</h2>
        <div v-if="!backendOnline" class="offline-hint">
          ● 后端未连接
        </div>
        <template v-else>
          <div class="config-section">
            <h3>当前状态</h3>
            <div class="model-item">
              <span class="model-name">人格</span><span class="model-val">{{ personaData?.persona?.name || personaData?.persona?.id || '默认' }}</span>
            </div>
          </div>
        </template>
      </div>

      <!-- ═══ 记忆 ═══ -->
      <div v-show="activeTab === 'memory'" class="config-page">
        <h2>记忆系统</h2>
        <div v-if="!backendOnline" class="offline-hint">
          ● 后端未连接
        </div>
        <template v-else>
          <div class="config-section">
            <h3>存储统计</h3>
            <div class="model-item">
              <span class="model-name">记忆节点</span><span class="model-val">{{ memoryStats?.nodeCount || memoryStats?.node_count || 0 }}</span>
            </div>
            <div class="model-item">
              <span class="model-name">记忆边</span><span class="model-val">{{ memoryStats?.edgeCount || memoryStats?.edge_count || 0 }}</span>
            </div>
            <div class="model-item">
              <span class="model-name">存储大小</span><span class="model-val">{{ memoryStats?.memorySize || memoryStats?.memory_size || 'N/A' }}</span>
            </div>
          </div>
          <div class="config-section">
            <h3>记忆层级</h3>
            <div class="model-item">
              <span class="model-name">短期记忆</span><span class="model-val">TTL 3600s</span>
            </div>
            <div class="model-item">
              <span class="model-name">对话记忆</span><span class="model-val">每会话 100 条</span>
            </div>
            <div class="model-item">
              <span class="model-name">长期记忆</span><span class="model-val">最多 10000 条</span>
            </div>
            <div class="model-item">
              <span class="model-name">语义记忆</span><span class="model-val status-on">SQLite / 1024维</span>
            </div>
          </div>
        </template>
      </div>

      <!-- ═══ 系统 ═══ -->
      <div v-show="activeTab === 'system'" class="config-page">
        <h2>系统</h2>
        <div class="config-section">
          <h3>API 连接</h3>
          <div class="model-item">
            <span class="model-name">后端状态</span><span class="model-val" :class="backendOnline ? 'status-on' : ''">{{ backendOnline ? '● 在线' : '○ 离线' }}</span>
          </div>
          <div class="config-item" style="margin-top:0.5rem">
            <label>API 地址</label>
            <InputText v-model="CONFIG.api.base_url" placeholder="http://localhost:8000" class="input-sm" />
          </div>
        </div>
        <div class="config-section">
          <h3>平台状态 ({{ platformData.length }})</h3>
          <div v-for="p in platformData" :key="p.id" class="model-item">
            <span class="model-name">{{ p.name || p.id }}</span>
            <span class="model-val" :class="p.status === 'online' ? 'status-on' : ''">{{ p.status === 'online' ? '在线' : p.status }}</span>
          </div>
          <div v-if="!platformData.length && backendOnline" class="model-item">
            <span class="model-name">加载中...</span>
          </div>
        </div>
        <div class="config-section">
          <h3>安全</h3>
          <div class="model-item">
            <span class="model-name">权限管理</span><span class="model-val status-on">已启用</span>
          </div>
          <div class="model-item">
            <span class="model-name">注入检测</span><span class="model-val status-on">已启用</span>
          </div>
          <div class="model-item">
            <span class="model-name">审计日志</span><span class="model-val status-on">已启用</span>
          </div>
        </div>
        <div class="config-section">
          <h3>配置文件</h3>
          <p class="hint">
            编辑 JSON/YAML 配置文件，保存后需重启生效
          </p>
          <div class="file-list">
            <button v-for="f in configFiles" :key="f.name" class="file-btn" :class="{ active: editingFile === f.path }" @click="openConfigFile(f.path)">
              <span class="file-name">{{ f.name }}</span>
              <span class="file-size">{{ (f.size / 1024).toFixed(1) }}KB</span>
            </button>
          </div>
          <div v-if="editingFile" class="editor-area" style="margin-top:0.5rem">
            <div class="editor-header">
              <span class="editor-path">{{ editingFile }}</span>
              <div class="editor-actions">
                <span v-if="editingSaved" class="saved-msg">✓ 已保存</span>
                <button class="action-btn" @click="saveConfigFile">
                  保存
                </button>
                <button class="action-btn" @click="editingFile = ''">
                  关闭
                </button>
              </div>
            </div>
            <textarea v-model="editingContent" class="editor-text" rows="20" spellcheck="false" />
          </div>
        </div>
      </div>

      <!-- ═══ 配置面板（API Key / 人设 / 管理账号） ═══ -->
      <div v-show="activeTab === 'panel'" class="config-page">
        <h2>配置中心</h2>
        <div v-if="!backendOnline" class="offline-hint">
          ● 后端未连接
        </div>
        <div v-else-if="panelLoading" class="offline-hint">
          正在读取配置…
        </div>
        <template v-else>
          <!-- API 密钥 -->
          <div v-for="g in envGroups" :key="g.group" class="config-section">
            <h3>{{ g.group }} <span class="effect-tag">{{ EFFECT_HINTS[g.effect] || '' }}</span></h3>
            <div v-for="item in g.keys" :key="item.key" class="secret-row">
              <div class="secret-label">
                <span class="secret-name">{{ item.label }}</span>
                <code class="secret-key">{{ item.key }}</code>
              </div>
              <span class="secret-masked" :class="{ configured: item.configured }">
                {{ item.configured ? item.masked : '未配置' }}
              </span>
              <div class="secret-input">
                <input
                  v-model="item.newValue"
                    type="password"
                    class="input-sm secret-field"
                    placeholder="输入新值…"
                    autocomplete="off"
                    @keyup.enter="saveEnvKey(item)"
                >
                <button class="action-btn" :disabled="!item.newValue.trim() || item.saving" @click="saveEnvKey(item)">
                  {{ item.saving ? '保存中…' : '保存' }}
                </button>
              </div>
            </div>
          </div>

          <!-- 人设卡 -->
          <div class="config-section">
            <h3>
              人设卡 ({{ personaList.length }})
              <span v-if="personaSwitchMsg" class="saved-msg">{{ personaSwitchMsg }}</span>
            </h3>
            <p class="hint">
              点击卡片切换当前形态（热切换立即生效）；「编辑」修改角色卡的名字、简介与提示词，保存前自动备份。
            </p>
            <div class="persona-grid">
              <div
                v-for="p in personaList" :key="p.id"
                class="persona-card" :class="{ active: p.id === currentPersona }"
                @click="switchPersona(p.id)"
              >
                <div class="persona-card-head">
                  <span class="persona-name">{{ p.name }}</span>
                  <span v-if="p.id === currentPersona" class="persona-current">当前</span>
                </div>
                <p class="persona-desc">{{ p.description }}</p>
                <div class="persona-card-actions">
                  <button
                    v-if="p.id !== 'normal' && p.id !== currentPersona"
                    class="action-btn danger" title="删除这张人设卡"
                    @click.stop="removePersona(p.id)"
                  >
                    删除
                  </button>
                  <button class="action-btn" :disabled="personaSwitching === p.id" @click.stop="openPersonaEditor(p.id)">
                    编辑
                  </button>
                </div>
              </div>
            </div>
            <button class="action-btn" style="margin-top:0.5rem" @click="creatingPersona = !creatingPersona">
              {{ creatingPersona ? '收起' : '+ 新建人设卡' }}
            </button>
            <div v-if="creatingPersona" class="persona-editor">
              <div class="editor-header">
                <span class="editor-path">新建人设卡</span>
                <div class="editor-actions">
                  <button class="action-btn" :disabled="personaCreating" @click="createPersona">
                    {{ personaCreating ? '创建中…' : '创建' }}
                  </button>
                </div>
              </div>
              <div class="form-grid">
                <div class="config-item">
                  <label>人设卡 ID（小写英文，如 yingge）</label>
                  <InputText v-model="newPersonaForm.id" class="input-sm" placeholder="yingge" />
                </div>
                <div class="config-item">
                  <label>形态名</label>
                  <InputText v-model="newPersonaForm.name" class="input-sm" placeholder="莺歌态" />
                </div>
                <div class="config-item">
                  <label>英文标识</label>
                  <InputText v-model="newPersonaForm.full_name" class="input-sm" placeholder="Yingge" />
                </div>
                <div class="config-item">
                  <label>基于</label>
                  <select v-model="newPersonaForm.template" class="route-select" style="width:100%">
                    <option v-for="opt in templateOptions" :key="opt.id || 'blank'" :value="opt.id">{{ opt.label }}</option>
                  </select>
                </div>
              </div>
              <div class="config-item">
                <label>简介</label>
                <InputText v-model="newPersonaForm.description" class="input-sm" placeholder="一句话介绍" />
              </div>
              <p class="hint">创建后自动打开编辑器，可继续填写提示词；weights/情绪等结构由模板提供。</p>
            </div>
            <div v-if="editingPersona" class="persona-editor">
              <div class="editor-header">
                <span class="editor-path">personality/{{ editingPersona }}.yaml</span>
                <div class="editor-actions">
                  <span v-if="personaMsg" class="saved-msg">{{ personaMsg }}</span>
                  <button class="action-btn" :disabled="personaSaving" @click="savePersona">
                    {{ personaSaving ? '保存中…' : '保存人设卡' }}
                  </button>
                  <button class="action-btn" @click="editingPersona = ''">
                    关闭
                  </button>
                </div>
              </div>
              <div class="config-item">
                <label>形态名（name，同步命令系统的 form_names 显示）</label>
                <InputText v-model="personaForm.name" class="input-sm" placeholder="如：绯雪态" />
              </div>
              <div class="config-item">
                <label>英文标识（full_name）</label>
                <InputText v-model="personaForm.full_name" class="input-sm" placeholder="如 Feixue" />
              </div>
              <div class="config-item">
                <label>简介（description）</label>
                <InputText v-model="personaForm.description" class="input-sm" placeholder="一句话介绍" />
              </div>
              <div class="config-item">
                <label>提示词（prompt）</label>
                <textarea v-model="personaForm.prompt" rows="10" spellcheck="false" class="editor-text" />
              </div>
            </div>
          </div>

          <!-- 管理账号 -->
          <div class="config-section">
            <h3>
              管理账号（超级管理员）
              <span v-if="adminMsg" class="saved-msg">{{ adminMsg }}</span>
            </h3>
            <p class="hint">
              各平台的超管 ID，多个用英文逗号分隔；清空某个平台则移除该平台权限。保存即时生效。
            </p>
            <div v-for="(info, person) in adminDraft" :key="person" class="admin-person">
              <div class="admin-person-name">{{ info.name || person }}</div>
              <div v-for="(ids, platform) in info.ids" :key="platform" class="admin-id-row">
                <span class="admin-platform">{{ platform }}</span>
                <input v-model="info.ids[platform]" class="input-sm" :placeholder="`${platform} 的超管 ID`">
              </div>
            </div>
            <button class="action-btn" :disabled="adminSaving" @click="saveAdmins">
              {{ adminSaving ? '保存中…' : '保存管理账号' }}
            </button>
          </div>

          <!-- 模型池 -->
          <div class="config-section">
            <h3>
              模型池 ({{ modelPool.models.length }})
              <span class="effect-tag">{{ EFFECT_HINTS.hot }}</span>
              <span v-if="modelMsg" class="saved-msg">{{ modelMsg }}</span>
            </h3>
            <p class="hint">
              点击「激活」切换当前默认模型；编辑或新增 OpenAI 兼容端点（Key 从 .env 引用）。
            </p>
            <div v-for="m in modelPool.models" :key="m.id" class="model-row">
              <div class="model-info">
                <span class="model-title">
                  {{ m.name }}
                  <span v-if="m.id === modelPool.active" class="persona-current">激活</span>
                  <span v-if="m.disabled" class="model-off">停用</span>
                </span>
                <code class="model-meta">{{ m.provider }} · {{ m.base_url }}<template v-if="m.env_key"> · {{ m.env_key }}</template></code>
              </div>
              <div class="model-ops">
                <button v-if="m.id !== modelPool.active" class="action-btn" :disabled="modelBusy === m.id" @click="setActiveModel(m.id)">
                  激活
                </button>
                <button class="action-btn" @click="openModelEditor(m)">
                  编辑
                </button>
                <button class="action-btn danger" :disabled="modelBusy === m.id" @click="removeModel(m.id)">
                  删除
                </button>
              </div>
            </div>
            <button class="action-btn" style="margin-top:0.5rem" @click="openModelEditor(null)">
              + 新增模型
            </button>

            <div v-if="editingModel" class="persona-editor">
              <div class="editor-header">
                <span class="editor-path">{{ editingModel.isNew ? '新模型' : `models/${editingModel.id}` }}</span>
                <div class="editor-actions">
                  <button class="action-btn" :disabled="modelSaving" @click="saveModel">
                    {{ modelSaving ? '保存中…' : '保存模型' }}
                  </button>
                  <button class="action-btn" @click="editingModel = null">
                    关闭
                  </button>
                </div>
              </div>
              <div class="form-grid">
                <div class="config-item">
                  <label>模型 ID（英文标识）</label>
                  <InputText v-model="editingModel.id" class="input-sm" :disabled="!editingModel.isNew" placeholder="如 my_proxy" />
                </div>
                <div class="config-item">
                  <label>模型名（API model 参数）</label>
                  <InputText v-model="editingModel.name" class="input-sm" placeholder="如 deepseek-chat" />
                </div>
                <div class="config-item">
                  <label>Provider</label>
                  <InputText v-model="editingModel.provider" class="input-sm" placeholder="openai / siliconflow / oneapi…" />
                </div>
                <div class="config-item">
                  <label>Base URL</label>
                  <InputText v-model="editingModel.base_url" class="input-sm" placeholder="https://api.example.com/v1" />
                </div>
                <div class="config-item">
                  <label>API Key 引用（.env 变量名，二选一）</label>
                  <InputText v-model="editingModel.env_key" class="input-sm" placeholder="如 MY_API_KEY" />
                </div>
                <div class="config-item">
                  <label>API Key 直填（中转站等非预设端点）</label>
                  <input
                    v-model="editingModel.api_key" type="password" class="input-sm"
                    :placeholder="editingModel.api_key_masked || 'sk-…（留空 = 不修改）'"
                    autocomplete="new-password"
                  >
                  <p v-if="editingModel.key_source === 'env'" class="hint" style="margin:0.25rem 0 0">
                    当前 Key 来源：.env 的 {{ editingModel.env_key }}
                  </p>
                  <p v-else-if="editingModel.key_source === 'inline'" class="hint" style="margin:0.25rem 0 0">
                    当前使用直存 Key（{{ editingModel.api_key_masked }}）
                  </p>
                </div>
                <div class="config-item">
                  <label>类型</label>
                  <InputText v-model="editingModel.type" class="input-sm" placeholder="chat / vision" />
                </div>
              </div>
              <div class="config-item">
                <label>描述</label>
                <InputText v-model="editingModel.description" class="input-sm" placeholder="一句话说明" />
              </div>
              <div class="toggle-row">
                <span>停用该模型</span>
                <ToggleSwitch v-model="editingModel.disabled" />
              </div>
            </div>

            <!-- 路由策略 -->
            <h3 style="margin-top:1rem">
              任务路由
              <span class="effect-tag">@active = 跟随激活模型</span>
            </h3>
            <div v-for="[task, taskLabel] in ROUTE_TASKS" :key="task" class="route-row">
              <span class="route-task">{{ taskLabel }}</span>
              <div class="route-selects">
                <select v-model="modelPool.routing[task].primary" class="route-select">
                  <option v-for="opt in modelRouteOptions" :key="opt" :value="opt">{{ opt }}</option>
                </select>
                <select v-model="modelPool.routing[task].secondary" class="route-select">
                  <option value="">—</option>
                  <option v-for="opt in modelRouteOptions" :key="opt" :value="opt">{{ opt }}</option>
                </select>
                <select v-model="modelPool.routing[task].fallback" class="route-select">
                  <option value="">—</option>
                  <option v-for="opt in modelRouteOptions" :key="opt" :value="opt">{{ opt }}</option>
                </select>
              </div>
            </div>
            <button class="action-btn" style="margin-top:0.5rem" :disabled="modelBusy === 'routing'" @click="saveRouting">
              保存路由策略
            </button>
          </div>

          <!-- 通用配置表单 -->
          <div v-for="form in genericForms" :key="form.id" class="config-section">
            <h3>
              {{ form.label }}
              <span class="effect-tag">{{ EFFECT_HINTS[form.effect] || '' }}</span>
              <span v-if="form.msg" class="saved-msg">{{ form.msg }}</span>
            </h3>
            <p v-if="form.hint" class="hint">{{ form.hint }}</p>
            <div class="form-grid">
              <div v-for="f in form.fields" :key="f.key" class="config-item">
                <template v-if="f.type === 'bool'">
                  <div class="toggle-row">
                    <span>{{ f.label }}</span>
                    <ToggleSwitch v-model="f.value" />
                  </div>
                </template>
                <template v-else-if="f.type === 'select'">
                  <label>{{ f.label }}</label>
                  <select v-model="f.value" class="route-select" style="width:100%">
                    <option v-for="opt in f.options" :key="opt" :value="opt">{{ opt }}</option>
                  </select>
                </template>
                <template v-else-if="f.type === 'secret'">
                  <label>{{ f.label }}{{ f.configured ? '' : '（未配置）' }}</label>
                  <input
                    v-model="f.value" type="password" class="input-sm"
                    placeholder="留空 = 不修改" autocomplete="new-password"
                  >
                </template>
                <template v-else-if="f.type === 'textarea'">
                  <label>{{ f.label }}</label>
                  <textarea v-model="f.value" rows="4" class="editor-text" spellcheck="false" />
                </template>
                <template v-else-if="f.type === 'int' || f.type === 'float'">
                  <label>{{ f.label }}</label>
                  <input v-model.number="f.value" type="number" class="input-sm" :step="f.type === 'float' ? 0.05 : 1">
                </template>
                <template v-else>
                  <label>{{ f.label }}</label>
                  <InputText v-model="f.value" class="input-sm" />
                </template>
              </div>
            </div>
            <button class="action-btn" :disabled="form.saving" @click="saveForm(form)">
              {{ form.saving ? '保存中…' : `保存${form.label}` }}
            </button>
          </div>
        </template>
      </div>

      <!-- ═══ 声音 ═══ -->
      <div v-show="activeTab === 'audio'" class="config-page">
        <h2>声音</h2>
        <div class="config-section">
          <h3>背景音乐</h3>
          <div class="toggle-row"><span class="model-name">启用</span><ToggleSwitch v-model="audioSettings.bgmEnabled" /></div>
          <div class="config-item" style="margin-top:0.5rem"><label>音量</label><div class="slider-row"><Slider v-model="audioSettings.bgmVolume" :min="0" :max="1" :step="0.01" /><span class="slider-val">{{ Math.round(audioSettings.bgmVolume * 100) }}%</span></div></div>
          <div class="config-item"><label>曲目</label><div class="color-modes"><button v-for="track in playableMusicLibrary" :key="track.id" class="color-btn file-btn-audio" :class="{ active: bgmState.file === track.url || currentBgmFile === track.id }" @click="currentBgmFile = track.id; playBgm(track.url, track.title).catch(() => {})">{{ track.kind === 'cover' ? `弥娅翻唱 · ${track.title}` : track.title }}</button><span v-if="!playableMusicLibrary.length" class="hint">暂无可用音乐</span></div></div>
        </div>
        <div class="config-section">
          <h3>音效</h3>
          <div class="toggle-row">
            <span class="model-name">启用</span>
            <ToggleSwitch v-model="audioSettings.effectEnabled" />
          </div>
          <div class="config-item" style="margin-top:0.5rem">
            <label>音量</label>
            <div class="slider-row">
              <Slider v-model="audioSettings.effectVolume" :min="0" :max="1" :step="0.01" />
              <span class="slider-val">{{ Math.round(audioSettings.effectVolume * 100) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ 调色 ═══ -->
      <div v-show="activeTab === 'color'" class="config-page">
        <h2>组件调色</h2>
        <p class="hint" style="margin-top:-0.5rem">
          每个组件独立配色，点击色块即可调整
        </p>
        <button class="action-btn" style="margin-bottom:0.8rem" @click="resetAllComponentColors()">
          恢复全部默认
        </button>
        <div v-for="group in COLOR_GROUPS" :key="group.id" class="config-section color-group">
          <h3 class="color-group-header">
            <span>{{ group.icon }} {{ group.label }}</span>
            <button class="action-btn ml-a" @click="resetComponentGroup(group.id)">
              恢复
            </button>
          </h3>
          <div class="color-picker-grid">
            <div v-for="c in group.colors" :key="colorStorageKey(group.id, c.key)" class="color-picker-item">
              <label class="cp-label">{{ c.label }}</label>
              <div class="cp-row">
                <input
                  type="color"
                  :value="componentColors[colorStorageKey(group.id, c.key)] || c.default"
                  class="cp-input"
                  @input="(e: Event) => { const tar = e.target as HTMLInputElement; componentColors[colorStorageKey(group.id, c.key)] = tar.value }"
                >
                <span class="cp-val">{{ componentColors[colorStorageKey(group.id, c.key)] || c.default }}</span>
              </div>
            </div>
          </div>
          <div v-if="group.id === 'hud'" class="hud-extras">
            <div class="hud-extra-row">
              <label class="he-label">透明度</label>
              <div class="he-slider">
                <Slider v-model="hudOpacity" :min="0.05" :max="1.5" :step="0.01" />
              </div>
              <span class="he-val">{{ Math.round(hudOpacity * 100) }}%</span>
            </div>
            <div class="hud-extra-row">
              <label class="he-label">显示 HUD</label>
              <ToggleSwitch v-model="hudVisible" />
            </div>
          </div>
        </div>

        <!-- 地球online 主题 -->
        <div v-if="earthTheme" class="config-section color-group">
          <h3 class="color-group-header">
            <span>◎ 地球online 主题</span>
            <span v-if="earthThemeSaved" class="saved-msg">已保存 ✓</span>
          </h3>
          <p class="hint">地球 Online 板块的主题色与磨砂玻璃，默认跟随 Miya OS；背景壁纸请在“外观”页设置。</p>
          <div class="earth-theme-presets">
            <button
              v-for="[name, accent, light] in EARTH_THEME_PRESETS"
              :key="name"
              class="color-btn"
              :class="{ active: earthTheme.accent === accent }"
              @click="earthTheme.accent = accent; earthTheme.accent_light = light"
            >
              <span class="earth-theme-dot" :style="{ background: `linear-gradient(135deg, ${light}, ${accent})` }" />
              {{ name }}
            </button>
          </div>
          <div class="color-picker-grid" style="margin-top:0.6rem">
            <div class="color-picker-item">
              <label class="cp-label">主色</label>
              <div class="cp-row">
                <input v-model="earthTheme.accent" type="color" class="cp-input">
                <span class="cp-val">{{ earthTheme.accent }}</span>
              </div>
            </div>
            <div class="color-picker-item">
              <label class="cp-label">亮色</label>
              <div class="cp-row">
                <input v-model="earthTheme.accent_light" type="color" class="cp-input">
                <span class="cp-val">{{ earthTheme.accent_light }}</span>
              </div>
            </div>
            <div class="color-picker-item">
              <label class="cp-label">深色</label>
              <div class="cp-row">
                <input v-model="earthTheme.accent_deep" type="color" class="cp-input">
                <span class="cp-val">{{ earthTheme.accent_deep }}</span>
              </div>
            </div>
          </div>
          <div class="hud-extra-row">
            <label class="he-label">磨砂玻璃</label>
            <ToggleSwitch v-model="earthTheme.glass" />
          </div>
          <div style="display:flex;gap:0.5rem;margin-top:0.7rem">
            <button class="action-btn" @click="saveEarthTheme">保存主题</button>
            <button class="action-btn" @click="resetEarthTheme">恢复默认值</button>
          </div>
        </div>
      </div>

      <!-- ═══ Live2D 独立窗口 ═══ -->
      <div v-show="activeTab === 'live2d'" class="config-page">
        <h2>Live2D 独立窗口</h2>
        <p class="hint" style="margin-top:-0.5rem">
          装配角色，并控制无边框桌面展示效果
        </p>
        <button class="action-btn" style="margin-bottom:0.8rem" @click="enableLive2dDesktopMode">
          一键桌面模式（透明无框）
        </button>

        <div class="config-section">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem">
            <h3 style="margin:0">角色装配</h3>
            <button class="action-btn" :disabled="live2dPackageBusy" @click="importLive2dPackage">
              导入 Live2D 文件夹
            </button>
          </div>
          <p class="hint">请选择只包含一个 .model3.json 的完整模型文件夹；导入前会校验 moc3、纹理和所有已声明依赖。模型会复制到用户数据目录，原文件夹之后可移动或删除。</p>
          <div v-if="live2dPackages.length" class="live2d-package-list">
            <div v-for="item in live2dPackages" :key="item.id" class="live2d-package-item">
              <div class="live2d-package-info">
                <span>{{ item.name }}</span>
                <small>{{ formatLive2dSize(item.size) }} · {{ item.modelPath }}</small>
              </div>
              <span v-if="item.active" class="live2d-active-badge">使用中</span>
              <button v-else class="action-btn" :disabled="live2dPackageBusy" @click="activateLive2dPackage(item.id)">切换</button>
              <button class="action-btn danger" :disabled="live2dPackageBusy" @click="removeLive2dPackage(item)">删除</button>
            </div>
          </div>
          <p v-else class="hint">还没有安装角色，导入第一个模型后会自动启用。</p>
          <p v-if="live2dPackageMsg" class="hint" style="color:var(--miya-accent)">{{ live2dPackageMsg }}</p>
        </div>

        <div class="config-section">
          <h3>窗口背景</h3>
          <div class="live2d-color-row">
            <input
              type="color"
              :value="live2dCfg.bgColor"
              class="cp-input"
              style="width:48px;height:36px;border-radius:6px;border:1px solid rgba(0, 173, 181, 0.2)"
              @input="setLive2dBg($event)"
            >
            <span style="font-size:0.75rem;color:var(--miya-text-dim)">{{ live2dCfg.bgColor }}</span>
          </div>
        </div>

        <div class="config-section">
          <h3>背景透明度</h3>
          <div class="slider-row">
            <Slider v-model="live2dCfg.bgAlpha" :min="0" :max="1" :step="0.05" style="flex:1" @update:model-value="setLive2dBg()" />
            <span class="slider-val">{{ Math.round(live2dCfg.bgAlpha * 100) }}%</span>
          </div>
        </div>

        <div class="config-section">
          <h3>窗口大小</h3>
          <p class="hint">调整透明窗口的实际占用范围，不改变角色在窗口内的相对比例。</p>
          <div class="slider-row">
            <Slider v-model="live2dCfg.windowScale" :min="40" :max="400" :step="1" style="flex:1" @update:model-value="setLive2dScale()" />
            <span class="slider-val">{{ live2dCfg.windowScale }}%</span>
          </div>
        </div>

        <div class="config-section">
          <h3>模型大小</h3>
          <p class="hint">单独放大角色；超过窗口后会自然裁切，适合去除模型资源自带的透明留白。</p>
          <div class="slider-row">
            <Slider v-model="live2dCfg.modelScale" :min="40" :max="400" :step="1" style="flex:1" @update:model-value="setLive2dModelScale()" />
            <span class="slider-val">{{ live2dCfg.modelScale }}%</span>
          </div>
        </div>

        <div class="config-section">
          <h3>显示选项</h3>
          <div class="toggle-row">
            <span>窗口置顶</span>
            <ToggleSwitch v-model="live2dCfg.alwaysOnTop" @change="setLive2dAlwaysOnTop()" />
          </div>
          <div class="toggle-row">
            <span>显示 Live2D 窗口</span>
            <ToggleSwitch v-model="live2dCfg.visible" @change="setLive2dVisibility()" />
          </div>
          <div class="toggle-row">
            <div>
              <span>鼠标穿透</span>
              <p class="hint" style="margin:0.15rem 0 0">开启后模型不会挡住桌面点击；关闭后可拖动窗口。</p>
            </div>
            <ToggleSwitch v-model="live2dCfg.clickThrough" @change="setLive2dClickThrough()" />
          </div>
          <div class="toggle-row">
            <div>
              <span>跟随鼠标</span>
              <p class="hint" style="margin:0.15rem 0 0">让角色的眼睛和头部跟随全局光标；鼠标穿透时也能生效。</p>
            </div>
            <ToggleSwitch v-model="live2dCfg.mouseTracking" @change="setLive2dMouseTracking()" />
          </div>
          <div class="toggle-row" :style="{ opacity: live2dCfg.mouseTracking ? 1 : 0.5 }">
            <div>
              <span>静止后回归视线</span>
              <p class="hint" style="margin:0.15rem 0 0">鼠标静止 10 秒后恢复自主视线，移动鼠标时自动继续跟随。</p>
            </div>
            <ToggleSwitch v-model="live2dCfg.mouseIdleReturn" :disabled="!live2dCfg.mouseTracking" @change="setLive2dMouseIdleReturn()" />
          </div>
        </div>

        <div class="config-section">
          <h3>窗口位置</h3>
          <div style="display:flex;gap:0.5rem">
            <button class="action-btn" @click="resetLive2dPos()">
              重置位置
            </button>
            <button class="action-btn" @click="resetLive2dSize()">
              重置窗口大小
            </button>
            <button class="action-btn" @click="resetLive2dModelSize()">
              重置模型大小
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.config-layout { display: flex; height: 100%; }

/* ═══ 侧边栏 — PGR 风格 ═══ */
.config-sidebar {
  width: 140px; flex-shrink: 0;
  background: rgba(0, 0, 0, 0.55);
  border-right: 1px solid rgba(0, 173, 181, 0.08);
  box-shadow:
    4px 0 12px rgba(0, 60, 70, 0.4),
    -1px 0 0 rgba(0, 200, 210, 0.08);
  display: flex; flex-direction: column; padding: 0.8rem 0;
}
.sidebar-header { display: flex; align-items: center; gap: 0.5rem; padding: 0 0.8rem 0.6rem; border-bottom: 1px solid rgba(0, 173, 181, 0.08); }
.sidebar-title { font-family: 'Noto Serif SC', serif; font-size: 0.9rem; color: #ffffff; font-weight: 700; letter-spacing: 0.1em; }
.sidebar-version { margin-top: auto; padding: 0.6rem 0.8rem 0; font-size: 0.6rem; color: rgba(200, 200, 200, 0.5); border-top: 1px solid rgba(0, 173, 181, 0.06); }

.sidebar-nav { display: flex; flex-direction: column; padding: 0.4rem; gap: 1px; }
.tab-btn {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.5rem 0.6rem; cursor: pointer;
  background: transparent; border: none; color: rgba(200, 200, 200, 0.55);
  font-size: 0.78rem; transition: all 0.35s cubic-bezier(0.22, 1, 0.36, 1); text-align: left;
}
.tab-btn:hover {
  background: rgba(0, 173, 181, 0.15);
  color: rgba(255, 255, 255, 0.9);
  transform: skewX(-6deg);
  box-shadow: 2px 2px 8px rgba(0, 60, 70, 0.3);
}
.tab-btn.active {
  background: rgba(0, 173, 181, 0.18);
  color: #ffffff;
  font-weight: 700;
  box-shadow: 2px 2px 8px rgba(0, 60, 70, 0.35), -1px -1px 4px rgba(0, 200, 210, 0.1);
}
.tab-icon { font-size: 0.8rem; width: 1.2rem; text-align: center; transition: transform 0.3s ease; }
.tab-btn:hover .tab-icon { transform: scale(1.15); }

/* ═══ 主内容区 ═══ */
.config-main { flex: 1; overflow-y: auto; padding: 1.2rem 1.8rem; color: var(--miya-text); font-size: 0.82rem; }
.config-page h2 {
  font-family: 'Noto Serif SC', serif; font-size: 1.3rem; font-weight: 700;
  color: #ffffff; margin: 0 0 1.2rem; letter-spacing: 0.08em;
  text-shadow: 0 0 12px rgba(0, 255, 245, 0.15);
}

/* ═══ 配置章节 — PGR 卡片风格 ═══ */
.config-section {
  margin-bottom: 1.4rem;
  padding: 0.9rem 1rem;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid rgba(0, 173, 181, 0.06);
  box-shadow:
    3px 3px 10px rgba(0, 60, 70, 0.35),
    -2px -2px 8px rgba(0, 200, 210, 0.08);
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}
.config-section:hover {
  background: rgba(0, 0, 0, 0.55);
  border-color: rgba(0, 255, 245, 0.12);
  box-shadow:
    4px 4px 14px rgba(0, 60, 70, 0.45),
    -2px -2px 10px rgba(0, 200, 210, 0.12);
}
.config-section h3 {
  font-size: 0.75rem; font-weight: 700; color: rgba(0, 255, 245, 0.55);
  margin: 0 0 0.6rem; letter-spacing: 0.1em; text-transform: uppercase;
}
.hint { font-size: 0.68rem; color: rgba(200, 200, 200, 0.4); margin-bottom: 0.6rem; }

.config-item { margin-bottom: 0.7rem; }
.config-item label { display: block; font-size: 0.75rem; color: rgba(228, 236, 240, 0.7); margin-bottom: 0.25rem; }
.slider-row { display: flex; align-items: center; gap: 0.6rem; }
.slider-row :first-child { flex: 1; }
.slider-val { font-size: 0.7rem; color: rgba(0, 255, 245, 0.45); min-width: 2.5rem; text-align: right; font-family: 'JetBrains Mono', monospace; }

.input-sm { width: 100%; max-width: 280px; background: rgba(0, 0, 0, 0.5) !important; border: 1px solid rgba(0, 173, 181, 0.15) !important; color: rgba(228, 236, 240, 0.9) !important; padding: 0.3rem 0.5rem !important; font-size: 0.75rem; }

.back-btn {
  display: flex; align-items: center; justify-content: center;
  width: 24px; height: 24px;
  border: 1px solid rgba(0, 173, 181, 0.15); background: rgba(0, 173, 181, 0.06);
  color: rgba(0, 173, 181, 0.6); cursor: pointer; transition: all 0.3s ease;
}
.back-btn:hover { background: rgba(0, 173, 181, 0.18); border-color: rgba(0, 255, 245, 0.35); color: rgba(0, 255, 245, 0.9); transform: skewX(-6deg); }

/* 背景 */
.bg-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.3rem; }
.bg-thumb {
  position: relative;
  aspect-ratio: 4/3; overflow: hidden; cursor: pointer;
  border: 2px solid transparent;
  background: rgba(0, 0, 0, 0.5);
  display: flex; align-items: center; justify-content: center;
  transition: all 0.3s ease;
}
.bg-thumb img { width: 100%; height: 100%; object-fit: cover; }
.bg-thumb:hover { border-color: rgba(0, 255, 245, 0.25); transform: scale(1.04); }
.bg-thumb.active { border-color: rgba(0, 255, 245, 0.5); box-shadow: 0 0 10px rgba(0, 255, 245, 0.15); }
.bg-default { font-size: 0.6rem; color: rgba(200, 200, 200, 0.4); }
.bg-actions { margin-top: 0.4rem; }
.bg-actions { display: flex; align-items: center; gap: var(--miya-space-3); }
.bg-message { color: var(--miya-success); font-size: 0.68rem; }
.custom-bg-thumb { position: relative; }
.custom-bg-thumb span {
  position: absolute;
  left: 5px;
  right: 5px;
  bottom: 4px;
  padding: 2px 5px;
  color: var(--miya-text-strong);
  background: rgba(7, 11, 18, 0.78);
  border-radius: var(--miya-radius-xs);
  font-size: 0.58rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}
.bg-thumb-remove { position: absolute; top: 5px; right: 5px; z-index: 2; display: grid; width: 24px; height: 24px; padding: 0; place-items: center; border: 1px solid rgba(255,255,255,0.34); background: rgba(7,11,18,0.84); color: rgba(255,255,255,0.9); cursor: pointer; font-size: 0.9rem; line-height: 1; box-shadow: 0 2px 8px rgba(0,0,0,0.4); }
.bg-thumb-remove:hover { border-color: rgba(255,100,100,0.82); background: rgba(95,20,26,0.9); color: #fff; }
.gallery-toggle-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.gallery-toggle-row .hint { margin: 0.2rem 0 0; }
.miya-gallery-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0.45rem; margin: 0.7rem 0; }
.miya-gallery-thumb { position: relative; aspect-ratio: 2 / 3; overflow: hidden; border: 1px solid rgba(0, 173, 181, 0.16); background: rgba(0,0,0,0.5); }
.miya-gallery-thumb img { width: 100%; height: 100%; object-fit: cover; }
.miya-gallery-thumb.selected { border-color: rgba(0,255,245,0.62); box-shadow: 0 0 12px rgba(0,255,245,0.16); }
.miya-gallery-thumb button { position: absolute; top: 4px; right: 4px; display: grid; width: 22px; height: 22px; padding: 0; place-items: center; border: 1px solid rgba(255,255,255,0.22); background: rgba(0,0,0,0.72); color: rgba(255,255,255,0.8); cursor: pointer; }
.miya-gallery-thumb button:hover { border-color: rgba(255,100,100,0.7); color: #ff8f8f; }
.miya-gallery-thumb span { position: absolute; left: 5px; bottom: 4px; color: rgba(255,255,255,0.65); font-family: 'JetBrains Mono', monospace; font-size: 0.56rem; text-shadow: 0 1px 4px #000; }
.miya-gallery-empty { margin: 0.65rem 0; padding: 1rem; border: 1px dashed rgba(0,173,181,0.14); color: rgba(200,200,200,0.42); font-size: 0.68rem; text-align: center; }
.gallery-message { margin-left: 0.7rem; color: rgba(0,255,245,0.55); font-size: 0.65rem; }
.miya-gallery-editor { margin-top: 0.75rem; padding: 0.75rem; border-left: 2px solid rgba(0,255,245,0.4); background: rgba(0,173,181,0.045); }
.miya-gallery-editor textarea { width: 100%; resize: vertical; border: 1px solid rgba(0,173,181,0.15); background: rgba(0,0,0,0.5); color: rgba(228,236,240,0.9); padding: 0.45rem 0.55rem; font: inherit; line-height: 1.55; }
.home-briefing-config h3 small { margin-left: 0.45rem; color: rgba(200,200,200,0.38); font-size: 0.58rem; font-weight: 400; letter-spacing: 0.08em; }
.briefing-greeting-input { max-width: 520px; }
.home-briefing-list { display: grid; gap: 0.5rem; margin: 0.75rem 0; }
.home-briefing-editor { display: grid; grid-template-columns: 110px minmax(0, 1fr) auto; align-items: stretch; gap: 0.6rem; padding: 0.5rem; border: 1px solid rgba(0,173,181,0.13); background: rgba(0,0,0,0.26); }
.home-briefing-preview { position: relative; min-height: 64px; overflow: hidden; display: grid; place-items: center; color: rgba(0,255,245,0.48); background: repeating-linear-gradient(135deg, rgba(0,173,181,0.08) 0 1px, transparent 1px 12px); }
.home-briefing-preview img { width: 100%; height: 100%; object-fit: cover; }
.home-briefing-preview > span { font-size: 1.7rem; }
.home-briefing-preview small { position: absolute; right: 4px; bottom: 3px; padding: 1px 4px; background: rgba(0,0,0,0.66); color: rgba(255,255,255,0.62); font-size: 0.5rem; }
.home-briefing-fields { min-width: 0; display: grid; align-content: center; gap: 0.35rem; }
.home-briefing-fields :deep(input) { width: 100%; }
.home-briefing-actions { display: flex; align-items: center; gap: 0.25rem; }
.home-briefing-actions button { width: 27px; height: 27px; padding: 0; border: 1px solid rgba(0,173,181,0.18); background: rgba(0,0,0,0.42); color: rgba(220,235,238,0.68); cursor: pointer; }
.home-briefing-actions button:hover:not(:disabled) { border-color: rgba(0,255,245,0.45); color: rgba(0,255,245,0.9); }
.home-briefing-actions button.danger:hover { border-color: rgba(255,100,100,0.55); color: #ff8f8f; }
.home-briefing-actions button:disabled { opacity: 0.22; cursor: not-allowed; }
@media (max-width: 980px) { .miya-gallery-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 760px) { .home-briefing-editor { grid-template-columns: 86px minmax(0, 1fr); } .home-briefing-actions { grid-column: 1 / -1; justify-content: flex-end; } }

.action-btn {
  padding: 0.25rem 0.7rem; font-size: 0.68rem;
  border: 1px solid rgba(0, 173, 181, 0.15); background: rgba(0, 173, 181, 0.04);
  color: rgba(0, 173, 181, 0.45); cursor: pointer; transition: all 0.3s ease;
}
.action-btn:hover {
  border-color: rgba(0, 255, 245, 0.3); background: rgba(0, 173, 181, 0.1);
  color: rgba(0, 255, 245, 0.75); transform: skewX(-4deg);
}
.ml-a { margin-left: auto; }

/* 颜色 */
.color-modes { display: flex; gap: 0.3rem; flex-wrap: wrap; }
.color-btn {
  display: flex; align-items: center; gap: 0.25rem; padding: 0.25rem 0.6rem;
  cursor: pointer; border: 1px solid rgba(0, 173, 181, 0.08);
  background: rgba(0, 0, 0, 0.35); color: rgba(200, 200, 200, 0.5);
  font-size: 0.7rem; transition: all 0.3s ease;
}
.color-btn:hover {
  border-color: rgba(0, 255, 245, 0.2);
  background: rgba(0, 173, 181, 0.08);
  color: rgba(255, 255, 255, 0.8);
  transform: skewX(-4deg);
}
.color-btn.active {
  border-color: rgba(0, 255, 245, 0.4);
  background: rgba(0, 173, 181, 0.12);
  color: #ffffff;
  box-shadow: 0 0 8px rgba(0, 255, 245, 0.1);
}
.color-dots { display: flex; gap: 1px; }

/* 地球online 主题 */
.earth-theme-presets { display: flex; gap: 0.3rem; flex-wrap: wrap; margin-top: 0.3rem; }
.earth-theme-dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 4px; vertical-align: -1px; }
.earth-theme-walls { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.3rem; }
.earth-theme-wall {
  width: 76px;
  height: 48px;
  border-radius: 7px;
  overflow: hidden;
  cursor: pointer;
  padding: 0;
  border: 2px solid rgba(255, 255, 255, 0.12);
  transition: all 0.2s;
  background: rgba(0, 0, 0, 0.35);
}
.earth-theme-wall:hover { border-color: rgba(0, 255, 245, 0.25); }
.earth-theme-wall.active { border-color: rgba(0, 255, 245, 0.55); box-shadow: 0 0 10px rgba(0, 255, 245, 0.15); }
.earth-theme-wall-img { display: block; width: 100%; height: 100%; background-size: cover; background-position: center; }
.earth-theme-wall-none { display: grid; place-items: center; width: 100%; height: 100%; font-size: 0.66rem; color: rgba(200, 200, 200, 0.45); }
.dot { width: 6px; height: 6px; border-radius: 50%; }

/* ═══ 模型/灵魂/记忆/系统信息项 — PGR 风格 ═══ */
.model-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.45rem 0.4rem;
  border-bottom: 1px solid rgba(0, 173, 181, 0.04);
  font-size: 0.75rem;
  cursor: default;
  transition: all 0.3s ease;
}
.model-item:hover {
  background: rgba(0, 173, 181, 0.08);
}
.model-name { color: rgba(200, 200, 200, 0.6); }
.model-val { color: rgba(228, 236, 240, 0.85); font-size: 0.7rem; font-family: 'JetBrains Mono', monospace; }
.status-on { color: rgba(0, 255, 245, 0.65); }

.offline-hint {
  padding: 1.5rem; text-align: center;
  color: rgba(200, 200, 200, 0.35); font-size: 0.8rem;
  background: rgba(0, 0, 0, 0.4);
  border: 1px dashed rgba(0, 173, 181, 0.08);
}

/* 声音 */
.toggle-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.4rem 0; border-bottom: 1px solid rgba(0, 173, 181, 0.04);
  cursor: pointer;
}
.toggle-row:hover { background: rgba(0, 173, 181, 0.04); }
.file-btn-audio { font-size: 0.68rem; }

/* 调色 */
.color-group-header { display: flex; align-items: center; gap: 0.4rem; }
.color-picker-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin-top: 0.4rem; }
.color-picker-item {
  padding: 0.4rem; background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(0, 173, 181, 0.05);
  transition: all 0.3s ease;
}
.color-picker-item:hover { border-color: rgba(0, 255, 245, 0.15); background: rgba(0, 0, 0, 0.45); }
.cp-label { display: block; font-size: 0.65rem; color: rgba(200, 200, 200, 0.5); margin-bottom: 0.3rem; }
.cp-row { display: flex; align-items: center; gap: 0.4rem; }
.cp-input { width: 28px; height: 22px; border: 1px solid rgba(0, 173, 181, 0.15); border-radius: 0.2rem; background: transparent; cursor: pointer; padding: 1px; }
.cp-val { font-size: 0.6rem; color: rgba(0, 255, 245, 0.4); font-family: 'JetBrains Mono', monospace; }

.hud-extras { margin-top: 0.6rem; padding-top: 0.6rem; border-top: 1px solid rgba(0, 173, 181, 0.06); display: flex; flex-direction: column; gap: 0.5rem; }
.hud-extra-row { display: flex; align-items: center; gap: 0.6rem; }
.he-label { font-size: 0.68rem; color: rgba(200, 200, 200, 0.5); min-width: 56px; }
.he-slider { flex: 1; }
.he-val { font-size: 0.6rem; color: rgba(0, 255, 245, 0.4); font-family: 'JetBrains Mono', monospace; min-width: 32px; text-align: right; }

/* Live2D 配置 */
.live2d-color-row { display: flex; align-items: center; gap: 0.6rem; }
.live2d-package-list { display: flex; flex-direction: column; gap: 0.45rem; margin-top: 0.7rem; }
.live2d-package-item { display: flex; align-items: center; gap: 0.5rem; padding: 0.55rem 0.65rem; border: 1px solid rgba(0,173,181,0.1); border-radius: 0.35rem; background: rgba(0,0,0,0.12); }
.live2d-package-info { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 0.15rem; }
.live2d-package-info small { overflow: hidden; color: var(--miya-text-dim); font-size: 0.65rem; text-overflow: ellipsis; white-space: nowrap; }
.live2d-active-badge { color: var(--miya-accent); font-size: 0.68rem; }

/* 文件列表 */
.file-list { display: flex; flex-direction: column; gap: 2px; }
.file-btn {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.35rem 0.5rem; cursor: pointer;
  background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(0, 173, 181, 0.04);
  color: rgba(200, 200, 200, 0.55); font-size: 0.7rem; transition: all 0.3s ease;
}
.file-btn:hover { background: rgba(0, 173, 181, 0.08); color: rgba(255, 255, 255, 0.8); }
.file-btn.active { background: rgba(0, 173, 181, 0.12); border-color: rgba(0, 255, 245, 0.25); color: #ffffff; }
.file-size { font-size: 0.6rem; color: rgba(0, 255, 245, 0.3); font-family: 'JetBrains Mono', monospace; }

.editor-area { border: 1px solid rgba(0, 173, 181, 0.08); background: rgba(0, 0, 0, 0.4); }
.editor-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.3rem 0.6rem; border-bottom: 1px solid rgba(0, 173, 181, 0.06);
}
.editor-path { font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; color: rgba(0, 255, 245, 0.4); }
.editor-actions { display: flex; gap: 0.3rem; align-items: center; }
.saved-msg { font-size: 0.6rem; color: rgba(0, 255, 245, 0.5); }
.editor-text {
  width: 100%; background: rgba(0, 0, 0, 0.6); border: none; outline: none;
  color: rgba(228, 236, 240, 0.85); font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem; padding: 0.5rem; resize: vertical;
}

/* ═══ 配置面板 ═══ */
.effect-tag {
  font-size: 0.6rem; font-weight: 400; color: rgba(0, 255, 245, 0.4);
  margin-left: 0.5rem; letter-spacing: normal; text-transform: none;
}
.secret-row {
  display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap;
  padding: 0.45rem 0.4rem; border-bottom: 1px solid rgba(0, 173, 181, 0.04);
  transition: background 0.3s ease;
}
.secret-row:hover { background: rgba(0, 173, 181, 0.06); }
.secret-label { display: flex; flex-direction: column; gap: 1px; min-width: 150px; flex: 1; }
.secret-name { font-size: 0.75rem; color: rgba(228, 236, 240, 0.85); }
.secret-key { font-size: 0.6rem; color: rgba(0, 255, 245, 0.35); font-family: 'JetBrains Mono', monospace; }
.secret-masked {
  font-size: 0.68rem; color: rgba(200, 200, 200, 0.35);
  font-family: 'JetBrains Mono', monospace; min-width: 110px;
}
.secret-masked.configured { color: rgba(0, 255, 245, 0.55); }
.secret-input { display: flex; align-items: center; gap: 0.4rem; }
.secret-field { max-width: 220px; }

.persona-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; }
@media (max-width: 1100px) { .persona-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 800px) { .persona-grid { grid-template-columns: repeat(2, 1fr); } }
.persona-card {
  padding: 0.6rem 0.7rem; cursor: pointer; position: relative;
  background: rgba(0, 0, 0, 0.35); border: 1px solid rgba(0, 173, 181, 0.08);
  transition: all 0.3s ease; display: flex; flex-direction: column; gap: 0.3rem;
}
.persona-card:hover {
  border-color: rgba(0, 255, 245, 0.25); background: rgba(0, 173, 181, 0.06);
  transform: translateY(-2px);
}
.persona-card.active {
  border-color: rgba(0, 255, 245, 0.5); background: rgba(0, 173, 181, 0.1);
  box-shadow: 0 0 12px rgba(0, 255, 245, 0.1);
}
.persona-card-head { display: flex; align-items: center; justify-content: space-between; gap: 0.4rem; }
.persona-name { font-size: 0.78rem; color: rgba(228, 236, 240, 0.9); font-weight: 700; }
.persona-current {
  font-size: 0.58rem; padding: 0.05rem 0.4rem; color: #001f24;
  background: rgba(0, 255, 245, 0.7); border-radius: 2px; flex-shrink: 0;
}
.persona-desc {
  font-size: 0.65rem; color: rgba(200, 200, 200, 0.45);
  margin: 0; flex: 1; overflow: hidden; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.persona-card-actions { display: flex; justify-content: flex-end; }
.persona-editor {
  margin-top: 0.8rem; padding: 0.7rem; border-left: 2px solid rgba(0, 255, 245, 0.4);
  background: rgba(0, 173, 181, 0.045);
}

.admin-person {
  padding: 0.5rem 0.4rem; border-bottom: 1px solid rgba(0, 173, 181, 0.04);
}
.admin-person-name { font-size: 0.75rem; color: rgba(228, 236, 240, 0.85); margin-bottom: 0.35rem; }
.admin-id-row { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.35rem; }
.admin-platform {
  font-size: 0.68rem; color: rgba(0, 255, 245, 0.45); min-width: 90px;
  font-family: 'JetBrains Mono', monospace;
}

/* ═══ 模型池 ═══ */
.model-row {
  display: flex; align-items: center; justify-content: space-between; gap: 0.8rem;
  padding: 0.5rem 0.4rem; border-bottom: 1px solid rgba(0, 173, 181, 0.04);
  transition: background 0.3s ease; flex-wrap: wrap;
}
.model-row:hover { background: rgba(0, 173, 181, 0.06); }
.model-info { display: flex; flex-direction: column; gap: 2px; flex: 1; min-width: 240px; }
.model-title { font-size: 0.78rem; color: rgba(228, 236, 240, 0.9); display: flex; align-items: center; gap: 0.4rem; }
.model-meta { font-size: 0.62rem; color: rgba(0, 255, 245, 0.35); font-family: 'JetBrains Mono', monospace; }
.model-off {
  font-size: 0.56rem; padding: 0.05rem 0.35rem; border-radius: 2px;
  color: rgba(255, 160, 120, 0.8); border: 1px solid rgba(255, 160, 120, 0.35);
}
.model-ops { display: flex; gap: 0.35rem; }
.action-btn.danger:hover { border-color: rgba(255, 100, 100, 0.5); color: #ff8f8f; }

.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.4rem 1rem; }
@media (max-width: 800px) { .form-grid { grid-template-columns: 1fr; } }

.route-row {
  display: flex; align-items: center; gap: 0.8rem;
  padding: 0.3rem 0.4rem; border-bottom: 1px solid rgba(0, 173, 181, 0.04);
}
.route-task { font-size: 0.72rem; color: rgba(200, 200, 200, 0.6); min-width: 64px; }
.route-selects { display: flex; gap: 0.4rem; flex: 1; flex-wrap: wrap; }
.route-select {
  flex: 1; min-width: 120px; padding: 0.25rem 0.4rem;
  background: rgba(0, 0, 0, 0.5); border: 1px solid rgba(0, 173, 181, 0.15);
  color: rgba(228, 236, 240, 0.9); font-size: 0.7rem;
  font-family: 'JetBrains Mono', monospace; outline: none;
}
.route-select:focus { border-color: rgba(0, 255, 245, 0.4); }

/* Miya OS: 高密度设置页采用稳定的双栏工作台规范。 */
.config-layout {
  gap: var(--miya-space-3);
  padding: var(--miya-space-3);
}

.config-sidebar {
  width: 176px;
  padding: var(--miya-space-3) var(--miya-space-2);
  background: var(--miya-surface-1);
  border: 1px solid var(--miya-line-soft);
  border-radius: var(--miya-radius-lg);
  box-shadow: var(--miya-shadow-panel);
  backdrop-filter: blur(16px);
}

.sidebar-header {
  padding: 0 var(--miya-space-2) var(--miya-space-3);
  border-color: var(--miya-line-soft);
}
.sidebar-title { color: var(--miya-text-strong); }
.sidebar-version { color: var(--miya-text-faint); border-color: var(--miya-line-soft); }

.sidebar-nav { gap: 2px; }
.tab-btn {
  min-height: 38px;
  padding: var(--miya-space-2) var(--miya-space-3);
  color: var(--miya-text-muted);
  border-radius: var(--miya-radius-sm);
}
.tab-btn:hover {
  color: var(--miya-text-strong);
  background: rgba(120, 207, 209, 0.07);
  transform: none;
  box-shadow: none;
}
.tab-btn.active {
  color: var(--miya-accent-bright);
  background: linear-gradient(90deg, rgba(120, 207, 209, 0.14), rgba(120, 207, 209, 0.04));
  box-shadow: inset 2px 0 var(--miya-accent-soft);
}

.config-main {
  padding: var(--miya-space-4) clamp(1rem, 2vw, 2rem);
  color: var(--miya-text-body);
  background: rgba(7, 11, 18, 0.32);
  border: 1px solid var(--miya-line-soft);
  border-radius: var(--miya-radius-lg);
}
.config-page { max-width: 980px; margin: 0 auto; }
.config-page h2 {
  color: var(--miya-text-strong);
  text-shadow: none;
  letter-spacing: 0.04em;
}

.config-section {
  padding: var(--miya-space-4);
  margin-bottom: var(--miya-space-3);
  background: var(--miya-surface-1);
  border-color: var(--miya-line-soft);
  border-radius: var(--miya-radius-md);
  box-shadow: none;
}
.config-section:hover {
  background: var(--miya-surface-2);
  border-color: var(--miya-line);
  box-shadow: none;
}
.config-section h3 { color: var(--miya-accent-soft); }
.hint { color: var(--miya-text-muted); }

.action-btn,
.back-btn {
  color: var(--miya-accent-soft);
  background: rgba(120, 207, 209, 0.05);
  border-color: var(--miya-line);
  border-radius: var(--miya-radius-sm);
}
.action-btn:hover,
.back-btn:hover {
  color: var(--miya-accent-bright);
  background: rgba(120, 207, 209, 0.1);
  border-color: var(--miya-line-strong);
  transform: none;
}

.bg-thumb,
.miya-gallery-thumb,
.route-select { border-radius: var(--miya-radius-sm); }
</style>
