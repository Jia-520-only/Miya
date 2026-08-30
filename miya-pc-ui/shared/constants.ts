// Live2D 情绪映射
export const EMOTION_TO_LIVE2D: Record<string, any> = {
  joy: {
    motion: 'idle_smile',
    expression: 'smile',
    intensityMap: {
      low: 'idle_smile_1',
      medium: 'idle_smile_2',
      high: 'idle_smile_3'
    }
  },
  sadness: {
    motion: 'sad',
    expression: 'sad',
    intensityMap: {
      low: 'sad_1',
      medium: 'sad_2',
      high: 'sad_3'
    }
  },
  anger: {
    motion: 'angry',
    expression: 'angry',
    intensityMap: {
      low: 'angry_1',
      medium: 'angry_2',
      high: 'angry_3'
    }
  },
  fear: {
    motion: 'surprise',
    expression: 'surprise',
    intensityMap: {
      low: 'surprise_1',
      medium: 'surprise_2',
      high: 'surprise_3'
    }
  },
  surprise: {
    motion: 'surprise',
    expression: 'surprise',
    intensityMap: {
      low: 'surprise_1',
      medium: 'surprise_2',
      high: 'surprise_3'
    }
  }
}

// 情绪颜色
export const EMOTION_COLORS = {
  joy: '#FFD700',
  sadness: '#4169E1',
  anger: '#FF4500',
  fear: '#9932CC',
  surprise: '#FF69B4'
}

// 情绪中文名称
export const EMOTION_NAMES = {
  joy: '快乐',
  sadness: '悲伤',
  anger: '愤怒',
  fear: '恐惧',
  surprise: '惊讶'
}
