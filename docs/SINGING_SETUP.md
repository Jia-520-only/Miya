# 弥娅 RVC 翻唱模块部署指南

在任意 Windows 电脑上快速配置弥娅 RVC 翻唱功能。

## 组件清单

| 组件 | 用途 | 必需 | 获取方式 |
|------|------|------|----------|
| RVC 整合包 | 声线换声 + 自带 UVR5 分离 + ffmpeg + MDX 分离部件 | ✅ | RVC WebUI 整合包（含 `runtime/`、`assets/weights/`、`assets/uvr5_weights/`、`start_api.bat`、`ffmpeg.exe`、`mdx/`） |
| 声线模型 (`.pth`) | 换声目标音色 | ✅ | 放入 `{rvc_root}/assets/weights/`（默认配置用 `xiadie`） |
| 音色索引 (`.index`) | 音色检索还原（可省略） | ⭕ 可选 | 放入 `{rvc_root}/assets/indices/`，`rvc_index_path` 配置 |
| MDX 分离部件 | 多轮分离（Inst_HQ_3 伴奏分离 + KARA_2 和声提取） | ✅* | 推荐放 `{rvc_root}/mdx/`（runtime + models），随 RVC 包一起分发 |
| GPT-SoVITS 整合包 | UVR5 最强分离 (BS-Roformer) | ⭕ 可选 | 没有时自动回退 RVC 自带的 HP5 分离（质量略低但可用） |
| NVIDIA GPU | RVC/UVR5 推理加速 | ✅ | CUDA 兼容显卡（推荐 8GB 显存以上；无独显可用 CPU 但极慢） |
| ffmpeg | 音频转换/混音兜底 | ⭕ | RVC 整合包自带，或系统安装 |
| NeteaseCloudMusicApi | 网易云点歌搜索 | ⭕ | 可选，`localhost:3000`；没有也能用本地/B 站源 |
| yutto | B 站音源下载 | ⭕ | 可选，装在 RVC runtime：`runtime\python.exe -m pip install yutto` |

> \* 仅当配置 `separation_stages_enabled=true`（默认）时必需；改为 `false` 则回退传统分离，
> 此时不需要 MDX 分离部件。
>
> MDX 分离部件取自 Live2D-Virtual-Girlfriend 整合包（`runtime/` 为 conda Python 3.11 环境，
> 含 torch + onnxruntime_gpu + audio_separator，整体拷贝即可，无路径依赖）：
>
> ```
> {rvc_root}/mdx/
> ├── runtime/              # conda 环境 (torch CUDA + onnxruntime_gpu + audio_separator)
> └── models/UVR/*.onnx     # MDX 模型 (Inst_HQ_3 + KARA_2 + json)
> ```
>
> 弥娅 TTS 若使用 GPT-SoVITS，则翻唱会自动复用它的最强分离器；即使完全没有 GPT-SoVITS，
> 翻唱也能用 RVC 整合包自带的 HP5 完成分离——**只部署一个 RVC 整合包即可开唱**。

## 分离引擎回退链（自动选择）

```
1. GPT-SoVITS UVR5 (BS-Roformer, SDR 12.97)   ← 有 GPT-SoVITS 整合包时, 质量最高
2. RVC 自带 UVR5 (HP5_only_main_vocal)         ← 只有 RVC 整合包时
3. demucs (需 pip install demucs)              ← 两个整合包都没有时
4. ffmpeg 整曲兜底 (跳过换声直接播原曲)
```

## 快速配置（换机器零配置）

整合包路径默认**全部留空、自动探测**：弥娅会扫描项目父目录、项目内 `tools/`、
各盘符根目录及 `AIvoice` 等常见目录，按目录特征自动识别：

- RVC 整合包：`start_api.bat` + `assets/weights/`（支持 `RVCxxx/RVCxxx` 双层嵌套结构）
- GPT-SoVITS 整合包：`tools/uvr5/uvr5_weights/`
- MDX 分离部件：`{rvc_root}/mdx/`（随 RVC 包自动跟随）

```json
"paths": {
  "rvc_root": "",          // 留空自动探测
  "gpt_sovits_root": "",   // 留空自动探测
  "mdx_root": "",          // 留空自动用 {rvc_root}/mdx
  "ffmpeg": ""             // 留空自动用 RVC 包自带
}
```

仅当整合包放在非常规位置时才需要显式填写（支持 `{rvc_root}` 模板）。

步骤：

1. 把声线模型（`.pth`）放进 `{rvc_root}/assets/weights/`，索引（`.index`）放进 `assets/indices/`；
2. 把配置里 `rvc_model` 改为你的模型名（可省略 `.pth` 后缀）；
3. 运行自检脚本确认环境（检查路径探测、三个整合包、模型、索引、ffmpeg、pip 依赖、服务连通性等 7 大类）：

```bash
python scripts/singing_env_check.py
```

4. 启动弥娅守护进程，点歌即可。RVC 服务未运行时弥娅会自动拉起 `start_api.bat`（首次需 1-2 分钟）。

## 换电脑部署清单

弥娅唱歌模块的外部依赖全部集中在以下三类，没有散落各处的隐藏配置：

```
1. 两个整合包目录 (整目录拷贝, 内含 runtime Python + torch/onnxruntime 等, 无需另装)
   ├─ RVC 整合包          (必需: 换声 + ffmpeg + 自带分离回退 + MDX 分离部件)
   └─ GPT-SoVITS 整合包   (可选: 最强分离备选)
2. 弥娅 Python 环境 pip 包 (requirements 已包含)
   numpy / soundfile / pedalboard / pydub / scipy / requests
3. 可选音源
   ├─ 本地音乐库: data/singing_input/*.mp3
   ├─ 网易云: 本机另跑 NeteaseCloudMusicApi (localhost:3000)
   └─ B站: RVC runtime 里装 yutto (可选)
```

步骤：

1. 拷贝整个 Miya 项目（或重新 `pip install -r requirements.txt`）；
2. 拷贝两个整合包目录到新机器（移动硬盘，任意位置——盘符根、`AIvoice/` 文件夹、项目父目录都会被自动探测到）；
3. **无需改配置**（paths 留空自动探测；非常规位置才需填写）；
4. `python scripts/singing_env_check.py` 全绿即开唱；
5. 已有学唱缓存（`data/singing/<歌名>/`）可直接一起拷走，无需重新学唱。

## 目录约定

```
{rvc_root}/
├── start_api.bat            # RVC WebUI 启动脚本 (Gradio API, 端口 7897)
├── assets/weights/*.pth     # 声线模型
├── assets/indices/*.index   # 音色检索索引 (可选, 提升还原度)
├── assets/rmvpe/rmvpe.pt    # rmvpe 音高模型
├── runtime/python.exe       # 自带 Python (demucs 备用分离用)
└── ffmpeg.exe               # 音频工具

{gpt_sovits_root}/
├── runtime/python.exe       # UVR5 CLI 运行环境
└── tools/uvr5/uvr5_weights/ # 分离模型
    ├── model_bs_roformer_ep_317_sdr_12.9755.ckpt   (主分离)
    ├── HP5_only_main_vocal.pth                     (备用)
    ├── 6_HP-Karaoke-UVR.pth                        (和声提取, 多轮分离用)
    └── UVR-De-Echo-Normal.pth                      (去混响, 多轮分离用)
```

## 配置速查（singing_config.json）

| 配置键 | 说明 | 默认 |
|--------|------|------|
| `paths.rvc_root` / `paths.gpt_sovits_root` / `paths.ffmpeg` | 外部工具路径（唯一必须改的） | — |
| `engines.builtin.rvc_model` | 声线模型名 | `guanguanV1` |
| `engines.builtin.rvc_f0_method` | 音高提取算法 `pm/harvest/crepe/rmvpe`（推荐 rmvpe） | `rmvpe` |
| `engines.builtin.rvc_auto_pitch` | 自动变调（按源基频与模型音域中心自适应） | `true` |
| `engines.builtin.rvc_auto_pitch_clamp` | 自动变调幅度上限（±半音，默认 5；过大变调音色劣化） | `5` |
| `engines.builtin.rvc_model_pitch_center` | 模型音域中心 (Hz) | `300` |
| `engines.builtin.rvc_auto_pitch_max_hz` | 变调后输出音高上限 (Hz)，超限时整曲整体下调 | `1000` |
| `engines.builtin.rvc_transpose_accompany` | 自动变调时伴奏/和声轨同步整曲移调（必须开启，否则人声与伴奏不同调） | `true` |
| `engines.builtin.rvc_resample_sr` | RVC 输出重采样采样率（`44100` 服务端 librosa 高质量重采样；`0` 保持模型原生 48k） | `44100` |
| `engines.builtin.rvc_filter_radius` | 音高中值滤波半径（官方默认 3，过大抹平颤音） | `3` |
| `engines.builtin.rvc_server.auto_launch` | RVC 未启动时自动拉起 | `true` |
| `engines.builtin.source_config.input_dirs` | 本地音乐库目录 | `data/singing_input` |
| 顶层 `ai_song_parse_enabled` | 搜索失败时用 AI 解析歌名 | `true` |

`uvr5_python` / `demucs_python` / `rvc_server.launch_bat` / `uvr5_models` 等留空即可，
代码会自动从 `paths` 推导；显式填写则优先使用。模型路径支持
`{rvc_root}` / `{gpt_sovits_root}` 模板。

## 点歌链路

```
点歌消息
 → 规则清洗歌名 (书名号/颜文字/emoji)
 → 搜索: 本地音乐库 → 网易云(可选) → B站
 → (失败) AI 解析歌名 → 再搜索
 → 下载原曲 → UVR5 BS-Roformer 人声分离 (断点续传)
 → 归一化 → RVC 换声 (Gradio API: infer_change_voice + infer_convert, 自动变调)
 → 整曲一致变调: 伴奏/和声轨按人声同一半音数同步移调 (ffmpeg)
 → 混音 (pydub → ffmpeg amix 兜底) → 播放
```

## 常见问题

- **RVC 服务 1-2 分钟才就绪**：正常，整合包需加载 torch；弥娅会轮询等待。
- **唱出来音色不对/偏低**：检查 `rvc_auto_pitch` 是否开启、模型是否训练充分（建议 ≥200 epoch）。
- **50 系显卡**：2024 版整合包对 Blackwell 支持有限，如遇数值异常建议用新整合包或关闭半精度。
- **没有 GPU**：RVC 与 UVR5 均可 CPU 推理，但速度慢数十倍，不建议。
