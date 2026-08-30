<script setup lang="ts">
withDefaults(defineProps<{
  disabled?: boolean
}>(), {
  disabled: false,
})

const emit = defineEmits<{
  change: []
}>()
const model = defineModel<boolean>({ required: true })

function toggle() {
  if (model.value === undefined)
    return
  model.value = !model.value
  emit('change')
}
</script>

<template>
  <button
    type="button"
    class="miya-toggle"
    :class="{ checked: model }"
    role="switch"
    :aria-checked="model"
    :disabled="disabled"
    @click="toggle"
  >
    <span class="miya-toggle-thumb" />
  </button>
</template>

<style scoped>
.miya-toggle {
  position: relative;
  flex: 0 0 auto;
  width: 36px;
  height: 20px;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.42);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.miya-toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: rgba(228, 236, 240, 0.55);
  transition: transform 0.2s, background 0.2s, box-shadow 0.2s;
}

.miya-toggle.checked {
  border-color: color-mix(in srgb, var(--miya-accent, #00adb5) 65%, transparent);
  background: color-mix(in srgb, var(--miya-accent, #00adb5) 28%, rgba(0, 0, 0, 0.42));
}

.miya-toggle.checked .miya-toggle-thumb {
  transform: translateX(16px);
  background: var(--miya-accent, #00adb5);
  box-shadow: 0 0 8px color-mix(in srgb, var(--miya-accent, #00adb5) 55%, transparent);
}

.miya-toggle:focus-visible {
  outline: 1px solid var(--miya-accent, #00adb5);
  outline-offset: 2px;
}

.miya-toggle:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}
</style>
