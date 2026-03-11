// Live2D 模型配置
export interface Live2DModelConfig {
  id: string
  name: string
  path: string
  description: string
  expressions?: { name: string; file: string }[]
  motions?: { group: string; files: string[] }[]
  devOnly?: boolean // 是否只在开发环境可用
}

// 当前支持的所有 Live2D 模型
// 注意：模型位于 miya-desktop/public/live2d/ 目录下
export const LIVE2D_MODELS: Record<string, Live2DModelConfig> = {
  // ==================== 实际存在的模型 ====================
  'ht': {
    id: 'ht',
    name: '御姐猫猫',
    path: '/live2d/ht/ht.model3.json',
    description: '御姐风格的猫猫角色'
  },
  'nun': {
    id: 'nun',
    name: '修女',
    path: '/live2d/nun/nun.model3.json',
    description: '修女角色模型'
  },
  'snow_lady': {
    id: 'snow_lady',
    name: '白发雪女',
    path: '/live2d/snow_lady_vts/snow_lady.model3.json',
    description: '白发雪女角色，冰雪主题'
  },
  'cheng': {
    id: 'cheng',
    name: '换装小承',
    path: '/live2d/cheng/cheng_huan_2024.model3.json',
    description: '换装小承角色模型'
  },
  'xiyu_dancer': {
    id: 'xiyu_dancer',
    name: '西域舞女',
    path: '/live2d/xiyu_dancer/Xiyu.model3.json',
    description: '西域舞女角色，异域风情'
  },
  'white_wolf': {
    id: 'white_wolf',
    name: '白狼',
    path: '/live2d/white_wolf/white_wolf.model3.json',
    description: '白狼角色'
  },
  'formal_sister': {
    id: 'formal_sister',
    name: '礼服御姐',
    path: '/live2d/formal_sister/formal_sister.model3.json',
    description: '礼服御姐角色'
  },
  'hong_zui': {
    id: 'hong_zui',
    name: '红醉',
    path: '/live2d/hong_zui/hong_zui.model3.json',
    description: '红醉角色，品酒主题'
  },
  'ye_ling': {
    id: 'ye_ling',
    name: '夜翎',
    path: '/live2d/ye_ling/ye_ling.model3.json',
    description: '夜翎角色，魅蝙蝠主题'
  },
  'ye_gu': {
    id: 'ye_gu',
    name: '夜蛊',
    path: '/live2d/ye_gu/ye_gu.model3.json',
    description: '夜蛊角色，魅魔主题'
  },
  'chest_cover': {
    id: 'chest_cover',
    name: '胸遮挡',
    path: '/live2d/chest_cover/chest_cover.model3.json',
    description: '胸遮挡角色'
  },
  'hestia': {
    id: 'hestia',
    name: '希斯提亚',
    path: '/live2d/hestia/AoiYume.model3.json',
    description: '希斯提亚角色'
  },
  'shi_bing': {
    id: 'shi_bing',
    name: '时冰',
    path: '/live2d/shi_bing/01.model3.json',
    description: '时冰角色，冰霜主题'
  },
  'fox': {
    id: 'fox',
    name: '狐仙',
    path: '/live2d/fox/fox.model3.json',
    description: '狐仙角色'
  },
  'cold_sister': {
    id: 'cold_sister',
    name: '白发清冷御姐',
    path: '/live2d/cold_sister/cold_sister.model3.json',
    description: '白发清冷御姐角色'
  },
  'formal_sister2': {
    id: 'formal_sister2',
    name: '礼服御姐2',
    path: '/live2d/formal_sister2/formal_sister2.model3.json',
    description: '礼服御姐角色版本2'
  },
  'xiumu': {
    id: 'xiumu',
    name: '修女(中文)',
    path: '/live2d/修女/修女.model3.json',
    description: '修女角色（中文目录）'
  }
}

// 自动扫描并加载 Live2D 模型
export async function scanLive2DModels(): Promise<Live2DModelConfig[]> {
  const models: Live2DModelConfig[] = []

  // 从配置中获取模型
  for (const [id, config] of Object.entries(LIVE2D_MODELS)) {
    models.push(config)
  }

  return models
}

// 根据模型路径自动提取表情列表
export async function detectExpressions(modelPath: string): Promise<{ name: string; file: string }[]> {
  try {
    const baseUrl = modelPath.replace(/\/[^/]+\.model3\.json$/, '')
    const response = await fetch(modelPath)
    const modelData = await response.json()

    // 从模型数据中提取表情信息
    const expressions: { name: string; file: string }[] = []

    // Cubism 4.x 格式 - 支持数组格式
    if (modelData.FileReferences?.Expressions) {
      const exprRef = modelData.FileReferences.Expressions

      // 如果是数组格式
      if (Array.isArray(exprRef)) {
        for (const expr of exprRef) {
          expressions.push({
            name: expr.Name || expr.name,
            file: expr.File || expr.file
          })
        }
      }
      // 如果是对象格式
      else if (typeof exprRef === 'object') {
        for (const [name, file] of Object.entries(exprRef)) {
          expressions.push({ name, file: file as string })
        }
      }
    }

    console.log('[Live2D Config] 检测到的表情:', expressions)
    return expressions
  } catch (error) {
    console.error('[Live2D] 检测表情失败:', error)
    return []
  }
}

// 根据模型路径自动提取动作列表
export async function detectMotions(modelPath: string): Promise<{ group: string; files: string[] }[]> {
  try {
    const response = await fetch(modelPath)
    const modelData = await response.json()

    // 从模型数据中提取动作信息
    const motions: { group: string; files: string[] }[] = []

    // Cubism 4.x 格式
    if (modelData.FileReferences?.Motions) {
      for (const [group, files] of Object.entries(modelData.FileReferences.Motions)) {
        motions.push({
          group,
          files: Array.isArray(files) ? files.map((f: any) => f.File || f) : []
        })
      }
    }

    return motions
  } catch (error) {
    console.error('[Live2D] 检测动作失败:', error)
    return []
  }
}

// 默认表情映射（模型没有表情时使用）
export const DEFAULT_EXPRESSIONS = [
  { name: '开心', value: 'expression1.exp3.json' },
  { name: '害羞', value: 'expression2.exp3.json' },
  { name: '生气', value: 'expression3.exp3.json' },
  { name: '悲伤', value: 'expression4.exp3.json' },
  { name: '平静', value: 'expression5.exp3.json' },
  { name: '兴奋', value: 'expression6.exp3.json' },
  { name: '调皮', value: 'expression7.exp3.json' },
  { name: '嘘声', value: 'expression8.exp3.json' }
]
