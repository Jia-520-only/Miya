# 弥娅画板 (ArtNet) 开发文档

弥娅 AI 绘画模块从零到上线的完整设计与实现。

---

## 目录

- [架构概览](#架构概览)
- [文件清单](#文件清单)
- [后端：绘画引擎适配器](#后端绘画引擎适配器)
- [后端：REST API & MCP 服务](#后端rest-api--mcp-服务)
- [前端：Vue 画板页面](#前端vue-画板页面)
- [配置与 API Key 管理](#配置与-api-key-管理)
- [调用方式](#调用方式)
- [踩坑记录](#踩坑记录)

---

## 架构概览

```
┌─ 后端 ─────────────────────────────────────────────────────┐
│  webnet/artnet/                                             │
│  ├── providers/                                             │
│  │   ├── base.py          ← ArtProvider 抽象基类            │
│  │   ├── stable_diffusion.py                                │
│  │   ├── dalle.py                                            │
│  │   ├── novelai.py                                          │
│  │   ├── cogview.py                                          │
│  │   ├── tongyi.py                                           │
│  │   └── comfyui.py       ← 默认引擎，本地 RTX 5060 8GB     │
│  ├── manager.py           ← 多引擎路由 + 故障转移            │
│  └── storage.py           ← 本地图片存储 (data/artwork/)     │
│                                                             │
│  core/web_api/art.py      ← REST API (/api/art/*)           │
│  mcpserver/art_service/   ← MCP 服务 (弥娅主动调用)         │
└─────────────────────────────────────────────────────────────┘
┌─ 前端 ─────────────────────────────────────────────────────┐
│  src/views/ArtboardView.vue           ← 画板主页            │
│  src/components/artboard/                                  │
│  │   ├── PromptPanel.vue              ← 提示词 + 引擎选择   │
│  │   ├── GallerySidebar.vue           ← 作品画廊            │
│  │   └── DoodleCanvas.vue             ← 涂鸦编辑器          │
│  src/api/art.ts                       ← API 客户端          │
│  src/types/art.ts                     ← TypeScript 类型     │
└─────────────────────────────────────────────────────────────┘
```

### 数据流

```
用户输入 → 决策层 → mcp_art_service_generate_image
                          ↓
           ArtProviderManager 路由 → Provider.generate()
                          ↓
           ArtStorage.save() → data/artwork/images/
                          ↓
           返回 local_paths → qq_image(local) → OneBot → QQ
```

---

## 文件清单

### 新增文件

| 文件 | 说明 |
|---|---|
| `webnet/artnet/__init__.py` | 模块入口 |
| `webnet/artnet/providers/base.py` | 抽象基类 `ArtProvider` + `ArtGenerationResult` |
| `webnet/artnet/providers/stable_diffusion.py` | SD WebUI / Forge API |
| `webnet/artnet/providers/dalle.py` | OpenAI DALL·E 3 |
| `webnet/artnet/providers/novelai.py` | NovelAI Diffusion (动漫特化) |
| `webnet/artnet/providers/cogview.py` | 智谱 CogView 异步生成 |
| `webnet/artnet/providers/tongyi.py` | 阿里通义万相异步生成 |
| `webnet/artnet/providers/comfyui.py` | ComfyUI 本地引擎 |
| `webnet/artnet/manager.py` | 多引擎管理器 (路由/故障转移) |
| `webnet/artnet/storage.py` | 本地图片存储 + JSON 索引 |
| `config/artnet/providers.json` | 引擎启用/禁用 + 优先级配置 |
| `core/web_api/art.py` | REST API 路由模块 |
| `mcpserver/art_service/agent-manifest.json` | MCP 服务声明 |
| `mcpserver/art_service/service.py` | MCP 服务实现 |
| `miya_frontend/src/views/ArtboardView.vue` | 画板主页 |
| `miya_frontend/src/components/artboard/PromptPanel.vue` | 左侧控制面板 |
| `miya_frontend/src/components/artboard/GallerySidebar.vue` | 右侧画廊 |
| `miya_frontend/src/components/artboard/DoodleCanvas.vue` | 涂鸦模式 |
| `miya_frontend/src/api/art.ts` | 前端 API 客户端 |
| `miya_frontend/src/types/art.ts` | TypeScript 类型定义 |

### 修改文件

| 文件 | 变更 |
|---|---|
| `core/web_api/__init__.py` | 注册 ArtRoutes |
| `hub/platform_tools.py` | `CORE_TOOLS` 添加 `mcp_art_service_*` + `qq_image` |
| `hub/decision_hub.py` | 画图后跳过智能表情包 |
| `webnet/ToolNet/subnet_router.py` | MCPNet 白名单添加 art 工具 |
| `webnet/ToolNet/tools/qq/qq_image.py` | 修复 target_type 自动检测 + 延迟清理 |
| `core/unified_platform_impl/onebot_platform.py` | 重写 `send_private_image` CQ JSON 段 |
| `miya_frontend/src/views/PanelView.vue` | 添加画板导航卡片 |
| `miya_frontend/src/main.ts` | 添加 `/artboard` 路由 |
| `miya_frontend/electron/main.ts` | 移除独立画板窗口 |
| `config/.env` / `.env.example` | 添加 `OPENAI_API_KEY` + `NOVELAI_API_KEY` |

---

## 后端：绘画引擎适配器

### Provider 抽象基类

```python
class ArtProvider(ABC):
    name: str
    display_name: str
    
    @abstractmethod
    async def generate(prompt, *, negative_prompt, width, height, ...) -> ArtGenerationResult: ...
    
    @abstractmethod
    async def is_available() -> bool: ...
```

所有引擎实现统一的 `generate()` 接口，由 `ArtProviderManager` 按优先级路由。

### 已对接的引擎

| 引擎 | 类型 | 需要 API Key | 特点 |
|---|---|---|---|
| ComfyUI | 本地 | 否 | 节点式工作流，SD 1.5/XL/3 均支持 |
| Stable Diffusion | 本地/远程 | 否 | AUTOMATIC1111 WebUI API |
| DALL·E 3 | 云端 | `OPENAI_API_KEY` | 质量最高，支持风格 |
| NovelAI | 云端 | `NOVELAI_API_KEY` | 动漫风特化，支持 V4 prompt |
| CogView | 云端 | `ZHIPU_API_KEY` | 异步生成，轮询结果 |
| 通义万相 | 云端 | `DASHSCOPE_API_KEY` | 阿里，异步生成 |

### 管理器路由逻辑

```python
# config/artnet/providers.json
{
  "priority": ["comfyui", "dalle", "novelai", "cogview", "tongyi"],
  "providers": { "comfyui": { "enabled": true }, ... }
}
```

- 按 `priority` 顺序尝试
- 跳过 `enabled: false` 的引擎
- `is_available()` 检测连接状态
- 全部失败时返回 `ArtGenerationResult` 含错误信息

---

## 后端：REST API & MCP 服务

### REST API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/art/providers` | 列出可用引擎及状态 |
| `POST` | `/api/art/generate` | 生成图片 |
| `GET` | `/api/art/gallery` | 作品列表 (分页) |
| `GET` | `/api/art/image/{filename}` | 获取图片文件 |
| `DELETE` | `/api/art/image/{id}` | 删除单张 |
| `DELETE` | `/api/art/gallery/clear` | 清空画廊 |
| `GET` | `/api/art/stats` | 存储统计 |

### MCP 工具

注册名：`art_service`，注册在 `mcpserver/art_service/agent-manifest.json`

| 工具 | 说明 |
|---|---|
| `generate_image` | 生成图片，返回 `local_paths` (可用于 qq_image) 和 `image_urls` |
| `list_providers` | 列出可用绘画引擎 |
| `get_gallery` | 查询已有作品 |

### 工具注册流程

MCP 工具有**三层过滤器**，缺少任何一层都会导致 AI 看不到工具：

1. `mcpserver/art_service/agent-manifest.json` — 声明服务
2. `webnet/ToolNet/subnet_router.py` — MCPNet 白名单
3. `hub/platform_tools.py` — 平台工具过滤 (`CORE_TOOLS` / `QQ_EXTENDED_TOOLS`)

---

## 前端：Vue 画板页面

### 路由与入口

- 路由：`/artboard`
- 入口：主面板「⬗ 弥娅画板」卡片
- 独立 Vue 应用页面（非新窗口）

### 页面布局

```
┌─────────────┬──────────────────────┬─────────────┐
│ PromptPanel │    ImageCanvas       │  Gallery    │
│             │    (zoom/pan)        │  Sidebar    │
│ - 引擎选择   │                      │             │
│ - Prompt    │      预览区域          │  缩略图列表  │
│ - 负面词     │                      │             │
│ - 尺寸/风格  │                      │             │
│ - 生成按钮   │                      │             │
└─────────────┴──────────────────────┴─────────────┘
```

### 涂鸦编辑器

`DoodleCanvas.vue` 提供简单的 Canvas 绘图功能，支持：
- 颜色 / 笔刷大小选择
- 参考图叠加（透明度可调）
- 导出 PNG

---

## 配置与 API Key 管理

### 引擎启用配置

```json
// config/artnet/providers.json
{
  "priority": ["comfyui"],
  "providers": {
    "comfyui": { "enabled": true, "base_url": "http://127.0.0.1:8188", "timeout": 300 }
  }
}
```

### API Key

所有 Key 从 `config/.env` 读取，**不在 `providers.json` 中硬编码**：

```env
# AI绘画引擎
OPENAI_API_KEY=       # DALL·E 3
NOVELAI_API_KEY=      # NovelAI Diffusion
# ZHIPU_API_KEY       # CogView (已有的通用 key)
# DASHSCOPE_API_KEY   # 通义万相 (已有的通用 key)
```

---

## 调用方式

### 1. MCP 工具（QQ 聊天）

用户："画一张美少女"

弥娅会自动调用 `mcp_art_service_generate_image` → 获取 `local_paths` → 调用 `qq_image(image_source="local", image_path="D:/...")` → 图片发送到 QQ

### 2. REST API（外部程序）

```bash
curl -X POST http://localhost:8000/api/art/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "一只白猫, 吉卜力风格", "provider": "comfyui", "width": 512, "height": 512}'
```

### 3. 桌面画板（应用内页面）

主面板 → 点击「⬗ 弥娅画板」→ 输入 prompt → 生成 → 预览 / 画廊

---

## 踩坑记录

### 1. MCP 工具三层过滤器 √

AI 提示"没有绘图能力"。

- **根因**：MCP 工具需要同时出现在 `subnet_router.py` MCPNet 白名单 和 `platform_tools.py` CORE_TOOLS 中
- **解决**：两侧都添加 `mcp_art_service_generate_image` / `list_providers` / `get_gallery`

### 2. OneBot 图片发送 √

图片发送失败，用户收到 CQ 码文本。

- **根因**：MIYA 的 `upload_image` 调用 `_call_onebot_api("upload_image")` 在新版 NapCat 中不存在
- **参考**：Undefined 项目 (`D:\AI_MIYA_Facyory\MIYA\AGENT\Undefined`) 直接构建 `[CQ:image,file=file:///绝对路径]` 字符串，NapCat 自动处理上传
- **解决**：`send_private_image` 直接构造 OneBot 标准 JSON 段：
  ```json
  {"type": "image", "data": {"file": "file:///D:/path/to/image.png"}}
  ```

### 3. send_private_msg vs send_msg √

`send_private_msg` 能发文字但不能发图片。

- **解决**：使用通用 `send_msg` action + `message_type: "private"`

### 4. 临时文件秒删 √

生成图片 → 发 JSON → 立即 `os.unlink()` → NapCat 来读 → 文件不存在。

- **解决**：`_delayed_cleanup()` 延迟 30 秒再删，给 NapCat 充足时间

### 5. qq_image 默认发群聊 √

`qq_image` 工具默认 `target_type: "group"`，私聊场景下图片发到不存在的群。

- **解决**：添加 `_detect_message_type()` 从 context 自动判断私聊/群聊

### 6. 画图后智能表情包干扰 √

弥娅发画图响应后，「智能表情包」系统又多发一张无关表情，用户看到错误的图。

- **解决**：响应包含 `画好了` / `发过去了` 时跳过智能表情包

### 7. 图片路径绕路 √

`mcp_art_service_generate_image` 只返回 HTTP URL，AI 用 `qq_image(image_source="url")` 下载到 temp 再发送。

- **解决**：MCP 返回 `local_paths` 绝对路径，AI 直接用 `qq_image(image_source="local")`

### 8. AI 反复尝试已禁用的引擎 √

AI 调用 `provider: "novelai"` → 失败 → 重试 → 浪费时间。

- **解决**：`providers.json` 优先级把 `comfyui` (已启用) 放第一位

### 9. E 盘爆满（ComfyUI） √

ComfyUI 输出目录在 E 盘，写满后生成崩溃 `[Errno 28] No space left on device`。

- **解决**：清理 `ComfyUI/output/` 旧文件，或迁移到空间更大的盘

---

## 总结

弥娅画板从零到上线，打通了以下链路：

```
AI 绘画引擎 → 后端 API → MCP 工具注册 → AI 决策调用 → OneBot 图片发送 → QQ 端展示
```

6 个绘画引擎适配，3 种调用方式（MCP 聊天 / REST API / 桌面画板），支持涂鸦编辑和画廊管理。关键参考：Undefined 项目的 OneBot 图片发送模式（CQ 码直传，无需预上传）。
