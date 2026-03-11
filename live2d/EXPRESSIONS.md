# Live2D 表情映射配置

## 📋 表情列表

### 御姐猫猫头模型 (ht)

| 表情ID | 表情名称 | 文件名 | 参数效果 | 适用情绪 |
|--------|---------|--------|---------|---------|
| expression1 | 黑脸 | expression1.exp3.json | 脸部变黑 | 生气、愤怒、暴躁 |
| expression2 | 流泪 | expression2.exp3.json | 眼角出现泪滴 | 悲伤、难过、痛苦 |
| expression3 | 白色爱心眼 | expression3.exp3.json | 眼睛变成白色爱心 | 开心、快乐、愉快 |
| expression4 | 粉色爱心眼 | expression4.exp3.json | 眼睛变成粉色爱心 | 兴奋、激动、热情 |
| expression5 | 害羞 | expression5.exp3.json | 脸部泛红 | 害羞、尴尬、羞涩 |
| expression6 | 嘘声 | expression6.exp3.json | 嘘声手势 | 嘘声、安静 |
| expression7 | 唱歌 | expression7.exp3.json | 拿麦克风 | 唱歌、音乐 |
| expression8 | 狐狸耳朵 | expression8.exp3.json | 耳朵变成狐狸耳 | 调皮、可爱、淘气 |

## 🎭 情绪映射表

### 系统情绪 → Live2D表情

```typescript
const emotionToExpressionMap: Record<string, string> = {
  // 正面情绪
  '开心': 'expression3',      // 白色爱心眼
  '快乐': 'expression3',
  '愉快': 'expression3',
  '喜悦': 'expression3',

  '兴奋': 'expression4',      // 粉色爱心眼
  '激动': 'expression4',
  '热情': 'expression4',

  '害羞': 'expression5',      // 害涩脸红
  '尴尬': 'expression5',
  '羞涩': 'expression5',

  '调皮': 'expression8',      // 狐狸耳朵
  '可爱': 'expression8',
  '淘气': 'expression8',

  // 负面情绪
  '生气': 'expression1',      // 黑脸
  '愤怒': 'expression1',
  '暴躁': 'expression1',

  '悲伤': 'expression2',      // 流泪
  '难过': 'expression2',
  '痛苦': 'expression2',

  // 特殊情绪
  '唱歌': 'expression7',      // 拿麦克风
  '嘘声': 'expression6',      // 嘘声手势

  // 默认情绪
  '平静': '',                 // 无表情变化
  '专注': '',                 // 无表情变化
  '思考': '',                 // 无表情变化
  '惊讶': 'expression3'       // 白色爱心眼
}
```

## 🔧 配置文件位置

### 桌面端应用
- **文件**: `miya-desktop/src/composables/useLive2D.ts`
- **组件**: `miya-desktop/src/components/Live2DViewer.vue`

### 后端情绪识别
- **系统状态**: `core/system_status.py`
- **情绪分析**: `core/emotion_analyzer.py`

## 🎨 自定义表情映射

### 添加新映射

在 `useLive2D.ts` 中添加：

```typescript
const emotionToExpressionMap: Record<string, string> = {
  // ... 现有映射
  '你的情绪': 'expression名称'
}
```

### 创建新表情

1. 在 `ht/` 目录下创建新表情文件：`expression9.exp3.json`

2. 配置表情参数：

```json
{
  "Type": "Live2D Expression",
  "Parameters": [
    {
      "Id": "参数ID",
      "Value": 1,
      "Blend": "Add"
    }
  ]
}
```

3. 在 `ht.model3.json` 中注册表情：

```json
"Expressions": [
  {
    "Name": "expression9",
    "File": "expression9.exp3.json"
  }
]
```

## 📊 表情参数说明

### 常用参数ID

| 参数ID | 参数名称 | 说明 | 值范围 |
|--------|---------|------|--------|
| ParamEyeLOpen | 左眼开闭 | 控制左眼睁开程度 | 0-2 |
| ParamEyeROpen | 右眼开闭 | 控制右眼睁开程度 | 0-2 |
| ParamEyeLSmile | 左眼微笑 | 左眼弧度变化 | 0-1 |
| ParamEyeRSmile | 右眼微笑 | 右眼弧度变化 | 0-1 |
| ParamEyeBallX | 眼珠X | 眼珠左右移动 | -1-1 |
| ParamEyeBallY | 眼珠Y | 眼珠上下移动 | -1-1 |
| ParamBrowLY | 左眉上下 | 左眉高度 | -1-1 |
| ParamBrowRY | 右眉上下 | 右眉高度 | -1-1 |
| ParamMouthForm | 嘴变形 | 嘴型变化 | -1-1 |
| ParamMouthOpenY | 嘴张开 | 嘴巴张开程度 | 0-2 |
| ParamCheek | 脸颊泛红 | 脸颊红晕强度 | 0-1 |
| ParamAngleX | 角度X | 头部左右旋转 | -30-30 |
| ParamAngleY | 角度Y | 头部上下旋转 | -20-20 |
| ParamAngleZ | 角度Z | 头部倾斜旋转 | -30-30 |
| ParamBreath | 呼吸 | 呼吸动画 | 0-1 |

### Blend模式

- **Add**: 叠加模式，数值相加
- **Multiply**: 乘法模式，数值相乘
- **Overwrite**: 覆盖模式，直接设置

## 🎯 情绪强度控制

### 表情强度调整

```typescript
// 根据情绪强度调整表情程度
const intensity = emotionState.intensity // 0-1

// 例如：情绪强度影响脸颊泛红程度
model.internalModel.coreModel.setParameterValueById('ParamCheek', intensity * 0.8)
```

### 情绪分级

| 强度级别 | 范围 | 表现 |
|---------|------|------|
| 微弱 | 0.0 - 0.3 | 轻微表情变化 |
| 中等 | 0.3 - 0.6 | 明显表情变化 |
| 强烈 | 0.6 - 1.0 | 夸张表情变化 |

## 🔍 调试表情

### 查看当前表情

```typescript
console.log('当前表情:', currentExpression.value)
```

### 手动测试表情

```vue
<Live2DViewer
  model-path="/live2d/ht/ht.model3.json"
  :show-controls="true"  <!-- 启用测试控制面板 -->
/>
```

### 检查表情文件

确保表情文件JSON格式正确：

```bash
# 验证JSON格式
python -m json.tool expression1.exp3.json
```

## 📝 表情设计建议

### 表情设计原则

1. **真实性**: 表情应符合人类情绪表达
2. **可识别性**: 表情应该容易识别
3. **适度夸张**: 可以适度夸张但不要过度
4. **一致性**: 同类情绪的表情应该保持一致

### 情绪组合

某些情绪可以组合多个参数：

```json
{
  "Parameters": [
    {"Id": "ParamMouthForm", "Value": 0.5, "Blend": "Add"},
    {"Id": "ParamEyeLSmile", "Value": 0.8, "Blend": "Add"},
    {"Id": "ParamEyeRSmile", "Value": 0.8, "Blend": "Add"},
    {"Id": "ParamCheek", "Value": 0.6, "Blend": "Add"}
  ]
}
```

## 🎬 表情过渡动画

### 平滑过渡

```typescript
// 使用缓动函数实现平滑过渡
function animateExpression(targetValue: number, duration: number) {
  const startValue = currentValue
  const startTime = Date.now()

  function animate() {
    const elapsed = Date.now() - startTime
    const progress = Math.min(elapsed / duration, 1)
    const eased = easeInOutQuad(progress)

    currentValue = startValue + (targetValue - startValue) * eased

    if (progress < 1) {
      requestAnimationFrame(animate)
    }
  }

  animate()
}

function easeInOutQuad(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
}
```

## 📚 参考资料

- [Live2D Cubism 表情系统文档](https://docs.live2d.com/)
- [表情制作教程](https://www.live2d.com/learn/)

---

**表情映射配置** - 让弥娅更生动地表达情绪！
