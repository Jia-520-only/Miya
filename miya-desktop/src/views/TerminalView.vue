<script setup lang="ts">
import { ref, nextTick } from 'vue'
import axios from 'axios'
import NavigationTabs from '../components/NavigationTabs.vue'

const command = ref('')
const output = ref<any[]>([])
const isLoading = ref(false)
const terminalContainer = ref<HTMLElement>()

const executeCommand = async () => {
  if (!command.value.trim() || isLoading.value) return

  const cmd = command.value
  command.value = ''
  isLoading.value = true

  output.value.push({
    type: 'command',
    content: `$ ${cmd}`,
    time: new Date().toLocaleTimeString()
  })

  await nextTick()
  scrollToBottom()

  try {
    const response = await axios.post('http://localhost:8000/api/desktop/terminal/execute', null, {
      params: { command: cmd }
    })

    output.value.push({
      type: 'success',
      content: response.data.stdout || '(无输出)',
      exit_code: response.data.exit_code
    })

    if (response.data.stderr) {
      output.value.push({
        type: 'error',
        content: response.data.stderr
      })
    }
  } catch (error: any) {
    output.value.push({
      type: 'error',
      content: error.response?.data?.detail || error.message || '命令执行失败'
    })
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

const scrollToBottom = () => {
  if (terminalContainer.value) {
    terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight
  }
}

const clearTerminal = () => {
  output.value = []
}

const quickCommands = [
  'dir', 'ls -la', 'pwd', 'node --version', 'python --version',
  'git status', 'git log --oneline -5', 'pip list | grep miya'
]
</script>

<template>
  <div class="terminal-view">
    <!-- 导航标签 -->
    <div class="navigation-wrapper">
      <NavigationTabs />
    </div>

    <div class="terminal-header">
      <h2>终端</h2>
      <button class="clear-button" @click="clearTerminal">
        <i class="pi pi-trash"></i>
        清空
      </button>
    </div>

    <div class="terminal-output" ref="terminalContainer">
      <div v-if="output.length === 0" class="empty">
        <i class="pi pi-terminal"></i>
        <span>输入命令开始执行...</span>
      </div>

      <div v-for="(item, index) in output" :key="index" class="output-line" :class="item.type">
        <div class="line-time" v-if="item.time">{{ item.time }}</div>
        <div class="line-content" v-if="item.type === 'command'">{{ item.content }}</div>
        <div class="line-content" v-else-if="item.type === 'success'">{{ item.content }}</div>
        <div class="line-content" v-else-if="item.type === 'error'">{{ item.content }}</div>
      </div>

      <div v-if="isLoading" class="output-line loading">
        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>

    <div class="terminal-input">
      <div class="quick-commands">
        <button
          v-for="cmd in quickCommands"
          :key="cmd"
          class="quick-cmd-btn"
          @click="command = cmd; executeCommand()"
          :disabled="isLoading"
        >
          {{ cmd }}
        </button>
      </div>
      <div class="input-wrapper">
        <span class="prompt">$</span>
        <input
          v-model="command"
          @keydown.enter.prevent="executeCommand"
          placeholder="输入命令..."
          :disabled="isLoading"
          class="command-input"
        >
        <button class="execute-button" @click="executeCommand" :disabled="!command.trim() || isLoading">
          <i class="pi pi-play"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.terminal-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1a2e;
  position: relative;
}

.navigation-wrapper {
  z-index: 100;
}

.terminal-header {
  padding: 20px;
  border-bottom: 1px solid #2a2a4a;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.terminal-header h2 {
  margin: 0;
  font-size: 18px;
  color: #e0e0e0;
}

.clear-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #16213e;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.clear-button:hover {
  background: #2a2a4a;
  border-color: #e94560;
}

.terminal-output {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #0d1117;
  font-family: 'Courier New', Consolas, monospace;
  font-size: 13px;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 16px;
  color: #666;
}

.empty i {
  font-size: 48px;
}

.output-line {
  padding: 4px 0;
  line-height: 1.6;
}

.line-time {
  font-size: 11px;
  color: #666;
  margin-bottom: 4px;
}

.output-line.command .line-content {
  color: #e94560;
  font-weight: 600;
}

.output-line.success .line-content {
  color: #22c55e;
}

.output-line.error .line-content {
  color: #ef4444;
}

.typing-indicator {
  display: flex;
  gap: 4px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e94560;
  animation: blink 1.4s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes blink {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}

.terminal-input {
  padding: 20px;
  border-top: 1px solid #2a2a4a;
}

.quick-commands {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.quick-cmd-btn {
  padding: 6px 12px;
  background: #16213e;
  border: 1px solid #2a2a4a;
  border-radius: 4px;
  color: #a0a0a0;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-cmd-btn:hover:not(:disabled) {
  background: #2a2a4a;
  border-color: #e94560;
  color: #e0e0e0;
}

.quick-cmd-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #16213e;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  padding: 12px;
}

.prompt {
  color: #e94560;
  font-weight: bold;
  font-family: 'Courier New', Consolas, monospace;
}

.command-input {
  flex: 1;
  background: transparent;
  border: none;
  color: #e0e0e0;
  font-size: 14px;
  font-family: 'Courier New', Consolas, monospace;
  outline: none;
}

.command-input:disabled {
  opacity: 0.6;
}

.execute-button {
  width: 36px;
  height: 36px;
  background: #e94560;
  border: none;
  border-radius: 6px;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.execute-button:hover:not(:disabled) {
  background: #ff6b8a;
  transform: scale(1.05);
}

.execute-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
