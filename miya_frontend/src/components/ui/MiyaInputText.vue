<script setup lang="ts">
const model = defineModel<string | number | null>()
</script>

<template>
  <input v-model="model" type="text" class="miya-input-text">
</template>

<style scoped>
.miya-input-text {
  box-sizing: border-box;
  border-radius: 4px;
  outline: none;
  font: inherit;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.miya-input-text:focus {
  border-color: color-mix(in srgb, var(--miya-accent, #00adb5) 55%, transparent) !important;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--miya-accent, #00adb5) 12%, transparent);
}

.miya-input-text:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
</style>
