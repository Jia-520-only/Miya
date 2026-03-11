<script setup lang="ts">
</script>

<template>
  <div class="settings-view">
    <div class="settings-header">
      <h2>设置</h2>
    </div>

    <div class="settings-content">
      <div class="settings-section">
        <h3>通用设置</h3>
        <div class="setting-item">
          <label>开机自启动</label>
          <input type="checkbox" />
        </div>
        <div class="setting-item">
          <label>系统托盘最小化</label>
          <input type="checkbox" checked />
        </div>
      </div>

      <div class="settings-section">
        <h3>悬浮球设置</h3>
        <div class="setting-item">
          <label>启用悬浮球</label>
          <input type="checkbox" checked />
        </div>
        <div class="setting-item">
          <label>失焦自动收起</label>
          <input type="checkbox" />
        </div>
      </div>

      <div class="settings-section">
        <h3>外观设置</h3>
        <div class="setting-item">
          <label>暗色模式</label>
          <input type="checkbox" checked disabled />
        </div>
      </div>
    </div>
  </div>
</template>

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
