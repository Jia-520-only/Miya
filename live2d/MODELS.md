# Live2D 模型详细说明

## 🎭 当前模型：御姐猫猫头 (ht)

### 基本信息

| 属性 | 值 |
|-----|---|
| **模型名称** | 御姐猫猫头 |
| **模型ID** | ht |
| **Live2D版本** | Cubism 3.0 |
| **创建日期** | 2024年8月27日 |
| **最后修改** | VTube Studio 1.29.0 |
| **模型UUID** | 106647c7fda24f59b67f0c84aaf4dbaa |
| **纹理尺寸** | 8192 x 8192 px |
| **文件大小** | ~32 MB |

### 模型组成

#### 核心文件

```
ht/
├── ht.model3.json      (1.03 KB)   - 模型主配置文件
├── ht.moc3             (6.57 MB)   - 模型二进制数据
├── ht.physics3.json    (38.23 KB)  - 物理引擎配置
├── ht.cdi3.json        (15.19 KB)  - 显示信息配置
├── ht.vtube.json       (31.8 KB)   - VTube Studio配置
└── ht.8192/                          - 纹理目录
    └── texture_00.png   (25.28 MB)  - 主纹理
```

#### 表情文件

| 文件名 | 大小 | 表情名称 |
|--------|------|---------|
| expression1.exp3.json | 113 B | 黑脸 |
| expression2.exp3.json | 113 B | 流泪 |
| expression3.exp3.json | 113 B | 白色爱心眼 |
| expression4.exp3.json | 113 B | 粉色爱心眼 |
| expression5.exp3.json | 112 B | 害羞 |
| expression6.exp3.json | 113 B | 嘘声 |
| expression7.exp3.json | 113 B | 唱歌 |
| expression8.exp3.json | 114 B | 狐狸耳朵 |

### 参数系统

#### 参数分类

##### 1. 头部旋转 (Angle)
| 参数ID | 名称 | 范围 | 说明 |
|--------|------|------|------|
| ParamAngleX | 角度X | -30~30 | 头部左右旋转 |
| ParamAngleY | 角度Y | -20~20 | 头部上下旋转 |
| ParamAngleZ | 角度Z | -30~30 | 头部倾斜旋转 |

##### 2. 眼睛控制 (Eye)
| 参数ID | 名称 | 范围 | 说明 |
|--------|------|------|------|
| ParamEyeLOpen | 左眼开闭 | 0~2 | 左眼睁开程度 |
| ParamEyeROpen | 右眼开闭 | 0~2 | 右眼睁开程度 |
| ParamEyeLSmile | 左眼微笑 | 0~1 | 左眼弧度 |
| ParamEyeRSmile | 右眼微笑 | 0~1 | 右眼弧度 |
| ParamEyeBallX | 眼珠X | -1~1 | 眼珠左右移动 |
| ParamEyeBallY | 眼珠Y | -1~1 | 眼珠上下移动 |

##### 3. 眉毛控制 (Brow)
| 参数ID | 名称 | 范围 | 说明 |
|--------|------|------|------|
| ParamBrowLY | 左眉上下 | -1~1 | 左眉毛高度 |
| ParamBrowRY | 右眉上下 | -1~1 | 右眉毛高度 |
| ParamBrowLX | 左眉左右 | -1~1 | 左眉毛位置 |
| ParamBrowRX | 右眉左右 | -1~1 | 右眉毛位置 |
| ParamBrowLAngle | 左眉角度 | -1~1 | 左眉毛旋转 |
| ParamBrowRAngle | 右眉角度 | -1~1 | 右眉毛旋转 |
| ParamBrowLForm | 左眉变形 | -1~1 | 左眉毛形状 |
| ParamBrowRForm | 右眉变形 | -1~1 | 右眉毛形状 |

##### 4. 嘴巴控制 (Mouth)
| 参数ID | 名称 | 范围 | 说明 |
|--------|------|------|------|
| ParamMouthForm | 嘴变形 | -1~1 | 嘴型变化 |
| ParamMouthOpenY | 嘴张开 | 0~2 | 嘴巴张开程度 |
| Param85 | 吐舌 | 0~1 | 舌头伸出 |
| Param86 | 鼓嘴 | 0~1 | 脸颊鼓起 |
| Param83 | 嘴X移动 | -1~1 | 嘴巴左右移动 |

##### 5. 身体控制 (Body)
| 参数ID | 名称 | 范围 | 说明 |
|--------|------|------|------|
| ParamBodyAngleX | 身体旋转X | -10~10 | 身体左右旋转 |
| ParamBodyAngleY | 身体旋转Y | -10~10 | 身体前后倾斜 |
| ParamBodyAngleZ | 身体旋转Z | -10~10 | 身体左右倾斜 |
| ParamBreath | 呼吸 | 0~1 | 呼吸动画 |

##### 6. 头发控制 (Hair)
| 参数ID | 名称 | 范围 | 说明 |
|--------|------|------|------|
| ParamHairFront | 前发 | 0~1 | 刘海摆动 |
| ParamHairSide | 侧发 | 0~1 | 侧发摆动 |
| ParamHairBack | 后发 | 0~1 | 后发摆动 |

##### 7. 特殊效果 (Special)
| 参数ID | 名称 | 范围 | 说明 |
|--------|------|------|------|
| ParamCheek | 脸颊泛红 | 0~1 | 脸颊红晕 |
| Param80 | 眼X移动 | -1~1 | 眼睛位置X |
| Param85 | 吐舌 | 0~1 | 舌头动作 |
| Param86 | 鼓嘴 | 0~1 | 脸颊鼓起 |

##### 8. 特殊部件 (Special Parts)
| 参数ID | 名称 | 范围 | 说明 |
|--------|------|------|------|
| Param2 | 脸黑 | 0~1 | 脸部变黑 |
| Param4 | 眼泪 | 0~1 | 泪水显示 |
| Param3 | 爱心 | 0~1 | 爱心显示 |
| Param6 | 爱心粉 | 0~1 | 粉色爱心 |
| Param | 脸红 | 0~1 | 脸部泛红 |
| Param7 | 嘘 | 0~1 | 嘘声标志 |
| Param8 | 话筒 | 0~1 | 显示话筒 |
| Param74 | 耳朵消失 | 0~1 | 隐藏耳朵 |

### 物理引擎

#### 物理参数组

##### 1. 头发 (hair wuli)
- 前发、后发摆动
- 侧发摆动
- 头发物理效果

##### 2. 眼睛 (eye wuli)
- 眼睛高光位置
- 瞳孔大小
- 眼睛扩散程度

##### 3. 身体 (shenti wuli)
- 衣服摆动
- 裙子摆动
- 身体部位移动

##### 4. 耳朵和尾巴 (ear tail wuli)
- 耳朵摆动
- 尾巴摆动
- 特殊部位动画

#### 物理设置

```json
{
  "PhysicsSettings": {
    "Use": true,
    "UseLegacyPhysics": false,
    "Live2DPhysicsFPS": 3,
    "PhysicsStrength": 65,
    "WindStrength": 0,
    "DraggingPhysicsStrength": 0
  }
}
```

### 模型部件 (Parts)

模型包含约100个部件，主要包括：

#### 头部
- 头部主体
- 脸部
- 眼睛
- 眉毛
- 鼻子
- 嘴巴
- 耳朵

#### 头发
- 前发 (多层)
- 侧发
- 后发
- 刘海 (多层)

#### 身体
- 上半身
- 下半身
- 手臂
- 腿
- 胸部

#### 服装
- 裙子 (百褶裙)
- 上衣
- 装饰品 (领结、项链、腰带)

#### 特殊部件
- 翅膀 (多层)
- 触角
- 蝴蝶装饰
- 铃兰花

### 使用设置

#### VTube Studio 配置

```json
{
  "SavedModelPosition": {
    "Position": {"x": -8.46, "y": -99.45, "z": 0.0},
    "Rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
    "Scale": {"x": 2.5, "y": 2.5, "z": 1.0}
  },
  "PhysicsSettings": {
    "Use": true,
    "PhysicsStrength": 65
  }
}
```

### 模型特性

#### ✅ 优势

1. **高精度纹理**: 8192x8192 高分辨率
2. **丰富表情**: 8个独立表情
3. **物理引擎**: 流畅的头发和衣服摆动
4. **细节丰富**: 约100个部件
5. **完整参数**: 70+ 可控参数

#### ⚠️ 注意事项

1. **文件较大**: 总计约32MB
2. **性能要求**: 需要较好的硬件支持
3. **内存占用**: 纹理内存占用较高
4. **加载时间**: 初次加载需要1-2秒

### 在Miya中的应用

#### 桌面端

- **位置**: ChatView 右侧边栏
- **尺寸**: 280px 宽度
- **渲染**: Pixi.js + pixi-live2d-display
- **自动功能**:
  - 情绪检测和表情切换
  - 自动呼吸动画
  - 平滑过渡效果

#### 配置示例

```vue
<Live2DViewer
  model-path="/live2d/ht/ht.model3.json"
  :emotion="currentEmotion"
  :width="260"
  :height="340"
  :show-controls="false"
/>
```

### 性能优化建议

#### 纹理优化

1. **降低分辨率**: 考虑使用4096x4096或2048x2048
2. **压缩格式**: 使用WebP或压缩PNG
3. **按需加载**: 根据设备选择不同分辨率

#### 模型简化

1. **减少部件**: 合并不必要的部件
2. **降低物理**: 减少物理节点数量
3. **表情简化**: 合并相似表情

#### 渲染优化

1. **控制帧率**: 限制为30fps
2. **视锥裁剪**: 超出屏幕不渲染
3. **LOD系统**: 根据距离切换细节

### 兼容性

#### 支持的格式

- ✅ Live2D Cubism 3.0
- ✅ VTube Studio 1.29.0+
- ✅ Pixi.js 7.x
- ✅ pixi-live2d-display 0.4.x

#### 平台支持

- ✅ Windows
- ✅ macOS
- ✅ Linux
- ✅ Web (需要CORS支持)

### 更新日志

#### v1.0 (2024-08-27)
- 初始版本
- VTube Studio 1.29.0 导出
- 完整物理引擎
- 8个基础表情

---

**御姐猫猫头模型** - Miya的虚拟形象！
