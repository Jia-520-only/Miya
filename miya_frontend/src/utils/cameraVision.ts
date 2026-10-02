import { ref, shallowRef } from 'vue'
import API from '@/api/core'
import { rigCommandFromAnalysis } from '@/utils/facialTracking'
import { proxySetFacialTracking } from '@/utils/live2dProxy'

export type CameraMode = 'off' | 'snapshot' | 'companion'
export type CameraPolicy = 'auto' | 'single' | 'multi'
export type VisionControl = 'user' | 'miya' | 'hybrid'
export type StartupPolicy = 'on_demand' | 'resident'

export interface LocalCameraCapabilities {
  status: 'ready' | 'partial' | 'unavailable' | 'unknown'
  cameraMode?: 'cloud' | 'local'
  runtime?: string
  modelDir?: string
  message: string
  features?: Record<string, { available: boolean, model: string }>
}

const mode = ref<CameraMode>('off')
const status = ref('摄像头关闭')
const error = ref('')
const devices = ref<MediaDeviceInfo[]>([])
const selectedDeviceId = ref(localStorage.getItem('miya-camera-device') || '')
const stream = shallowRef<MediaStream | null>(null)
const streams = shallowRef<Record<string, MediaStream>>({})
const activeBrowserSources = ref<Array<Record<string, any>>>([])
const lastObservation = ref('')
// One line about what this side is doing. It no longer carries a locally
// invented motion score: the backend measures that, and the panel shows it.
const localEvent = ref('')
const faceRecognitionEnabled = ref(localStorage.getItem('miya-face-recognition') === 'true')
const emotionInferenceEnabled = ref(localStorage.getItem('miya-emotion-inference') === 'true')
const actionRecognitionEnabled = ref(localStorage.getItem('miya-action-recognition') !== 'false')
const localOnly = ref(localStorage.getItem('miya-camera-local-only') === 'true')
const alwaysOn = ref(localStorage.getItem('miya-camera-always-on') !== 'false')
const cameraPolicy = ref<CameraPolicy>((localStorage.getItem('miya-camera-policy') as CameraPolicy) || 'auto')
const visionControl = ref<VisionControl>((localStorage.getItem('miya-vision-control') as VisionControl) || 'hybrid')
const startupPolicy = ref<StartupPolicy>((localStorage.getItem('miya-vision-startup') as StartupPolicy) || 'resident')
const localCapabilities = ref<LocalCameraCapabilities>({
  status: 'unknown',
  message: '正在检查本地视觉模型…',
})
// Physical devices as OpenCV sees them. A phone-as-webcam or a Windows virtual
// camera can open successfully while returning only black frames, so the probe
// result matters more than the device count. Sleeping devices are re-checked
// automatically, because a phone screen goes to sleep and wakes back up.
const backendDevices = ref<Array<Record<string, any>>>([])
const cameraSourcesMessage = ref('')
const presence = ref<Record<string, any> | null>(null)
const activity = ref<Record<string, any> | null>(null)
// Which OpenCV index the browser's preview corresponds to. The backend cannot
// open a device the browser is holding, so it needs to be told which index the
// frames it receives belong to.
const backendDeviceIndex = ref<number>(Number(localStorage.getItem('miya-camera-backend-index') ?? '') || 0)
const backendDeviceMapping = ref<'matched' | 'ambiguous' | 'unmatched'>('unmatched')
// Miya's own watching loop: she starts it at boot, but the desktop must be able
// to see that she is looking and to stop her.
const agentState = ref<Record<string, any> | null>(null)
const agentAgency = ref<Record<string, any> | null>(null)
// What she has been wanting to say. Without an outlet she watches all evening
// and never gets to speak, because delivery only ran into chat platforms.
const agentVoice = ref<Record<string, any> | null>(null)
const agentVoiceQueue = ref<Array<Record<string, any>>>([])
// Her observation rounds, so the page can show her working instead of only her
// conclusions. Thumbnails are fetched per event, only when expanded.
const visionEvents = ref<Array<Record<string, any>>>([])
const visionStreamStatus = ref<Record<string, any>>({})
const visionCadence = ref<Record<string, any>>({})
const thumbnailsEnabled = ref(false)
// Device health, so the monitor can say how many cameras actually work right now
// instead of showing an empty box when one is asleep.
const cameraHealth = ref<Record<string, any>>({ devices: [], usableCount: 0, count: 0, message: '' })
// Which side holds which camera. The monitor needs this to say "预览持有 #0" and
// to know which frames the backend can produce on its own. Keys are camelCase
// because the API layer converts every response; they used to be written here as
// snake_case, which made all three lists permanently empty.
const visionSources = ref<Record<string, any>>({ sources: {}, browserOwned: [], backendOwned: [], readersRunning: [] })
// DirectShow device names by OpenCV index, so the page can show "4K USB Camera"
// instead of a bare number - and so the browser's deviceId can be matched to the
// index the backend needs.
const backendNames = ref<Record<string, string>>({})
// Whether her seeing can reach her speaking. Without this the page looks healthy
// while nothing is ever submitted to the proactive chain.
const visionBridge = ref<Record<string, any> | null>(null)

let timer: ReturnType<typeof setTimeout> | null = null
let analysisInFlight = false
let previewVideo: HTMLVideoElement | null = null
const mediaVideos = new Map<string, HTMLVideoElement>()
let deviceChangeHandler: (() => void) | null = null
let remotePollTimer: ReturnType<typeof setInterval> | null = null
let remoteCommandInFlight = false
let observationRequestInFlight = false
let companionStartInFlight: Promise<void> | null = null
let companionStartInFlightVersion = 0
let companionStartVersion = 0
let lastRemoteCommandId = localStorage.getItem('miya-camera-command-seen') || ''
let lastObservationRequestId = localStorage.getItem('miya-camera-observation-seen') || ''
const lastPublishedEvents = new Map<string, number>()
// The skeleton history handed to the backend so it can read *actions* rather
// than a single posture. This was assigned without ever being declared, which
// TypeScript flagged and which would throw a ReferenceError the first time the
// camera was stopped - so the history was never actually kept.
let poseHistory: Array<Record<string, any>> = []
let signatureCanvas: HTMLCanvasElement | null = null
let signatureContext: CanvasRenderingContext2D | null = null
let lastFrameSharedAt = 0
const SNAPSHOT_INTERVAL_MS = 3000
// How often this side hands a frame to Miya. She decides what it means; the
// preview only decides how often it can spare one.
const FRAME_SHARE_INTERVAL_MS = 15_000
const EVENT_REPEAT_COOLDOWN_MS = 90_000

function handleStreamEnded(sourceId = 'primary') {
  const ended = streams.value[sourceId]
  if (ended) removeStream(sourceId)
  if (!Object.keys(streams.value).length) stop('摄像头已断开，请检查设备或权限')
}

function getMediaVideo(sourceId = selectedDeviceId.value || 'primary') {
  let video = mediaVideos.get(sourceId)
  if (!video) {
    video = document.createElement('video')
    video.autoplay = true
    video.muted = true
    video.playsInline = true
    mediaVideos.set(sourceId, video)
  }
  return video
}

function browserSourceId(deviceId: string, index: number) {
  const raw = `${deviceId || `index-${index}`}`
  let hash = 2166136261
  for (let i = 0; i < raw.length; i += 1) hash = Math.imul(hash ^ raw.charCodeAt(i), 16777619)
  return `browser:${(hash >>> 0).toString(16)}`
}

function removeStream(sourceId: string) {
  const current = streams.value[sourceId]
  if (!current) return
  current.getTracks().forEach(track => track.stop())
  const next = { ...streams.value }
  delete next[sourceId]
  streams.value = next
  const video = mediaVideos.get(sourceId)
  if (video) video.srcObject = null
  activeBrowserSources.value = activeBrowserSources.value.filter(item => item.sourceId !== sourceId)
  if (stream.value === current) {
    const primary = Object.values(next)[0] || null
    stream.value = primary
    if (previewVideo) previewVideo.srcObject = primary
  }
}

function primarySourceId() {
  return activeBrowserSources.value.find(item => item.deviceId === selectedDeviceId.value)?.sourceId
    || activeBrowserSources.value[0]?.sourceId
    || selectedDeviceId.value
    || 'primary'
}

function publishState() {
  localStorage.setItem('miya-camera-mode', mode.value)
  localStorage.setItem('miya-camera-status', status.value)
  localStorage.setItem('miya-camera-heartbeat', String(Date.now()))
  window.dispatchEvent(new CustomEvent('miya-camera-state', {
    detail: { mode: mode.value, status: status.value },
  }))
}

async function listDevices() {
  if (!navigator.mediaDevices?.enumerateDevices) {
    error.value = '当前环境不支持摄像头设备枚举'
    return []
  }
  try {
    devices.value = (await navigator.mediaDevices.enumerateDevices())
      .filter(device => device.kind === 'videoinput')
    if (selectedDeviceId.value && !devices.value.some(device => device.deviceId === selectedDeviceId.value)) {
      selectedDeviceId.value = ''
      localStorage.removeItem('miya-camera-device')
    }
    if (!selectedDeviceId.value && devices.value[0]) {
      selectedDeviceId.value = devices.value[0].deviceId
      localStorage.setItem('miya-camera-device', selectedDeviceId.value)
    }
    return devices.value
  } catch (err: any) {
    error.value = err?.message || '无法读取摄像头列表'
    return []
  }
}

async function refreshCapabilities() {
  try {
    const response = await API.mcpCall('screen_vision', 'camera_capabilities')
    const raw = response?.result
    const data = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (data?.capabilities) localCapabilities.value = { ...data.capabilities, cameraMode: data.camera_mode }
  } catch {
    localCapabilities.value = {
      status: 'unknown',
      message: '无法连接视觉服务，暂时不能确认本地模型状态。',
    }
  }
  return localCapabilities.value
}

function attachPreview(video: HTMLVideoElement | null) {
  previewVideo = video
  if (previewVideo && stream.value) {
    previewVideo.srcObject = stream.value
    void previewVideo.play().catch(() => {})
  }
}

async function attachStreamToVideos(activeStream: MediaStream, sourceId = selectedDeviceId.value || 'primary') {
  const source = getMediaVideo(sourceId)
  source.srcObject = activeStream
  await source.play().catch(() => {})
  if (previewVideo && activeStream === stream.value) {
    previewVideo.srcObject = activeStream
    await previewVideo.play().catch(() => {})
  }
}

async function open(modeToUse: Exclude<CameraMode, 'off'>) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('当前环境不支持摄像头访问')
  }

  if (stream.value && (cameraPolicy.value !== 'multi' || Object.keys(streams.value).length > 1)) {
    mode.value = modeToUse
    status.value = modeToUse === 'companion' ? '陪伴视觉运行中' : '准备看你'
    publishState()
    await attachStreamToVideos(stream.value)
    return
  }

  error.value = ''
  status.value = '正在请求摄像头权限'
  publishState()
  try {
    await listDevices()
    const candidates = cameraPolicy.value === 'multi'
      ? devices.value
      : [devices.value.find(device => device.deviceId === selectedDeviceId.value) || devices.value[0]].filter(Boolean)
    const opened: Record<string, MediaStream> = {}
    const sources: Array<Record<string, any>> = []
    for (let index = 0; index < candidates.length; index += 1) {
      const device = candidates[index]
      const sourceId = browserSourceId(device?.deviceId || '', index)
      try {
        const activeStream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: device?.deviceId
            ? { deviceId: { exact: device.deviceId }, width: { ideal: 640 }, height: { ideal: 480 } }
            : { width: { ideal: 640 }, height: { ideal: 480 } },
        })
        opened[sourceId] = activeStream
        activeStream.getTracks().forEach(track => track.addEventListener('ended', () => handleStreamEnded(sourceId), { once: true }))
        await attachStreamToVideos(activeStream, sourceId)
        sources.push({ sourceId, deviceId: device?.deviceId || '', label: device?.label || `摄像头 ${index + 1}`, backendIndex: null })
      } catch (err) {
        if (cameraPolicy.value !== 'multi') throw err
      }
    }
    if (!Object.keys(opened).length) throw new Error('没有可用的浏览器摄像头')
    streams.value = opened
    const primarySource = activeBrowserSources.value.find(item => item.deviceId === selectedDeviceId.value)
    stream.value = (primarySource ? opened[primarySource.sourceId] : undefined) || Object.values(opened)[0] || null
    activeBrowserSources.value = sources
    if (!deviceChangeHandler && navigator.mediaDevices.addEventListener) {
      deviceChangeHandler = () => { void listDevices() }
      navigator.mediaDevices.addEventListener('devicechange', deviceChangeHandler)
    }
    mode.value = modeToUse
    status.value = modeToUse === 'companion' ? '陪伴视觉运行中' : '准备看你'
    await attachStreamToVideos(stream.value, activeBrowserSources.value.find(item => item.deviceId === selectedDeviceId.value)?.sourceId || 'primary')
    publishState()
  } catch (err: any) {
    mode.value = 'off'
    Object.keys(streams.value).forEach(removeStream)
    streams.value = {}
    stream.value = null
    status.value = '摄像头未启用'
    error.value = err?.name === 'NotAllowedError' ? '摄像头权限被拒绝' : (err?.message || '摄像头启动失败')
    publishState()
    throw err
  }
}

function stop(reason = '') {
  companionStartVersion += 1
  lastFrameSharedAt = 0
  const releaseIndex = selectedDeviceId.value && backendDeviceMapping.value === 'matched' ? backendDeviceIndex.value : null
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
  Object.values(streams.value).forEach(active => active.getTracks().forEach(track => track.stop()))
  streams.value = {}
  stream.value = null
  activeBrowserSources.value = []
  if (deviceChangeHandler && navigator.mediaDevices?.removeEventListener) {
    navigator.mediaDevices.removeEventListener('devicechange', deviceChangeHandler)
    deviceChangeHandler = null
  }
  mediaVideos.forEach(video => { video.srcObject = null })
  if (previewVideo) previewVideo.srcObject = null
  // Tell the backend immediately. Without this handshake its ownership grace
  // period keeps the physical device reserved after this tab has stopped it.
  void API.mcpCall('screen_vision', 'camera_event', {
    event: { kind: 'preview_released', ...(releaseIndex === null ? {} : { camera_index: releaseIndex }) },
    ...(releaseIndex === null ? {} : { camera_index: releaseIndex }),
    browser_source_ids: activeBrowserSources.value.map(item => item.sourceId),
  }).catch(() => {})
  mode.value = 'off'
  status.value = reason || '摄像头关闭'
  error.value = reason
  localEvent.value = ''
  lastPublishedEvents.clear()
  poseHistory = []
  analysisInFlight = false
  publishState()
}

function captureFrame(sourceId = primarySourceId()) {
  const resolvedSourceId = streams.value[sourceId] ? sourceId : primarySourceId()
  const activeStream = streams.value[resolvedSourceId] || stream.value
  const source = getMediaVideo(resolvedSourceId)
  if (!activeStream || source.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
    throw new Error('摄像头画面还没有准备好')
  }
  const canvas = document.createElement('canvas')
  const width = Math.min(source.videoWidth || 640, 1024)
  const height = Math.round(width * (source.videoHeight || 480) / (source.videoWidth || 640))
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('无法创建画面采样器')
  context.drawImage(source, 0, 0, width, height)
  return canvas.toDataURL('image/jpeg', 0.78)
}

async function waitForMediaFrame() {
  const source = getMediaVideo(primarySourceId())
  for (let index = 0; index < 25; index += 1) {
    if (source.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && source.videoWidth > 0) return
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('摄像头画面还没有准备好')
}

function scheduleCompanionTick(delay = SNAPSHOT_INTERVAL_MS) {
  if (mode.value !== 'companion' || !stream.value) return
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    timer = null
    void companionTick()
  }, delay)
}

async function publishLocalEvent(
  kind: string,
  summary: string,
  confidence = 1,
  options: { repeatable?: boolean, imageData?: string, source?: Record<string, any> } = {},
) {
  const now = Date.now()
  // Repeatable publications (sharing a frame on a slow cadence) must not be
  // swallowed by the de-duplication window that real events rely on.
  if (!options.repeatable) {
    const key = `${kind}:${summary}`
    if (now - (lastPublishedEvents.get(key) || 0) < EVENT_REPEAT_COOLDOWN_MS) return
    lastPublishedEvents.set(key, now)
  }
  try {
    // A live preview holds the device, so only this side can read frames from
    // it. The frame is captured by the caller so a failed capture cannot send an
    // event that claims one.
    const imageData = options.imageData || ''
    const source = options.source || activeBrowserSources.value.find(item => item.deviceId === selectedDeviceId.value)
    const index = source?.backendIndex !== null && source?.backendIndex !== undefined
      ? Number(source.backendIndex)
      : selectedDeviceId.value && backendDeviceMapping.value !== 'matched'
      ? null
      : backendDeviceIndex.value
    await API.mcpCall('screen_vision', 'camera_event', {
      event: {
        kind, summary, confidence, mode: 'companion', status: 'success',
        ...(source?.sourceId ? { browser_source_id: source.sourceId } : {}),
        ...(source?.deviceId ? { device_id_hash: browserSourceId(source.deviceId, 0) } : {}),
        ...(source?.label ? { camera_label: source.label } : {}),
      },
      ...(index === null ? {} : { camera_index: index }),
      ...(source?.sourceId ? { browser_source_id: source.sourceId } : {}),
      ...(source?.deviceId ? { device_id_hash: browserSourceId(source.deviceId, 0) } : {}),
      ...(source?.label ? { camera_label: source.label } : {}),
      ...(imageData ? { image_data: imageData } : {}),
    })
  } catch {
    // Event publication is best effort; camera observation must keep running.
  }
}

function buildQuery(query = '') {
  const extras = [
    faceRecognitionEnabled.value ? '如果画面中能可靠识别已登记身份，再补充身份；不能确定就说未知。' : '',
    emotionInferenceEnabled.value ? '请把表情推测作为不确定的表情线索，说明置信度，不要当作绝对情绪或心理诊断。' : '',
  ].filter(Boolean).join(' ')
  return query.trim() || `请观察我当前的画面，描述可见的姿态、动作和环境。${extras}`
}

function localPoseAvailable() {
  return localCapabilities.value.features?.pose?.available === true
}

function localOnlyReady() {
  const features = localCapabilities.value.features || {}
  const identityReady = !faceRecognitionEnabled.value || (features.face_detection?.available && features.identity?.available)
  const emotionReady = !emotionInferenceEnabled.value || (features.face_detection?.available && features.emotion?.available)
  const poseReady = !actionRecognitionEnabled.value || features.pose?.available
  return Boolean(identityReady && emotionReady && poseReady)
}

function rememberPose(data: any) {
  const pose = data?.observations?.[0]?.pose
  if (!pose?.keypoints?.length) return
  poseHistory = [...poseHistory, pose].slice(-11)
}

let lastFacialAt = 0

/**
 * Feed a measured rig command to Miya's face.
 *
 * The backend already converted the geometry into rig parameters from the same
 * frame it analysed, so no conversion happens here and no second camera is
 * opened - the desktop preview is holding that device.
 *
 * Note this only runs while a preview is open: the browser owns the camera, so
 * the backend cannot measure a face on its own. With no preview Miya keeps
 * watching and remembering, she just does not mirror Jia's expression.
 */
function applyFacialTracking(data: any) {
  const now = performance.now()
  const dt = lastFacialAt ? Math.min(now - lastFacialAt, 200) : 16
  lastFacialAt = now
  const command = rigCommandFromAnalysis(data)
  // No measurable face this tick: let the rig blend back to its own idle motion.
  proxySetFacialTracking(command?.params ?? null, dt)
}

/**
 * One round trip that both measures the face and updates what is on screen.
 *
 * It used to exist to run action classification in the browser; that is gone,
 * because the backend classifies with real inference instead. What is left is
 * the one thing only this side can obtain: a frame from the camera it holds.
 */
async function measureFaceFromPreview() {
  if (!stream.value || !localPoseAvailable()) return
  const measureVersion = companionStartVersion
  await waitForMediaFrame()
  if (measureVersion !== companionStartVersion || mode.value !== 'companion' || !stream.value) return
  const response = await API.mcpCall('screen_vision', 'camera_analyze_local', {
    image_data: captureFrame(),
    identity: false,
    emotion: false,
    pose: true,
    // Ask for face detection even though identity and emotion are off: the
    // measured face geometry is what drives Miya's own expression.
    faces: true,
    pose_history: poseHistory,
  })
  const raw = response?.result
  const data = typeof raw === 'string' ? JSON.parse(raw) : raw
  if (measureVersion !== companionStartVersion || mode.value !== 'companion' || !stream.value || data?.status !== 'success') return
  applyFacialTracking(data)
  rememberPose(data)
}

async function lookAtMe(query = '') {
  if (localOnly.value && !localOnlyReady()) {
    throw new Error(localCapabilities.value.message)
  }
  let temporary = false
  if (!stream.value) {
    temporary = true
    await open('snapshot')
  }
  status.value = '正在看你'
  publishState()
  try {
    await waitForMediaFrame()
    const imageData = captureFrame()
    const response = await API.mcpCall('screen_vision', 'look_me', {
      image_data: imageData,
      query: buildQuery(query),
      local_only: localOnly.value,
      identity: faceRecognitionEnabled.value,
      emotion: emotionInferenceEnabled.value,
      pose: Boolean(actionRecognitionEnabled.value && localCapabilities.value.features?.pose?.available),
      pose_history: poseHistory,
    })
    const raw = response?.result
    const data = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (data?.status !== 'success') throw new Error(data?.message || '视觉分析失败')
    rememberPose(data)
    lastObservation.value = data.message || '弥娅看到了你，但没有生成描述。'
    status.value = mode.value === 'companion' ? '陪伴视觉运行中' : '看你完成'
    publishState()
    return lastObservation.value
  } finally {
    if (temporary) stop()
  }
}

async function lookBoth(query = '') {
  let temporary = false
  if (!stream.value) {
    temporary = true
    await open('snapshot')
  }
  status.value = '正在同时观察屏幕和你'
  publishState()
  try {
    await waitForMediaFrame()
    const response = await API.mcpCall('screen_vision', 'look_both', {
      image_data: captureFrame(),
      query: buildQuery(query),
      local_only: localOnly.value,
    })
    const raw = response?.result
    const data = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!['success', 'partial'].includes(data?.status)) throw new Error(data?.message || data?.error || '一起观察失败')
    lastObservation.value = data.message || '弥娅看到了屏幕和你。'
    status.value = mode.value === 'companion' ? '陪伴视觉运行中' : '一起观察完成'
    publishState()
    return lastObservation.value
  } finally {
    if (temporary) stop()
  }
}

async function enrollIdentity(name: string) {
  await waitForMediaFrame()
  let lastMessage = '身份登记失败'
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const response = await API.mcpCall('screen_vision', 'camera_enroll_identity', {
      image_data: captureFrame(),
      name,
    })
    if (response?.success === false) {
      throw new Error(response?.error || response?.message || '身份登记请求失败')
    }
    const raw = response?.result
    let data: any
    try {
      data = typeof raw === 'string' ? JSON.parse(raw) : raw
    } catch {
      throw new Error('身份登记服务返回了无法解析的结果，请检查后端日志')
    }
    if (data?.status === 'success') {
      await refreshCapabilities()
      return data
    }
    lastMessage = data?.message || lastMessage
    if (!String(lastMessage).includes('没有可靠检测到人脸') || attempt >= 2) break
    await new Promise(resolve => setTimeout(resolve, 180))
    await waitForMediaFrame()
  }
  throw new Error(lastMessage)
}

async function listIdentities() {
  const response = await API.mcpCall('screen_vision', 'camera_list_identities', {})
  const raw = response?.result
  const data = typeof raw === 'string' ? JSON.parse(raw) : raw
  return data?.identities || []
}

async function deleteIdentity(identityId: string) {
  const response = await API.mcpCall('screen_vision', 'camera_delete_identity', { identity_id: identityId })
  const raw = response?.result
  const data = typeof raw === 'string' ? JSON.parse(raw) : raw
  if (data?.status !== 'success') throw new Error(data?.message || '删除身份失败')
  await refreshCapabilities()
  return data
}

/**
 * The companion loop, stripped to what only the browser can do.
 *
 * It used to run its own frame-difference motion detection, its own thresholds,
 * and a second confirmation pass over the backend's action labels. All of that
 * duplicated work the backend now does properly with ONNX and temporal
 * accumulation, and layering invented thresholds on top of real inference was
 * the main source of the readings feeling wrong.
 *
 * What remains is genuinely browser-side: this process holds the camera device,
 * so it is the only thing that can *hand Miya frames*. Everything about what
 * those frames mean is hers to decide.
 */
async function companionTick() {
  if (mode.value !== 'companion' || !stream.value) return
  const tickVersion = companionStartVersion
  if (analysisInFlight) {
    scheduleCompanionTick(SNAPSHOT_INTERVAL_MS)
    return
  }
  const now = Date.now()
  try {
    localStorage.setItem('miya-camera-heartbeat', String(now))
    // Hand over a frame on a steady cadence. Miya's own observation loop decides
    // what to do with it; this side only supplies the pixels.
    if (now - lastFrameSharedAt >= FRAME_SHARE_INTERVAL_MS) {
      lastFrameSharedAt = now
      const frameSources = cameraPolicy.value === 'multi' ? activeBrowserSources.value : activeBrowserSources.value.slice(0, 1)
      if (frameSources.length) {
        analysisInFlight = true
        try {
          for (const source of frameSources) {
            if (tickVersion !== companionStartVersion || mode.value !== 'companion' || !stream.value) return
            const frame = captureFrame(source.sourceId)
            if (frame) await publishLocalEvent('companion_frame', '预览正在把画面交给弥娅', 0.5,
              { repeatable: true, imageData: frame, source })
          }
          if (tickVersion !== companionStartVersion || mode.value !== 'companion' || !stream.value) return
          status.value = '预览运行中 · 正在把画面交给弥娅'
        } finally {
          analysisInFlight = false
        }
      }
    }
    // Face geometry is the one measurement the backend cannot take on its own
    // while this preview owns the camera, so measure it from here.
    if (tickVersion !== companionStartVersion || mode.value !== 'companion' || !stream.value) return
    await measureFaceFromPreview()
  } catch (err: any) {
    localEvent.value = err?.message || '摄像头采样失败'
  } finally {
    if (tickVersion === companionStartVersion && mode.value === 'companion' && stream.value && !timer) {
      scheduleCompanionTick()
    }
  }
}

async function startCompanion() {
  if (mode.value === 'companion' && stream.value) return
  if (companionStartInFlight) return companionStartInFlight
  const startVersion = ++companionStartVersion
  companionStartInFlightVersion = startVersion
  companionStartInFlight = (async () => {
    await refreshCapabilities()
    if (startVersion !== companionStartVersion) return
    await open('companion')
    if (startVersion !== companionStartVersion) {
      stop()
      return
    }
    if (!timer) scheduleCompanionTick(0)
  })()
  try {
    await companionStartInFlight
  } finally {
    if (companionStartInFlightVersion === startVersion) {
      companionStartInFlight = null
      if (startVersion !== companionStartVersion && alwaysOn.value && mode.value === 'off') {
        void startCompanion()
      }
    }
  }
}

async function startAlwaysOnCompanion() {
  await startCompanion()
  if (!alwaysOn.value || mode.value !== 'companion') return
  try {
    const response = await API.setCameraControl({
      mode: 'companion',
      local_only: localOnly.value,
      action_recognition: actionRecognitionEnabled.value,
      identity_recognition: faceRecognitionEnabled.value,
      autonomous: true,
      camera_policy: cameraPolicy.value,
      camera_indices: cameraPolicy.value === 'single' ? [backendDeviceIndex.value] : [],
      preferred_index: backendDeviceIndex.value,
      camera_source_ids: cameraPolicy.value === 'single' && selectedBackendSourceId() ? [selectedBackendSourceId()!] : [],
      preferred_source_id: selectedBackendSourceId() || '',
      vision_control: visionControl.value,
      startup_policy: startupPolicy.value,
      consent_granted: true,
      browser_source_ids: activeBrowserSources.value.map(item => item.sourceId),
      preferred_browser_source_id: activeBrowserSources.value.find(item => item.deviceId === selectedDeviceId.value)?.sourceId,
    })
    const requestId = String(response?.state?.requestId || '')
    if (requestId) {
      lastRemoteCommandId = requestId
      localStorage.setItem('miya-camera-command-seen', requestId)
    }
  } catch (err: any) {
    error.value = err?.message || '摄像头已启动，但自主视觉状态同步失败'
    publishState()
    throw err
  }
}

async function setCameraPolicy(value: CameraPolicy) {
  const wasActive = mode.value === 'companion'
  cameraPolicy.value = value
  localStorage.setItem('miya-camera-policy', value)
  try {
    await API.setCameraControl({
      mode: mode.value === 'off' ? 'off' : mode.value,
      local_only: localOnly.value,
      action_recognition: actionRecognitionEnabled.value,
      identity_recognition: faceRecognitionEnabled.value,
      autonomous: alwaysOn.value,
      camera_policy: value,
      camera_indices: value === 'single' ? [backendDeviceIndex.value] : [],
      preferred_index: backendDeviceIndex.value,
      camera_source_ids: value === 'single' && selectedBackendSourceId() ? [selectedBackendSourceId()!] : [],
      preferred_source_id: selectedBackendSourceId() || '',
      vision_control: visionControl.value,
      startup_policy: startupPolicy.value,
      consent_granted: Boolean(mode.value !== 'off'),
      browser_source_ids: activeBrowserSources.value.map(item => item.sourceId),
      preferred_browser_source_id: activeBrowserSources.value.find(item => item.deviceId === selectedDeviceId.value)?.sourceId,
    })
  } catch (err: any) {
    error.value = err?.message || '摄像头策略同步失败'
  }
  if (wasActive) {
    stop()
    await startCompanion().catch(() => {})
  }
  return cameraPolicy.value
}

function setAlwaysOn(value: boolean) {
  alwaysOn.value = value
  localStorage.setItem('miya-camera-always-on', String(value))
  if (!value) {
    if (mode.value === 'companion' || companionStartInFlight) stop()
    void API.setCameraControl({ mode: 'off', local_only: true, autonomous: false }).catch(() => {})
    return
  }
  void enableAlwaysOn().catch(() => {})
}

async function setVisionControl(value: VisionControl) {
  visionControl.value = value
  localStorage.setItem('miya-vision-control', value)
  await API.setCameraControl({
    mode: mode.value === 'off' ? 'off' : mode.value,
    autonomous: value !== 'user' && alwaysOn.value,
    vision_control: value,
    startup_policy: startupPolicy.value,
    consent_granted: Boolean(mode.value !== 'off'),
    camera_policy: cameraPolicy.value,
    preferred_index: backendDeviceIndex.value,
    camera_source_ids: cameraPolicy.value === 'single' && selectedBackendSourceId() ? [selectedBackendSourceId()!] : [],
    preferred_source_id: selectedBackendSourceId() || '',
  }).catch(() => {})
  return value
}

async function setStartupPolicy(value: StartupPolicy) {
  startupPolicy.value = value
  alwaysOn.value = value === 'resident'
  localStorage.setItem('miya-vision-startup', value)
  localStorage.setItem('miya-camera-always-on', String(alwaysOn.value))
  await API.setCameraControl({
    mode: mode.value === 'off' ? 'off' : mode.value,
    autonomous: visionControl.value !== 'user' && alwaysOn.value,
    vision_control: visionControl.value,
    startup_policy: value,
    consent_granted: Boolean(mode.value !== 'off'),
  }).catch(() => {})
  return value
}

async function enableAlwaysOn() {
  alwaysOn.value = true
  localStorage.setItem('miya-camera-always-on', 'true')
  try {
    await startAlwaysOnCompanion()
  } catch (err: any) {
    error.value = err?.message || '本地陪伴视觉启动失败'
    if (mode.value === 'off') status.value = '摄像头未启用'
    publishState()
    throw err
  }
}

async function syncRemoteCommand() {
  if (remoteCommandInFlight) return
  remoteCommandInFlight = true
  try {
    const response = await API.getCameraControl()
    const state = response?.state
    const requestId = String(state?.requestId || '')
    if (!requestId || requestId === 'initial' || requestId === lastRemoteCommandId) return
    lastRemoteCommandId = requestId
    localStorage.setItem('miya-camera-command-seen', requestId)
    if (state.mode === 'off') {
      alwaysOn.value = false
      localStorage.setItem('miya-camera-always-on', 'false')
      if (mode.value !== 'off' || companionStartInFlight) stop('已按命令关闭摄像头')
      return
    }
    localOnly.value = Boolean(state.localOnly)
    actionRecognitionEnabled.value = state.actionRecognition !== false
    if (state.cameraPolicy === 'auto' || state.cameraPolicy === 'single' || state.cameraPolicy === 'multi') {
      cameraPolicy.value = state.cameraPolicy
      localStorage.setItem('miya-camera-policy', cameraPolicy.value)
    }
    if (state.visionControl === 'user' || state.visionControl === 'miya' || state.visionControl === 'hybrid') {
      visionControl.value = state.visionControl
      localStorage.setItem('miya-vision-control', visionControl.value)
    }
    if (state.startupPolicy === 'on_demand' || state.startupPolicy === 'resident') {
      startupPolicy.value = state.startupPolicy
      alwaysOn.value = startupPolicy.value === 'resident'
      localStorage.setItem('miya-vision-startup', startupPolicy.value)
      localStorage.setItem('miya-camera-always-on', String(alwaysOn.value))
    }
    localStorage.setItem('miya-camera-local-only', String(localOnly.value))
    localStorage.setItem('miya-action-recognition', String(actionRecognitionEnabled.value))
    if (state.mode === 'snapshot') {
      await lookAtMe()
    } else if (state.mode === 'companion' && mode.value !== 'companion') {
      await startCompanion()
    }
  } catch (err: any) {
    error.value = err?.message || '远程摄像头命令无法执行'
    publishState()
  } finally {
    remoteCommandInFlight = false
  }
}

async function syncObservationRequest() {
  if (remoteCommandInFlight || observationRequestInFlight || mode.value === 'off') return
  observationRequestInFlight = true
  let currentRequestId = ''
  try {
    const response = await API.getCameraRequest()
    const request = response?.request
    const requestId = String(request?.requestId || '')
    if (!request || !requestId || requestId === lastObservationRequestId) return
    if (mode.value !== 'companion' || !stream.value) return
    currentRequestId = requestId
    const requestLocalOnly = request.localOnly === undefined || request.localOnly === null
      ? localOnly.value
      : typeof request.localOnly === 'string'
        ? ['true', '1', 'yes', 'on'].includes(request.localOnly.trim().toLowerCase())
        : Boolean(request.localOnly)
    await waitForMediaFrame()
    const imageData = captureFrame()
    let result: any
    if (requestLocalOnly) {
      const localResponse = await API.mcpCall('screen_vision', 'camera_analyze_local', {
        image_data: imageData, identity: faceRecognitionEnabled.value,
        emotion: emotionInferenceEnabled.value, pose: actionRecognitionEnabled.value,
        pose_history: poseHistory,
      })
      result = typeof localResponse?.result === 'string' ? JSON.parse(localResponse.result) : localResponse?.result
    } else {
      const cameraResponse = await API.mcpCall('screen_vision', 'look_me', {
        image_data: imageData, query: request.query || '请观察我当前的姿态、动作和环境。',
        local_only: requestLocalOnly, identity: faceRecognitionEnabled.value,
        emotion: emotionInferenceEnabled.value, pose: actionRecognitionEnabled.value,
        pose_history: poseHistory,
      })
      result = typeof cameraResponse?.result === 'string' ? JSON.parse(cameraResponse.result) : cameraResponse?.result
    }
    if (result?.status === 'success') rememberPose(result)
    // Carry the question and the mode back with the answer. The backend stores
    // them alongside the observation, and without them every stored result
    // claimed `query: ""` and `mode: autonomous` no matter what was asked.
    await API.publishCameraResult(
      requestId,
      result || { status: 'error', message: '摄像头观察没有返回结果。', persisted: false },
      { query: request.query || '', localOnly: requestLocalOnly, mode: 'autonomous' },
    )
    lastObservationRequestId = requestId
    localStorage.setItem('miya-camera-observation-seen', requestId)
    localEvent.value = '弥娅自主观察完成 · 结果已返回'
  } catch (err: any) {
    localEvent.value = err?.message || '弥娅自主观察失败'
    if (currentRequestId && currentRequestId !== lastObservationRequestId) {
      try {
        await API.publishCameraResult(currentRequestId, {
          status: 'error',
          message: err?.message || '摄像头观察失败。',
          persisted: false,
        })
        lastObservationRequestId = currentRequestId
        localStorage.setItem('miya-camera-observation-seen', currentRequestId)
      } catch {
        // Leave it unseen so the next poll can retry publishing the failure.
      }
    }
  } finally {
    observationRequestInFlight = false
  }
}

function startRemoteCommandPolling() {
  if (remotePollTimer) return
  void syncRemoteCommand()
  remotePollTimer = setInterval(() => {
    void syncRemoteCommand()
    void syncObservationRequest()
    // Presence and activity are derived from camera ticks that already ran;
    // reading them here keeps the UI and the conversation layer on one state.
    void refreshPresence()
    void refreshActivity()
    void refreshAgentState()
    void refreshAgentVoice()
    void refreshVisionStream()
    void refreshCameraHealth()
    void refreshVisionSources()
    void refreshVisionBridge()
    // Sleeping cameras (a phone with its screen off) are re-probed on the
    // backend's own schedule, so this is cheap most of the time.
    void refreshCameraSources()
  }, 2500)
}

function stopRemoteCommandPolling() {
  if (remotePollTimer) clearInterval(remotePollTimer)
  remotePollTimer = null
}

function selectDevice(deviceId: string) {
  selectedDeviceId.value = deviceId
  localStorage.setItem('miya-camera-device', deviceId)
  if (stream.value) {
    const wasCompanion = mode.value === 'companion'
    stop()
    if (wasCompanion) void startCompanion()
  }
}

async function refreshBackendDevices() {
  return refreshCameraSources()
}

async function refreshPresence() {
  try {
    const response = await API.getVisionPresence()
    presence.value = response?.presence || null
  } catch {
    // Presence is an optional sense; a failure must not disturb the preview.
  }
  return presence.value
}

async function refreshActivity() {
  try {
    const response = await API.getVisionActivity()
    activity.value = response?.activity || null
  } catch {
    // Activity is derived; a failure must not disturb the preview.
  }
  return activity.value
}

/**
 * Which backend camera index the browser's preview is actually showing.
 *
 * The browser addresses cameras by `deviceId` and the backend by an OpenCV
 * index, and nothing makes the two orders agree. The index used to be whatever
 * number happened to be in localStorage, so switching the preview to the second
 * camera kept filing its frames under the first one's index - the backend then
 * believed the wrong physical device was working.
 *
 * The backend now reports DirectShow names, which Chromium's device labels are
 * derived from, so the two can be matched instead of assumed. When they cannot
 * be matched this returns `null` and the caller keeps its previous value rather
 * than inventing one.
 */
function matchBackendIndexForSelectedDevice(): number | null {
  const selected = devices.value.find(device => device.deviceId === selectedDeviceId.value)
  const label = String(selected?.label || '').trim()
  if (!label) return null
  const names = backendNames.value || {}
  const normalize = (text: string) => text.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, '')
  const wanted = normalize(label)
  if (!wanted) return null
  const matches: number[] = []
  for (const [index, name] of Object.entries(names)) {
    const candidate = normalize(String(name || ''))
    if (!candidate) continue
    // Fuzzy substring matches silently bind a selected camera to another
    // device (especially when Windows exposes generic or duplicate labels).
    if (candidate === wanted) matches.push(Number(index))
  }
  if (matches.length === 1) return matches[0]!
  if (matches.length > 1) backendDeviceMapping.value = 'ambiguous'
  return null
}

async function refreshCameraSources() {
  try {
    const response = await API.getCameraSources()
    backendDevices.value = Array.isArray(response?.devices) ? response.devices : []
    cameraSourcesMessage.value = response?.message || ''
    backendNames.value = response?.names || {}
    backendDeviceMapping.value = 'unmatched'
    // camelCase: the API layer converts responses, so `usable_indices` is never
    // the key that exists here. Reading the old name made this whole fallback
    // dead code and froze the reported index.
    const usable: number[] = Array.isArray(response?.usableIndices) ? response.usableIndices : []
    const sleeping: number[] = Array.isArray(response?.sleepingIndices) ? response.sleepingIndices : []
    const unopenable: number[] = Array.isArray(response?.unopenableIndices) ? response.unopenableIndices : []
    // Health is derived from this one response instead of being fetched from a
    // second endpoint that opened every camera on the machine every 2.5s and
    // could disagree with this list.
    cameraHealth.value = {
      devices: backendDevices.value,
      usableCount: usable.length,
      sleepingCount: sleeping.length,
      unopenableCount: unopenable.length,
      unknownCount: Array.isArray(response?.unknownIndices) ? response.unknownIndices.length : 0,
      count: backendDevices.value.length,
      defaultIndex: (response as any)?.defaultIndex ?? null,
      message: cameraSourcesMessage.value,
      names: backendNames.value,
    }
    const matched = matchBackendIndexForSelectedDevice()
    if (matched !== null) {
      backendDeviceMapping.value = 'matched'
      if (matched !== Number(backendDeviceIndex.value)) setBackendDeviceIndex(matched)
      return backendDevices.value
    }
    // Do not silently attribute browser frames to a different physical device.
    // Keep a sensible fallback only when no browser camera has been selected.
    if (!selectedDeviceId.value) {
      const current = Number(backendDeviceIndex.value)
      if (!usable.includes(current) && usable.length) setBackendDeviceIndex(usable[0]!)
      else if (!usable.length && sleeping.length && !sleeping.includes(current)) setBackendDeviceIndex(sleeping[0]!)
    }
  } catch (err: any) {
    cameraSourcesMessage.value = err?.message || '无法读取本机摄像头状态'
  }
  return backendDevices.value
}

function setBackendDeviceIndex(index: number) {
  backendDeviceIndex.value = Number(index)
  localStorage.setItem('miya-camera-backend-index', String(backendDeviceIndex.value))
}

function selectedBackendSourceId(): string | undefined {
  const selected = backendDevices.value.find(item => Number(item?.index) === Number(backendDeviceIndex.value))
  return selected?.sourceId ? String(selected.sourceId) : undefined
}

async function refreshAgentState() {
  try {
    const response = await API.getVisionAgent()
    agentState.value = response?.agent || null
    agentAgency.value = response?.agency || null
  } catch {
    // Autonomous watching is optional; never disturb the preview over it.
  }
  return agentState.value
}

async function refreshAgentVoice() {
  try {
    const response = await API.getVisionVoice()
    agentVoiceQueue.value = Array.isArray(response?.pending) ? response.pending : []
    agentVoice.value = response?.next || null
  } catch {
    // Reading her queue is best effort.
  }
  return agentVoice.value
}

/**
 * Take the next thing she wanted to say.
 *
 * Taking removes it from her queue, so it must only be called once the message
 * has actually been shown - not while merely polling.
 */
async function takeAgentVoice(): Promise<Record<string, any> | null> {
  try {
    const response = await API.takeVisionVoice('take')
    const message = response?.message || null
    await refreshAgentVoice()
    return message
  } catch {
    return null
  }
}

async function clearAgentVoice(): Promise<number> {
  try {
    const response = await API.takeVisionVoice('clear')
    await refreshAgentVoice()
    return Number(response?.cleared || 0)
  } catch {
    return 0
  }
}

async function refreshVisionStream() {
  try {
    const response = await API.getVisionStream()
    // Newest first: the panel reads top-down as "most recent".
    visionEvents.value = Array.isArray(response?.events) ? [...response.events].reverse() : []
    visionStreamStatus.value = response?.status || {}
    visionCadence.value = response?.cadence || {}
    thumbnailsEnabled.value = Boolean(response?.status?.thumbnailsEnabled)
  } catch {
    // The stream is a view onto her work; never disturb the preview over it.
  }
  return visionEvents.value
}

/** Fetch one round including its thumbnails; call only when it is expanded. */
async function loadVisionEvent(eventId: string): Promise<Record<string, any> | null> {
  try {
    const response = await API.getVisionEvent(eventId)
    return response?.event || null
  } catch {
    return null
  }
}

async function setThumbnailStorage(enabled: boolean) {
  try {
    const response = await API.setVisionThumbnails(enabled)
    visionStreamStatus.value = response?.status || visionStreamStatus.value
    thumbnailsEnabled.value = Boolean(response?.status?.thumbnailsEnabled)
    await refreshVisionStream()
  } catch (err: any) {
    error.value = err?.message || '无法切换缩略图存储'
  }
  return thumbnailsEnabled.value
}

/**
 * Camera device health.
 *
 * A read of the value `refreshCameraSources` already computed, not a second
 * network call: a dedicated health endpoint would have to open every camera on
 * the machine to answer, and it ran on the 2.5-second poll.
 */
function refreshCameraHealth() {
  return cameraHealth.value
}

/** Which side owns which camera, and whether a frame is currently held. */
async function refreshVisionSources() {
  try {
    const payload = await API.getVisionSources()
    if (payload?.success) {
      // camelCase throughout: see the note on getCameraSources. Reading the
      // snake_case keys here kept "Miya's own view" and the owner labels off
      // the panel no matter how healthy the backend was.
      visionSources.value = {
        sources: payload.sources || {},
        names: payload.names || {},
        browserFrames: payload.browserFrames || [],
        browserOwned: payload.browserOwned || [],
        backendOwned: payload.backendOwned || [],
        readersRunning: payload.readersRunning || [],
      }
      if (payload.names && Object.keys(payload.names).length) {
        backendNames.value = { ...backendNames.value, ...payload.names }
      }
    }
  } catch {
    // Same: informational only.
  }
  return visionSources.value
}

/** Whether her seeing can actually turn into her speaking. */
async function refreshVisionBridge() {
  try {
    const payload = await API.getVisionBridge()
    visionBridge.value = payload?.bridge || null
  } catch {
    // Informational only.
  }
  return visionBridge.value
}

async function setWatching(action: 'start' | 'stop') {
  try {
    const response = await API.setVisionAgent(action)
    agentState.value = response?.agent || null
    await refreshAgentState()
  } catch (err: any) {
    error.value = err?.message || '无法切换弥娅的自主观察'
  }
  return agentState.value
}

async function setFaceRecognition(value: boolean) {
  faceRecognitionEnabled.value = value
  localStorage.setItem('miya-face-recognition', String(value))
  await API.setCameraControl({
    mode: mode.value,
    identity_recognition: value,
  }).catch(() => {})
}

function setEmotionInference(value: boolean) {
  emotionInferenceEnabled.value = value
  localStorage.setItem('miya-emotion-inference', String(value))
}

function setActionRecognition(value: boolean) {
  actionRecognitionEnabled.value = value
  localStorage.setItem('miya-action-recognition', String(value))
}

function setLocalOnly(value: boolean) {
  localOnly.value = value
  localStorage.setItem('miya-camera-local-only', String(value))
}

export function useCameraVision() {
  return {
    mode, status, error, devices, selectedDeviceId, stream, lastObservation, localEvent,
    faceRecognitionEnabled, emotionInferenceEnabled, actionRecognitionEnabled,
    alwaysOn, cameraPolicy,
    localOnly, localCapabilities, backendDevices, cameraSourcesMessage, presence, activity, backendDeviceIndex, backendDeviceMapping, backendNames,
    streams, activeBrowserSources, visionControl, startupPolicy,
    agentState, agentAgency, agentVoice, agentVoiceQueue,
    visionEvents, visionStreamStatus, visionCadence, thumbnailsEnabled, cameraHealth, visionSources, visionBridge,
    listDevices, refreshCapabilities, attachPreview, open, stop, lookAtMe, lookBoth, startCompanion, selectDevice,
    setFaceRecognition, setEmotionInference, setActionRecognition, setLocalOnly, setAlwaysOn, enableAlwaysOn, setCameraPolicy, enrollIdentity, listIdentities, deleteIdentity,
    setVisionControl, setStartupPolicy,
    syncRemoteCommand, startRemoteCommandPolling, stopRemoteCommandPolling, startAlwaysOnCompanion,
    refreshBackendDevices, refreshPresence, refreshActivity, refreshCameraSources, setBackendDeviceIndex,
    refreshAgentState, setWatching, refreshAgentVoice, takeAgentVoice, clearAgentVoice,
    refreshVisionStream, loadVisionEvent, setThumbnailStorage, refreshCameraHealth, refreshVisionSources, refreshVisionBridge,
  }
}
