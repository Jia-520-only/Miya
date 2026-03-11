# Live2D完整版测试指南

## 已完成的修改

✅ **删除简化版组件**：`src/components/Live2DViewerSimple.vue` 已删除
✅ **创建完整版组件**：`src/components/Live2DFull.vue` 已创建
✅ **更新引用**：`ChatView.vue` 已更新为使用完整版组件
✅ **模型文件复制**：Live2D模型已复制到 `public/live2d/ht/` 目录

## 技术实现

### 使用的技术栈
- **PIXI.js v7.3.2** - WebGL渲染引擎
- **pixi-live2d-display v0.4.0** - Live2D模型加载器
- **Vue 3 + TypeScript** - 组件框架

### 功能特性
✅ 真正的Live2D 3D渲染（不是emoji）
✅ 8种表情切换（开心、害羞、生气、悲伤、平静、兴奋、调皮、嘘声）
✅ 实时情绪响应
✅ 加载状态显示
✅ 错误重试机制
✅ 表情控制按钮
✅ 模型信息显示

## 模型文件结构

```
public/live2d/ht/
├── ht.model3.json          # 主模型配置
├── ht.moc3                 # 模型数据（6.57MB）
├── ht.physics3.json        # 物理模拟配置
├── ht.cdi3.json            # 显示信息
├── expression1-8.exp3.json # 8个表情文件
└── ht.8192/
    └── texture_00.png      # 纹理贴图
```

## 如何测试

### 方法1：使用测试脚本
```batch
test_live2d_full.bat
```

### 方法2：手动启动
```batch
# 终端1：启动Vite开发服务器
npm run dev

# 终端2：启动Electron
npm run dev:electron
```

## 表情映射

| 表情名 | emotion值 | 表情文件 |
|--------|-----------|----------|
| 开心   | 开心/快乐/喜悦 | expression1.exp3.json |
| 害羞   | 害羞/尴尬/羞涩 | expression2.exp3.json |
| 生气   | 生气/愤怒/暴躁 | expression3.exp3.json |
| 悲伤   | 悲伤/难过/痛苦 | expression4.exp3.json |
| 平静   | 平静/安静/专注 | expression5.exp3.json |
| 兴奋   | 兴奋/激动/热情 | expression6.exp3.json |
| 调皮   | 调皮/可爱 | expression7.exp3.json |
| 嘘声   | 嘘声/安静 | expression8.exp3.json |

## 常见问题

### 1. 模型加载失败
**原因**：模型文件路径错误或文件缺失
**解决**：检查 `public/live2d/ht/` 目录下是否包含所有必需文件

### 2. WebGL上下文创建失败
**原因**：Electron的GPU加速问题
**解决**：已在 `package.json` 的启动脚本中添加 `--disable-gpu` 参数

### 3. 表情切换不生效
**原因**：表达式文件加载失败
**解决**：检查控制台日志，确认表情文件路径正确

### 4. 模型显示位置错误
**原因**：模型缩放或定位参数需要调整
**解决**：在 `Live2DFull.vue` 中修改 `scale` 和 `anchor` 参数

## 调试技巧

1. **打开开发者工具**：按 `Ctrl+Shift+I`
2. **查看控制台日志**：搜索 "Live2D" 关键字
3. **检查网络请求**：确认模型文件是否成功加载
4. **测试表情切换**：点击表情按钮观察变化

## 性能优化

- 模型文件已启用 `preserveDrawingBuffer` 优化
- 使用 `devicePixelRatio` 适配高分屏
- 表情切换使用异步加载，避免阻塞主线程

## 下一步

如需添加更多模型：
1. 将新模型文件夹复制到 `public/live2d/` 目录
2. 更新 `Live2DFull.vue` 中的 `modelPath` 参数
3. 根据模型配置调整表情映射
