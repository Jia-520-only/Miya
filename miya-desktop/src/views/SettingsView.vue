<script setup lang="ts">
import { useRouter } from 'vue-router'
import SettingsPanel from '../components/SettingsPanel.vue'

const router = useRouter()

function goBack() {
  router.push('/chat')
}
</script>

<template>
  <div class="settings-view">
    <div class="settings-header">
      <button class="back-btn" @click="goBack">
        <i class="pi pi-arrow-left"></i>
        <span>返回</span>
      </button>
    </div>
    <SettingsPanel />
  </div>
</template>

<style scoped>
.settings-view {
  height: 100%;
  overflow-y: auto;
}

.settings-header {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-secondary);
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(45, 212, 191, 0.1);
  border: 1px solid rgba(45, 212, 191, 0.3);
  border-radius: 8px;
  color: #2dd4bf;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.back-btn:hover {
  background: rgba(45, 212, 191, 0.2);
  border-color: rgba(45, 212, 191, 0.5);
}
</style>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1a2e;
}

.settings-header {
  padding: 20px;
  border-bottom: 1px solid #2a2a4a;
}

.settings-header h2 {
  margin: 0;
  font-size: 18px;
  color: #e0e0e0;
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.settings-section {
  background: #16213e;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}

.settings-section h3 {
  margin: 0 0 16px 0;
  font-size: 14px;
  color: #e0e0e0;
  font-weight: 600;
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #2a2a4a;
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-item label {
  font-size: 13px;
  color: #a0a0a0;
}

.setting-item input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}
</style>
