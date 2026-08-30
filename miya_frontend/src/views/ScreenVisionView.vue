<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import API from '@/api/core'
import { MESSAGES } from '@/utils/session'

const router = useRouter()
const query = ref('')
const loading = ref(false)
const result = ref('')
const screenshotPreview = ref('')
const status = ref<'idle' | 'success' | 'error' | 'partial'>('idle')
const screenshots = ref<string[]>([])

function pushToConversation(text: string) {
  MESSAGES.value.push({
    role: 'user',
    content: query.value
      ? `【截屏问题】${query.value}\n\n【AI分析结果】${text}`
      : `【屏幕分析】${text}`,
    sender: '屏幕视觉',
  })
}

async function doLook() {
  if (loading.value) return
  loading.value = true
  result.value = '正在截图并分析...'
  status.value = 'idle'

  let wasMinimized = false
  try {
    if (window.electronAPI?.minimize) {
      window.electronAPI.minimize()
      wasMinimized = true
      await new Promise(r => setTimeout(r, 800))
    }
  } catch {}

  try {
    const resp = await API.mcpCall('screen_vision', 'look_screen', {
      query: query.value || undefined,
    })
    const r = resp?.result
    const data = typeof r === 'string' ? JSON.parse(r) : r

    if (data?.status === 'success') {
      result.value = data.message
      status.value = 'success'
      pushToConversation(data.message)
      router.push('/chat')
    } else if (data?.status === 'partial') {
      result.value = data.message
      status.value = 'partial'
      pushToConversation(data.message)
      router.push('/chat')
    } else {
      result.value = data?.message || '分析失败'
      status.value = 'error'
    }
  } catch (e: any) {
    result.value = e?.message || '请求失败'
    status.value = 'error'
  }

  loading.value = false
}

async function doScreenshot() {
  if (loading.value) return
  loading.value = true

  try {
    const resp = await API.mcpCall('screen_vision', 'screenshot', {})
    const r = resp?.result
    const data = typeof r === 'string' ? JSON.parse(r) : r
    if (data?.status === 'success') {
      screenshots.value.unshift(data.message)
      if (screenshots.value.length > 10) screenshots.value.pop()
      pushToConversation(data.message || '截图完成')
      router.push('/chat')
    }
  } catch (_e) {
    /* stay on page to show error */
  }
  loading.value = false
}
</script>

<template>
  <div class="sv-root">
    <header class="sv-header">
      <button class="sv-back-btn" @click="router.push('/')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
      </button>
      <div class="sv-title-group">
        <span class="sv-title">屏幕视觉</span>
        <span class="sv-sub">截图 · AI 分析</span>
      </div>
    </header>

    <div class="sv-body">
      <div class="sv-panel">
        <div class="sv-controls">
          <textarea
            v-model="query"
            class="sv-textarea"
            placeholder="想问弥娅关于屏幕的问题？（留空则自动描述所有内容）"
            rows="2"
            :disabled="loading"
          />
          <div class="sv-btn-row">
            <button class="sv-btn primary" :disabled="loading" @click="doLook">
              {{ loading ? '分析中...' : '分析屏幕' }}
            </button>
            <button class="sv-btn" :disabled="loading" @click="doScreenshot">只截图</button>
          </div>
        </div>

        <div v-if="result" class="sv-result" :class="status">
          <div class="sv-result-label">
            {{ status === 'success' ? '✓ 分析结果' : status === 'error' ? '✗ 错误' : status === 'partial' ? '⚠ 部分成功' : '⟳ 处理中' }}
          </div>
          <div class="sv-result-content">{{ result }}</div>
        </div>

        <div v-if="!result" class="sv-empty">
          <span class="sv-empty-icon">⬡</span>
          <span class="sv-empty-text">点击「分析屏幕」让弥娅帮你看看屏幕上的内容</span>
          <span class="sv-empty-hint">适用于：游戏界面分析 · 错误排查 · 操作指引 · 内容识别</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sv-root {
  display: flex; flex-direction: column; height: 100%;
  padding: 1rem 1.2rem; gap: 0.8rem;
  perspective: 800px; -webkit-perspective: 800px;
  overflow: hidden;
  color: var(--miya-text, #E4ECF0);
  font-family: 'Noto Sans SC', sans-serif;
}

/* ── Header ── */
.sv-header {
  display: flex; align-items: center; gap: 0.8rem;
  padding: 0.5rem 0.8rem; flex-shrink: 0;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(0, 173, 181, 0.06);
  box-shadow:
    3px 3px 8px rgba(0, 40, 50, 0.3),
    -2px -2px 6px rgba(0, 180, 200, 0.04);
  border-radius: 4px;
  transform: rotateY(2deg);
  transition: border-color 0.3s ease, transform 0.5s ease;
}
.sv-header:hover { border-color: rgba(0, 255, 245, 0.15); transform: rotateY(1deg); }

.sv-back-btn {
  width: 28px; height: 28px; border-radius: 5px;
  border: 1px solid rgba(0, 173, 181, 0.1);
  background: rgba(0, 173, 181, 0.04);
  color: rgba(0, 173, 181, 0.5); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.sv-back-btn:hover {
  background: rgba(0, 173, 181, 0.1); border-color: rgba(0, 255, 245, 0.3);
  color: rgba(0, 255, 245, 0.8); transform: skewX(-4deg);
}
.sv-back-btn svg { width: 14px; height: 14px; }

.sv-title-group { display: flex; flex-direction: column; }
.sv-title {
  font-family: 'Noto Serif SC', serif; font-size: 0.9rem;
  font-weight: 700; letter-spacing: 0.05em; color: #ffffff;
}
.sv-sub {
  font-family: 'JetBrains Mono', monospace; font-size: 0.5rem;
  color: rgba(0, 173, 181, 0.3); letter-spacing: 0.1em;
}

/* ── Body Panel ── */
.sv-body {
  flex: 1; display: flex; align-items: flex-start; justify-content: center;
  padding-top: 1rem; overflow: hidden;
}

.sv-panel {
  width: 100%; max-width: 560px;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(0, 173, 181, 0.06);
  box-shadow:
    3px 3px 10px rgba(0, 40, 50, 0.35),
    -1px -1px 4px rgba(0, 180, 200, 0.04);
  border-radius: 4px; padding: 1rem;
  transform: rotateX(2deg);
  transition: transform 0.5s ease, border-color 0.3s ease;
  overflow-y: auto; max-height: 100%;
}
.sv-panel:hover { transform: rotateX(1deg); border-color: rgba(0, 255, 245, 0.1); }
.sv-panel::-webkit-scrollbar { width: 3px; }
.sv-panel::-webkit-scrollbar-thumb { background: rgba(0, 173, 181, 0.1); border-radius: 2px; }

.sv-controls { display: flex; flex-direction: column; gap: 0.6rem; }

.sv-textarea {
  width: 100%; padding: 0.6rem; resize: vertical; box-sizing: border-box;
  background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(0, 173, 181, 0.08);
  border-radius: 4px; color: var(--miya-text); font-size: 0.75rem;
  font-family: inherit; outline: none; min-height: 60px;
  transition: border-color 0.2s;
}
.sv-textarea:focus { border-color: rgba(0, 255, 245, 0.2); }
.sv-textarea::placeholder { color: rgba(0, 173, 181, 0.15); }
.sv-textarea:disabled { opacity: 0.3; }

.sv-btn-row { display: flex; gap: 0.5rem; }

.sv-btn {
  padding: 0.5rem 1.2rem; border-radius: 5px; cursor: pointer;
  font-size: 0.7rem; font-family: inherit;
  background: rgba(0, 0, 0, 0.3); color: rgba(200, 200, 200, 0.5);
  border: 1px solid rgba(0, 173, 181, 0.08);
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.sv-btn:hover:not(:disabled) {
  color: rgba(255, 255, 255, 0.85); background: rgba(129, 191, 241, 0.1);
  border-color: rgba(0, 255, 245, 0.2); transform: skewX(-3deg);
}
.sv-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.sv-btn.primary {
  background: rgba(0, 173, 181, 0.12); color: rgba(0, 255, 245, 0.7);
  border-color: rgba(0, 173, 181, 0.18);
}
.sv-btn.primary:hover:not(:disabled) {
  background: rgba(0, 173, 181, 0.2); border-color: rgba(0, 255, 245, 0.3);
  box-shadow: 0 0 12px rgba(0, 173, 181, 0.1);
}

/* ── Result ── */
.sv-result {
  margin-top: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px; padding: 0.8rem;
  border: 1px solid rgba(0, 173, 181, 0.06);
}
.sv-result.success { border-color: rgba(0, 173, 181, 0.15); }
.sv-result.error { border-color: rgba(248, 113, 113, 0.15); }
.sv-result.partial { border-color: rgba(251, 191, 36, 0.15); }

.sv-result-label {
  font-family: 'JetBrains Mono', monospace; font-size: 0.58rem; font-weight: 600;
  margin-bottom: 0.5rem;
}
.sv-result.success .sv-result-label { color: rgba(0, 173, 181, 0.7); }
.sv-result.error .sv-result-label { color: rgba(248, 113, 113, 0.7); }
.sv-result.partial .sv-result-label { color: rgba(251, 191, 36, 0.7); }

.sv-result-content { font-size: 0.75rem; line-height: 1.7; color: var(--miya-text); white-space: pre-wrap; }

/* ── Empty ── */
.sv-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.5rem; padding: 2rem 0; }
.sv-empty-icon { font-size: 2rem; opacity: 0.08; }
.sv-empty-text { font-size: 0.72rem; color: rgba(200, 200, 200, 0.25); }
.sv-empty-hint { font-size: 0.58rem; color: rgba(200, 200, 200, 0.12); }
</style>
