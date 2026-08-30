<script setup lang="ts">
import { computed, ref } from 'vue'

export interface TemplateField {
  key: string
  label: string
  placeholder?: string
}

const props = defineProps<{
  modelValue: Record<string, any>
  templateFields?: TemplateField[]
}>()

const emit = defineEmits<{ (e: 'update:modelValue', v: Record<string, any>): void }>()

const fields = computed(() => props.modelValue || {})

function setField(key: string, value: any) {
  const next: Record<string, any> = { ...fields.value }
  if (value === '' || value == null)
    delete next[key]
  else
    next[key] = value
  emit('update:modelValue', next)
}

const templateKeys = computed(() => new Set((props.templateFields || []).map(f => f.key)))
const customEntries = computed(() => Object.entries(fields.value).filter(([k]) => !templateKeys.value.has(k)))

const newKey = ref('')
const newValue = ref('')

function addCustom() {
  const key = newKey.value.trim()
  if (!key)
    return
  setField(key, newValue.value)
  newKey.value = ''
  newValue.value = ''
}
</script>

<template>
  <div class="fields-editor">
    <div v-for="tf in templateFields" :key="tf.key" class="field-row">
      <span class="field-label">{{ tf.label }}</span>
      <input
        class="field-input"
        :value="fields[tf.key] ?? ''"
        :placeholder="tf.placeholder || ''"
        @input="setField(tf.key, ($event.target as HTMLInputElement).value)"
      />
    </div>
    <div v-for="[k, v] in customEntries" :key="k" class="field-row">
      <span class="field-label field-key">{{ k }}</span>
      <input
        class="field-input"
        :value="v"
        @input="setField(k, ($event.target as HTMLInputElement).value)"
      />
      <button class="btn-sm btn-danger" type="button" @click="setField(k, '')">×</button>
    </div>
    <div class="field-row field-new">
      <input v-model="newKey" class="field-new-key" placeholder="新参数名 (如 产地)" />
      <input v-model="newValue" class="field-input" placeholder="值" />
      <button class="btn-sm" type="button" @click="addCustom">+ 添加</button>
    </div>
  </div>
</template>

<style scoped>
.fields-editor {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}
.field-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.field-label {
  min-width: 72px;
  font-size: 0.7rem;
  color: var(--miya-text-dim);
  flex-shrink: 0;
}
.field-key {
  color: var(--miya-gold);
}
.field-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent);
  border-radius: 6px;
  padding: 0.4rem 0.55rem;
  color: var(--miya-text);
  font-size: 0.78rem;
  outline: none;
  min-width: 0;
}
.field-new {
  margin-top: 0.15rem;
  padding-top: 0.4rem;
  border-top: 1px dashed color-mix(in srgb, var(--miya-border) 20%, transparent);
}
.field-new-key {
  width: 130px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid color-mix(in srgb, var(--miya-border) 20%, transparent);
  border-radius: 6px;
  padding: 0.4rem 0.55rem;
  color: var(--miya-text);
  font-size: 0.78rem;
  outline: none;
}
</style>
