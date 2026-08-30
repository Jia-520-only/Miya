<script  lang="ts">
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt()

function decodeHtmlEntities(s: string): string {
  return s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
}

export function render(content: string) {
  let html = md.render(content)
  // 将 ```tool-result 代码块转换为可折叠的 <details> 元素
  html = html.replace(
    /<pre><code class="language-tool-result">([\s\S]*?)<\/code><\/pre>/g,
    (_, raw) => {
      const decoded = decodeHtmlEntities(raw).trim()
      const lines = decoded.split('\n')
      const summary = lines[0] || '工具结果'
      const body = lines.slice(1).join('\n').trim()
      if (!body) {
        return `<div class="tool-result-line">${summary}</div>`
      }
      return `<details class="tool-result"><summary>${summary}</summary><pre class="tool-result-body">${body}</pre></details>`
    },
  )
  return html
}
</script>

<script setup lang="ts">
defineProps<{ source: string }>()
</script>

<template>
  <div v-html="render(source)" />
</template>
