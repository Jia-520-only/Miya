<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import API from '@/api/core'
import { MESSAGES } from '@/utils/session'
import { useCameraVision } from '@/utils/cameraVision'

type VisionTab = 'both' | 'screen' | 'me'

const router = useRouter()
const activeTab = ref<VisionTab>('both')
const query = ref('')
const loading = ref(false)
const result = ref('')
const status = ref<'idle' | 'success' | 'error' | 'partial'>('idle')
const screenshots = ref<string[]>([])
const previewVideo = ref<HTMLVideoElement | null>(null)
const cameraQuery = ref('')
const identityName = ref('')
const identities = ref<Array<{ id: string, name: string, created_at?: number }>>([])
const identityBusy = ref(false)

const camera = useCameraVision()
const companionActive = computed(() => camera.mode.value === 'companion')

function pushToConversation(text: string, prompt: string, sender = '弥娅视觉') {
  MESSAGES.value.push({
    role: 'user',
    content: prompt ? `${prompt}\n\n【AI分析结果】${text}` : `【${sender}】${text}`,
    sender,
  })
}

function parseResult(response: any) {
  const raw = response?.result
  return typeof raw === 'string' ? JSON.parse(raw) : raw
}

async function doLookScreen() {
  if (loading.value) return
  loading.value = true
  result.value = '正在截图并分析...'
  status.value = 'idle'
  let wasMinimized = false
  try {
    if (window.electronAPI?.minimize) {
      window.electronAPI.minimize()
      wasMinimized = true
      await new Promise(resolve => setTimeout(resolve, 800))
    }
    const data = parseResult(await API.mcpCall('screen_vision', 'look_screen', {
      query: query.value || undefined,
    }))
    if (data?.status === 'success') {
      result.value = data.message
      status.value = 'success'
      pushToConversation(data.message, query.value ? `【截屏问题】${query.value}` : '', '屏幕视觉')
      router.push('/chat')
    } else if (data?.status === 'partial') {
      result.value = data.message
      status.value = 'partial'
      pushToConversation(data.message, query.value ? `【截屏问题】${query.value}` : '', '屏幕视觉')
      router.push('/chat')
    } else {
      result.value = data?.message || '分析失败'
      status.value = 'error'
    }
  } catch (err: any) {
    result.value = err?.message || '请求失败'
    status.value = 'error'
  } finally {
    if (wasMinimized) window.electronAPI?.restore()
    loading.value = false
  }
}

async function doScreenshot() {
  if (loading.value) return
  loading.value = true
  try {
    const data = parseResult(await API.mcpCall('screen_vision', 'screenshot', {}))
    if (data?.status === 'success') {
      screenshots.value.unshift(data.message || '截图完成')
      if (screenshots.value.length > 10) screenshots.value.pop()
      pushToConversation(data.message || '截图完成', '', '屏幕视觉')
      router.push('/chat')
    }
  } catch (err: any) {
    result.value = err?.message || '截图失败'
    status.value = 'error'
  } finally {
    loading.value = false
  }
}

async function waitForFrame() {
  for (let index = 0; index < 20; index += 1) {
    if (previewVideo.value && previewVideo.value.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) return
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('摄像头画面还没有准备好')
}

async function doLookMe() {
  if (loading.value) return
  loading.value = true
  result.value = '正在看你...'
  status.value = 'idle'
  let temporary = false
  try {
    camera.attachPreview(previewVideo.value)
    if (!camera.stream.value) {
      temporary = true
      await camera.open('snapshot')
      await nextTick()
      camera.attachPreview(previewVideo.value)
    }
    await waitForFrame()
    const message = await camera.lookAtMe(cameraQuery.value)
    result.value = message
    status.value = 'success'
    pushToConversation(message, cameraQuery.value ? `【看我】${cameraQuery.value}` : '', '弥娅视觉')
    router.push('/chat')
  } catch (err: any) {
    result.value = err?.message || '看我失败'
    status.value = 'error'
  } finally {
    if (temporary) camera.stop()
    loading.value = false
  }
}

async function doLookBoth() {
  if (loading.value) return
  loading.value = true
  result.value = '正在同时观察屏幕和你...'
  status.value = 'idle'
  try {
    camera.attachPreview(previewVideo.value)
    const message = await camera.lookBoth(cameraQuery.value)
    result.value = message
    status.value = 'success'
    pushToConversation(message, cameraQuery.value ? `【一起看】${cameraQuery.value}` : '', '弥娅视觉')
  } catch (err: any) {
    result.value = err?.message || '一起观察失败'
    status.value = 'error'
  } finally {
    loading.value = false
  }
}

async function toggleCompanion() {
  if (companionActive.value) {
    camera.stop()
    return
  }
  try {
    camera.attachPreview(previewVideo.value)
    await camera.startCompanion()
    await nextTick()
    camera.attachPreview(previewVideo.value)
  } catch {
    /* error is surfaced by the shared camera state */
  }
}

function handleDeviceChange(event: Event) {
  camera.selectDevice((event.target as HTMLSelectElement).value)
}

function setFaceRecognition(event: Event) {
  camera.setFaceRecognition((event.target as HTMLInputElement).checked)
}

function setEmotionInference(event: Event) {
  camera.setEmotionInference((event.target as HTMLInputElement).checked)
}

function setActionRecognition(event: Event) {
  camera.setActionRecognition((event.target as HTMLInputElement).checked)
}

function setLocalOnly(event: Event) {
  camera.setLocalOnly((event.target as HTMLInputElement).checked)
}

async function enrollCurrentIdentity() {
  const name = identityName.value.trim()
  if (!name || identityBusy.value) return
  identityBusy.value = true
  let temporary = false
  try {
    camera.attachPreview(previewVideo.value)
    if (!camera.stream.value) {
      temporary = true
      await camera.open('snapshot')
      await nextTick()
      camera.attachPreview(previewVideo.value)
    }
    await camera.enrollIdentity(name)
    identities.value = await camera.listIdentities()
    identityName.value = ''
    result.value = `已在本机登记「${name}」的特征向量（未保存原图）`
    status.value = 'success'
  } catch (err: any) {
    result.value = err?.message || '身份登记失败'
    status.value = 'error'
  } finally {
    if (temporary) camera.stop()
    identityBusy.value = false
  }
}

async function removeIdentity(identityId: string) {
  if (identityBusy.value) return
  identityBusy.value = true
  try {
    await camera.deleteIdentity(identityId)
    identities.value = await camera.listIdentities()
  } catch (err: any) {
    result.value = err?.message || '删除身份失败'
    status.value = 'error'
  } finally {
    identityBusy.value = false
  }
}

onMounted(() => {
  void camera.listDevices()
  void camera.refreshCapabilities()
  void camera.listIdentities().then((items) => { identities.value = items }).catch(() => {})
})
onBeforeUnmount(() => { camera.attachPreview(null) })
</script>

<template>
  <div class="vision-root">
    <header class="vision-header">
      <button class="vision-back" title="返回首页" @click="router.push('/')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
      </button>
      <div class="vision-title-group">
        <span class="vision-title">弥娅视觉</span>
        <span class="vision-sub">MIYA VISION · SCREEN / SELF</span>
      </div>
      <div class="vision-live-state" :class="{ active: companionActive }">
        <span class="vision-state-dot" />
        {{ companionActive ? '陪伴视觉运行中' : '摄像头关闭' }}
      </div>
    </header>

    <div class="vision-tabs" role="tablist" aria-label="视觉来源">
      <button class="vision-tab" :class="{ active: activeTab === 'both' }" @click="activeTab = 'both'">
        <span class="tab-icon">◉</span><span>一起看</span><small>BOTH</small>
      </button>
      <button class="vision-tab" :class="{ active: activeTab === 'screen' }" @click="activeTab = 'screen'">
        <span class="tab-icon">▣</span><span>看屏幕</span><small>SCREEN</small>
      </button>
      <button class="vision-tab" :class="{ active: activeTab === 'me' }" @click="activeTab = 'me'">
        <span class="tab-icon">◉</span><span>看我</span><small>CAMERA</small>
      </button>
    </div>

    <main class="vision-body">
      <section v-if="activeTab === 'both'" class="vision-panel camera-panel">
        <div class="panel-heading">
          <div><span class="panel-kicker">SCREEN + CAMERA</span><h1>弥娅同时看着你和屏幕</h1></div>
          <span class="panel-badge">TOGETHER</span>
        </div>
        <div class="camera-preview" :class="{ active: !!camera.stream.value }">
          <video ref="previewVideo" autoplay muted playsinline />
          <div v-if="!camera.stream.value" class="preview-placeholder"><span>◉</span><b>摄像头默认关闭</b><small>点击“一起观察”时再请求开启</small></div>
          <div v-if="camera.stream.value" class="preview-status"><span class="vision-state-dot active" />{{ camera.status.value }}</div>
        </div>
        <div class="camera-controls">
          <label class="field-label" for="camera-device-both">摄像头</label>
          <select id="camera-device-both" class="camera-select" :value="camera.selectedDeviceId.value" :disabled="companionActive" @change="handleDeviceChange">
            <option value="">自动选择</option>
            <option v-for="(device, index) in camera.devices.value" :key="device.deviceId" :value="device.deviceId">{{ device.label || `摄像头 ${index + 1}` }}</option>
          </select>
        </div>
        <textarea v-model="cameraQuery" class="vision-textarea" placeholder="想让弥娅结合你的状态和屏幕内容留意什么？" rows="2" :disabled="loading" />
        <div class="vision-actions camera-actions">
          <button class="vision-btn primary" :disabled="loading" @click="doLookBoth">{{ loading ? '观察中...' : '一起观察' }}</button>
          <button class="vision-btn" :disabled="loading" @click="activeTab = 'screen'">只看屏幕</button>
          <button class="vision-btn" :disabled="loading" @click="activeTab = 'me'">只看我</button>
        </div>
        <div v-if="result" class="vision-result" :class="status">
          <div class="result-label">{{ status === 'error' ? '✗ 观察状态' : '✓ 联合观察结果' }}</div>
          <div class="result-content">{{ result }}</div>
        </div>
        <p class="privacy-note">一起观察会将本次屏幕截图与摄像头画面发送给视觉模型；摄像头只在本次操作期间开启，不保存原图。“仅本地”开启时不会发送。</p>
      </section>

      <section v-else-if="activeTab === 'screen'" class="vision-panel">
        <div class="panel-heading">
          <div><span class="panel-kicker">SCREEN SIGHT</span><h1>让弥娅看一眼屏幕</h1></div>
          <span class="panel-badge">OCR · AI</span>
        </div>
        <textarea v-model="query" class="vision-textarea" placeholder="想问弥娅关于屏幕的问题？留空则描述主要内容" rows="3" :disabled="loading" />
        <div class="vision-actions">
          <button class="vision-btn primary" :disabled="loading" @click="doLookScreen">{{ loading ? '分析中...' : '分析屏幕' }}</button>
          <button class="vision-btn" :disabled="loading" @click="doScreenshot">只截图</button>
        </div>
        <div v-if="result" class="vision-result" :class="status">
          <div class="result-label">{{ status === 'success' ? '✓ 分析结果' : status === 'error' ? '✗ 错误' : '⚠ 部分成功' }}</div>
          <div class="result-content">{{ result }}</div>
        </div>
        <div v-else class="vision-empty"><span class="empty-mark">⊙</span><span>游戏、报错、网页、操作界面</span><small>截图只在你主动操作时发送给视觉模型</small></div>
      </section>

      <section v-else class="vision-panel camera-panel">
        <div class="panel-heading">
          <div><span class="panel-kicker">CAMERA SIGHT</span><h1>让弥娅看见你</h1></div>
          <span class="panel-badge" :class="{ live: companionActive }">{{ companionActive ? 'LIVE' : 'OFF' }}</span>
        </div>

        <div class="camera-preview" :class="{ active: !!camera.stream.value }">
          <video ref="previewVideo" autoplay muted playsinline />
          <div v-if="!camera.stream.value" class="preview-placeholder"><span>◉</span><b>摄像头默认关闭</b><small>点击一次看我，或明确开启陪伴视觉</small></div>
          <div v-if="camera.stream.value" class="preview-status"><span class="vision-state-dot active" />{{ camera.status.value }}</div>
        </div>

        <div class="camera-controls">
          <label class="field-label" for="camera-device">物理摄像头</label>
          <select id="camera-device" class="camera-select" :value="camera.selectedDeviceId.value" :disabled="companionActive" @change="handleDeviceChange">
            <option value="">自动选择</option>
            <option v-for="device in camera.devices.value" :key="device.deviceId" :value="device.deviceId">{{ device.label || `摄像头 ${camera.devices.value.indexOf(device) + 1}` }}</option>
          </select>
        </div>

        <textarea v-model="cameraQuery" class="vision-textarea" placeholder="想让弥娅特别留意什么？例如：看看我现在是不是很累" rows="2" :disabled="loading || companionActive" />
        <div class="vision-actions camera-actions">
          <button class="vision-btn primary" :disabled="loading || companionActive" @click="doLookMe">{{ loading ? '观察中...' : '看我一眼' }}</button>
          <button class="vision-btn companion-btn" :class="{ stop: companionActive }" :disabled="loading" @click="toggleCompanion">{{ companionActive ? '关闭陪伴视觉' : '开启陪伴视觉' }}</button>
        </div>

        <div class="camera-event" :class="{ active: companionActive, motion: camera.localEventCode.value !== 'stable' }"><span class="event-dot" />{{ camera.localEvent.value || '本地视觉待机' }}</div>
        <div v-if="camera.lastObservation.value || camera.error.value" class="vision-result" :class="camera.error.value ? 'error' : 'success'">
          <div class="result-label">{{ camera.error.value ? '✗ 摄像头状态' : '✓ 弥娅看到的' }}</div>
          <div class="result-content">{{ camera.error.value || camera.lastObservation.value }}</div>
        </div>

        <div class="camera-options">
          <label title="初版由视觉模型提供实验性身份线索；本地人脸库将在后续模型层接入"><input type="checkbox" :checked="camera.faceRecognitionEnabled.value" @change="setFaceRecognition"><span>身份线索（实验）</span></label>
          <label title="只推测可见表情线索，不作为心理或医疗判断"><input type="checkbox" :checked="camera.emotionInferenceEnabled.value" @change="setEmotionInference"><span>表情线索（实验）</span></label>
          <label title="使用本地姿态模型和短时序关键点识别常见动作"><input type="checkbox" :checked="camera.actionRecognitionEnabled.value" @change="setActionRecognition"><span>本地动作识别</span></label>
          <label title="启用后没有本地模型就会拒绝分析，不会回退到云端"><input type="checkbox" :checked="camera.localOnly.value" @change="setLocalOnly"><span>仅本地</span></label>
        </div>
        <div class="identity-tools">
          <div class="identity-heading"><span>本地身份</span><small>只保存特征向量</small></div>
          <div class="identity-enroll">
            <input v-model="identityName" class="identity-input" placeholder="登记名称" maxlength="80" :disabled="identityBusy">
            <button class="vision-btn" :disabled="identityBusy || !identityName.trim()" @click="enrollCurrentIdentity">登记当前画面</button>
          </div>
          <div v-if="identities.length" class="identity-list">
            <div v-for="identity in identities" :key="identity.id" class="identity-row">
              <span>{{ identity.name }}</span>
              <button class="identity-delete" title="删除本地身份" :disabled="identityBusy" @click="removeIdentity(identity.id)">删除</button>
            </div>
          </div>
          <small v-else class="identity-empty">还没有登记身份；未知的人不会自动加入。</small>
        </div>
        <div class="local-capability" :class="camera.localCapabilities.value.status">
          <span class="capability-dot" />
          <span>{{ camera.localCapabilities.value.message }}</span>
          <small v-if="camera.localCapabilities.value.cameraMode" class="camera-route">看我：{{ camera.localCapabilities.value.cameraMode === 'local' ? '本地模型' : '云端视觉' }}</small>
          <button class="capability-refresh" title="重新检查本地模型" @click="camera.refreshCapabilities">↻</button>
        </div>
        <p class="privacy-note">统一路线在 config/qq_config.yaml 的 tools.qq_image_analyzer.vision_mode 中设置为 local、cloud 或 hybrid。local 下“一起看”只返回本地 OCR 与姿态信号，不上传云端；cloud 下才做跨画面语义理解。</p>
        <p class="privacy-note">默认不占用摄像头、不保存画面。陪伴模式先用本地帧差与姿态关键点识别动作，仅在本地无法确认时按冷却策略发送单帧分析。</p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.vision-root { display: flex; flex-direction: column; height: 100%; padding: 1rem 1.2rem; gap: .8rem; color: var(--miya-text, #e4ecf0); font-family: 'Noto Sans SC', sans-serif; overflow: hidden; }
.vision-header { display: flex; align-items: center; gap: .8rem; min-height: 44px; padding: .45rem .75rem; background: rgba(0,0,0,.5); border: 1px solid rgba(0,173,181,.08); border-radius: 4px; }
.vision-back { width: 28px; height: 28px; display: grid; place-items: center; border: 1px solid rgba(0,173,181,.12); border-radius: 5px; background: rgba(0,173,181,.04); color: rgba(0,255,245,.6); cursor: pointer; }
.vision-back svg { width: 14px; height: 14px; }
.vision-title-group { display: flex; flex-direction: column; min-width: 0; }
.vision-title { color: #fff; font-family: 'Noto Serif SC', serif; font-size: .9rem; font-weight: 700; }
.vision-sub, .panel-kicker, .panel-badge, .vision-live-state { font-family: 'JetBrains Mono', monospace; letter-spacing: .08em; }
.vision-sub { color: rgba(0,173,181,.42); font-size: .48rem; }
.vision-live-state { display: flex; align-items: center; gap: .35rem; margin-left: auto; color: rgba(220,230,235,.36); font-size: .52rem; white-space: nowrap; }
.vision-live-state.active { color: #ff807d; }
.vision-state-dot, .event-dot { width: 6px; height: 6px; display: inline-block; border-radius: 50%; background: rgba(180,190,195,.35); }
.vision-live-state.active .vision-state-dot, .vision-state-dot.active, .camera-event.active .event-dot { background: #ff706e; box-shadow: 0 0 10px rgba(255,92,92,.7); }
.vision-tabs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .5rem; max-width: 680px; width: 100%; margin: 0 auto; }
.vision-tab { display: flex; align-items: center; gap: .45rem; min-height: 42px; padding: .55rem .8rem; border: 1px solid rgba(0,173,181,.08); border-radius: 4px; background: rgba(0,0,0,.32); color: rgba(205,215,220,.48); cursor: pointer; text-align: left; }
.vision-tab.active { color: #eaffff; border-color: rgba(0,255,245,.32); background: rgba(0,173,181,.12); box-shadow: 0 0 18px rgba(0,173,181,.08); }
.tab-icon { color: #00fff5; font-size: 1rem; }
.vision-tab small { margin-left: auto; font: .48rem 'JetBrains Mono', monospace; opacity: .35; }
.vision-body { flex: 1; min-height: 0; display: flex; justify-content: center; overflow: auto; padding-bottom: .5rem; }
.vision-panel { width: 100%; max-width: 680px; align-self: flex-start; padding: 1rem; border: 1px solid rgba(0,173,181,.08); border-radius: 4px; background: rgba(0,0,0,.5); box-shadow: 3px 3px 10px rgba(0,40,50,.3); }
.panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: .85rem; }
.panel-kicker { display: block; color: rgba(0,255,245,.45); font-size: .48rem; }
h1 { margin: .25rem 0 0; color: #f3f7f8; font: 700 1.05rem 'Noto Serif SC', serif; }
.panel-badge { padding: .25rem .4rem; color: rgba(0,255,245,.58); border: 1px solid rgba(0,255,245,.16); border-radius: 3px; font-size: .48rem; }
.panel-badge.live { color: #ff9a96; border-color: rgba(255,112,110,.36); }
.vision-textarea { box-sizing: border-box; width: 100%; min-height: 60px; padding: .65rem; resize: vertical; border: 1px solid rgba(0,173,181,.1); border-radius: 4px; outline: none; background: rgba(0,0,0,.32); color: var(--miya-text); font: .73rem/1.65 inherit; }
.vision-textarea:focus { border-color: rgba(0,255,245,.3); }
.vision-textarea::placeholder { color: rgba(200,210,215,.22); }
.vision-actions { display: flex; gap: .5rem; margin-top: .65rem; }
.vision-btn { min-height: 34px; padding: .45rem .9rem; border: 1px solid rgba(0,173,181,.12); border-radius: 4px; background: rgba(0,0,0,.3); color: rgba(220,230,235,.58); cursor: pointer; font: .68rem inherit; }
.vision-btn:hover:not(:disabled) { color: #fff; border-color: rgba(0,255,245,.35); background: rgba(0,173,181,.14); }
.vision-btn:disabled { cursor: not-allowed; opacity: .35; }
.vision-btn.primary { color: rgba(0,255,245,.82); border-color: rgba(0,173,181,.3); background: rgba(0,173,181,.14); }
.companion-btn.stop { color: #ffaaa5; border-color: rgba(255,112,110,.3); }
.vision-result { margin-top: .8rem; padding: .75rem; border: 1px solid rgba(0,173,181,.12); border-radius: 4px; background: rgba(0,0,0,.25); }
.vision-result.error { border-color: rgba(248,113,113,.28); }
.result-label { margin-bottom: .45rem; color: rgba(0,255,245,.7); font: 600 .55rem 'JetBrains Mono', monospace; }
.vision-result.error .result-label { color: rgba(248,113,113,.85); }
.result-content { white-space: pre-wrap; color: var(--miya-text); font-size: .73rem; line-height: 1.7; }
.vision-empty { display: flex; flex-direction: column; align-items: center; gap: .42rem; padding: 3rem .5rem 2rem; color: rgba(210,220,225,.35); font-size: .7rem; }
.vision-empty small { color: rgba(210,220,225,.2); font-size: .58rem; }
.empty-mark { color: rgba(0,255,245,.25); font-size: 2rem; }
.camera-preview { position: relative; min-height: 210px; display: grid; place-items: center; overflow: hidden; border: 1px solid rgba(0,173,181,.1); border-radius: 4px; background: #050b10; }
.camera-preview video { display: block; width: 100%; max-height: 340px; object-fit: cover; transform: scaleX(-1); }
.camera-preview:not(.active) video { display: none; }
.preview-placeholder { display: flex; flex-direction: column; align-items: center; gap: .45rem; color: rgba(220,230,235,.42); font-size: .72rem; }
.preview-placeholder span { color: rgba(0,255,245,.28); font-size: 2.2rem; }
.preview-placeholder small { color: rgba(220,230,235,.2); font-size: .58rem; }
.preview-status { position: absolute; top: .55rem; left: .6rem; display: flex; align-items: center; gap: .35rem; padding: .3rem .45rem; border-radius: 3px; background: rgba(0,0,0,.62); color: rgba(255,235,235,.8); font: .52rem 'JetBrains Mono', monospace; }
.camera-controls { display: flex; align-items: center; gap: .6rem; margin: .75rem 0 .6rem; }
.field-label { color: rgba(220,230,235,.42); font-size: .62rem; white-space: nowrap; }
.camera-select { flex: 1; min-width: 0; padding: .45rem .55rem; border: 1px solid rgba(0,173,181,.1); border-radius: 4px; background: rgba(0,0,0,.35); color: rgba(220,230,235,.74); font: .65rem inherit; }
.camera-select:disabled { opacity: .45; }
.camera-event { display: flex; align-items: center; gap: .4rem; margin-top: .7rem; color: rgba(220,230,235,.34); font: .54rem 'JetBrains Mono', monospace; }
.camera-event.active { color: rgba(255,200,195,.7); }
.camera-event.motion { color: rgba(255, 210, 140, .78); }
.camera-options { display: flex; gap: 1rem; margin-top: .9rem; padding-top: .75rem; border-top: 1px solid rgba(0,173,181,.07); }
.camera-options label { display: flex; align-items: center; gap: .35rem; color: rgba(220,230,235,.52); font-size: .62rem; }
.camera-options input { accent-color: #00c9ca; }
.identity-tools { margin-top: .85rem; padding-top: .75rem; border-top: 1px solid rgba(0,173,181,.07); }
.identity-heading { display: flex; align-items: baseline; gap: .5rem; color: rgba(220,230,235,.62); font-size: .62rem; }
.identity-heading small, .identity-empty { color: rgba(220,230,235,.28); font-size: .54rem; }
.identity-enroll { display: flex; gap: .45rem; margin-top: .5rem; }
.identity-input { flex: 1; min-width: 0; padding: .45rem .55rem; border: 1px solid rgba(0,173,181,.1); border-radius: 4px; outline: none; background: rgba(0,0,0,.35); color: rgba(230,240,242,.82); font: .65rem inherit; }
.identity-input:focus { border-color: rgba(0,255,245,.3); }
.identity-list { display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .55rem; }
.identity-row { display: flex; align-items: center; gap: .4rem; padding: .3rem .45rem; border: 1px solid rgba(0,173,181,.1); border-radius: 3px; color: rgba(220,230,235,.56); font-size: .58rem; }
.identity-delete { border: 0; background: transparent; color: rgba(255,150,145,.65); cursor: pointer; font-size: .54rem; }
.identity-delete:disabled { opacity: .35; cursor: not-allowed; }
.privacy-note { margin: .7rem 0 0; color: rgba(220,230,235,.26); font-size: .56rem; line-height: 1.6; }
.local-capability { display: flex; align-items: center; gap: .38rem; margin-top: .65rem; color: rgba(220,230,235,.36); font: .54rem 'JetBrains Mono', monospace; }
.local-capability.ready { color: rgba(123, 226, 183, .72); }
.local-capability.unavailable { color: rgba(255, 190, 140, .68); }
.local-capability.partial { color: rgba(255, 210, 140, .72); }
.capability-dot { width: 5px; height: 5px; border-radius: 50%; background: rgba(180,190,195,.4); }
.local-capability.ready .capability-dot { background: #73e2b7; box-shadow: 0 0 8px rgba(115,226,183,.5); }
.local-capability.unavailable .capability-dot { background: #ffb878; }
.local-capability.partial .capability-dot { background: #ffd28c; }
.camera-route { color: rgba(220,230,235,.34); white-space: nowrap; }
.capability-refresh { margin-left: auto; border: 0; background: transparent; color: inherit; cursor: pointer; font-size: .8rem; }
@media (max-width: 560px) { .vision-root { padding: .7rem; } .vision-header { padding-inline: .55rem; } .vision-live-state { font-size: .45rem; } .vision-panel { padding: .75rem; } .camera-preview { min-height: 170px; } }
</style>
