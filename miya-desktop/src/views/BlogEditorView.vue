<script setup lang="ts">
import { ref } from 'vue'

const title = ref('')
const content = ref('')
const category = ref('技术')
const tags = ref('')

const savePost = () => {
  console.log('保存文章:', { title: title.value, content: content.value })
}
</script>

<template>
  <div class="blog-editor">
    <div class="editor-header">
      <h2>编辑文章</h2>
      <button @click="savePost">保存</button>
    </div>
    <input v-model="title" placeholder="文章标题" class="title-input" />
    <textarea v-model="content" placeholder="文章内容" class="content-input" rows="20"></textarea>
  </div>
</template>

<style scoped>
.blog-editor {
  padding: 20px;
}
</style>
