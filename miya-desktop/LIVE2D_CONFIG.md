# Live2D完整版配置指南

## 模型配置

Live2D模型文件位于 `/live2d/ht/` 目录，包含：
- `ht.model3.json` - 模型主配置文件
- `ht.moc3` - 模型数据文件
- `ht.physics3.json` - 物理配置文件
- `ht.cdi3.json` - Cubism显示信息文件
- `expression1-8.exp3.json` - 8个表情文件
- `ht.8192/` - 纹理贴图目录

## 使用方法

1. **模型路径配置**：
   ```
   modelPath: "/live2d/ht/ht.model3.json"
   ```

2. **表情映射**：
   - expression1 - 开心
   - expression2 - 害羞
   - expression3 - 生气
   - expression4 - 悲伤
   - expression5 - 平静
   - expression6 - 兴奋
   - expression7 - 调皮
   - expression8 - 嘘声

## 技术实现

- 使用 PIXI.js v7.3.2 进行WebGL渲染
- 使用 pixi-live2d-display 加载和渲染Live2D模型
- 支持实时表情切换
- 支持鼠标跟随（可选）

## 注意事项

- 确保模型文件路径正确
- 需要WebGL支持
- 在Electron中会自动禁用GPU加速避免兼容性问题
