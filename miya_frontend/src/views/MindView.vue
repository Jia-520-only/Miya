<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiUrl } from '@/utils/api-url'

const router = useRouter()

interface StarNode {
  id: string; label: string; type: string
  x: number; y: number; z: number
  size: number; color: string
  level: string; emotion: string; significance: number; tags: string[]
  content: string; createdAt: string; isAnchor: boolean
}

const canvasRef = ref<HTMLCanvasElement>()
const searchQuery = ref('')
const loading = ref(false)
const nodeCount = ref(0)
const demoMode = ref(false)
const selectedNode = ref<StarNode | null>(null)


let nodes: StarNode[] = []
let animId = 0
let ctx: CanvasRenderingContext2D | null = null
let mouseX = 0, mouseY = 0
let dragging = false, dragStartX = 0, dragStartY = 0
let camRotY = 0, camRotX = 0.3, camZoom = 1
let targetRotY = 0, targetRotX = 0.3
const autoRotate = ref(true)
const FOV = 600
const DEPTH = 800

// 3D 背景星场
const bgStars: Array<{ x: number; y: number; z: number; size: number; alpha: number; twinkle: number }> = []

function onMouseMove(e: MouseEvent) {
  if (!canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  const cx = e.clientX - rect.left, cy = e.clientY - rect.top
  if (dragging) {
    targetRotY += (cx - dragStartX) * 0.005
    targetRotX += (cy - dragStartY) * 0.003
    targetRotX = Math.max(-1.2, Math.min(1.2, targetRotX))
    dragStartX = cx; dragStartY = cy
    autoRotate.value = false
  }
  mouseX = cx; mouseY = cy
}

function onMouseDown(e: MouseEvent) {
  dragging = true
  if (!canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  dragStartX = e.clientX - rect.left
  dragStartY = e.clientY - rect.top
  autoRotate.value = false
}

function onDoubleClick() {
  autoRotate.value = true
}

function onMouseUp(e: MouseEvent) {
  if (dragging && Math.abs(e.movementX) + Math.abs(e.movementY) < 3) {
    // 点击
    pickNode(mouseX, mouseY)
  }
  dragging = false
}

function onWheel(e: WheelEvent) {
  e.preventDefault()
  camZoom = Math.max(0.3, Math.min(3, camZoom + e.deltaY * -0.001))
}

function pickNode(sx: number, sy: number) {
  const w = ctx!.canvas.width, h = ctx!.canvas.height
  let best: StarNode | null = null, bestDist = Infinity
  for (const n of nodes) {
    const cosY = Math.cos(camRotY), sinY = Math.sin(camRotY)
    const cosX = Math.cos(camRotX), sinX = Math.sin(camRotX)
    const rx = n.x * cosY - n.z * sinY
    const rz = n.x * sinY + n.z * cosY
    const ry = n.y * cosX - rz * sinX
    const rz2 = n.y * sinX + rz * cosX + DEPTH
    const projX = w / 2 + (rx * FOV * camZoom) / Math.max(rz2, 1)
    const projY = h / 2 - (ry * FOV * camZoom) / Math.max(rz2, 1)
    const dist = Math.hypot(sx - projX, sy - projY)
    const hitSize = (n.size * camZoom * 200) / Math.max(rz2, 1) + 8
    if (dist < hitSize && dist < bestDist) { best = n; bestDist = dist }
  }
  selectedNode.value = best
}

function getColor(node: StarNode): string {
  if (node.isAnchor) return cachedAnchorColor
  if (node.emotion && cachedEmotionColors[node.emotion]) return cachedEmotionColors[node.emotion]!
  return cachedLevelColors[node.type] || cachedLevelColors[node.level] || '#aaa'
}

// 缓存：只在初始化时读取一次 CSS 变量，避免 animate 每帧读取
let cachedAnchorColor = '#ffd700'
let cachedLevelColors: Record<string, string> = {}
let cachedEmotionColors: Record<string, string> = {}

function refreshColorCache() {
  const root = getComputedStyle(document.documentElement)
  cachedAnchorColor = root.getPropertyValue('--miya-comp-mind-anchor').trim() || '#ffd700'
  cachedLevelColors = {
    long_term: root.getPropertyValue('--miya-comp-mind-long-term').trim() || '#00ADB5',
    short_term: root.getPropertyValue('--miya-comp-mind-short-term').trim() || '#7dd3fc',
    dialogue: root.getPropertyValue('--miya-comp-mind-dialogue').trim() || '#00ADB5',
    semantic: root.getPropertyValue('--miya-comp-mind-semantic').trim() || '#ff6b9d',
    knowledge: root.getPropertyValue('--miya-comp-mind-knowledge').trim() || '#ffd700',
    core: cachedAnchorColor,
    user: root.getPropertyValue('--miya-comp-mind-semantic').trim() || '#ff6b9d',
    system: root.getPropertyValue('--miya-comp-mind-short-term').trim() || '#7dd3fc',
  }
  cachedEmotionColors = {
    joy: root.getPropertyValue('--miya-comp-emotion-joy').trim() || '#ffd700',
    sadness: root.getPropertyValue('--miya-comp-emotion-sadness').trim() || '#7dd3fc',
    anger: root.getPropertyValue('--miya-comp-emotion-anger').trim() || '#ff4444',
    fear: root.getPropertyValue('--miya-comp-emotion-fear').trim() || '#00ADB5',
    love: root.getPropertyValue('--miya-comp-emotion-love').trim() || '#ff6b9d',
    neutral: root.getPropertyValue('--miya-comp-emotion-neutral').trim() || '#aaa',
    surprise: root.getPropertyValue('--miya-comp-emotion-surprise').trim() || '#ff8c00',
  }
}
function getName(level: string): string {
  const m: Record<string, string> = { long_term: '长期', short_term: '短期', dialogue: '对话', semantic: '语义', knowledge: '知识', core: '锚点', user: '用户锚点', cognitive: '认知', pinned: '置顶', system: '系统' }
  return m[level] || level
}

let frameCount = 0
function animate() {
  if (!ctx) return
  const w = ctx.canvas.width, h = ctx.canvas.height
  ctx.clearRect(0, 0, w, h)

  // 自动旋转
  if (autoRotate.value) { targetRotY += 0.002; targetRotX += Math.sin(frameCount * 0.003) * 0.0003 }
  camRotY += (targetRotY - camRotY) * 0.03
  camRotX += (targetRotX - camRotX) * 0.03

  const cosY = Math.cos(camRotY), sinY = Math.sin(camRotY)
  const cosX = Math.cos(camRotX), sinX = Math.sin(camRotX)

  // 3D 背景星场
  for (const s of bgStars) {
    s.twinkle += 0.02
    const rx = s.x * cosY - s.z * sinY
    const rz = s.x * sinY + s.z * cosY
    const ry = s.y * cosX - rz * sinX
    const rz2 = s.y * sinX + rz * cosX + DEPTH
    if (rz2 <= 0) continue
    const px = w / 2 + (rx * FOV * camZoom) / rz2
    const py = h / 2 - (ry * FOV * camZoom) / rz2
    const alpha = Math.max(0, (0.1 + Math.sin(s.twinkle) * 0.05) * (DEPTH / rz2))
    ctx.fillStyle = `rgba(0, 173, 181, ${alpha})`
    ctx.fillRect(px, py, s.size, s.size)
  }

  // 节点投影 + 排序
  const projected = nodes.map(n => {
    const rx = n.x * cosY - n.z * sinY
    const rz = n.x * sinY + n.z * cosY
    const ry = n.y * cosX - rz * sinX
    const rz2 = n.y * sinX + rz * cosX + DEPTH
    if (rz2 <= 1) return { node: n, px: -1, py: -1, depth: Infinity, screenSize: 0 }
    const px = w / 2 + (rx * FOV * camZoom) / rz2
    const py = h / 2 - (ry * FOV * camZoom) / rz2
    const screenSize = Math.max(1, (n.size * camZoom * 200) / rz2)
    return { node: n, px, py, depth: rz2, screenSize }
  }).filter(p => p.px > -50 && p.px < w + 50 && p.py > -50 && p.py < h + 50)
    .sort((a, b) => b.depth - a.depth)

  // 绘制
  for (const p of projected) {
    const n = p.node
    const color = getColor(n)
    const isSel = selectedNode.value?.id === n.id
    const s = p.screenSize

    // 光晕
    const haloSize = s + (n.isAnchor ? 12 : 4)
    const grad = ctx.createRadialGradient(p.px, p.py, 0, p.px, p.py, haloSize)
    grad.addColorStop(0, color)
    grad.addColorStop(0.3, color.replace(')', ',0.4)').replace('rgb', 'rgba'))
    grad.addColorStop(1, 'transparent')
    ctx.beginPath()
    ctx.arc(p.px, p.py, haloSize, 0, Math.PI * 2)
    ctx.fillStyle = grad
    ctx.fill()

    // 主体
    ctx.beginPath()
    ctx.arc(p.px, p.py, Math.max(1.5, s * 0.5), 0, Math.PI * 2)
    ctx.fillStyle = isSel ? '#fff' : color
    ctx.fill()

    // 锚点光环
    if (n.isAnchor) {
      const pulse = 1 + Math.sin(frameCount * 0.05) * 0.4
      ctx.beginPath()
      ctx.arc(p.px, p.py, s * 0.8 * pulse, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(255,215,0,0.5)'
      ctx.lineWidth = 1
      ctx.stroke()
    }

    // 选中高亮
    if (isSel) {
      ctx.beginPath()
      ctx.arc(p.px, p.py, s * 0.6 + 4, 0, Math.PI * 2)
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      ctx.stroke()
    }

    // 标签 (近距离节点)
    if (p.depth < DEPTH * 1.5 && s > 3) {
      ctx.fillStyle = '#fff'
      ctx.font = `${Math.max(8, s * 0.5)}px "Noto Sans SC", sans-serif`
      ctx.textAlign = 'center'
      ctx.fillText(n.label.slice(0, 10), p.px, p.py - s * 0.4 - 4)
    }
  }

  frameCount++
  animId = requestAnimationFrame(animate)
}

function buildGraph(data: any) {
  const apiNodes = data?.nodes || []
  const w = ctx?.canvas.width || 1000, h = ctx?.canvas.height || 700
  demoMode.value = apiNodes.length === 0

  const srcNodes = demoMode.value ? getDemoNodes() : apiNodes
  nodes = []
  for (const n of srcNodes) {
    nodes.push({
      id: String(n.id || n.label),
      label: String(n.label || n.id || '?'),
      type: String(n.type || 'memory'),
      x: (Math.random() - 0.5) * DEPTH * 0.8,
      y: (Math.random() - 0.5) * DEPTH * 0.6,
      z: (Math.random() - 0.5) * DEPTH * 0.7,
      size: (n.isAnchor || n.type === 'core' || n.type === 'user') ? 10 : 5 + (n.significance || 0.5) * 6,
      color: '#0ff',
      level: String(n.level || 'dialogue'),
      emotion: String(n.emotion || ''),
      significance: n.significance || 0.5,
      tags: n.tags || [],
      content: n.content || '',
      createdAt: n.created_at || n.timestamp || '',
      isAnchor: !!(n.isAnchor || n.type === 'core' || n.type === 'user'),
    })
  }
  nodeCount.value = nodes.length
}

function getDemoNodes() {
  return [
    { id: 'miya', label: '弥娅', type: 'core', isAnchor: true, significance: 1, emotion: 'love', level: 'long_term', tags: ['核心'], content: '弥娅·阿尔缪斯' },
    { id: 'jia', label: '佳', type: 'user', isAnchor: true, significance: 1, emotion: 'love', level: 'long_term', tags: ['创造者'], content: '弥娅的创造者' },
    { id: 'heart', label: '心脏', type: 'user', isAnchor: true, significance: 0.9, emotion: 'sadness', level: 'long_term', tags: ['健康'], content: '佳有先天性心脏病' },
    { id: 'm1', label: '酸汤鱼', type: 'dialogue', isAnchor: false, significance: 0.6, emotion: 'joy', level: 'short_term', tags: ['饮食'], content: '佳爱吃酸汤鱼' },
    { id: 'm2', label: '茉莉蜜茶', type: 'dialogue', isAnchor: false, significance: 0.5, emotion: 'joy', level: 'short_term', tags: ['饮品'], content: '最爱茉莉蜜茶' },
    { id: 'm3', label: '记忆存档', type: 'system', isAnchor: false, significance: 0.7, emotion: 'neutral', level: 'knowledge', tags: ['系统'], content: 'MIYA五层记忆' },
    { id: 'm4', label: '情绪感知', type: 'system', isAnchor: false, significance: 0.7, emotion: 'surprise', level: 'knowledge', tags: ['系统'], content: '9种情绪识别' },
    { id: 'm5', label: '认知推演', type: 'system', isAnchor: false, significance: 0.6, emotion: 'neutral', level: 'semantic', tags: ['系统'], content: '话题识别+检索' },
  ]
}

// ── 数据加载 ──
async function loadData() {
  loading.value = true
  try {
    const memoryNodes: any[] = []
    const anchorFiles = [
      { path: 'data/memory_anchors_identity.json', type: 'core' },
      { path: 'data/memory_anchors_user.json', type: 'user' },
      { path: 'data/memory/pinned_memories.json', type: 'pinned' },
      { path: 'data/memory/cognitive_memories.json', type: 'cognitive' },
    ]
    for (const af of anchorFiles) {
      try {
        const res = await fetch(apiUrl(`/api/desktop/files/read?path=${encodeURIComponent(af.path)}`)).then(r => r.json())
        if (res?.lines) {
          const arr = JSON.parse(res.lines.join(''))
          for (const item of (Array.isArray(arr) ? arr : [arr])) {
            memoryNodes.push({ id: String(item.id || item.name || item.uuid || Math.random()), label: String(item.title || item.fact || item.content || item.id || '?').slice(0, 20), type: af.type, isAnchor: true, significance: 0.9, level: 'long_term', emotion: '', tags: item.tags || [af.type], content: item.content || item.description || item.fact || '' })
          }
        }
      } catch {}
    }

    const dirs = [
      { dir: 'data/memory/long_term', level: 'long_term', limit: 300 },
      { dir: 'data/memory/short_term', level: 'short_term', limit: 200 },
      { dir: 'data/memory/dialogue', level: 'dialogue', limit: 200 },
    ]

    for (const d of dirs) {
      try {
        const listRes = await fetch(apiUrl(`/api/desktop/files/list?path=${encodeURIComponent(d.dir)}`)).then(r => r.json())
        const files = (listRes?.files || []).filter((f: any) => f.name.endsWith('.json'))
        const shuffled = files.sort(() => Math.random() - 0.5).slice(0, d.limit)
        // 并发批量加载 (10个一组)
        for (let batch = 0; batch < shuffled.length; batch += 10) {
          const batchFiles = shuffled.slice(batch, batch + 10)
          const results = await Promise.allSettled(batchFiles.map((f: any) =>
            fetch(apiUrl(`/api/desktop/files/read?path=${encodeURIComponent(`${d.dir}/${f.name}`)}`)).then(r => r.json())
          ))
          for (const r of results) {
            if (r.status !== 'fulfilled' || !r.value?.lines) continue
            try {
              const item = JSON.parse(r.value.lines.join(''))
              memoryNodes.push({ id: item.id || '', label: (item.content || item.fact || item.id || '').slice(0, 20), type: item.level || d.level, isAnchor: false, significance: item.priority || 0.5, level: item.level || d.level, emotion: item.emotion || item.emotional_tone || '', tags: item.tags || [], content: item.content || item.fact || '', createdAt: item.created_at || '' })
            } catch {}
          }
        }
      } catch {}
    }

    console.log(`[记忆星河] 已加载: ${memoryNodes.length} 节点 (锚点+采样记忆)`)

    demoMode.value = memoryNodes.length === 0
    if (!demoMode.value) {
      buildGraph({ nodes: memoryNodes, edges: [] })
      selectedNode.value = null
    } else {
      buildGraph(null)
    }
  } catch { buildGraph(null) } finally { loading.value = false }
}

async function search() {
  if (!searchQuery.value.trim()) { loadData(); return }
  loading.value = true
  const q = searchQuery.value.toLowerCase()
  try {
    const foundNodes: any[] = []
    // quick scan of anchors + long_term
    const scanFiles = [
      'data/memory_anchors_identity.json', 'data/memory_anchors_user.json',
      'data/memory/pinned_memories.json', 'data/memory/cognitive_memories.json',
    ]
    for (const path of scanFiles) {
      try {
        const res = await fetch(apiUrl(`/api/desktop/files/read?path=${encodeURIComponent(path)}`)).then(r => r.json())
        if (res?.lines) {
          const arr = JSON.parse(res.lines.join(''))
          for (const item of (Array.isArray(arr) ? arr : [arr])) {
            if (JSON.stringify(item).toLowerCase().includes(q)) {
              foundNodes.push({ id: String(item.id || Math.random()), label: String(item.content || item.title || item.id || '?').slice(0, 20), type: 'memory', isAnchor: true, significance: 1, level: 'long_term', emotion: '', tags: item.tags || [], content: item.content || '' })
            }
          }
        }
      } catch {}
    }
    // scan long_term
    try {
      const listRes = await fetch(apiUrl('/api/desktop/files/list?path=data/memory/long_term')).then(r => r.json())
      for (const f of (listRes?.files || []).slice(0, 30)) {
        try {
          const readRes = await fetch(apiUrl(`/api/desktop/files/read?path=${encodeURIComponent(`data/memory/long_term/${f.name}`)}`)).then(r => r.json())
          if (readRes?.lines) {
            const item = JSON.parse(readRes.lines.join(''))
            if (JSON.stringify(item).toLowerCase().includes(q)) {
              foundNodes.push({ id: item.id, label: (item.content || '').slice(0, 20), type: 'long_term', isAnchor: false, significance: item.priority || 0.5, level: 'long_term', emotion: item.emotional_tone || '', tags: item.tags || [], content: item.content || '' })
            }
          }
        } catch {}
      }
    } catch {}
    buildGraph({ nodes: foundNodes.slice(0, 50), edges: [] })
  } catch { buildGraph(null) } finally { loading.value = false }
}

onMounted(() => {
  if (!canvasRef.value) return
  ctx = canvasRef.value.getContext('2d')
  if (!ctx) return
  canvasRef.value.width = canvasRef.value.offsetWidth
  canvasRef.value.height = canvasRef.value.offsetHeight

  // 3D 背景星场
  for (let i = 0; i < 200; i++) {
    bgStars.push({
      x: (Math.random() - 0.5) * DEPTH * 1.5,
      y: (Math.random() - 0.5) * DEPTH * 1.2,
      z: (Math.random() - 0.5) * DEPTH * 1.5,
      size: Math.random() * 2 + 0.5,
      alpha: 0, twinkle: Math.random() * Math.PI * 2,
    })
  }

  refreshColorCache()
  loadData()
  animId = requestAnimationFrame(animate)
})

onUnmounted(() => cancelAnimationFrame(animId))

</script>

<template>
  <div class="star-river">
    <div class="sr-header">
      <button class="back-btn" @click="router.push('/')" title="返回首页">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
      </button>
      <h1>记忆星河</h1>
      <span class="sr-counts">{{ nodeCount }} 星</span>
      <span v-if="demoMode" class="sr-demo-badge">演示</span>
      <span class="sr-help">🖱 拖拽 · 滚轮 · 双击恢复旋转 · ↻ 换一批</span>
    </div>
    <div class="sr-toolbar">
      <input v-model="searchQuery" class="sr-search" placeholder="搜索记忆..." @keydown.enter="search">
      <button class="sr-btn" @click="search">搜索</button>
      <button class="sr-btn sr-btn-reset" @click="searchQuery = ''; loadData()">清除</button>
      <button class="sr-btn" @click="autoRotate = !autoRotate" :class="{ active: autoRotate }">{{ autoRotate ? '暂停' : '旋转' }}</button>
      <button class="sr-btn" @click="loadData()" title="重新随机采样">&nbsp;↻&nbsp;</button>
      <div class="sr-legend">
        <span class="legend-item"><i style="color:var(--miya-comp-mind-anchor,#ffd700)">●</i>锚点</span>
        <span class="legend-item"><i style="color:var(--miya-comp-mind-long-term,#00ADB5)">●</i>长期</span>
        <span class="legend-item"><i style="color:var(--miya-comp-mind-dialogue,#00ADB5)">●</i>对话</span>
        <span class="legend-item"><i style="color:var(--miya-comp-mind-semantic,#ff6b9d)">●</i>语义</span>
        <span class="legend-item"><i style="color:var(--miya-comp-mind-short-term,#7dd3fc)">●</i>短期</span>
      </div>
    </div>
    <div class="sr-canvas-wrap" :class="{ loading: loading }">
      <canvas ref="canvasRef" class="sr-canvas"
        @mousemove="onMouseMove" @mousedown="onMouseDown" @mouseup="onMouseUp" @dblclick="onDoubleClick" @wheel.prevent="onWheel"
      />
      <div v-if="loading" class="sr-loading">✦ 加载记忆星河...</div>
    </div>
    <div v-if="selectedNode" class="sr-detail">
      <button class="detail-close" @click="selectedNode = null">✕</button>
      <div class="detail-header">
        <span class="detail-star" :style="{ color: getColor(selectedNode) }">✦</span>
        <span class="detail-name">{{ selectedNode.label }}</span>
        <span v-if="selectedNode.isAnchor" class="detail-anchor-badge">锚点</span>
      </div>
      <div class="detail-meta">
        <span class="meta-tag">{{ getName(selectedNode.level || selectedNode.type) }}</span>
        <span v-if="selectedNode.emotion" class="meta-tag">{{ selectedNode.emotion }}</span>
        <span v-for="t in selectedNode.tags" :key="t" class="meta-tag">{{ t }}</span>
      </div>
      <p class="detail-content">{{ selectedNode.content || '(无内容)' }}</p>
      <div v-if="selectedNode.isAnchor" class="detail-relations"><small>★ 核心锚点 — 不会被遗忘</small></div>
    </div>
  </div>
</template>

<style scoped>
.star-river {
  --line: var(--miya-comp-mind-line, #00ADB5);
  --anchor: var(--miya-comp-mind-anchor, #ffd700);
  --highlight: var(--miya-comp-mind-highlight, #00ADB5);
  height: 100%; display: flex; flex-direction: column; color: var(--miya-text); }
.sr-header { display: flex; align-items: center; gap: 0.6rem; padding: 0.5rem 1rem; border-bottom: 1px solid rgba(0, 173, 181, 0.06); flex-shrink: 0; }
.sr-header h1 { font-family: 'Noto Serif SC', serif; font-size: 1rem; color: var(--miya-accent); margin: 0; }
.sr-counts { font-size: 0.65rem; color: var(--miya-text-dim); font-family: 'JetBrains Mono', monospace; }
.sr-demo-badge { font-size: 0.55rem; color: rgba(255,215,0,0.5); border: 1px solid rgba(255,215,0,0.2); border-radius: 0.15rem; padding: 0.05rem 0.35rem; }
.sr-help { font-size: 0.6rem; color: var(--miya-text-dim); margin-left: auto; opacity: 0.5; }
.back-btn { display: flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 0.3rem; border: 1px solid rgba(0, 173, 181, 0.12); background: rgba(0, 173, 181, 0.04); color: rgba(0, 173, 181, 0.6); cursor: pointer; }
.back-btn:hover { background: rgba(0, 173, 181, 0.1); }

.sr-toolbar { display: flex; align-items: center; gap: 0.4rem; padding: 0.4rem 1rem; border-bottom: 1px solid rgba(0, 173, 181, 0.04); flex-shrink: 0; flex-wrap: wrap; position: relative; z-index: 10; }
.sr-search { flex: 1; max-width: 200px; background: rgba(10,18,32,0.8); border: 1px solid rgba(0, 173, 181, 0.12); border-radius: 0.3rem; color: var(--miya-text); padding: 0.3rem 0.5rem; font-size: 0.7rem; outline: none; }
.sr-search:focus { border-color: rgba(0, 173, 181, 0.3); }
.sr-btn { padding: 0.25rem 0.5rem; font-size: 0.65rem; border: 1px solid rgba(0, 173, 181, 0.15); border-radius: 0.25rem; background: rgba(0, 173, 181, 0.03); color: rgba(0, 173, 181, 0.5); cursor: pointer; transition: all 0.2s; }
.sr-btn:hover { background: rgba(0, 173, 181, 0.08); border-color: rgba(0, 173, 181, 0.3); }
.sr-btn.active { background: rgba(0, 173, 181, 0.1); color: rgba(0, 173, 181, 0.8); }
.sr-btn-reset { border-color: rgba(255,255,255,0.05); color: var(--miya-text-dim); }
.sr-legend { display: flex; gap: 0.6rem; margin-left: auto; font-size: 0.55rem; color: var(--miya-text-dim); }
.legend-item { display: flex; align-items: center; gap: 0.15rem; }
.legend-item i { font-style: normal; }

.sr-canvas-wrap { flex: 1; position: relative; min-height: 0; overflow: hidden; }
.sr-canvas { width: 100%; height: 100%; cursor: grab; }
.sr-canvas:active { cursor: grabbing; }
.sr-loading { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--miya-text-dim); font-size: 0.9rem; }

.sr-detail { position: absolute; top: 10px; right: 10px; width: 250px; max-height: 70%; overflow-y: auto; background: rgba(8,16,28,0.96); border: 1px solid rgba(0, 173, 181, 0.15); border-radius: 0.4rem; padding: 0.7rem; z-index: 20; box-shadow: 0 0 30px rgba(0,0,0,0.5); }
.detail-close { position: absolute; top: 0.3rem; right: 0.3rem; width: 18px; height: 18px; border: none; background: none; color: var(--miya-text-dim); cursor: pointer; font-size: 0.7rem; }
.detail-header { display: flex; align-items: center; gap: 0.3rem; margin-bottom: 0.4rem; }
.detail-star { font-size: 1rem; }
.detail-name { font-weight: 600; font-size: 0.85rem; }
.detail-anchor-badge { font-size: 0.5rem; color: var(--miya-comp-mind-anchor, #ffd700); border: 1px solid color-mix(in srgb, var(--miya-comp-mind-anchor, #ffd700) 30%, transparent); border-radius: 0.15rem; padding: 0.03rem 0.25rem; }
.detail-meta { display: flex; flex-wrap: wrap; gap: 0.2rem; margin-bottom: 0.4rem; }
.meta-tag { font-size: 0.55rem; padding: 0.08rem 0.3rem; border-radius: 0.15rem; background: rgba(0, 173, 181, 0.06); color: rgba(0, 173, 181, 0.5); }
.detail-content { font-size: 0.72rem; color: var(--miya-text); line-height: 1.5; margin: 0 0 0.4rem; }
.detail-relations small { color: rgba(255,215,0,0.5); font-size: 0.55rem; }
</style>
