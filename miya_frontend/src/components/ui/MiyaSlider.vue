<script setup lang="ts">
withDefaults(defineProps<{
  min?: number
  max?: number
  step?: number
  disabled?: boolean
}>(), {
  min: 0,
  max: 100,
  step: 1,
  disabled: false,
})

const model = defineModel<number>({ required: true })
</script>

<template>
  <input
    v-model.number="model"
    class="miya-slider"
    type="range"
    :min="min"
    :max="max"
    :step="step"
    :disabled="disabled"
  >
</template>

<style scoped>
.miya-slider {
  width: 100%;
  height: 18px;
  margin: 0;
  appearance: none;
  background: transparent;
  cursor: pointer;
}

.miya-slider::-webkit-slider-runnable-track {
  height: 4px;
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00adb5) 20%, transparent);
  border-radius: 2px;
  background: color-mix(in srgb, var(--miya-accent, #00adb5) 12%, rgba(0, 0, 0, 0.55));
}

.miya-slider::-webkit-slider-thumb {
  width: 14px;
  height: 14px;
  margin-top: -6px;
  appearance: none;
  border: 1px solid color-mix(in srgb, var(--miya-accent, #00adb5) 70%, white 10%);
  border-radius: 50%;
  background: var(--miya-accent, #00adb5);
  box-shadow: 0 0 8px color-mix(in srgb, var(--miya-accent, #00adb5) 40%, transparent);
}

.miya-slider:focus-visible {
  outline: 1px solid var(--miya-accent, #00adb5);
  outline-offset: 2px;
}

.miya-slider:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}
</style>
