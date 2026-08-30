<script setup lang="ts">
import { shallowRef } from 'vue'

interface Particle { x: number, y: number, s: number, d: number, a: number }
interface Orb { x: number, y: number, s: number, d: number }

function createParticles(count: number): Particle[] {
  const result: Particle[] = []
  for (let i = 0; i < count; i++) {
    result.push({
      x: Math.random() * 100,
      y: Math.random() * 100,
      s: Math.random() * 3 + 1,
      d: Math.random() * 5,
      a: Math.random(),
    })
  }
  return result
}

function createOrbs(count: number): Orb[] {
  const result: Orb[] = []
  for (let i = 0; i < count; i++) {
    result.push({
      x: Math.random() * 100,
      y: Math.random() * 100,
      s: Math.random() * 20 + 8,
      d: Math.random() * 6,
    })
  }
  return result
}

const particles = shallowRef(createParticles(36))
const orbs = shallowRef(createOrbs(6))
</script>

<template>
  <div class="sci-fi-overlay">
    <div class="corner tl">
      <div class="corner-bracket">
        <span class="cb-h" /><span class="cb-v" /><span class="cb-glow" />
      </div>
      <div class="corner-dot cdot-1" />
      <div class="corner-dot cdot-2" />
    </div>

    <div class="particle-field">
      <div v-for="(p, i) in particles" :key="'p' + i" class="particle"
        :style="{ left: `${p.x}%`, top: `${p.y}%`, width: `${p.s}px`, height: `${p.s}px`, animationDelay: `${p.d}s`, opacity: 0.25 + p.a * 0.35 }"
      />
    </div>

    <div class="orb-field">
      <div v-for="(o, i) in orbs" :key="'o' + i" class="orb"
        :style="{ left: `${o.x}%`, top: `${o.y}%`, width: `${o.s}px`, height: `${o.s}px`, animationDelay: `${o.d}s` }"
      />
    </div>

    <div class="scan-zone bl">
      <div class="scan-up" v-for="i in 4" :key="'su' + i" :style="{ animationDelay: `${i * 0.6}s` }" />
    </div>

    <div class="beam-zone br">
      <div class="beam" v-for="i in 3" :key="'bm' + i" :style="{ top: `${i * 14}px`, animationDelay: `${i * 0.7}s` }" />
    </div>

    <div class="flicker-field">
      <div class="flicker-bar" v-for="i in 8" :key="'fb' + i" :style="{ top: `${5 + i * 11}%`, animationDelay: `${i * 1.3}s` }" />
    </div>
  </div>
</template>

<style scoped>
.sci-fi-overlay {
  position: fixed; inset: 0; pointer-events: none; z-index: 100; overflow: hidden;
  --c1: var(--miya-comp-hud-primary-r, 0,255,245);
  --c2: var(--miya-comp-hud-secondary-r, 0,173,181);
}

/* bracket */
.corner.tl { position: absolute; top: 16px; left: 76px; width: 48px; height: 48px; }
.corner-bracket { position: absolute; inset: 0; }
.cb-h { position: absolute; top: 0; left: 0; width: 24px; height: 1px; background: rgba(var(--c1), 0.5); }
.cb-v { position: absolute; top: 0; left: 0; width: 1px; height: 24px; background: rgba(var(--c1), 0.5); }
.cb-glow {
  position: absolute; top: -1px; left: -1px;
  width: 6px; height: 6px; border-radius: 50%;
  background: rgba(var(--c1), 0.8);
  box-shadow: 0 0 12px rgba(var(--c1), 0.6), 0 0 24px rgba(var(--c1), 0.3);
  animation: corner-pulse 2s ease-in-out infinite;
}
@keyframes corner-pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.4); }
}
.corner-dot { position: absolute; width: 2px; height: 2px; border-radius: 50%; background: rgba(var(--c1), 0.5); }
.cdot-1 { top: 36px; left: 36px; animation: dot-fade 3s ease-in-out infinite; }
.cdot-2 { top: 42px; left: 8px; animation: dot-fade 4s ease-in-out 1.5s infinite; }
@keyframes dot-fade {
  0%, 100% { opacity: 0; }
  30% { opacity: 0.6; }
  50% { opacity: 0.1; }
}

/* particles */
.particle-field { position: absolute; inset: 0; }
.particle {
  position: absolute; border-radius: 50%;
  background: rgba(var(--c2), 0.5);
  animation: pt-float 8s ease-in-out infinite;
}
@keyframes pt-float {
  0%, 100% { opacity: 0; transform: translateY(0) scale(0.5); }
  15% { opacity: 0.6; }
  35% { opacity: 0.15; transform: translateY(-12px) scale(1.2); }
  70% { opacity: 0; transform: translateY(-20px) scale(0.3); }
}

/* orbs */
.orb-field { position: absolute; inset: 0; }
.orb {
  position: absolute; border-radius: 50%;
  background: radial-gradient(circle, rgba(var(--c1), 0.15) 0%, transparent 70%);
  animation: orb-drift 12s ease-in-out infinite;
}
@keyframes orb-drift {
  0%, 100% { opacity: 0; transform: translate(0, 0) scale(0.6); }
  20% { opacity: 0.6; }
  50% { opacity: 0.2; transform: translate(20px, -15px) scale(1.3); }
  80% { opacity: 0.5; transform: translate(-10px, 10px) scale(0.9); }
}

/* scan */
.scan-zone.bl { position: absolute; bottom: 0; left: 0; width: 180px; height: 200px; }
.scan-up {
  position: absolute; left: 0; width: 100%; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(var(--c1), 0.12), rgba(var(--c1), 0.05), transparent);
  animation: scan-rise 3s linear infinite;
}
@keyframes scan-rise {
  0% { top: 100%; opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { top: 0; opacity: 0; }
}

/* beams */
.beam-zone.br { position: absolute; bottom: 20px; right: 20px; width: 160px; height: 56px; }
.beam { position: absolute; left: 0; width: 100%; height: 1px; overflow: hidden; }
.beam::after {
  content: '';
  position: absolute; top: 0; width: 40px; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(var(--c2), 0.45), transparent);
  animation: beam-fly 2.5s linear infinite;
}
@keyframes beam-fly { 0% { left: -40px; } 100% { left: 100%; } }

/* flicker */
.flicker-field { position: absolute; inset: 0; }
.flicker-bar {
  position: absolute; left: 0; width: 100%; height: 1px;
  background: linear-gradient(90deg, transparent 10%, rgba(var(--c1), 0.08) 30%, rgba(var(--c1), 0.05) 50%, transparent 70%);
  animation: flick 5s ease-in-out infinite;
}
@keyframes flick {
  0%, 100% { opacity: 0; } 8% { opacity: 0.7; } 12% { opacity: 0; }
  25% { opacity: 0.3; } 27% { opacity: 0; }
  60% { opacity: 0; } 62% { opacity: 0.5; } 64% { opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .sci-fi-overlay * { animation: none !important; }
}
</style>
