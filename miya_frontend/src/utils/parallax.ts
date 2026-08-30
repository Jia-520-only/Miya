import { readonly, ref } from 'vue'

const parallaxX = ref(0)
const parallaxY = ref(0)

let targetX = 0
let targetY = 0
let rafId = 0
let lastTime = 0
const SETTLE_EPSILON = 0.0005

const HALF_LIFE = 80 // ms — controls smoothing speed
const DECAY = Math.LN2 / HALF_LIFE

function onMouseMove(e: MouseEvent) {
  const cx = window.innerWidth / 2
  const cy = window.innerHeight / 2
  targetX = (e.clientX - cx) / cx // [-1, 1]
  targetY = (e.clientY - cy) / cy
  scheduleTick()
}

function onMouseLeave() {
  targetX = 0
  targetY = 0
  scheduleTick()
}

function scheduleTick() {
  if (!rafId)
    rafId = requestAnimationFrame(tick)
}

function tick(now: number) {
  if (lastTime) {
    const dt = now - lastTime
    const factor = 1 - Math.exp(-DECAY * dt)
    parallaxX.value += (targetX - parallaxX.value) * factor
    parallaxY.value += (targetY - parallaxY.value) * factor
  }
  lastTime = now
  const settled = Math.abs(targetX - parallaxX.value) < SETTLE_EPSILON
    && Math.abs(targetY - parallaxY.value) < SETTLE_EPSILON
  if (settled) {
    parallaxX.value = targetX
    parallaxY.value = targetY
    rafId = 0
    lastTime = 0
    return
  }
  rafId = requestAnimationFrame(tick)
}

export function initParallax() {
  if (rafId)
    return
  window.addEventListener('mousemove', onMouseMove, { passive: true })
  document.documentElement.addEventListener('mouseleave', onMouseLeave)
}

export function destroyParallax() {
  window.removeEventListener('mousemove', onMouseMove)
  document.documentElement.removeEventListener('mouseleave', onMouseLeave)
  if (rafId)
    cancelAnimationFrame(rafId)
  rafId = 0
  lastTime = 0
  targetX = 0
  targetY = 0
  parallaxX.value = 0
  parallaxY.value = 0
}

export const pX = readonly(parallaxX)
export const pY = readonly(parallaxY)
