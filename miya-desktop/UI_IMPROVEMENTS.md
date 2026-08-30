# UI 美化和桌宠关闭修复

## 修复内容

### 1. 桌宠窗口无法关闭问题

**问题原因：**
- `toggleDesktopPet()` 函数没有足够的调试日志
- 缺少错误处理后的状态重置
- 缺少窗口创建后的延迟等待

**解决方案：**
```javascript
async function toggleDesktopPet() {
  try {
    console.log('[ChatView] ========== toggleDesktopPet 被调用 ==========')
    console.log('[ChatView] 当前状态:', live2DWindowOpen.value)

    if (!window.electronAPI?.live2d) {
      console.error('[ChatView] electronAPI不可用，无法切换桌宠模式')
      return
    }

    if (live2DWindowOpen.value) {
      // 关闭桌宠
      console.log('[ChatView] 准备关闭桌宠...')
      await window.electronAPI.live2d.close()
      live2DWindowOpen.value = false
      console.log('[ChatView] 桌宠已关闭，状态已更新为:', live2DWindowOpen.value)
    } else {
      // 打开桌宠
      console.log('[ChatView] 准备打开桌宠...')
      await window.electronAPI.live2d.create()
      live2DWindowOpen.value = true
      console.log('[ChatView] 桌宠已打开，状态已更新为:', live2DWindowOpen.value)

      // 等待窗口创建完成再同步数据
      await new Promise(resolve => setTimeout(resolve, 500))

      // 同步模型和表情
      ...
    }
  } catch (error) {
    console.error('[ChatView] 切换桌宠模式失败:', error)
    // 发生错误时重置状态
    live2DWindowOpen.value = false
  }
}
```

### 2. UI 美化 - 整体改进

#### 2.1 Live2D 控制面板
- **宽度增加**：320px → 380px，更宽敞
- **背景透明度提升**：0.95 → 0.98
- **模糊效果增强**：blur(20px) → blur(24px)
- **动画效果**：使用更平滑的 cubic-bezier 缓动函数
- **阴影增强**：更深的阴影和更好的层次感
- **标题样式**：字号增大（14px → 15px），字重增加（600 → 700）

#### 2.2 控制面板头部
- **padding 增加**：16px 20px → 20px 24px
- **渐变背景**：添加微妙的渐变效果
- **阴影效果**：添加底部阴影增强层次感
- **关闭按钮**：
  - 尺寸增大：32px → 36px
  - 悬停动画：旋转 90°
  - 阴影效果

#### 2.3 Live2D 状态区域
- **渐变背景**：添加对角线渐变
- **状态指示器**：添加呼吸灯动画效果
  ```css
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  ```
- **背景模糊**：增强毛玻璃效果
- **间距增加**：16px → 20px
- **圆角增大**：8px → 12px

#### 2.4 表情和动作按钮
- **尺寸增加**：
  - padding: 10px 12px → 14px 16px
  - font-size: 12px → 13px
- **间距增加**：8px → 12px
- **圆角增大**：8px → 10px
- **悬停效果**：
  - 向上移动：-2px
  - 阴影：0 4px 12px rgba(45, 212, 191, 0.2)
- **激活状态**：
  - 渐变背景
  - 发光效果
  - 字重增加：500 → 600

#### 2.5 模型选择器
- **padding 增加**：10px 12px → 14px 16px
- **字号增大**：13px → 14px
- **字重增加**：添加 font-weight: 500
- **悬停效果**：添加阴影
- **聚焦效果**：添加外发光
  ```css
  box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.15);
  ```

#### 2.6 Live2D 预览区域
- **尺寸增加**：
  - width: 280px → 320px
  - min/max-height: 380px → 400px
- **渐变背景**：添加对角线渐变
- **背景模糊增强**：blur(8px) → blur(12px)
- **圆角增大**：12px → 16px
- **边框增强**：rgba(45, 212, 191, 0.2) → 0.25
- **内阴影**：添加 inset 光泽效果

#### 2.7 侧边栏按钮
- **尺寸增加**：
  - width/height: 44px → 48px
  - icon font-size: 18px → 20px
- **圆角增大**：10px → 12px
- **悬停效果**：
  - 缩放：scale(1.05) → 1.06
  - 阴影：0 4px 12px rgba(45, 212, 191, 0.2)

#### 2.8 桌宠按钮激活状态
- **渐变背景**：添加发光渐变效果
- **外发光**：增强阴影效果
- **内光泽**：添加 inset 效果

#### 2.9 聊天区域
- **间距增加**：
  - gap: 20px → 24px
  - padding: 20px 24px → 24px 28px
- **消息间距**：18px → 20px
- **滚动条宽度**：6px → 8px

#### 2.10 滚动条样式
- **轨道背景**：添加半透明背景和圆角
- **滑块**：
  - 宽度增加：6px → 8px
  - 圆角增加：3px → 4px
  - 悬停效果增强

#### 2.11 人格面板
- **宽度增加**：360px → 400px
- **padding 增加**：16px 20px → 20px 24px
- **关闭按钮**：
  - 尺寸：32px → 36px
  - 圆角：8px → 10px
  - 字号：增大
  - 悬停效果：阴影增强

#### 2.12 左侧边栏
- **宽度增加**：60px → 64px
- **padding 增加**：16px 0 → 20px 0
- **背景透明度**：0.6 → 0.7
- **模糊效果**：blur(12px) → 16px
- **分隔线**：添加渐变效果
  ```css
  background: linear-gradient(90deg, transparent 0%, rgba(45, 212, 191, 0.3) 50%, transparent 100%);
  ```

## 视觉改进总结

### 空间感
- 整体间距增加 20-30%
- 按钮和面板尺寸增大
- 更多留白，减少拥挤感

### 层次感
- 增强阴影效果
- 添加内阴影和外发光
- 渐变背景增强深度

### 交互感
- 更流畅的动画过渡
- 悬停状态反馈更明显
- 点击反馈更清晰

### 现代感
- 圆角增大，更柔和
- 模糊效果增强，毛玻璃效果
- 渐变和光效增添科技感

## 技术细节

### 动画曲线
从 ease 改为更流畅的 cubic-bezier：
```css
transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
```

### 背景模糊
增强毛玻璃效果：
```css
backdrop-filter: blur(24px);
-webkit-backdrop-filter: blur(24px);
```

### 颜色系统
- 主色：#2dd4bf (青色)
- 次色：#5eead4 (浅青色)
- 强调色：#a78bfa (紫色，用于桌宠)
- 文字：#f0fdfa (浅白)
- 辅助：#94a3b8 (灰蓝)

### 阴影层次
- 轻微：0 4px 12px rgba(0, 0, 0, 0.15)
- 中等：0 8px 24px rgba(0, 0, 0, 0.2)
- 深度：-8px 0 32px rgba(0, 0, 0, 0.4)

## 测试要点

1. 桌宠开关是否正常工作
2. 控制面板打开关闭动画流畅
3. 按钮悬停和激活状态清晰
4. 响应式布局不破坏
5. 滚动条样式美观
6. 文字可读性良好
