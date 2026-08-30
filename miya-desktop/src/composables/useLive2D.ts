import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Live2DModel } from 'pixi-live2d-display'
import { Application } from 'pixi.js'

interface Live2DConfig {
  modelPath: string
  width?: number
  height?: number
  onLoaded?: (model: Live2DModel) => void
  onError?: (error: Error) => void
}

export function useLive2D(config: Live2DConfig) {
  const canvasRef = ref<HTMLCanvasElement | null>(null)
  const app = ref<Application | null>(null)
  const model = ref<Live2DModel | null>(null)
  const isLoading = ref(true)
  const currentExpression = ref<string>('')

  const emotionToExpressionMap: Record<string, string> = {
    '开心': 'expression3',
    '兴奋': 'expression4',
    '害羞': 'expression5',
    '平静': '',
    '悲伤': 'expression2',
    '生气': 'expression1',
    '惊讶': 'expression3',
    '思考': '',
    '唱歌': 'expression7',
    '专注': '',
    '调皮': 'expression8',
    '嘘声': 'expression6'
  }

  const loadModel = async () => {
    if (!canvasRef.value || app.value) return

    try {
      isLoading.value = true

      const newApp = new Application({
        view: canvasRef.value,
        width: config.width || 300,
        height: config.height || 400,
        backgroundAlpha: 0,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true
      })

      app.value = newApp

      const live2dModel = await Live2DModel.from(config.modelPath)

      live2dModel.scale.set(0.8)
      live2dModel.x = newApp.screen.width / 2
      live2dModel.y = newApp.screen.height / 2 + 50
      live2dModel.anchor.set(0.5, 0.5)

      newApp.stage.addChild(live2dModel)
      model.value = live2dModel

      isLoading.value = false
      config.onLoaded?.(live2dModel)
    } catch (error) {
      console.error('Live2D加载失败:', error)
      isLoading.value = false
      config.onError?.(error as Error)
    }
  }

  const setExpression = (emotion: string) => {
    if (!model.value) return

    const expressionName = emotionToExpressionMap[emotion] || ''

    if (expressionName) {
      try {
        model.value.internalModel.motionManager.expressionManager?.setExpression(
          expressionName
        )
        currentExpression.value = expressionName
      } catch (error) {
        console.warn('设置表情失败:', emotion, error)
      }
    } else {
      currentExpression.value = ''
    }
  }

  const setMouthOpen = (open: number) => {
    if (!model.value) return
    model.value.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', open)
  }

  const setEyeOpen = (open: number) => {
    if (!model.value) return
    model.value.internalModel.coreModel.setParameterValueById('ParamEyeLOpen', open)
    model.value.internalModel.coreModel.setParameterValueById('ParamEyeROpen', open)
  }

  const lookAt = (x: number, y: number) => {
    if (!model.value) return
    model.value.internalModel.coreModel.setParameterValueById('ParamEyeBallX', x)
    model.value.internalModel.coreModel.setParameterValueById('ParamEyeBallY', y)
  }

  const breathe = () => {
    if (!model.value) return
    const breathValue = Math.sin(Date.now() / 1000) * 0.5 + 0.5
    model.value.internalModel.coreModel.setParameterValueById('ParamBreath', breathValue)
  }

  let breatheInterval: number

  const startBreathing = () => {
    breatheInterval = window.setInterval(() => {
      breathe()
    }, 16)
  }

  const stopBreathing = () => {
    if (breatheInterval) {
      clearInterval(breatheInterval)
    }
  }

  const destroy = () => {
    stopBreathing()

    if (model.value) {
      model.value.destroy()
      model.value = null
    }

    if (app.value) {
      app.value.destroy(true)
      app.value = null
    }
  }

  onMounted(() => {
    loadModel().then(() => {
      startBreathing()
    })
  })

  onUnmounted(() => {
    destroy()
  })

  return {
    canvasRef,
    model,
    isLoading,
    currentExpression,
    setExpression,
    setMouthOpen,
    setEyeOpen,
    lookAt,
    destroy
  }
}
