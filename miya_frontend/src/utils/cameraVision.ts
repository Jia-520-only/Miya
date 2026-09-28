import { ref, shallowRef } from 'vue'
import API from '@/api/core'

export type CameraMode = 'off' | 'snapshot' | 'companion'

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
const lastObservation = ref('')
const localEvent = ref('')
const localEventCode = ref<'stable' | 'light_motion' | 'clear_motion' | 'scene_change' | 'long_still'>('stable')
const motionScore = ref(0)
const localAction = ref('')
const localActionConfidence = ref(0)
const faceRecognitionEnabled = ref(localStorage.getItem('miya-face-recognition') === 'true')
const emotionInferenceEnabled = ref(localStorage.getItem('miya-emotion-inference') === 'true')
const actionRecognitionEnabled = ref(localStorage.getItem('miya-action-recognition') !== 'false')
const localOnly = ref(localStorage.getItem('miya-camera-local-only') === 'true')
const localCapabilities = ref<LocalCameraCapabilities>({
  status: 'unknown',
  message: '正在检查本地视觉模型…',
})

let timer: ReturnType<typeof setInterval> | null = null
let lastSignature = ''
let lastRemoteAnalysis = 0
let analysisInFlight = false
let poseHistory: Array<{ keypoints: Array<{ x: number, y: number, confidence: number }> }> = []
let previewVideo: HTMLVideoElement | null = null
let mediaVideo: HTMLVideoElement | null = null
let deviceChangeHandler: (() => void) | null = null
let remotePollTimer: ReturnType<typeof setInterval> | null = null
let remoteCommandInFlight = false
let observationRequestInFlight = false
let lastRemoteCommandId = localStorage.getItem('miya-camera-command-seen') || ''
let lastObservationRequestId = localStorage.getItem('miya-camera-observation-seen') || ''
let stableSince = 0
let lastPublishedEvent = ''
const LONG_STILL_MS = 10 * 60 * 1000

function handleStreamEnded() {
  if (!stream.value) return
  stop('摄像头已断开，请检查设备或权限')
}

function getMediaVideo() {
  if (!mediaVideo) {
    mediaVideo = document.createElement('video')
    mediaVideo.autoplay = true
    mediaVideo.muted = true
    mediaVideo.playsInline = true
  }
  return mediaVideo
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

async function attachStreamToVideos(activeStream: MediaStream) {
  const source = getMediaVideo()
  source.srcObject = activeStream
  await source.play().catch(() => {})
  if (previewVideo) {
    previewVideo.srcObject = activeStream
    await previewVideo.play().catch(() => {})
  }
}

async function open(modeToUse: Exclude<CameraMode, 'off'>) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('当前环境不支持摄像头访问')
  }

  if (stream.value) {
    mode.value = modeToUse
    status.value = modeToUse === 'companion' ? '陪伴视觉运行中' : '准备看你'
    publishState()
    await attachStreamToVideos(stream.value)
    return
  }

  error.value = ''
  status.value = '正在请求摄像头权限'
  publishState()
  const constraints: MediaStreamConstraints = {
    audio: false,
    video: selectedDeviceId.value && devices.value.some(device => device.deviceId === selectedDeviceId.value)
      ? { deviceId: { exact: selectedDeviceId.value }, width: { ideal: 640 }, height: { ideal: 480 } }
      : { width: { ideal: 640 }, height: { ideal: 480 } },
  }

  try {
    stream.value = await navigator.mediaDevices.getUserMedia(constraints)
    stream.value.getTracks().forEach(track => {
      track.addEventListener('ended', handleStreamEnded, { once: true })
    })
    if (!deviceChangeHandler && navigator.mediaDevices.addEventListener) {
      deviceChangeHandler = () => { void listDevices() }
      navigator.mediaDevices.addEventListener('devicechange', deviceChangeHandler)
    }
    mode.value = modeToUse
    status.value = modeToUse === 'companion' ? '陪伴视觉运行中' : '准备看你'
    await attachStreamToVideos(stream.value)
    await listDevices()
    publishState()
  } catch (err: any) {
    mode.value = 'off'
    stream.value = null
    status.value = '摄像头未启用'
    error.value = err?.name === 'NotAllowedError' ? '摄像头权限被拒绝' : (err?.message || '摄像头启动失败')
    publishState()
    throw err
  }
}

function stop(reason = '') {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  stream.value?.getTracks().forEach(track => track.stop())
  stream.value = null
  if (deviceChangeHandler && navigator.mediaDevices?.removeEventListener) {
    navigator.mediaDevices.removeEventListener('devicechange', deviceChangeHandler)
    deviceChangeHandler = null
  }
  if (mediaVideo) mediaVideo.srcObject = null
  if (previewVideo) previewVideo.srcObject = null
  mode.value = 'off'
  status.value = reason || '摄像头关闭'
  error.value = reason
  localEvent.value = ''
  localEventCode.value = 'stable'
  stableSince = 0
  lastPublishedEvent = ''
  motionScore.value = 0
  localAction.value = ''
  localActionConfidence.value = 0
  poseHistory = []
  lastSignature = ''
  analysisInFlight = false
  publishState()
}

function captureFrame() {
  const source = getMediaVideo()
  if (!stream.value || source.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
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
  const source = getMediaVideo()
  for (let index = 0; index < 25; index += 1) {
    if (source.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && source.videoWidth > 0) return
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('摄像头画面还没有准备好')
}

function getSignature() {
  const source = getMediaVideo()
  if (!stream.value || source.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return ''
  const canvas = document.createElement('canvas')
  canvas.width = 32
  canvas.height = 24
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) return ''
  context.drawImage(source, 0, 0, 32, 24)
  const pixels = context.getImageData(0, 0, 32, 24).data
  let signature = ''
  for (let index = 0; index < pixels.length; index += 16) {
    signature += Math.round((pixels[index]! + pixels[index + 1]! + pixels[index + 2]!) / 3 / 16).toString(16)
  }
  return signature
}

function measureMotion(signature: string) {
  if (!signature || !lastSignature) {
    lastSignature = signature
    return 0
  }
  let difference = 0
  const length = Math.min(signature.length, lastSignature.length)
  for (let index = 0; index < length; index += 1) {
    difference += Math.abs(parseInt(signature[index]!, 16) - parseInt(lastSignature[index]!, 16))
  }
  lastSignature = signature
  return difference / Math.max(length, 1)
}

function classifyMotion(score: number): typeof localEventCode.value {
  if (score >= 3.2) return 'scene_change'
  if (score >= 1.8) return 'clear_motion'
  if (score >= 0.65) return 'light_motion'
  return 'stable'
}

async function publishLocalEvent(kind: string, summary: string, confidence = 1) {
  const key = `${kind}:${summary}`
  if (key === lastPublishedEvent) return
  lastPublishedEvent = key
  try {
    await API.mcpCall('screen_vision', 'camera_event', {
      event: { kind, summary, confidence, mode: 'companion', status: 'success' },
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
  const action = data?.observations?.[0]?.action
  if (action?.label) {
    localAction.value = action.label
    localActionConfidence.value = Number(action.confidence || 0)
  }
}

async function analyzeLocalAction() {
  if (!stream.value || !actionRecognitionEnabled.value || !localPoseAvailable()) return null
  await waitForMediaFrame()
  const response = await API.mcpCall('screen_vision', 'camera_analyze_local', {
    image_data: captureFrame(),
    identity: false,
    emotion: false,
    pose: true,
    pose_history: poseHistory,
  })
  const raw = response?.result
  const data = typeof raw === 'string' ? JSON.parse(raw) : raw
  if (data?.status !== 'success') return null
  rememberPose(data)
  return data?.observations?.[0]?.action || null
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
  const response = await API.mcpCall('screen_vision', 'camera_enroll_identity', {
    image_data: captureFrame(),
    name,
  })
  const raw = response?.result
  const data = typeof raw === 'string' ? JSON.parse(raw) : raw
  if (data?.status !== 'success') throw new Error(data?.message || '身份登记失败')
  await refreshCapabilities()
  return data
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

async function companionTick() {
  if (mode.value !== 'companion' || !stream.value || analysisInFlight) return
  const signature = getSignature()
  const score = measureMotion(signature)
  motionScore.value = Number(score.toFixed(2))
  localEventCode.value = classifyMotion(score)
  localStorage.setItem('miya-camera-heartbeat', String(Date.now()))
  if (localEventCode.value === 'stable') {
    if (!stableSince) stableSince = Date.now()
    if (Date.now() - stableSince >= LONG_STILL_MS) {
      localEventCode.value = 'long_still'
      localEvent.value = '本地观察中 · 长时间静止'
      await publishLocalEvent('long_still', '画面长时间稳定，可能一直保持静止', 0.78)
    } else {
      localEvent.value = '本地观察中 · 画面稳定'
    }
    return
  }
  stableSince = 0
  const eventText = {
    light_motion: '检测到轻微移动 · 仅本地判断',
    clear_motion: '检测到明显动作 · 仅本地判断',
    scene_change: '检测到画面突变 · 仅本地判断',
    stable: '本地观察中 · 画面稳定',
    long_still: '本地观察中 · 长时间静止',
  }[localEventCode.value]
  localEvent.value = `${eventText} · ${motionScore.value}`
  if (localEventCode.value === 'scene_change') {
    await publishLocalEvent('scene_change', '摄像头画面发生明显变化', 0.82)
  }
  const now = Date.now()
  if (localEventCode.value === 'light_motion') return

  if (actionRecognitionEnabled.value && localPoseAvailable()) {
    analysisInFlight = true
    try {
      const action = await analyzeLocalAction()
      if (action?.label && action.kind !== 'unknown' && action.kind !== 'still') {
        const confidence = Number(action.confidence || 0)
        localEvent.value = `本地动作 · ${action.label} · ${confidence.toFixed(2)}`
        await publishLocalEvent(action.kind || 'motion', action.label, confidence)
        // A confident local label is enough for the companion loop. Keep the
        // remote vision fallback for uncertain or scene-level changes.
        if (localOnly.value || confidence >= 0.68 || now - lastRemoteAnalysis < 90_000) {
          analysisInFlight = false
          return
        }
      } else if (localOnly.value) {
        localEvent.value = '本地动作识别中 · 暂未确认具体动作'
        analysisInFlight = false
        return
      }
    } catch (err: any) {
      if (localOnly.value) {
        localEvent.value = err?.message || '本地动作识别暂不可用'
        analysisInFlight = false
        return
      }
      analysisInFlight = false
    }
    // Local inference is complete; the optional remote fallback below owns
    // its own in-flight lock.
    analysisInFlight = false
  } else if (localOnly.value) {
    localEvent.value = '本地动作模型未就绪 · 未发送云端分析'
    return
  }

  if (now - lastRemoteAnalysis < 90_000) return
  lastRemoteAnalysis = now
  analysisInFlight = true
  try {
    status.value = '发现变化，正在看你'
    publishState()
    await lookAtMe('请简短描述我刚才的姿态或动作变化，只说能从画面确认的内容。')
    localEvent.value = '刚刚看过 · 等待下一次变化'
  } catch (err: any) {
    error.value = err?.message || '陪伴视觉分析失败'
    status.value = '陪伴视觉运行中'
    publishState()
  } finally {
    analysisInFlight = false
  }
}

async function startCompanion() {
  if (localOnly.value && !localOnlyReady()) {
    throw new Error(localCapabilities.value.message)
  }
  await open('companion')
  if (!timer) timer = setInterval(() => { void companionTick() }, 15_000)
  void companionTick()
}

async function syncRemoteCommand() {
  if (remoteCommandInFlight) return
  remoteCommandInFlight = true
  try {
    const response = await API.getCameraControl()
    const state = response?.state
    const requestId = String(state?.request_id || '')
    if (!requestId || requestId === lastRemoteCommandId) return
    lastRemoteCommandId = requestId
    localStorage.setItem('miya-camera-command-seen', requestId)
    if (state.mode === 'off') {
      if (mode.value !== 'off') stop('已按命令关闭摄像头')
      return
    }
    localOnly.value = Boolean(state.local_only)
    actionRecognitionEnabled.value = state.action_recognition !== false
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
    const requestId = String(request?.request_id || '')
    if (!request || !requestId || requestId === lastObservationRequestId) return
    if (mode.value !== 'companion' || !stream.value) return
    currentRequestId = requestId
    const requestLocalOnly = request.local_only === undefined || request.local_only === null
      ? localOnly.value
      : typeof request.local_only === 'string'
        ? ['true', '1', 'yes', 'on'].includes(request.local_only.trim().toLowerCase())
        : Boolean(request.local_only)
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
    await API.publishCameraResult(requestId, result || { status: 'error', message: '摄像头观察没有返回结果。', persisted: false })
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
  remotePollTimer = setInterval(() => { void syncRemoteCommand(); void syncObservationRequest() }, 2500)
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

function setFaceRecognition(value: boolean) {
  faceRecognitionEnabled.value = value
  localStorage.setItem('miya-face-recognition', String(value))
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
  startRemoteCommandPolling()
  return {
    mode, status, error, devices, selectedDeviceId, stream, lastObservation, localEvent, localEventCode, motionScore,
    faceRecognitionEnabled, emotionInferenceEnabled, actionRecognitionEnabled, localAction, localActionConfidence,
    localOnly, localCapabilities,
    listDevices, refreshCapabilities, attachPreview, open, stop, lookAtMe, lookBoth, startCompanion, selectDevice,
    setFaceRecognition, setEmotionInference, setActionRecognition, setLocalOnly, enrollIdentity, listIdentities, deleteIdentity,
    syncRemoteCommand, startRemoteCommandPolling, stopRemoteCommandPolling,
  }
}
