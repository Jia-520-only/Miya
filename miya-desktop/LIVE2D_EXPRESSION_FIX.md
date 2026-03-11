# Live2D 表情控制修复说明

## 问题诊断

根据日志分析，发现表情控制失败的原因：

1. **表情文件存在但加载方式错误**：日志显示"检测到表情: 8个"，但"模型可用表情数量: 0"
2. **模型文件格式**：ht.model3.json 中的表情是数组格式，之前的代码只能处理对象格式
3. **表情设置方法**：PIXI.live2d 的表情设置方法需要调整

## 已修复的内容

### 1. 修复表情检测逻辑 (live2dModels.ts)
- 支持数组格式的表情配置（Cubism 4.x）
- 兼容对象格式
- 增加详细的日志输出

### 2. 修复表情设置逻辑 (Live2DFull.vue)
- 尝试多种表情设置方法：
  - 方法1: `live2dModel.internalModel.expression()`
  - 方法2: `expressionManager.setExpression()`
  - 方法3: 通过表情对象的 `setValues()`
- 使用表情名称而不是索引来设置
- 增强错误处理和日志

### 3. 添加模型切换功能
- 右上角 "🎭 换装" 按钮（桌宠窗口中）
- 下拉菜单选择不同模型
- 支持自动检测表情和动作

## 如何使用

### 打开桌宠窗口
1. 启动主程序
2. 在左侧工具栏点击 "🐾 桌宠" 按钮
3. 独立的桌宠窗口会打开
4. 桌宠窗口右上角有 "🎭 换装" 按钮

### 切换Live2D模型
1. 点击桌宠窗口右上角的 "🎭 换装" 按钮
2. 在下拉菜单中选择模型：
   - 御姐猫猫
   - 修女
3. 模型会自动加载并适应

### 控制表情
在主聊天窗口的Live2D控制面板中：
1. 点击左侧 "Live2D" 按钮
2. 在面板中选择表情（开心、害羞、生气、悲伤、平静等）
3. 模型会切换到对应表情

### 测试表情控制
1. 打开浏览器控制台（F12）
2. 查看日志：
   - 应该看到 "[Live2D] 使用表情名称: expressionX"
   - 应该看到 "[Live2D] 通过 xxx 设置成功"
3. 如果失败，会尝试使用动作替代

## 如果表情仍然不工作

### 检查模型文件
确保 model3.json 包含表情配置：
```json
{
  "FileReferences": {
    "Expressions": [
      {
        "Name": "expression1",
        "File": "expression1.exp3.json"
      }
    ]
  }
}
```

### 查看日志
打开控制台查看：
```
[Live2D] 模型内部结构
[Live2D] 使用表情名称
[Live2D] 检测到的表情列表
```

### 手动测试表情
在控制台输入：
```javascript
// 获取模型实例
const model = document.querySelector('canvas').__pixi_app.stage.children[0]

// 尝试设置表情
if (model.internalModel) {
  model.internalModel.expression('expression1')
}
```

## 模型管理

### 添加新模型
1. 将模型文件夹放入 `live2d/` 目录
2. 编辑 `miya-desktop/src/config/live2dModels.ts`
3. 添加模型配置：
```typescript
'新模型': {
  id: '新模型',
  name: '显示名称',
  path: '/live2d/新模型/新模型.model3.json',
  description: '描述'
}
```

### 表情文件命名规范
推荐使用标准命名：
- expression1.exp3.json
- expression2.exp3.json
- ...

## 技术细节

### Live2D Cubism SDK 版本
- Core 版本: 5.1.0
- PIXI 版本: 6.5.10
- PIXI.live2d 版本: Cubism 4 runtime

### 表情控制流程
1. 从 model3.json 读取表情列表
2. 存储在 `availableExpressions` 数组
3. 设置表情时使用表情名称
4. 通过 expressionManager 或直接调用模型方法

### 后备机制
如果表情设置失败，会自动尝试：
- 使用动作替代表情
- 在控制台输出详细错误信息
