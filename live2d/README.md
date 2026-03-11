# Miya Live2D 模型库

## 📁 目录结构

```
live2d/
├── README.md                 # 本文档
├── MODELS.md                # 模型详细说明
├── EXPRESSIONS.md           # 表情映射说明
└── models/                  # Live2D模型存储目录
    ├── ht/                  # 御姐猫猫头模型（当前使用）
    │   ├── ht.model3.json   # 模型配置文件
    │   ├── ht.moc3         # 模型二进制文件
    │   ├── ht.physics3.json # 物理引擎配置
    │   ├── ht.cdi3.json    # 显示信息配置
    │   ├── ht.vtube.json   # VTube Studio配置
    │   ├── expression*.exp3.json # 8个表情文件
    │   └── ht.8192/        # 纹理目录
    │       └── texture_00.png # 贴图文件
    └── [其他模型]/         # 预留位置，可添加更多模型
```

## 🎭 当前模型：御姐猫猫头 (ht)

### 模型信息

- **模型名称**: 御姐猫猫头
- **模型ID**: ht
- **版本**: Live2D Cubism 3.0
- **创建日期**: 2024年8月27日
- **纹理尺寸**: 8192x8192

### 模型特性

✅ 完整的物理引擎支持
✅ 8个可切换的表情
✅ 自动呼吸动画
✅ 眼睛追踪功能
✅ 嘴型同步
✅ 身体旋转控制
✅ 眉毛/眼睛/嘴部独立控制

### 表情列表

1. **expression1** - 黑脸 😠
2. **expression2** - 流泪 😢
3. **expression3** - 白色爱心眼 😍
4. **expression4** - 粉色爱心眼 💕
5. **expression5** - 害羞 😳
6. **expression6** - 嘘声 🤫
7. **expression7** - 唱歌 🎤
8. **expression8** - 狐狸耳朵 🦊

## 🎨 在Miya中的应用

### 桌面端
- **路径**: `miya-desktop/src/components/Live2DViewer.vue`
- **显示位置**: ChatView 右侧边栏 (280px)
- **自动集成**: 根据系统情绪自动切换表情

### 使用方式

```typescript
// 自动情绪映射
const emotionToExpressionMap = {
  '开心': 'expression3',
  '兴奋': 'expression4',
  '害羞': 'expression5',
  '悲伤': 'expression2',
  '生气': 'expression1',
  '唱歌': 'expression7',
  '调皮': 'expression8',
  '嘘声': 'expression6'
}
```

## 📦 添加新模型

### 步骤1：准备模型文件

确保你的Live2D模型包含以下文件：
- `*.model3.json` - 主配置
- `*.moc3` - 模型文件
- `*.physics3.json` - 物理配置（可选）
- `*.cdi3.json` - 显示信息（可选）
- `*.exp3.json` - 表情文件（可选）
- `texture_*.png` - 纹理文件

### 步骤2：创建模型目录

```bash
cd live2d
mkdir models/your-model-name
```

### 步骤3：复制文件

将所有模型文件复制到 `live2d/models/your-model-name/` 目录

### 步骤4：更新配置

在 `miya-desktop/src/components/Live2DViewer.vue` 中更新模型路径：

```vue
<Live2DViewer
  model-path="/live2d/models/your-model-name/your-model.model3.json"
  ...
/>
```

### 步骤5：测试表情映射

根据模型特点更新表情映射表（参见 `EXPRESSIONS.md`）

## 🔧 技术说明

### Live2D SDK版本

- **Cubism SDK**: Version 3
- **渲染引擎**: Pixi.js 7.x
- **Display Library**: pixi-live2d-display 0.4.x

### 性能优化建议

1. **纹理压缩**: 使用适当尺寸的纹理
2. **模型简化**: 减少不必要的参数
3. **LOD切换**: 根据距离切换细节级别
4. **渲染频率**: 控制帧率避免过高

## 📚 相关文档

- [Live2D Cubism SDK文档](https://www.live2d.com/sdk/download/)
- [Pixi.js 官方文档](https://pixijs.io/)
- [pixi-live2d-display GitHub](https://github.com/guansss/pixi-live2d-display)

## 📝 更新日志

### 2026-03-08
- ✅ 创建 live2d 目录结构
- ✅ 部署御姐猫猫头模型
- ✅ 完成Miya桌面端集成
- ✅ 建立表情映射系统

## 🤝 贡献

如果你有其他Live2D模型想要集成到Miya，欢迎提交！

## ⚠️ 注意事项

1. **版权**: 确保你使用的Live2D模型有合法的使用授权
2. **文件大小**: 模型文件较大，注意存储空间
3. **性能**: 复杂模型可能影响性能
4. **兼容性**: 确保模型为Live2D Cubism 3格式

---

**Miya Live2D模型库** - 让弥娅更生动！
