<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

interface IoTDevice {
  id: string
  name: string
  type: string
  status: 'online' | 'offline'
  ip: string
  lastSeen: string
  capabilities: string[]
}

const devices = ref<IoTDevice[]>([])
const isLoading = ref(false)
const selectedDevice = ref<IoTDevice | null>(null)
const commandOutput = ref('')

// 示例设备数据
const mockDevices: IoTDevice[] = [
  {
    id: '1',
    name: '客厅灯光',
    type: 'light',
    status: 'online',
    ip: '192.168.1.100',
    lastSeen: new Date().toISOString(),
    capabilities: ['on', 'off', 'brightness', 'color']
  },
  {
    id: '2',
    name: '空调控制',
    type: 'climate',
    status: 'online',
    ip: '192.168.1.101',
    lastSeen: new Date().toISOString(),
    capabilities: ['on', 'off', 'temperature', 'mode']
  },
  {
    id: '3',
    name: '智能门锁',
    type: 'security',
    status: 'offline',
    ip: '192.168.1.102',
    lastSeen: new Date(Date.now() - 3600000).toISOString(),
    capabilities: ['lock', 'unlock', 'status']
  },
  {
    id: '4',
    name: '监控摄像头',
    type: 'camera',
    status: 'online',
    ip: '192.168.1.103',
    lastSeen: new Date().toISOString(),
    capabilities: ['stream', 'snapshot', 'ptz']
  }
]

const loadDevices = () => {
  // 模拟加载设备列表
  // 实际应用中应该从后端 API 获取
  devices.value = mockDevices
}

const selectDevice = (device: IoTDevice) => {
  selectedDevice.value = device
  commandOutput.value = ''
}

const sendCommand = async (command: string, value?: any) => {
  if (!selectedDevice.value) return

  commandOutput.value = `正在发送命令到 ${selectedDevice.value.name}...\n`
  commandOutput.value += `命令: ${command}${value ? ` = ${value}` : ''}\n\n`

  try {
    const response = await axios.post('http://localhost:8000/api/desktop/terminal/execute', null, {
      params: {
        command: `echo "IoT Control: ${selectedDevice.value.name} - ${command}"`
      }
    })

    commandOutput.value += `执行结果:\n${response.data.stdout}\n`
    if (response.data.exit_code === 0) {
      commandOutput.value += '\n✅ 命令执行成功'
    } else {
      commandOutput.value += `\n⚠️ 退出码: ${response.data.exit_code}`
    }
  } catch (error: any) {
    commandOutput.value += `❌ 错误: ${error.message}\n`
  }
}

const togglePower = () => {
  const device = selectedDevice.value
  if (!device) return

  const isOnline = device.status === 'online'
  sendCommand('power', isOnline ? 'off' : 'on')
}

const scanNetwork = async () => {
  isLoading.value = true
  commandOutput.value = '正在扫描网络中的 IoT 设备...\n\n'

  try {
    const response = await axios.post('http://localhost:8000/api/desktop/terminal/execute', null, {
      params: {
        command: 'arp -a',
        timeout: 30
      }
    })

    commandOutput.value += `扫描结果:\n${response.data.stdout}\n`
    commandOutput.value += `\n发现 ${devices.value.length} 个已配置设备\n`
  } catch (error: any) {
    commandOutput.value += `❌ 扫描失败: ${error.message}\n`
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadDevices()
})

const getDeviceIcon = (type: string): string => {
  const icons: Record<string, string> = {
    light: 'pi pi-lightbulb',
    climate: 'pi pi-sun',
    security: 'pi pi-lock',
    camera: 'pi pi-video',
    sensor: 'pi pi-chart-line',
    switch: 'pi pi-clone',
    default: 'pi pi-microchip'
  }
  return icons[type] || icons.default
}
</script>

<template>
  <div class="iot-view">
    <div class="iot-header">
      <h2>物联网控制中心</h2>
      <button class="scan-btn" @click="scanNetwork" :disabled="isLoading">
        <i class="pi pi-search" :class="{ spinning: isLoading }"></i>
        扫描网络
      </button>
    </div>

    <div class="iot-content">
      <div class="devices-list">
        <div
          v-for="device in devices"
          :key="device.id"
          class="device-card"
          :class="{ selected: selectedDevice?.id === device.id, offline: device.status === 'offline' }"
          @click="selectDevice(device)"
        >
          <div class="device-icon">
            <i :class="getDeviceIcon(device.type)"></i>
          </div>
          <div class="device-info">
            <div class="device-name">{{ device.name }}</div>
            <div class="device-meta">
              <span class="device-status" :class="device.status">
                {{ device.status === 'online' ? '在线' : '离线' }}
              </span>
              <span class="device-ip">{{ device.ip }}</span>
            </div>
            <div class="device-caps">
              <span
                v-for="cap in device.capabilities"
                :key="cap"
                class="cap-badge"
              >
                {{ cap }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="devices.length === 0" class="empty">
          <i class="pi pi-microchip"></i>
          <span>暂无设备</span>
        </div>
      </div>

      <div v-if="selectedDevice" class="device-panel">
        <div class="panel-header">
          <h3>{{ selectedDevice.name }}</h3>
          <button class="close-btn" @click="selectedDevice = null">
            <i class="pi pi-times"></i>
          </button>
        </div>

        <div class="panel-content">
          <div class="device-info-full">
            <div class="info-item">
              <span class="label">类型:</span>
              <span class="value">{{ selectedDevice.type }}</span>
            </div>
            <div class="info-item">
              <span class="label">IP 地址:</span>
              <span class="value">{{ selectedDevice.ip }}</span>
            </div>
            <div class="info-item">
              <span class="label">状态:</span>
              <span class="value" :class="selectedDevice.status">
                {{ selectedDevice.status === 'online' ? '在线' : '离线' }}
              </span>
            </div>
            <div class="info-item">
              <span class="label">最后连接:</span>
              <span class="value">{{ new Date(selectedDevice.lastSeen).toLocaleString() }}</span>
            </div>
          </div>

          <div class="device-actions">
            <h4>控制操作</h4>
            <div class="action-grid">
              <button
                class="action-btn primary"
                @click="togglePower"
                :disabled="selectedDevice.status === 'offline'"
              >
                <i :class="selectedDevice.status === 'online' ? 'pi pi-power-off' : 'pi pi-play'"></i>
                {{ selectedDevice.status === 'online' ? '关闭' : '开启' }}
              </button>

              <button
                v-for="cap in selectedDevice.capabilities"
                :key="cap"
                class="action-btn"
                @click="sendCommand(cap)"
                :disabled="selectedDevice.status === 'offline'"
              >
                <i class="pi pi-sliders-h"></i>
                {{ cap }}
              </button>
            </div>
          </div>

          <div v-if="commandOutput" class="command-output">
            <h4>命令输出</h4>
            <pre>{{ commandOutput }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.iot-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1a2e;
}

.iot-header {
  padding: 20px;
  border-bottom: 1px solid #2a2a4a;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.iot-header h2 {
  margin: 0;
  font-size: 18px;
  color: #e0e0e0;
}

.scan-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #22c55e;
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.scan-btn:hover:not(:disabled) {
  background: #16a34a;
  transform: translateY(-1px);
}

.scan-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.scan-btn i.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.iot-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.devices-list {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  border-right: 1px solid #2a2a4a;
}

.device-card {
  background: #16213e;
  border: 2px solid transparent;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.device-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(233, 69, 96, 0.1);
}

.device-card.selected {
  border-color: #e94560;
  background: rgba(233, 69, 96, 0.05);
}

.device-card.offline {
  opacity: 0.5;
}

.device-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: linear-gradient(135deg, #e94560, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 20px;
  flex-shrink: 0;
}

.device-info {
  flex: 1;
  min-width: 0;
}

.device-name {
  font-size: 15px;
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 6px;
}

.device-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 12px;
}

.device-status {
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.device-status.online {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.device-status.offline {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.device-ip {
  color: #a0a0a0;
  font-family: 'Courier New', Consolas, monospace;
}

.device-caps {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.cap-badge {
  padding: 2px 8px;
  background: rgba(233, 69, 96, 0.1);
  border-radius: 4px;
  font-size: 11px;
  color: #e94560;
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

.device-panel {
  width: 400px;
  background: #0d1117;
  border-left: 1px solid #2a2a4a;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 16px 20px;
  border-bottom: 1px solid #2a2a4a;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: #e0e0e0;
}

.close-btn {
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #a0a0a0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #2a2a4a;
  color: #e0e0e0;
}

.panel-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.device-info-full {
  background: #16213e;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #2a2a4a;
}

.info-item:last-child {
  border-bottom: none;
}

.info-item .label {
  color: #a0a0a0;
  font-size: 13px;
}

.info-item .value {
  color: #e0e0e0;
  font-size: 13px;
  font-weight: 500;
}

.info-item .value.online {
  color: #22c55e;
}

.info-item .value.offline {
  color: #ef4444;
}

.device-actions {
  margin-bottom: 20px;
}

.device-actions h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #e0e0e0;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.action-btn {
  padding: 12px;
  background: #16213e;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  color: #e0e0e0;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  background: #2a2a4a;
  border-color: #e94560;
  transform: translateY(-1px);
}

.action-btn.primary {
  background: #e94560;
  border-color: #e94560;
}

.action-btn.primary:hover:not(:disabled) {
  background: #ff6b8a;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.command-output {
  background: #16213e;
  border-radius: 8px;
  overflow: hidden;
}

.command-output h4 {
  margin: 0 0 8px 0;
  padding: 12px;
  font-size: 12px;
  color: #a0a0a0;
  border-bottom: 1px solid #2a2a4a;
}

.command-output pre {
  margin: 0;
  padding: 12px;
  font-size: 12px;
  color: #22c55e;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
