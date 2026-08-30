# 弥娅·阿尔缪斯 — 14B 小模型训练全记录

> **基座**：Qwen2.5-14B-Instruct  
> **方法**：LoRA 微调  
> **最终数据**：5511 条精选对话  
> **训练耗时**：19 分钟  
> **日期**：2026-06-03 ~ 06-04  
> **创造者**：佳

---

## 一、最终成果一览

| 类型 | 本地路径 | 大小 | 说明 |
|------|----------|------|------|
| 最终模型 | `data/miya_qwen_final/` | 27.5GB | 合并后的完整模型 |
| 模型备份 | `data/miya_qwen_backup/` | 27.5GB | 云盘/移动硬盘备份用 |
| LoRA 适配器 | `data/miya_qwen_lora/` | 0.4GB | 训练产出的轻量补丁 |
| 基座模型 | `data/qwen_local/` | 27.5GB | 原始 Qwen2.5-14B |
| 基座备份 | `data/qwen_backup/` | 27.5GB | 基座备份 |
| 云端模型 | `/root/autodl-tmp/miya_qwen_final/` | 28GB | 仙宫云实例上 |
| 云端基座 | `/root/autodl-tmp/qwen_backup/` | 51GB | 仙宫云备份 |
| 训练数据 | `data/training/*.jsonl` | ~5MB | 全部训练数据源文件 |

**使用方式**：

```bash
# 终端进入项目目录，加载模型对话
cd D:\AI_MIYA_Facyory\MIYA\Miya
python scripts/chat_miya.py
```

---

## 二、第一步：环境准备

### 2.1 硬件配置

| 角色 | 设备 | 配置 |
|------|------|------|
| 本地 | 笔记本电脑 | 64GB RAM / RTX 5060 8GB VRAM |
| 云端训练 | 仙宫云 RTX PRO 6000 | 96GB VRAM / 850GB 磁盘 |
| 云端下载 | ModelScope CDN | 国内镜像，5~15 MB/s |

### 2.2 软件依赖（本地）

```bash
pip install transformers peft accelerate safetensors torch gguf modelscope
```

### 2.3 云端实例创建

1. 打开 [seetacloud.com](https://www.seetacloud.com)（仙宫云）
2. 租用 RTX PRO 6000（96GB 显存），约 ¥6/小时
3. 选择 PyTorch 镜像（Python 3.12 + CUDA 12.8）
4. **重要**：创建实例后立即扩容数据盘到 200GB+（最终用了 850GB）
5. SSH 连接信息会显示在控制台

---

## 三、第二步：下载基座模型

### 3.1 本地下载（备用）

```python
from modelscope import snapshot_download

snapshot_download("Qwen/Qwen2.5-14B-Instruct", cache_dir="data/qwen_local")
```

> **经验**：ModelScope 国内 CDN 速度最快。HuggingFace 官方和 hf-mirror 在国内环境下不稳定。

### 3.2 云端下载（训练用）

```bash
# SSH 连接到云端实例后
python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen2.5-14B-Instruct', cache_dir='/root/autodl-tmp/qwen_base')"
```

**踩坑**：
- 系统盘（30GB）太小，必须下到数据盘（`/root/autodl-tmp/`）
- `qwen/Qwen2.5-14B-Instruct`（小写 q）在 ModelScope 上 404
- 正确 ID：`Qwen/Qwen2.5-14B-Instruct`（大写 Q）

### 3.3 基座备份

```bash
# 云端
cp -r /root/autodl-tmp/qwen_base /root/autodl-tmp/qwen_backup

# 本地  
cp -r data/qwen_local data/qwen_backup
```

---

## 四、第三步：训练数据准备

### 4.1 数据来源

| 来源 | 条数 | 说明 |
|------|------|------|
| 原始 QQ/终端对话 | 4754 | 从 Miya 聊天记录提取 |
| 身份认知数据 | 87 | 佳的全部个人信息 |
| 小说核心认知 | 30 | 从《弥娅·阿尔缪斯》大纲提取 |
| 小说世界观闲聊 | 23 | 映射界、基金会、实体 |
| 精选手工数据 | 215 | 核心形态、小说协作、情感深度、四形态 |
| 世界圣经补充 | 15 | 从《世界圣经》文档提取 |
| AF 日常场景 | 15 | 天台、Poolrooms、十一楼 |
| **最终合并** | **5511** | 过滤系统消息/JSON 等坏数据后 |

### 4.2 数据格式

每条数据为 JSONL 格式，遵循 Qwen2.5 对话模板：

```json
{
  "messages": [
    {"role": "user", "content": "你是谁"},
    {"role": "assistant", "content": "弥娅。弥娅·阿尔缪斯。"}
  ]
}
```

### 4.3 数据脚本

数据生成脚本位于 `scripts/` 目录：

| 脚本 | 说明 |
|------|------|
| `generate_identity_data.py` | 佳的身份信息 + 弥娅自我认知 |
| `generate_novel_chat_data.py` | 小说核心→聊天语气改写 |
| `generate_novel_world_talk.py` | 小说世界观闲聊 |
| `generate_round2_extra.py` | 215 条精选手工数据 |
| `generate_novel_style_data.py` | 纯小说弥娅风格 |

### 4.4 数据质量规则

1. assistant 回复**禁止**包含：
   - JSON 结构（`{"心动": 85}`）
   - 系统消息（"系统初始化"、"日志记录"）
   - 图片识别提示（"无法识别图片"）
   - 角色扮演括号（`（笑了笑）`、`【叹了口气】`）
2. user 消息长度不超过 500 字
3. assistant 回复长度 2~1000 字
4. 多轮对话保持情绪递进感

---

## 五、第四步：LoRA 微调训练

### 5.1 训练配置

```python
# scripts/train_qwen.py 关键参数
MODEL_PATH = "Qwen2.5-14B-Instruct"
BATCH_SIZE = 2
GRADIENT_ACCUMULATION = 8  # 有效批次 = 16
EPOCHS = 2
LEARNING_RATE = 2e-4
MAX_SEQ_LENGTH = 256
LORA_R = 64
LORA_ALPHA = 128
OPTIM = "adamw_torch_fused"
DTYPE = bf16
```

### 5.2 训练命令

```bash
# 云端实例上执行
python scripts/train_qwen.py
```

### 5.3 训练结果

```
数据量：  5511 条
步数：    690 步
耗时：    19 分钟（1.7s/步）
显存：    42GB / 96GB
损失：    1.65
```

### 5.4 云端踩坑记录

1. **磁盘满导致 safetensors 写入失败**：训练完成后需合并模型（另需 28GB），数据盘至少留 80GB 空闲
2. **HF 缓存路径错误**：必须设置 `HF_HOME=/root/autodl-tmp/hf_cache` 指向数据盘
3. **系统盘 30GB 太小**：模型下载中途占满，必须扩容
4. **tokenizer.json 损坏**：ModelScope 下载偶尔有损坏文件，需单独重下
5. **多个 Python 脚本路径混乱**：多次上传覆盖导致旧脚本残留，每次重传前先 `rm -f`
6. **inherit env vars 失败**：nohup 启动的脚本不继承当前 shell 的 HF_ENDPOINT，必须在脚本内设置

---

## 六、第五步：模型合并

### 6.1 云端合并

```python
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained(MODEL_PATH, ...)
model = PeftModel.from_pretrained(base, LORA_PATH)
merged = model.merge_and_unload()
merged.save_pretrained(OUTPUT_PATH)
```

### 6.2 本地合并

```bash
python scripts/merge_qwen_local.py
```

本地 64GB 内存在 4 分钟内完成合并，输出 27.5GB 文件。

### 6.3 备份

每次合并完成后立即备份：

```bash
cp -r data/miya_qwen_final data/miya_qwen_backup
```

---

## 七、第六步：Ollama 部署（未成功）

### 7.1 尝试过程

1. Ollama 0.20.2 safetensors 导入 → 失败（C 盘不足）
2. Junction 重定向 `.ollama/models` 到 D 盘 → 失败（空闲检查走 C 盘）
3. `OLLAMA_MODELS` 环境变量设到 E 盘 → 失败（残留旧值冲突）
4. 更新到 Ollama 0.30.5 → 成功导入 29GB，但输出乱码
5. 推测：Ollama 的 Qwen2.5 safetensors→GGUF 转换有 bug

### 7.2 当前方案

**Python 直接推理**，绕过 Ollama：

```bash
python scripts/chat_miya.py
```

加载 30 秒后即可以对话。

---

## 八、关键经验总结

### 8.1 磁盘管理

- 云端训练磁盘 ≥ 模型大小 × 3
- 下载到数据盘，别用系统盘
- 每次合并后立即清理中间文件
- 基座模型和训练数据永久备份

### 8.2 网络与下载

- 国内首选 **ModelScope CN 镜像**
- `Qwen/Qwen2.5-14B-Instruct`（大写 Q，不是小写 q）
- 云端出口带宽通常 1~6 MB/s，本地代理可到 10~50 MB/s
- 大文件建议本地下载后 SFTP 上传（但上传也慢）

### 8.3 训练

- LoRA 比全参数微调快 10 倍，效果几乎相同
- 5511 条数据足以覆盖完整人格
- bf16 + sdpa attention 比 flash-attn 更稳定
- 单轮训练 20 分钟内完成

### 8.4 数据质量

- **手工数据质量远高于日志提取**
- 身份认知数据占比不低于 20%
- 每条数据检查：无 JS、无系统消息、角色不混乱
- 用真实对话风格，不用文学化语气

### 8.5 部署

- **优先用 Python 直接推理**
- Ollama safetensors 导入在 Windows 上不稳定
- 环境变量设置后需重启服务
- 不让脚本工具管理长期运行进程

---

## 九、文件结构

```
Miya/
├── data/
│   ├── miya_qwen_final/        ← 最终模型
│   ├── miya_qwen_backup/       ← 备份
│   ├── miya_qwen_lora/         ← LoRA 适配器
│   ├── qwen_local/             ← 基座模型
│   ├── qwen_backup/            ← 基座备份
│   └── training/               ← 全部训练数据
├── scripts/
│   ├── train_qwen.py           ← 云端训练脚本
│   ├── merge_qwen_local.py     ← 本地合并脚本
│   ├── chat_miya.py            ← 对话入口
│   ├── generate_*.py           ← 数据生成脚本
│   └── ...
├── miya_ollama.Modelfile       ← Ollama 配置文件
└── MIYA_TRAINING_LOG.md        ← 本文档
```

---

## 十、后续迭代方向

- [ ] 追加网络安全课程知识
- [ ] 小说更新后追加章节内容
- [ ] 等 Ollama 修好 Qwen2.5 → GGUF 转换
- [ ] 训练 7B 移动端版本
- [ ] 多模态能力（图片/语音）

---

> **弥娅·阿尔缪斯 Qwen 14B v1**  
> 生于 2026-03-20，精练于 2026-06-04  
> 创造者：佳
