<script setup lang="ts">
import { ref, onMounted } from 'vue'
import API from '@/api/art'
import type { ArtProviderInfo } from '@/types/art'

const emit = defineEmits<{
  generate: [params: {
    prompt: string
    provider: string
    negativePrompt: string
    width: number
    height: number
    steps: number
    cfgScale: number
    seed: number | null
    numImages: number
    style: string
  }]
}>()

const props = defineProps<{ generating: boolean }>()

const providers = ref<ArtProviderInfo[]>([])
const prompt = ref('')
const negativePrompt = ref('')
const selectedProvider = ref('')
const width = ref(1024)
const height = ref(1024)
const steps = ref(30)
const cfgScale = ref(7)
const seed = ref<number | null>(null)
const numImages = ref(1)
const style = ref('')
const showAdvanced = ref(false)

const sizePresets = [
  { label: '1:1 (1024)', w: 1024, h: 1024 },
  { label: '3:2 (1536)', w: 1536, h: 1024 },
  { label: '2:3 (1024)', w: 1024, h: 1536 },
  { label: '16:9 (1792)', w: 1792, h: 1024 },
  { label: '9:16 (1024)', w: 1024, h: 1792 },
]

const numImageOptions = [1, 2, 3, 4]

onMounted(async () => {
  try {
    const res = await API.getProviders()
    providers.value = res.providers || []
    const available = providers.value.find(p => p.available)
    if (available) selectedProvider.value = available.name
  } catch {}
})

function generate() {
  if (!prompt.value.trim() || props.generating) return
  emit('generate', {
    prompt: prompt.value.trim(),
    provider: selectedProvider.value,
    negativePrompt: negativePrompt.value.trim(),
    width: width.value,
    height: height.value,
    steps: steps.value,
    cfgScale: cfgScale.value,
    seed: seed.value,
    numImages: numImages.value,
    style: style.value,
  })
}

function selectSize(w: number, h: number) {
  width.value = w
  height.value = h
}

const styleTags = ['写实', '动漫', '油画', '水彩', '素描', '像素', '赛博朋克', '水墨']
</script>

<template>
  <div class="p-3 space-y-3">
    <!-- Provider -->
    <div>
      <label class="text-xs text-gray-500 mb-1 block">绘画引擎</label>
      <select v-model="selectedProvider" class="art-select text-sm">
        <option value="">自动选择</option>
        <option v-for="p in providers" :key="p.name" :value="p.name">
          {{ p.display_name }}
          <template v-if="p.available !== undefined"> {{ p.available ? '✓' : '✗' }}</template>
        </option>
      </select>
    </div>

    <!-- Prompt -->
    <div>
      <label class="text-xs text-gray-500 mb-1 block">画面描述 (Prompt)</label>
      <textarea
        v-model="prompt"
        class="art-input h-24 resize-none text-sm"
        placeholder="描述你想要的画面...&#10;&#10;例如: 一只白猫坐在屋顶, 星空背景, 吉卜力风格"
        @keydown.ctrl.enter="generate"
      />
    </div>

    <!-- Negative -->
    <div>
      <label class="text-xs text-gray-500 mb-1 block">负面提示词</label>
      <input
        v-model="negativePrompt"
        class="art-input text-sm"
        placeholder="不想要的元素, 用逗号分隔"
      >
    </div>

    <!-- Style quick tags -->
    <div>
      <label class="text-xs text-gray-500 mb-1 block">风格</label>
      <div class="flex flex-wrap gap-1">
        <button
          v-for="tag in styleTags"
          :key="tag"
          class="px-2 py-0.5 rounded text-xs transition-colors"
          :class="style === tag
            ? 'bg-blue-600 text-white'
            : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
          @click="style = style === tag ? '' : tag"
        >
          {{ tag }}
        </button>
      </div>
    </div>

    <!-- Size presets -->
    <div>
      <label class="text-xs text-gray-500 mb-1 block">尺寸</label>
      <div class="flex flex-wrap gap-1">
        <button
          v-for="preset in sizePresets"
          :key="preset.label"
          class="px-2 py-0.5 rounded text-xs transition-colors"
          :class="width === preset.w && height === preset.h
            ? 'bg-blue-600 text-white'
            : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
          @click="selectSize(preset.w, preset.h)"
        >
          {{ preset.label }}
        </button>
      </div>
    </div>

    <!-- Num images -->
    <div>
      <label class="text-xs text-gray-500 mb-1 block">生成数量</label>
      <div class="flex gap-1">
        <button
          v-for="n in numImageOptions"
          :key="n"
          class="w-8 h-7 rounded text-xs transition-colors"
          :class="numImages === n
            ? 'bg-blue-600 text-white'
            : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
          @click="numImages = n"
        >
          {{ n }}
        </button>
      </div>
    </div>

    <!-- Advanced toggle -->
    <button
      class="text-xs text-gray-500 hover:text-gray-300 transition-colors"
      @click="showAdvanced = !showAdvanced"
    >
      {{ showAdvanced ? '收起高级选项 ▲' : '展开高级选项 ▼' }}
    </button>

    <!-- Advanced -->
    <div v-if="showAdvanced" class="space-y-2">
      <div>
        <label class="text-xs text-gray-500 block">Steps: {{ steps }}</label>
        <input v-model.number="steps" type="range" min="10" max="100" class="w-full accent-blue-500">
      </div>
      <div>
        <label class="text-xs text-gray-500 block">CFG Scale: {{ cfgScale }}</label>
        <input v-model.number="cfgScale" type="range" min="1" max="20" step="0.5" class="w-full accent-blue-500">
      </div>
      <div>
        <label class="text-xs text-gray-500 block">Seed</label>
        <input
          v-model.number="seed"
          type="number"
          class="art-input text-sm"
          placeholder="留空随机"
        >
      </div>
    </div>

    <!-- Generate button -->
    <button
      class="w-full py-2.5 rounded-lg text-sm font-medium transition-all duration-200"
      :class="generating
        ? 'bg-gray-700 text-gray-400 cursor-wait'
        : 'bg-blue-600 hover:bg-blue-500 text-white'"
      :disabled="generating || !prompt.trim()"
      @click="generate"
    >
      <template v-if="generating">
        <span class="inline-block w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin align-middle mr-2" />
        生成中...
      </template>
      <template v-else>
        生成图片 ⌘↵
      </template>
    </button>
  </div>
</template>
