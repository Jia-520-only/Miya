# Live2D 模型快速参考

## 🚀 快速开始

### 添加新模型（3 步）

```bash
# 1. 复制模型文件到 live2d 文件夹
D:/AI_MIYA_Facyory/MIYA/Miya/live2d/your-model/

# 2. 编辑配置文件
miya-desktop/src/config/live2dModels.ts

# 3. 添加配置
'your-model': {
  id: 'your-model',
  name: '模型名称',
  path: '/live2d/your-model/your-model.model3.json',
  description: '描述'
}

# 4. 重启应用
```

---

## 📋 当前模型列表

### ✅ 可用模型（5个）

| # | ID | 名称 | 路径 |
|---|----|------|------|
| 1 | `ht` | 御姐猫猫 | `/live2d/ht/ht.model3.json` |
| 2 | `修女` | 修女 | `/live2d/修女/修女.model3.json` |
| 3 | `承` | 承 | `/live2d/承/承/承欢2024.model3.json` |
| 4 | `白发雪女` | 白发雪女 | `/live2d/白发雪女vts/白发雪女vts/白发雪女.model3.json` |
| 5 | `西域舞女` | 西域舞女 | `/live2d/西域舞女/西域舞女/Xiyu.model3.json` |

### ⚠️ 待修复模型（8个）

需要先修复路径才能使用，详见 [修复指南](./LIVE2D_PATH_FIX_GUIDE.md)

| # | ID | 名称 | 状态 |
|---|----|------|------|
| 6 | `白发清冷御姐` | 白发清冷御姐 | 需启用 |
| 7 | `红醉` | 红醉 | 路径问题 |
| 8 | `奶糖啵啵` | 奶糖啵啵 | 路径问题 |
| 9 | `夜翎` | 夜翎 | 路径问题 |
| 10 | `时冰` | 时冰 | 路径问题 |
| 11 | `夜蛊` | 夜蛊 | 路径问题 |
| 12 | `希斯提亚` | 希斯提亚 | 路径问题 |
| 13 | `漫漫` | 漫漫 | 路径问题 |

---

## 😊 8 种表情

| 表情 | 文件 | 对应情绪 |
|------|------|----------|
| 😊 开心 | expression1.exp3.json | 快乐、喜悦 |
| 😳 害羞 | expression2.exp3.json | 尴尬、羞涩 |
| 😠 生气 | expression3.exp3.json | 愤怒、暴躁 |
| 😢 悲伤 | expression4.exp3.json | 难过、痛苦 |
| 😐 平静 | expression5.exp3.json | 安静、专注 |
| 🤩 兴奋 | expression6.exp3.json | 激动、热情 |
| 😜 调皮 | expression7.exp3.json | 可爱、调皮 |
| 🤫 嘘声 | expression8.exp3.json | 安静 |

---

## 🎮 操作快捷方式

| 操作 | 方法 |
|------|------|
| 切换模型 | 控制面板 → 模型选择 |
| 改变表情 | 控制面板 → 表情按钮 |
| 播放动作 | 控制面板 → 动作按钮 |
| 缩放模型 | 鼠标滚轮 |
| 移动模型 | 鼠标拖拽 |
| 打开桌宠 | 控制面板 → 打开桌宠 |
| 打开控制面板 | 左侧边栏 → 表情控制 |

---

## 📂 模型文件结构

```
your-model/
├── your-model.model3.json    # 必需 ✅
├── your-model.moc3           # 必需 ✅
├── your-model.physics3.json  # 推荐 ⭐
├── expression1.exp3.json     # 可选
├── expression2.exp3.json     # 可选
├── ...更多表情
└── idle.motion3.json          # 可选
```

---

## 🐛 常见问题速查

| 问题 | 解决方案 |
|------|----------|
| 模型加载失败 | 检查文件路径和必需文件 |
| 切换出错 | 等待自动重新初始化或重启 |
| 表情不生效 | 检查表情文件是否存在 |
| 动作不播放 | 确认模型支持该动作 |
| 桌宠打不开 | 重启应用 |
| 位置偏移 | 拖拽或滚轮调整 |

---

## 📝 配置模板

```typescript
// 在 live2dModels.ts 中添加
'your-model-id': {
  id: 'your-model-id',
  name: '显示名称',
  path: '/live2d/folder/model.model3.json',
  description: '描述文字'
}
```

---

## 🔍 调试技巧

```javascript
// 浏览器控制台查看日志
console.log('[Live2D] 模型加载成功')
console.log('[Live2D] 表情变化: 平静')
console.log('[Live2D] 播放动作: Idle')

// F12 打开开发者工具查看详细信息
```

---

## 📖 详细文档

完整使用指南：[LIVE2D_MODEL_GUIDE.md](./LIVE2D_MODEL_GUIDE.md)

---

*最后更新：2026-03-08*
