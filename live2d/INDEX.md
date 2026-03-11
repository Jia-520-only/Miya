# Miya Live2D 中心

## 📁 目录结构

```
live2d/                          # Live2D模型库（主目录）
├── INDEX.md                      # 本文档 - 总览索引
├── README.md                     # 使用说明和快速开始
├── CONFIG.md                     # 详细配置指南
├── MODELS.md                     # 模型技术文档
├── EXPRESSIONS.md                # 表情映射配置
├── .gitignore                    # Git忽略配置
│
└── ht/                           # 御姐猫猫头模型（当前使用）
    ├── ht.model3.json            # 模型配置文件 (1.03 KB)
    ├── ht.moc3                   # 模型二进制数据 (6.57 MB)
    ├── ht.physics3.json          # 物理引擎配置 (38.23 KB)
    ├── ht.cdi3.json              # 显示信息配置 (15.19 KB)
    ├── ht.vtube.json             # VTube Studio配置 (31.8 KB)
    ├── items_pinned_to_model.json # 物品配置 (424 B)
    ├── expression1.exp3.json     # 表情1: 黑脸 (113 B)
    ├── expression2.exp3.json     # 表情2: 流泪 (113 B)
    ├── expression3.exp3.json     # 表情3: 白色爱心眼 (113 B)
    ├── expression4.exp3.json     # 表情4: 粉色爱心眼 (113 B)
    ├── expression5.exp3.json     # 表情5: 害羞 (112 B)
    ├── expression6.exp3.json     # 表情6: 嘘声 (113 B)
    ├── expression7.exp3.json     # 表情7: 唱歌 (113 B)
    ├── expression8.exp3.json     # 表情8: 狐狸耳朵 (114 B)
    └── ht.8192/                  # 纹理目录
        └── texture_00.png        # 主纹理 (25.28 MB)
```

## 🎯 快速导航

### 📖 文档索引

| 文档 | 用途 | 适用对象 |
|-----|------|---------|
| **INDEX.md** | 总览和导航 | 所有用户 |
| **README.md** | 使用说明和快速开始 | 新用户 |
| **CONFIG.md** | 详细配置指南 | 开发者 |
| **MODELS.md** | 模型技术文档 | 高级用户 |
| **EXPRESSIONS.md** | 表情映射配置 | 开发者 |

### 🚀 快速开始

1. **阅读** [README.md](./README.md) - 了解基本使用
2. **配置** [CONFIG.md](./CONFIG.md) - 调整配置参数
3. **了解** [MODELS.md](./MODELS.md) - 深入模型细节
4. **定制** [EXPRESSIONS.md](./EXPRESSIONS.md) - 自定义表情

## 🎭 当前模型：御姐猫猫头 (ht)

### 基本信息

- **模型名称**: 御姐猫猫头
- **模型ID**: ht
- **版本**: Live2D Cubism 3.0
- **创建日期**: 2024年8月27日
- **纹理尺寸**: 8192x8192 px
- **总大小**: 约 32 MB

### 模型特性

✅ **8个表情**: 黑脸、流泪、爱心眼、害羞、嘘声、唱歌、狐狸耳朵
✅ **完整物理**: 头发、衣服摆动效果
✅ **丰富参数**: 70+ 可控参数
✅ **高精度**: 8192x8192 超高分辨率
✅ **完整支持**: 眼睛追踪、嘴型同步、呼吸动画

### 表情列表

| 表情ID | 名称 | 对应情绪 |
|--------|------|---------|
| expression1 | 黑脸 😠 | 生气、愤怒 |
| expression2 | 流泪 😢 | 悲伤、难过 |
| expression3 | 白色爱心眼 😍 | 开心、快乐 |
| expression4 | 粉色爱心眼 💕 | 兴奋、激动 |
| expression5 | 害羞 😳 | 害羞、尴尬 |
| expression6 | 嘘声 🤫 | 嘘声、安静 |
| expression7 | 唱歌 🎤 | 唱歌、音乐 |
| expression8 | 狐狸耳朵 🦊 | 调皮、可爱 |

## 🎨 在Miya中的应用

### 桌面端集成

- **应用**: Miya Desktop
- **位置**: `miya-desktop/src/views/ChatView.vue`
- **显示**: 右侧边栏 280px 区域
- **组件**: `Live2DViewer.vue`
- **逻辑**: `useLive2D.ts`

### 自动化功能

- ✅ **情绪检测**: 自动识别对话情绪
- ✅ **表情切换**: 根据情绪自动切换表情
- ✅ **呼吸动画**: 自动播放呼吸效果
- ✅ **平滑过渡**: 表情切换使用缓动动画

### 技术栈

- **渲染引擎**: Pixi.js 7.3.2
- **Live2D库**: pixi-live2d-display 0.4.0
- **Cubism版本**: Live2D Cubism SDK 3.0
- **开发框架**: Vue 3 + TypeScript

## 📊 系统要求

### 最低配置

- **CPU**: 双核 2.0 GHz+
- **内存**: 4 GB RAM
- **显卡**: 支持WebGL 2.0
- **浏览器**: Chrome 90+, Firefox 88+, Safari 14+

### 推荐配置

- **CPU**: 四核 3.0 GHz+
- **内存**: 8 GB RAM+
- **显卡**: 独立显卡
- **浏览器**: 最新版本

## 🔧 维护和更新

### 日常维护

1. **定期检查**: 每月检查模型文件完整性
2. **性能监控**: 观察FPS和内存使用
3. **日志审查**: 检查错误日志
4. **备份**: 定期备份模型文件

### 版本更新

当有新版本可用时：

1. 备份当前模型
2. 下载新版本
3. 测试新版本
4. 更新配置文件
5. 部署到生产环境

## 🤝 贡献指南

### 添加新模型

1. 在 `live2d/` 下创建模型目录
2. 复制模型文件
3. 创建模型文档
4. 更新配置
5. 测试验证

### 改进文档

1. 修正错误
2. 添加示例
3. 补充说明
4. 提交PR

## 📞 支持和反馈

### 获取帮助

- 📖 查阅文档：[README.md](./README.md)
- 🐛 报告问题：创建Issue
- 💡 提出建议：提交Feature Request

### 常见问题

**Q: 模型无法加载？**
A: 检查文件路径、文件完整性、浏览器控制台错误。

**Q: 表情不切换？**
A: 确认情绪状态正常，检查表情映射配置。

**Q: 性能卡顿？**
A: 降低分辨率、减少物理效果、关闭其他应用。

**Q: 如何更换模型？**
A: 参考 [README.md](./README.md) 中的"添加新模型"章节。

## 📝 更新日志

### 2026-03-08 - v1.0.0

#### 🎉 初始发布

- ✅ 创建 `live2d/` 目录结构
- ✅ 部署御姐猫猫头模型 (ht)
- ✅ 完成Miya桌面端集成
- ✅ 建立完整表情映射系统
- ✅ 编写全套文档（5个文档文件）

#### 📚 文档完成

- INDEX.md - 总览索引
- README.md - 使用说明
- CONFIG.md - 配置指南
- MODELS.md - 模型文档
- EXPRESSIONS.md - 表情配置

#### 🔧 技术集成

- Pixi.js渲染引擎
- pixi-live2d-display库
- Vue 3组件
- 自动情绪检测
- 表情平滑过渡

## 📊 文件统计

### 模型文件

| 类型 | 数量 | 大小 |
|-----|------|------|
| 配置文件 | 5 | 87 KB |
| 表情文件 | 8 | 0.9 KB |
| 模型文件 | 1 | 6.57 MB |
| 纹理文件 | 1 | 25.28 MB |
| **总计** | **15** | **~32 MB** |

### 文档文件

| 文件 | 大小 | 用途 |
|-----|------|------|
| INDEX.md | ~6 KB | 总览索引 |
| README.md | ~4 KB | 使用说明 |
| CONFIG.md | ~9 KB | 配置指南 |
| MODELS.md | ~7 KB | 模型文档 |
| EXPRESSIONS.md | ~6 KB | 表情配置 |
| **总计** | **5** | **~32 KB** |

## 🎯 未来计划

### 短期目标

- [ ] 添加鼠标追踪功能
- [ ] 实现嘴型同步
- [ ] 添加更多交互效果
- [ ] 优化加载性能

### 长期目标

- [ ] 支持多个模型
- [ ] 模型在线更新
- [ ] 自定义表情编辑器
- [ ] 实时动作捕捉

## 📄 许可证

Live2D模型和SDK的使用请遵循各自的许可证：

- **Live2D Cubism SDK**: [Live2D License](https://www.live2d.com/eula/live2d-free-software-license-agreement_en.html)
- **御姐猫猫头模型**: 请参考模型自带的授权信息

## 🙏 致谢

感谢以下开源项目：

- [Live2D Cubism](https://www.live2d.com/)
- [Pixi.js](https://pixijs.io/)
- [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display)

---

**Miya Live2D中心** - 让弥娅更生动！ 🎭✨

**最后更新**: 2026-03-08
**当前版本**: v1.0.0
