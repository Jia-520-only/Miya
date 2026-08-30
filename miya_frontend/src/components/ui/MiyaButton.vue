<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
}>(), {
  variant: 'secondary',
  size: 'md',
  disabled: false,
  type: 'button',
})
</script>

<template>
  <button class="miya-button" :class="[`is-${variant}`, `is-${size}`]" :type="type" :disabled="disabled">
    <slot />
  </button>
</template>

<style scoped>
.miya-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--miya-space-2);
  min-height: 34px;
  padding: 0 var(--miya-space-3);
  color: var(--miya-text-body);
  background: var(--miya-surface-2);
  border: 1px solid var(--miya-line);
  border-radius: var(--miya-radius-sm);
  cursor: pointer;
  transition: color var(--miya-duration-fast), background var(--miya-duration-fast), border-color var(--miya-duration-fast), transform var(--miya-duration-fast);
}
.miya-button:hover:not(:disabled) {
  color: var(--miya-text-strong);
  border-color: var(--miya-line-strong);
  transform: translateY(-1px);
}
.miya-button:active:not(:disabled) { transform: translateY(0); }
.miya-button:disabled { opacity: 0.42; cursor: not-allowed; }
.is-sm { min-height: 28px; padding-inline: var(--miya-space-2); font-size: 0.72rem; }
.is-primary { color: #071014; background: var(--miya-accent-soft); border-color: var(--miya-accent-soft); }
.is-primary:hover:not(:disabled) { color: #020809; background: var(--miya-accent-bright); }
.is-ghost { background: transparent; border-color: transparent; }
.is-danger { color: var(--miya-danger); background: rgba(231, 125, 135, 0.07); border-color: rgba(231, 125, 135, 0.24); }
</style>
