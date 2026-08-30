<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Prism, Highlighter } from '@vueuse/integrations/usePrismjs'

interface Props {
  code: string
  language?: string
  showLineNumbers?: boolean
  copyButton?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  language: 'text',
  showLineNumbers: true,
  copyButton: true
})

const codeElement = ref<HTMLElement>()
const isCopied = ref(false)

let prismInstance: Highlighter | null = null

onMounted(async () => {
  if (props.language !== 'text') {
    // 动态导入 prismjs
    const { default: Prism } = await import('prismjs')
    // 导入语言包
    await import(`prismjs/components/prism-${props.language}`)
    prismInstance = Prism
    highlightCode()
  }
})

onUnmounted(() => {
  prismInstance = null
})

function highlightCode() {
  if (codeElement.value && prismInstance) {
    prismInstance.highlightElement(codeElement.value)
  }
}

async function copyCode() {
  try {
    await navigator.clipboard.writeText(props.code)
    isCopied.value = true
    setTimeout(() => {
      isCopied.value = false
    }, 2000)
  } catch (error) {
    console.error('Failed to copy:', error)
  }
}

const lines = computed(() => {
  return props.code.split('\n')
})
</script>

<template>
  <div class="code-block">
    <div v-if="copyButton" class="code-header">
      <span class="language">{{ language }}</span>
      <button class="copy-button" @click="copyCode" :class="{ copied: isCopied }">
        {{ isCopied ? '已复制' : '复制' }}
      </button>
    </div>
    <div class="code-content">
      <div v-if="showLineNumbers" class="line-numbers">
        <span v-for="(_, index) in lines" :key="index" class="line-number">
          {{ index + 1 }}
        </span>
      </div>
      <pre class="code-pre"><code ref="codeElement" :class="`language-${language}`">{{ code }}</code></pre>
    </div>
  </div>
</template>

<style scoped>
.code-block {
  border-radius: 8px;
  overflow: hidden;
  background: #0d1117;
}

.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.language {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.copy-button {
  padding: 4px 12px;
  font-size: 12px;
  background: rgba(233, 69, 96, 0.2);
  border: 1px solid rgba(233, 69, 96, 0.3);
  border-radius: 4px;
  color: #e94560;
  cursor: pointer;
  transition: all 0.2s;
}

.copy-button:hover {
  background: rgba(233, 69, 96, 0.3);
}

.copy-button.copied {
  background: rgba(34, 197, 94, 0.2);
  border-color: rgba(34, 197, 94, 0.3);
  color: #22c55e;
}

.code-content {
  display: flex;
  overflow-x: auto;
}

.line-numbers {
  padding: 12px 8px;
  background: rgba(0, 0, 0, 0.2);
  text-align: right;
  user-select: none;
  border-right: 1px solid rgba(255, 255, 255, 0.1);
}

.line-number {
  display: block;
  font-size: 12px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.3);
}

.code-pre {
  flex: 1;
  margin: 0;
  padding: 12px;
  overflow-x: auto;
}

.code-pre code {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}

/* 亮色主题 */
:deep(.light-mode .code-block) {
  background: #f6f8fa;
}

:deep(.light-mode .code-header) {
  background: rgba(0, 0, 0, 0.03);
  border-bottom-color: rgba(0, 0, 0, 0.1);
}

:deep(.light-mode .line-numbers) {
  background: rgba(0, 0, 0, 0.03);
  border-right-color: rgba(0, 0, 0, 0.1);
}

:deep(.light-mode .line-number) {
  color: rgba(0, 0, 0, 0.3);
}
</style>
