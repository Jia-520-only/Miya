# 弥娅的 ComfyUI 工作台

工具名：`mcp_art_service_comfyui`，由现有 `art_service` 注册，所有聊天平台均可用。安装代码后重启弥娅使工具清单生效。ComfyUI 需保持运行；地址读取 `config/artnet/providers.json` 中的 `comfyui.base_url`，本机当前为 `http://127.0.0.1:3198`。

支持两条可直接执行的 API 工作流：

- `image`：Illustrious XL 动漫绘图，默认 768×1024、24步；可修改模型、尺寸、种子、步数、CFG、负面词和批量张数。
- `video`：H3 W6A8 图生视频，默认 288×512、5秒、4步、静音、原生 MP4；需要首帧，可增加多媒体参考。配置文件位于 `config/artnet/comfyui_workflows/`。

调用流程：

1. `action=list_workflows` 检查连接；`describe_workflow` 查看该工作流的可调参数与默认值。
2. `action=assist_prompt`，传入 `workflow` 和中文 `prompt`，复用 ComfyUI 已配置的中文助手。该步骤会调用助手当前配置的云端平台；API 密钥保留在原助手配置里。也可直接使用弥娅自己写的提示词。
3. `action=generate`，传入 `workflow`、最终 `prompt` 和可选的 `parameters_json`，例如 `{"width":512,"height":512,"seed":42}`。这里只提交任务，返回 `prompt_id`。
4. `action=get_task`，传入 `prompt_id`，每次最多等20秒；`wait_seconds=0` 可立即查询。只有 `status=success` 才算完成；`queued/running` 仍需等待，`error` 应如实报告。不要重复提交等待中的任务。若任务从队列与历史中消失，会返回 `unknown`。
5. 成功后 `local_paths` 是弥娅本地文件的绝对路径，可交给 `send_platform_file` 发送给当前对话。文件保存在 `data/artwork/comfyui/<prompt_id>/`。

图生视频：先绘图并取得 `local_paths`，或选用已有图片；调用 `action=upload_media`、`file_path=<本机绝对路径>`，得到 `input_name`。然后提交 `workflow=video`，`parameters_json={"first_frame":"miya/返回的文件名.png","seconds":5}`。视频提示词使用中文描述动作、镜头和光线。此入口不执行人物替换；人物/背景替换仍通过原工作流的素材分析与映射确认流程。

工作台只连接本机 HTTP 服务，禁止跟随重定向和系统代理；不会启动其他 ComfyUI 实例或更改显存策略。默认视频沿用 W6A8 稳定路径，不启用 Hybrid INT8。

可在弥娅项目目录用命令行检查，或在重启前独立试用：

```powershell
.venv\Scripts\python.exe scripts\comfyui_workshop.py list_workflows
.venv\Scripts\python.exe scripts\comfyui_workshop.py describe_workflow --workflow video
```

2026-11-04 本机验证：20项测试通过；复用中文助手实际生成了512×512图片，并完成288×512、24 FPS、1秒/24帧的H.264 MP4生成、下载和解码检查。
