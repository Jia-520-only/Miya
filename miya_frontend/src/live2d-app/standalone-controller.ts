import type { Live2DModel } from 'pixi-live2d-display/cubism4'
import * as PIXI from 'pixi.js'

interface Keyframe { t: number, params: Record<string, number> }
interface StateConfig { loop: boolean, duration?: number, keyframes?: Keyframe[], params?: Record<string, number> }
interface ActionConfig { duration: number, repeat: number, keyframes: Keyframe[] }
export interface ActionsData { states: Record<string, StateConfig>, actions: Record<string, ActionConfig> }
export interface ExpressionDef {
  name: string
  fadeInTime: number
  params: Array<{ Id: string, Value: number, Blend: 'Add' | 'Multiply' | 'Overwrite' }>
}
type Live2dState = 'idle' | 'thinking' | 'talking'
type SemanticParam = 'angleX' | 'angleY' | 'angleZ' | 'bodyAngleX' | 'eyeX' | 'eyeY' | 'eyeLOpen' | 'eyeROpen' | 'browLY' | 'browRY' | 'mouthOpen' | 'mouthForm' | 'breath'

const PARAM_ALIASES: Record<SemanticParam, string[]> = {
  angleX: ['ParamAngleX', 'AngleX', 'HeadAngleX'],
  angleY: ['ParamAngleY', 'AngleY', 'HeadAngleY'],
  angleZ: ['ParamAngleZ', 'AngleZ', 'HeadAngleZ'],
  bodyAngleX: ['ParamBodyAngleX', 'BodyAngleX'],
  eyeX: ['ParamEyeBallX', 'EyeBallX', 'EyeX'],
  eyeY: ['ParamEyeBallY', 'EyeBallY', 'EyeY'],
  eyeLOpen: ['ParamEyeLOpen', 'EyeLOpen', 'EyeOpenL'],
  eyeROpen: ['ParamEyeROpen', 'EyeROpen', 'EyeOpenR'],
  browLY: ['ParamBrowLY', 'BrowLY', 'BrowLForm'],
  browRY: ['ParamBrowRY', 'BrowRY', 'BrowRForm'],
  mouthOpen: ['ParamMouthOpenY', 'MouthOpenY', 'MouthOpen', 'JawOpen'],
  mouthForm: ['ParamMouthForm', 'MouthForm', 'MouthSmile'],
  breath: ['ParamBreath', 'Breath'],
}

const DEFAULT_ACTIONS: ActionsData = {
  states: {
    idle: { loop: true, duration: 4000, keyframes: [{ t: 0, params: { ParamBodyAngleX: -1 } }, { t: 0.5, params: { ParamBodyAngleX: 1 } }, { t: 1, params: { ParamBodyAngleX: -1 } }] },
    thinking: { loop: true, duration: 3000, keyframes: [{ t: 0, params: { ParamAngleZ: 0 } }, { t: 0.5, params: { ParamAngleZ: 4 } }, { t: 1, params: { ParamAngleZ: 0 } }] },
    talking: { loop: true, duration: 1600, keyframes: [{ t: 0, params: { ParamBodyAngleX: -2 } }, { t: 0.5, params: { ParamBodyAngleX: 2 } }, { t: 1, params: { ParamBodyAngleX: -2 } }] },
  },
  actions: {
    nod: { duration: 800, repeat: 1, keyframes: [{ t: 0, params: { ParamAngleY: 0 } }, { t: 0.5, params: { ParamAngleY: -12 } }, { t: 1, params: { ParamAngleY: 0 } }] },
    shake: { duration: 650, repeat: 2, keyframes: [{ t: 0, params: { ParamAngleX: 0 } }, { t: 0.25, params: { ParamAngleX: 12 } }, { t: 0.75, params: { ParamAngleX: -12 } }, { t: 1, params: { ParamAngleX: 0 } }] },
  },
}

let model: Live2DModel | null = null
let actionsData: ActionsData = DEFAULT_ACTIONS
let currentStateName: Live2dState = 'idle'
let stateStartTime = 0
let lastTickTime = 0
let targetMouthParams: Record<string, number> = {}
let mouthParams: Record<string, number> = {}
let activeAction: { config: ActionConfig, startTime: number } | null = null
let trackingEnabled = false
let trackingDesiredX = 0
let trackingDesiredY = 0
let trackingSmoothedX = 0
let trackingSmoothedY = 0
let trackingWarmupStartedAt = 0
let smallMotionX = 0
let smallMotionY = 0
let smallMotionZ = 0
let smallMotionBody = 0
let smallMotionTargetX = 0
let smallMotionTargetY = 0
let smallMotionTargetZ = 0
let smallMotionTargetBody = 0
let nextSmallMotionAt = 0
let lastSmallMotionAt = 0
let restoreNativeUpdateFocus: (() => void) | null = null
const expressionDefs = new Map<string, ExpressionDef>()
let currentExpression: ExpressionDef | null = null
let expressionValues: Record<string, number> = {}
let fallbackEmotion = 'neutral'
let semanticParams: Partial<Record<SemanticParam, string>> = {}
let nextBlinkAt = 0
let blinkStartedAt = -1
let nextGazeAt = 0
let gazeTargetX = 0
let gazeTargetY = 0
let gazeX = 0
let gazeY = 0
let lastMouthUpdateAt = -Infinity

const live2dControl = {
  setEmotion(emotion: string) { selectEmotion(emotion) },
  setState(state: string) {
    if (state !== 'idle' && state !== 'thinking' && state !== 'talking') return
    currentStateName = state
    stateStartTime = performance.now()
  },
  setMouth(params: Record<string, number>) {
    targetMouthParams = { ...params }
    lastMouthUpdateAt = performance.now()
  },
  triggerAction(action: string) {
    const config = actionsData.actions[action]
    if (config?.keyframes?.length) activeAction = { config, startTime: performance.now() }
    selectEmotion(action)
  },
  setTracking(enabled: boolean) {
    trackingEnabled = enabled
    if (!enabled) {
      trackingDesiredX = 0
      trackingDesiredY = 0
    }
  },
  setTrackingTarget(x: number, y: number, active = true) {
    trackingDesiredX = trackingEnabled && active ? Math.max(-1, Math.min(1, Number(x) || 0)) * 0.86 : 0
    trackingDesiredY = trackingEnabled && active ? Math.max(-1, Math.min(1, Number(y) || 0)) * 0.74 : 0
  },
}

;(window as unknown as { __live2dControl: typeof live2dControl }).__live2dControl = live2dControl

export async function initStandaloneController(rawModel: Live2DModel, suppliedActions: ActionsData | null, expressions: ExpressionDef[]): Promise<void> {
  PIXI.Ticker.shared.remove(tickStandalone)
  model = rawModel
  semanticParams = detectSemanticParams(rawModel)
  actionsData = suppliedActions ?? DEFAULT_ACTIONS
  expressionDefs.clear()
  for (const expression of expressions) expressionDefs.set(expression.name.toLowerCase(), expression)
  currentStateName = 'idle'
  stateStartTime = performance.now()
  lastTickTime = stateStartTime
  activeAction = null
  trackingDesiredX = 0
  trackingDesiredY = 0
  trackingSmoothedX = 0
  trackingSmoothedY = 0
  trackingWarmupStartedAt = stateStartTime
  setNativeFocus(0, 0, true)
  resetSmallMotion(stateStartTime)
  installNativeSmallMotion(rawModel)
  scheduleNextBlink(stateStartTime)
  scheduleNextGaze(stateStartTime)
  PIXI.Ticker.shared.add(tickStandalone)
  console.log('[Live2D Standalone] Controller ready:', { expressions: [...expressionDefs.keys()], customActions: !!suppliedActions, universalParams: semanticParams })
}

export function destroyStandaloneController(): void {
  PIXI.Ticker.shared.remove(tickStandalone)
  restoreNativeUpdateFocus?.()
  restoreNativeUpdateFocus = null
  model = null
  expressionDefs.clear()
  currentExpression = null
  expressionValues = {}
  activeAction = null
  mouthParams = {}
  targetMouthParams = {}
  lastMouthUpdateAt = -Infinity
  semanticParams = {}
}

function tickStandalone(): void {
  if (!model) return
  const now = performance.now()
  const dt = Math.min(100, Math.max(0, now - lastTickTime))
  lastTickTime = now
  updateNativeFocus(dt)
  const merged = { ...computeAutonomousBehavior(now, dt), ...computeState(now), ...computeAction(now) }

  for (const [key, target] of Object.entries(targetMouthParams)) {
    mouthParams[key] = lerp(mouthParams[key] ?? 0, target, smoothFactor(55, dt))
    const resolved = resolveIncomingParam(key)
    if (resolved) merged[resolved] = mouthParams[key]!
  }
  if (currentStateName === 'talking' && now - lastMouthUpdateAt > 350) {
    const syllable = Math.max(0, Math.sin(now / 85))
    const phrase = Math.sin(now / 430) > -0.72 ? 1 : 0.08
    assignSemantic(merged, 'mouthOpen', (0.12 + syllable * 0.58) * phrase)
  }
  for (const [key, value] of Object.entries(computeExpression(dt))) merged[key] = value
  for (const [id, value] of Object.entries(merged)) setParam(id, value)
}

function computeState(now: number): Record<string, number> {
  const config = actionsData.states[currentStateName]
  if (!config) return {}
  if (config.params) return remapParams(config.params)
  if (!config.keyframes?.length || !config.duration) return {}
  const elapsed = now - stateStartTime
  const progress = config.loop ? (elapsed % config.duration) / config.duration : Math.min(1, elapsed / config.duration)
  return remapParams(interpolate(config.keyframes, progress))
}

function computeAction(now: number): Record<string, number> {
  if (!activeAction) return {}
  const { config, startTime } = activeAction
  if (!config.keyframes.length || config.duration <= 0) { activeAction = null; return {} }
  const elapsed = now - startTime
  const repeats = Math.max(1, config.repeat || 1)
  if (elapsed >= config.duration * repeats) {
    activeAction = null
    return remapParams(config.keyframes[config.keyframes.length - 1]!.params)
  }
  return remapParams(interpolate(config.keyframes, (elapsed % config.duration) / config.duration))
}

function interpolate(frames: Keyframe[], progress: number): Record<string, number> {
  let left = frames[0]!
  let right = frames[frames.length - 1]!
  for (let i = 0; i < frames.length - 1; i++) {
    if (progress >= frames[i]!.t && progress <= frames[i + 1]!.t) { left = frames[i]!; right = frames[i + 1]!; break }
  }
  const ratio = right.t === left.t ? 0 : (progress - left.t) / (right.t - left.t)
  const result: Record<string, number> = {}
  for (const key of new Set([...Object.keys(left.params), ...Object.keys(right.params)])) {
    result[key] = lerp(left.params[key] ?? 0, right.params[key] ?? left.params[key] ?? 0, ratio)
  }
  return result
}

function detectSemanticParams(rawModel: Live2DModel): Partial<Record<SemanticParam, string>> {
  const core = rawModel.internalModel.coreModel as any
  const available = new Map<string, string>()
  try {
    const collection = core?.getParameterIds?.() ?? core?.getModel?.()?.parameters?.ids
    const ids: unknown[] = Array.isArray(collection)
      ? collection
      : collection?.getSize && collection?.at
        ? Array.from({ length: collection.getSize() }, (_, index) => collection.at(index))
        : collection && Symbol.iterator in Object(collection)
          ? Array.from(collection as Iterable<unknown>)
          : []
    for (const rawId of ids) {
      const id = typeof rawId === 'string' ? rawId : (rawId as any)?.getString?.() ?? String(rawId)
      if (id && id !== '[object Object]') available.set(id.toLowerCase(), id)
    }
  }
  catch { /* parameter discovery is optional */ }

  const result: Partial<Record<SemanticParam, string>> = {}
  for (const [semantic, aliases] of Object.entries(PARAM_ALIASES) as Array<[SemanticParam, string[]]>) {
    const exact = aliases.map(alias => available.get(alias.toLowerCase())).find(Boolean)
    const normalizedAliases = aliases.map(normalizeParameterId)
    const fuzzy = [...available.values()].find((id) => {
      const normalizedId = normalizeParameterId(id)
      return normalizedAliases.some(alias => normalizedId === alias || normalizedId.endsWith(alias) || alias.endsWith(normalizedId))
    })
    // If discovery itself is unavailable, retain the conventional Cubism ID;
    // otherwise never invent a parameter that the selected model lacks.
    result[semantic] = exact ?? fuzzy ?? (available.size === 0 ? aliases[0] : undefined)
  }
  return result
}

function normalizeParameterId(id: string): string {
  return id.toLowerCase().replace(/^param(?:eter)?/, '').replace(/[^\p{L}\p{N}]/gu, '')
}

function resolveIncomingParam(id: string): string | null {
  for (const [semantic, aliases] of Object.entries(PARAM_ALIASES) as Array<[SemanticParam, string[]]>) {
    if (aliases.some(alias => alias.toLowerCase() === id.toLowerCase())) return semanticParams[semantic] ?? id
  }
  return id
}

function remapParams(params: Record<string, number>): Record<string, number> {
  const result: Record<string, number> = {}
  for (const [id, value] of Object.entries(params)) {
    const resolved = resolveIncomingParam(id)
    if (resolved) result[resolved] = value
  }
  return result
}

function assignSemantic(target: Record<string, number>, semantic: SemanticParam, value: number): void {
  const id = semanticParams[semantic]
  if (id) target[id] = value
}

function scheduleNextBlink(now: number): void {
  nextBlinkAt = now + 2200 + Math.random() * 4200
}

function scheduleNextGaze(now: number): void {
  nextGazeAt = now + 2500 + Math.random() * 4500
}

function computeAutonomousBehavior(now: number, dt: number): Record<string, number> {
  const result: Record<string, number> = {}

  if (now >= nextGazeAt) {
    gazeTargetX = (Math.random() * 2 - 1) * 0.65
    gazeTargetY = (Math.random() * 2 - 1) * 0.4
    scheduleNextGaze(now)
  }
  const gazeSmooth = smoothFactor(240, dt)
  gazeX = lerp(gazeX, gazeTargetX, gazeSmooth)
  gazeY = lerp(gazeY, gazeTargetY, gazeSmooth)
  assignSemantic(result, 'eyeX', gazeX)
  assignSemantic(result, 'eyeY', gazeY)

  if (blinkStartedAt < 0 && now >= nextBlinkAt) blinkStartedAt = now
  let eyeOpen = 1
  if (blinkStartedAt >= 0) {
    const progress = (now - blinkStartedAt) / 180
    if (progress >= 1) {
      blinkStartedAt = -1
      scheduleNextBlink(now)
    }
    else {
      eyeOpen = 1 - Math.sin(progress * Math.PI) ** 1.5
    }
  }
  assignSemantic(result, 'eyeLOpen', eyeOpen)
  assignSemantic(result, 'eyeROpen', eyeOpen)
  return result
}

function installNativeSmallMotion(rawModel: Live2DModel): void {
  restoreNativeUpdateFocus?.()
  const internal = rawModel.internalModel as any
  const original = internal.updateFocus
  if (typeof original !== 'function') return
  internal.updateFocus = function (...args: unknown[]) {
    original.apply(this, args)
    applyNativeSmallMotion()
  }
  restoreNativeUpdateFocus = () => { internal.updateFocus = original }
}

function resetSmallMotion(now: number): void {
  smallMotionX = smallMotionY = smallMotionZ = smallMotionBody = 0
  smallMotionTargetX = smallMotionTargetY = smallMotionTargetZ = smallMotionTargetBody = 0
  lastSmallMotionAt = now
  nextSmallMotionAt = now + 900
}

function applyNativeSmallMotion(): void {
  const currentModel = model
  if (!currentModel) return
  const now = performance.now()
  const warmup = trackingWarmupProgress(now)
  const dt = Math.min(100, Math.max(0, now - lastSmallMotionAt))
  lastSmallMotionAt = now
  if (now >= nextSmallMotionAt) {
    const energy = currentStateName === 'talking' ? 1.15 : currentStateName === 'thinking' ? 0.72 : 1
    smallMotionTargetX = (Math.random() * 2 - 1) * 1.35 * energy
    smallMotionTargetY = (Math.random() * 2 - 1) * 0.75 * energy
    smallMotionTargetZ = (Math.random() * 2 - 1) * 0.65 * energy
    smallMotionTargetBody = (Math.random() * 2 - 1) * 0.48 * energy
    nextSmallMotionAt = now + 1800 + Math.random() * 3200
  }
  const follow = smoothFactor(780, dt)
  smallMotionX = lerp(smallMotionX, smallMotionTargetX, follow)
  smallMotionY = lerp(smallMotionY, smallMotionTargetY, follow)
  smallMotionZ = lerp(smallMotionZ, smallMotionTargetZ, follow)
  smallMotionBody = lerp(smallMotionBody, smallMotionTargetBody, follow)

  try {
    const internal = currentModel.internalModel as any
    const core = internal.coreModel
    // Same default parameter set as ViewerEX Small Motions. This wrapper runs
    // immediately after native Focus and before Physics without polluting the
    // motion manager's saved base parameters.
    core.addParameterValueById(internal.idParamAngleX, smallMotionX * warmup)
    core.addParameterValueById(internal.idParamAngleY, smallMotionY * warmup)
    core.addParameterValueById(internal.idParamAngleZ, smallMotionZ * warmup)
    core.addParameterValueById(internal.idParamBodyAngleX, smallMotionBody * warmup)
  }
  catch { /* selected model is being replaced */ }
}

function updateNativeFocus(dt: number): void {
  // ViewerEX exposes this as Smoothing Time. A non-oscillating exponential
  // filter prevents sudden cursor jumps from over-exciting soft model physics.
  // Cubism recommends stabilizing physics before applying non-default input;
  // this older runtime has no stabilization(), so keep the first frames neutral
  // and smoothly restore the livelier range once normal evaluation has settled.
  const warmup = trackingWarmupProgress(performance.now())
  const smoothingTime = trackingEnabled ? lerp(150, 65, warmup) : 180
  const follow = smoothFactor(smoothingTime, dt)
  trackingSmoothedX = lerp(trackingSmoothedX, trackingDesiredX * warmup, follow)
  trackingSmoothedY = lerp(trackingSmoothedY, trackingDesiredY * warmup, follow)
  setNativeFocus(trackingSmoothedX, trackingSmoothedY)
}

function trackingWarmupProgress(now: number): number {
  const progress = Math.max(0, Math.min(1, (now - trackingWarmupStartedAt - 450) / 1450))
  return progress * progress * (3 - 2 * progress)
}

function setNativeFocus(x: number, y: number, instant = false): void {
  try {
    // Use the runtime's controller instead of writing parameters after the
    // update. It runs before physics and drives ViewerEX's six defaults:
    // Angle X/Y/Z, EyeBall X/Y and BodyAngle X.
    ;(model?.internalModel as any)?.focusController?.focus(x, y, instant)
  }
  catch { /* model is being switched or destroyed */ }
}

function selectEmotion(emotion: string): void {
  const aliases: Record<string, string[]> = {
    happy: ['happy', 'enjoy', 'smile', 'positive'], sad: ['sad', 'negative'],
    angry: ['angry', 'anger'], surprise: ['surprise', 'surprised'], neutral: ['normal', 'neutral', 'idle'],
  }
  fallbackEmotion = emotion.toLowerCase()
  currentExpression = (aliases[fallbackEmotion] ?? [fallbackEmotion]).map(name => expressionDefs.get(name)).find(Boolean) ?? null
}

function computeExpression(dt: number): Record<string, number> {
  if (!currentExpression) return computeFallbackExpression(dt)
  const targets = new Map(currentExpression?.params.map(param => [param.Id, param]) ?? [])
  const result: Record<string, number> = {}
  for (const id of new Set([...Object.keys(expressionValues), ...targets.keys()])) {
    const target = targets.get(id)
    const next = lerp(expressionValues[id] ?? 0, target?.Value ?? 0, smoothFactor(Math.max(80, (currentExpression?.fadeInTime ?? 0.3) * 300), dt))
    expressionValues[id] = next
    if (target?.Blend === 'Add') result[id] = (result[id] ?? 0) + next
    else if (target?.Blend === 'Multiply') result[id] = (result[id] ?? 1) * next
    else result[id] = next
    if (!target && Math.abs(next) < 0.001) delete expressionValues[id]
  }
  return result
}

function computeFallbackExpression(dt: number): Record<string, number> {
  const presets: Record<string, Partial<Record<SemanticParam, number>>> = {
    happy: { mouthForm: 0.75, eyeLOpen: 0.75, eyeROpen: 0.75, browLY: 0.25, browRY: 0.25 },
    sad: { mouthForm: -0.55, eyeLOpen: 0.72, eyeROpen: 0.72, browLY: -0.35, browRY: -0.35 },
    angry: { mouthForm: -0.35, eyeLOpen: 0.62, eyeROpen: 0.62, browLY: -0.7, browRY: -0.7 },
    surprise: { mouthOpen: 0.55, mouthForm: 0, eyeLOpen: 1, eyeROpen: 1, browLY: 0.55, browRY: 0.55 },
    neutral: { mouthForm: 0, browLY: 0, browRY: 0 },
    normal: { mouthForm: 0, browLY: 0, browRY: 0 },
  }
  const preset = presets[fallbackEmotion] ?? presets.neutral!
  const result: Record<string, number> = {}
  for (const [semantic, target] of Object.entries(preset) as Array<[SemanticParam, number]>) {
    const id = semanticParams[semantic]
    if (!id) continue
    const next = lerp(expressionValues[id] ?? 0, target, smoothFactor(120, dt))
    expressionValues[id] = next
    result[id] = next
  }
  return result
}

function setParam(id: string, value: number): void {
  try { (model?.internalModel.coreModel as any)?.setParameterValueById(id, value) } catch {}
}
function smoothFactor(halfLife: number, dt: number): number { return 1 - Math.exp((-0.693 / halfLife) * dt) }
function lerp(a: number, b: number, t: number): number { return a + (b - a) * Math.max(0, Math.min(1, t)) }
