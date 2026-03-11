<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useSettingsStore } from '../stores/settings'
import { copyToClipboard } from '../utils'

interface Props {
  content: string
  enableCodeHighlight?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  enableCodeHighlight: true
})

const settings = useSettingsStore()

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
  headerIds: true,
  mangle: false
})

// 渲染 Markdown
const renderedContent = computed(() => {
  if (!settings.settings.markdownEnabled) {
    return escapeHtml(props.content)
  }

  try {
    const html = marked.parse(props.content) as string
    return DOMPurify.sanitize(html)
  } catch (error) {
    console.error('Markdown rendering error:', error)
    return escapeHtml(props.content)
  }
})

// HTML 转义
function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// 复制代码块
async function copyCodeBlock(code: string, event: Event): Promise<void> {
  event.stopPropagation()
  const success = await copyToClipboard(code)
  if (success) {
    // 可以添加提示
    console.log('Code copied to clipboard')
  }
}

// 处理点击事件
function handleCodeClick(event: Event, code: string) {
  const target = event.target as HTMLElement
  if (target.classList.contains('copy-button')) {
    copyCodeBlock(code, event)
  }
}
</script>

<template>
  <div class="markdown-renderer" v-html="renderedContent" @click="handleCodeClick"></div>
</template>

<style scoped>
.markdown-renderer {
  line-height: 1.7;
  word-wrap: break-word;
}

.markdown-renderer :deep(h1),
.markdown-renderer :deep(h2),
.markdown-renderer :deep(h3),
.markdown-renderer :deep(h4),
.markdown-renderer :deep(h5),
.markdown-renderer :deep(h6) {
  margin-top: 1.5em;
  margin-bottom: 0.5em;
  font-weight: 600;
  line-height: 1.25;
}

.markdown-renderer :deep(h1) {
  font-size: 2em;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.3em;
}

.markdown-renderer :deep(h2) {
  font-size: 1.5em;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.3em;
}

.markdown-renderer :deep(h3) {
  font-size: 1.25em;
}

.markdown-renderer :deep(p) {
  margin: 1em 0;
}

.markdown-renderer :deep(a) {
  color: var(--accent);
  text-decoration: none;
}

.markdown-renderer :deep(a:hover) {
  text-decoration: underline;
}

.markdown-renderer :deep(ul),
.markdown-renderer :deep(ol) {
  margin: 1em 0;
  padding-left: 2em;
}

.markdown-renderer :deep(li) {
  margin: 0.5em 0;
}

.markdown-renderer :deep(blockquote) {
  margin: 1em 0;
  padding: 0.5em 1em;
  border-left: 4px solid var(--accent);
  background: rgba(233, 69, 96, 0.1);
  color: var(--text-secondary);
}

.markdown-renderer :deep(code) {
  padding: 0.2em 0.4em;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 0.9em;
}

.markdown-renderer :deep(pre) {
  position: relative;
  margin: 1em 0;
  padding: 1em;
  background: #0d1117;
  border-radius: 8px;
  overflow-x: auto;
}

.markdown-renderer :deep(pre code) {
  padding: 0;
  background: transparent;
  font-size: 0.875em;
  line-height: 1.5;
}

.markdown-renderer :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
}

.markdown-renderer :deep(th),
.markdown-renderer :deep(td) {
  padding: 0.5em 1em;
  border: 1px solid var(--border);
  text-align: left;
}

.markdown-renderer :deep(th) {
  background: rgba(255, 255, 255, 0.05);
  font-weight: 600;
}

.markdown-renderer :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 1em 0;
}

.markdown-renderer :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 2em 0;
}

/* 代码块复制按钮 */
.markdown-renderer :deep(pre)::before {
  content: '复制';
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px 8px;
  font-size: 12px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.markdown-renderer :deep(pre):hover::before {
  background: rgba(233, 69, 96, 0.3);
  color: white;
}

/* 亮色主题 */
:deep(.light-mode .markdown-renderer pre) {
  background: #f6f8fa;
}

:deep(.light-mode .markdown-renderer code) {
  background: rgba(0, 0, 0, 0.05);
}

:deep(.light-mode .markdown-renderer blockquote) {
  background: rgba(233, 69, 96, 0.05);
}
</style>
