<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const posts = ref<any[]>([])
const isLoading = ref(true)

onMounted(async () => {
  try {
    const response = await axios.get('http://localhost:8000/api/blog/posts')
    posts.value = response.data.posts || []
  } catch (error) {
    console.error('加载博客失败:', error)
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <div class="blog-view">
    <div class="blog-header">
      <h2>博客管理</h2>
      <router-link to="/blog/new" class="new-button">
        <i class="pi pi-plus"></i>
        新建文章
      </router-link>
    </div>

    <div class="blog-content">
      <div v-if="isLoading" class="loading">
        <div class="spinner"></div>
        <span>加载中...</span>
      </div>

      <div v-else-if="posts.length === 0" class="empty">
        <i class="pi pi-book"></i>
        <span>暂无文章</span>
      </div>

      <div v-else class="post-list">
        <div v-for="post in posts" :key="post.id" class="post-item">
          <router-link :to="`/blog/${post.slug}`" class="post-link">
            <div class="post-title">{{ post.title }}</div>
            <div class="post-meta">
              <span class="post-category">{{ post.category }}</span>
              <span class="post-date">{{ post.created_at }}</span>
            </div>
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.blog-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1a2e;
}

.blog-header {
  padding: 20px;
  border-bottom: 1px solid #2a2a4a;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.blog-header h2 {
  margin: 0;
  font-size: 18px;
  color: #e0e0e0;
}

.new-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #e94560;
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.new-button:hover {
  background: #ff6b8a;
  transform: translateY(-1px);
}

.blog-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 16px;
  color: #a0a0a0;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #2a2a4a;
  border-top-color: #e94560;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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

.post-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.post-item {
  background: #16213e;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.2s;
}

.post-item:hover {
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(233, 69, 96, 0.1);
}

.post-link {
  display: block;
  padding: 16px;
  text-decoration: none;
  color: inherit;
}

.post-title {
  font-size: 15px;
  font-weight: 500;
  color: #e0e0e0;
  margin-bottom: 8px;
}

.post-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #a0a0a0;
}

.post-category {
  padding: 2px 8px;
  background: rgba(233, 69, 96, 0.1);
  border-radius: 4px;
  color: #e94560;
}
</style>
