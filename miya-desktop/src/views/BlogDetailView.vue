<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const post = ref<any>(null)
const isLoading = ref(true)

onMounted(async () => {
  try {
    const response = await axios.get(`http://localhost:8000/api/blog/${route.params.slug}`)
    post.value = response.data
  } catch (error) {
    console.error('加载文章失败:', error)
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <div class="blog-detail">
    <div v-if="isLoading">加载中...</div>
    <div v-else-if="post">
      <h1>{{ post.title }}</h1>
      <div class="meta">{{ post.created_at }} · {{ post.category }}</div>
      <div class="content" v-html="post.content"></div>
    </div>
  </div>
</template>

<style scoped>
.blog-detail {
  padding: 20px;
  color: #e0e0e0;
}
</style>
