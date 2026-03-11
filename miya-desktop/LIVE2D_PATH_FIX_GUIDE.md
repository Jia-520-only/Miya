# Live2D 模型路径修复指南

## ❌ 问题说明

部分模型路径包含特殊字符（中文括号、特殊符号等），导致无法加载。这些模型已被暂时禁用。

## 🔍 被禁用的模型列表

| 模型ID | 原路径问题 | 当前状态 |
|--------|-----------|---------|
| 白发清冷御姐 | 路径正常 | 需要启用 |
| 红醉 | 路径包含 `【` `】` 和中文 | 路径问题 |
| 奶糖啵啵 | 路径包含 `【` `】` | 路径问题 |
| 夜翎 | 路径包含 `【` `】` | 路径问题 |
| 时冰 | 路径包含 `【` `】` | 路径问题 |
| 夜蛊 | 路径包含 `【` `】` 和 `·` | 路径问题 |
| 希斯提亚 | 路径包含 `(` `)` 和 `·` | 路径问题 |
| 漫漫 | 路径包含 `【` `】` 和 `·` | 路径问题 |

---

## ✅ 当前可用模型（5个）

- ✅ **御姐猫猫** (ht) - 正常
- ✅ **修女** - 正常
- ✅ **承** - 正常
- ✅ **白发雪女** - 正常
- ✅ **西域舞女** - 正常

---

## 🔧 修复方法

### 方法一：重命名文件夹（推荐）

通过重命名文件夹，去除特殊字符，然后更新配置。

#### 示例：修复「红醉」模型

**步骤 1：重命名文件夹**

```bash
# 原路径
D:/AI_MIYA_Facyory/MIYA/Miya/live2d/988小fa限量【红醉】动态皮套/

# 新路径
D:/AI_MIYA_Facyory/MIYA/Miya/live2d/red_wine/
```

**步骤 2：更新配置**

打开 `miya-desktop/src/config/live2dModels.ts`，找到被注释的配置：

```typescript
// 取消注释并修改路径
'red_wine': {
  id: 'red_wine',
  name: '红醉',
  path: '/live2d/red_wine/红醉/品酒.model3.json',
  description: '红醉角色，品酒主题'
},
```

**步骤 3：重启应用**

### 方法二：符号链接（高级用户）

使用符号链接避免重命名原始文件夹：

```powershell
# Windows PowerShell
New-Item -ItemType SymbolicLink -Path "D:/AI_MIYA_Facyory/MIYA/Miya/live2d/red_wine" -Target "D:/AI_MIYA_Facyory/MIYA/Miya/live2d/988小fa限量【红醉】动态皮套"
```

---

## 📋 详细修复步骤

### 1. 白发清冷御姐

这个模型路径正常，可以直接启用。

```typescript
// 取消注释
'白发清冷御姐': {
  id: '白发清冷御姐',
  name: '白发清冷御姐',
  path: '/live2d/白发清冷御姐/御姐完整版/御姐完整版.model3.json',
  description: '白发清冷御姐角色，支持多种表情和装扮'
},
```

### 2. 红醉

**重命名方案：**

```bash
# 原路径
988小fa限量【红醉】动态皮套/
└── 红醉/
    └── 品酒.model3.json

# 新路径
red_wine/
└── red_wine/
    └── pinjiu.model3.json

# 或保持中文
红醉/
└── 红醉/
    └── 品酒.model3.json
```

**配置更新：**

```typescript
'red_wine': {
  id: 'red_wine',
  name: '红醉',
  path: '/live2d/red_wine/red_wine/pinjiu.model3.json',
  description: '红醉角色，品酒主题'
},
```

### 3. 夜蛊

**重命名方案：**

```bash
# 原路径
夜蛊【皮套】/【夜蛊·小fa朵】动态皮套/夜蛊·小fa朵/

# 新路径
night_witch/
└── night_witch/
    └── demon_girl.model3.json
```

**配置更新：**

```typescript
'night_witch': {
  id: 'night_witch',
  name: '夜蛊',
  path: '/live2d/night_witch/night_witch/demon_girl.model3.json',
  description: '夜蛊角色，魅魔主题'
},
```

### 4. 夜翎

**重命名方案：**

```bash
# 原路径
【夜翎】皮套/【夜翎】动态皮套/夜翎/

# 新路径
ye_ling/
└── ye_ling/
    └── bat.model3.json
```

### 5. 希斯提亚

**重命名方案：**

```bash
# 原路径
希斯提亚量贩模型-小fa朵 (2)/希斯提亚量贩模型-小fa朵/希斯提亚模型本体小fa朵/

# 新路径
hestia/
└── hestia/
    └── model.model3.json
```

### 6. 漫漫

**重命名方案：**

```bash
# 原路径
小fa限定量贩【漫漫】动态皮套/小fa量贩·漫漫/

# 新路径
manman/
└── fox/
    └── model.model3.json
```

### 7. 奶糖啵啵

**重命名方案：**

```bash
# 原路径
狐仙【皮套】/奶糖啵啵/

# 新路径
candy_bubbles/
└── model/
    └── model.model3.json
```

---

## ⚠️ 注意事项

1. **保持文件完整性**：重命名时确保所有文件都正确移动
2. **更新所有引用**：重命名后记得更新 `live2dModels.ts` 中的配置
3. **测试加载**：重启后测试模型是否能正常加载
4. **备份建议**：重命名前建议先备份原始文件夹

---

## 🚀 批量修复脚本

如果你想批量修复所有模型，可以创建一个 PowerShell 脚本：

```powershell
# fix-live2d-paths.ps1

$basePath = "D:/AI_MIYA_Facyory/MIYA/Miya/live2d"

# 定义重命名映射
$mappings = @{
    "988小fa限量【红醉】动态皮套" = "red_wine"
    "夜蛊【皮套】" = "night_witch"
    "【夜翎】皮套" = "ye_ling"
    "希斯提亚量贩模型-小fa朵 (2)" = "hestia"
    "小fa限定量贩【漫漫】动态皮套" = "manman"
    "狐仙【皮套】" = "candy_bubbles"
}

# 执行重命名
foreach ($oldName in $mappings.Keys) {
    $newName = $mappings[$oldName]
    $oldPath = Join-Path $basePath $oldName
    $newPath = Join-Path $basePath $newName

    if (Test-Path $oldPath) {
        Write-Host "重命名: $oldName -> $newName"
        Rename-Item -Path $oldPath -NewName $newName -ErrorAction SilentlyContinue
    }
}

Write-Host "完成！请更新 live2dModels.ts 配置文件"
```

运行脚本：
```powershell
powershell -ExecutionPolicy Bypass -File fix-live2d-paths.ps1
```

---

## 📝 验证修复

修复后，检查以下几点：

1. ✅ 文件夹已成功重命名
2. ✅ `live2dModels.ts` 配置已更新
3. ✅ 重启应用
4. ✅ 在控制面板中能看到模型
5. ✅ 选择模型后能正常加载

---

## 🆘 仍无法加载？

如果修复后仍然无法加载：

1. 检查浏览器控制台（F12）的错误信息
2. 确认 `.model3.json` 和 `.moc3` 文件都存在
3. 确认路径拼写正确（区分大小写）
4. 尝试使用英文路径和文件名

---

## 📚 相关文档

- [Live2D 模型完整使用指南](./LIVE2D_MODEL_GUIDE.md)
- [Live2D 快速参考](./LIVE2D_QUICK_REFERENCE.md)

---

*最后更新：2026-03-08*
