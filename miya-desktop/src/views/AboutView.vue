<script setup lang="ts">
</script>

<template>
  <div class="about-view">
    <div class="about-content">
      <div class="logo-section">
        <div class="logo-placeholder">弥娅</div>
        <h1>弥娅</h1>
        <p class="tagline">数字生命伴侣</p>
      </div>

      <div class="info-section">
        <div class="info-item">
          <span class="label">版本</span>
          <span class="value">1.0.0</span>
        </div>
        <div class="info-item">
          <span class="label">架构</span>
          <span class="value">蛛网式模块化架构</span>
        </div>
        <div class="info-item">
          <span class="label">框架</span>
          <span class="value">Vue 3 + Electron</span>
        </div>
      </div>

      <div class="description">
        <p>弥娅是一个基于蛛网式模块化架构的数字生命伴侣系统,具备动态人格、情感演化、记忆管理、多模型智能调度等核心能力。</p>
      </div>

      <div class="links">
        <a href="https://github.com/Jia-520-only/Miya" target="_blank">
          <i class="pi pi-github"></i>
          GitHub 仓库
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.about-view {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: #1a1a2e;
}

.about-content {
  max-width: 600px;
  padding: 40px;
  text-align: center;
}

.logo-section {
  margin-bottom: 40px;
}

.logo {
  width: 120px;
  height: 120px;
  border-radius: 24px;
  margin-bottom: 20px;
  box-shadow: 0 8px 32px rgba(233, 69, 96, 0.3);
}

.logo-section h1 {
  font-size: 48px;
  font-weight: 700;
  background: linear-gradient(135deg, #e94560, #ff6b8a);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 8px 0;
}

.tagline {
  font-size: 16px;
  color: #a0a0a0;
  margin: 0;
}

.info-section {
  background: #16213e;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #2a2a4a;
}

.info-item:last-child {
  border-bottom: none;
}

.info-item .label {
  font-size: 13px;
  color: #a0a0a0;
}

.info-item .value {
  font-size: 13px;
  color: #e0e0e0;
  font-weight: 500;
}

.description {
  margin-bottom: 32px;
  line-height: 1.8;
  color: #a0a0a0;
  font-size: 14px;
}

.links {
  display: flex;
  justify-content: center;
  gap: 16px;
}

.links a {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: #16213e;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  color: #e0e0e0;
  text-decoration: none;
  transition: all 0.2s;
}

.links a:hover {
  background: #2a2a4a;
  border-color: #e94560;
  transform: translateY(-2px);
}

.links a i {
  font-size: 18px;
}
</style>
