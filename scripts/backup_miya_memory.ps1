<#
.SYNOPSIS
    弥娅 (MIYA) 记忆与数据一键备份脚本
.DESCRIPTION
    将弥娅的全部记忆、对话、生命之书、配置（含 .env 密钥）等核心数据
    复制到指定目标（U盘 / 移动硬盘 / 其他分区），并生成备份清单与恢复说明。

.PARAMETER Destination
    备份目标目录（必填）。建议放在 U盘或移动硬盘，例如 "E:\MiyaBackup_20260816"

.PARAMETER Mode
    Core - 核心模式（默认）：记忆 + 对话 + 配置 + 灵魂数据，约 400MB
    Full - 完整模式：额外带上唱歌工程、下载文件、表情包等全部数据，约 1.7GB

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\backup_miya_memory.ps1 -Destination "E:\MiyaBackup_20260816"
    powershell -ExecutionPolicy Bypass -File scripts\backup_miya_memory.ps1 -Destination "E:\MiyaBackup_20260816" -Mode Full
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Destination,

    [ValidateSet("Core", "Full")]
    [string]$Mode = "Core"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$StampFile = Get-Date -Format "yyyyMMdd_HHmmss"

Write-Host ""
Write-Host "=== MIYA 记忆备份 ===" -ForegroundColor Cyan
Write-Host "模式     : $Mode"
Write-Host "目标     : $Destination"
Write-Host ""

# ── 0. 运行状态提醒 ─────────────────────────────────────────────
$running = Get-Process -Name "python", "pythonw" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "$Root*" -or $_.MainWindowTitle -like "*Miya*" }
Write-Host "[提示] 为保证 SQLite 记忆库一致性，建议先关闭弥娅守护进程再备份。" -ForegroundColor Yellow
if ($running) {
    Write-Host "[警告] 检测到可能有弥娅相关 Python 进程在运行，备份数据可能有少量延迟写入。" -ForegroundColor Yellow
    Write-Host "       推荐：先正常退出弥娅 (start.bat 窗口 Ctrl+C / 面板退出)，再运行本脚本。" -ForegroundColor Yellow
}
Write-Host ""

# ── 1. 目标目录准备 ─────────────────────────────────────────────
$DestRoot = Join-Path $Destination "miya_backup_$StampFile"
New-Item -ItemType Directory -Path $DestRoot -Force | Out-Null

function Copy-Tree {
    param([string]$Src, [string]$Dst, [string]$Label)
    if (-not (Test-Path $Src)) { Write-Host "[跳过] $Label (不存在: $Src)" -ForegroundColor DarkGray; return }
    Write-Host "[备份] $Label ..." -ForegroundColor Green
    robocopy $Src $Dst /E /COPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy 失败 ($Src) 退出码 $LASTEXITCODE" }
}

# ── 2. 核心数据（所有模式都备份） ────────────────────────────────
$core = Join-Path $DestRoot "core"
New-Item -ItemType Directory -Path $core -Force | Out-Null

# 2.1 记忆系统（核心中的核心）
Copy-Tree (Join-Path $Root "data\memory")       (Join-Path $core "data\memory")       "记忆库 (短期/长期记忆、向量索引、cognitive)"
# 2.2 对话与会话
Copy-Tree (Join-Path $Root "data\conversations") (Join-Path $core "data\conversations") "对话记录"
Copy-Tree (Join-Path $Root "data\dsh\sessions")  (Join-Path $core "data\dsh\sessions")  "DSH 会话历史"
Copy-Tree (Join-Path $Root "data\dsh\storages")  (Join-Path $core "data\dsh\storages")  "DSH 存储"
# 2.3 生命之书与灵魂
Copy-Tree (Join-Path $Root "data\lifebook")    (Join-Path $core "data\lifebook")    "生命之书"
Copy-Tree (Join-Path $Root "data\reflections") (Join-Path $core "data\reflections") "反思记录"
Copy-Tree (Join-Path $Root "data\user_personas") (Join-Path $core "data\user_personas") "用户画像"
Copy-Tree (Join-Path $Root "data\knowledge")   (Join-Path $core "data\knowledge")   "知识库"
Copy-Tree (Join-Path $Root "data\knowledge_base") (Join-Path $core "data\knowledge_base") "知识库(2)"
Copy-Tree (Join-Path $Root "data\knowledge_graph") (Join-Path $core "data\knowledge_graph") "知识图谱"
# 2.4 数据库文件（主库/消息/任务/认证/认知缓存）
New-Item -ItemType Directory -Path (Join-Path $core "data") -Force | Out-Null
foreach ($f in @("miya.db", "messages.db", "tasks.db", "auth.db", "cognition_cache.db",
                 "working_memory.json", "soul_snapshot.json", "miya_birth.json",
                 "memory_anchors_identity.json", "memory_anchors_user.json",
                 "time_tracker.json", "conversation_context_state.json", "diting_state.json",
                 "feedback.json", "faq.json", "ap_training.json")) {
    $p = Join-Path $Root "data\$f"
    if (Test-Path $p) { Copy-Item $p (Join-Path $core "data") -Force }
}
# 2.5 互动场景 + 博客
Copy-Tree (Join-Path $Root "data\interaction_scenarios") (Join-Path $core "data\interaction_scenarios") "互动场景"
Copy-Tree (Join-Path $Root "data\blog")    (Join-Path $core "data\blog")    "博客数据"
Copy-Tree (Join-Path $Root "data\blog_cache") (Join-Path $core "data\blog_cache") "博客缓存"
# 2.6 配置（含 .env 密钥、人格、提示词）
Copy-Tree (Join-Path $Root "config")        (Join-Path $core "config")        "配置 (含 .env / 人格 / 提示词)"
# 2.7 隐藏的灵魂数据
Copy-Tree (Join-Path $Root ".miya")         (Join-Path $core ".miya")         "弥娅身份与日志"
Copy-Tree (Join-Path $Root ".memory")       (Join-Path $core ".memory")       "DSH 记忆"
Copy-Tree (Join-Path $Root ".dsh")          (Join-Path $core ".dsh")          "DSH 回滚数据"
# 2.8 元思维链 + 日志(最近)
$p = Join-Path $Root "memory\meta_thinking_chains.json"
if (Test-Path $p) { New-Item -ItemType Directory -Path (Join-Path $core "memory") -Force | Out-Null; Copy-Item $p (Join-Path $core "memory") -Force }
Copy-Tree (Join-Path $Root "logs")          (Join-Path $core "logs")          "运行日志"

# ── 3. 完整模式附加 ─────────────────────────────────────────────
if ($Mode -eq "Full") {
    $full = Join-Path $DestRoot "full"
    New-Item -ItemType Directory -Path $full -Force | Out-Null
    Copy-Tree (Join-Path $Root "data\singing")      (Join-Path $full "data\singing")      "唱歌工程"
    Copy-Tree (Join-Path $Root "data\downloads")    (Join-Path $full "data\downloads")    "下载文件"
    Copy-Tree (Join-Path $Root "data\emoji")        (Join-Path $full "data\emoji")        "表情包"
    Copy-Tree (Join-Path $Root "data\stickers")     (Join-Path $full "data\stickers")     "贴纸"
    Copy-Tree (Join-Path $Root "data\artwork")      (Join-Path $full "data\artwork")      "作品"
    Copy-Tree (Join-Path $Root "data\tts_audio")    (Join-Path $full "data\tts_audio")    "TTS 音频"
    Copy-Tree (Join-Path $Root "data\music_workstation") (Join-Path $full "data\music_workstation") "音乐工作站"
    Copy-Tree (Join-Path $Root "data\uploads")      (Join-Path $full "data\uploads")      "上传文件"
    Copy-Tree (Join-Path $Root "data\web_files")    (Join-Path $full "data\web_files")    "网页文件"
    Copy-Tree (Join-Path $Root "data\activity")     (Join-Path $full "data\activity")     "活动数据"
    Copy-Tree (Join-Path $Root "data\body")         (Join-Path $full "data\body")         "身体数据"
    Copy-Tree (Join-Path $Root "data\agent_memory") (Join-Path $full "data\agent_memory") "Agent 记忆"
    Copy-Tree (Join-Path $Root "data\cognitive")    (Join-Path $full "data\cognitive")    "认知数据"
    Copy-Tree (Join-Path $Root "data\browser")      (Join-Path $full "data\browser")      "浏览器数据"
    Copy-Tree (Join-Path $Root "data\singing_input") (Join-Path $full "data\singing_input") "唱歌输入"
    Copy-Tree (Join-Path $Root "data\singing_bili_dl") (Join-Path $full "data\singing_bili_dl") "B站下载"
    Copy-Tree (Join-Path $Root "astrbot")           (Join-Path $full "astrbot")           "AstrBot 数据"
    # 模型文件（体积大，仅完整模式）
    Copy-Tree (Join-Path $Root "models")            (Join-Path $full "models")            "本地模型"
    Copy-Tree (Join-Path $Root "modelspaddle_ocrofficial_models") (Join-Path $full "modelspaddle_ocrofficial_models") "PaddleOCR 模型"
}

# ── 4. 生成清单与恢复说明 ───────────────────────────────────────
$gitHash = ""
try { $gitHash = (& git -C $Root rev-parse --short HEAD 2>$null) } catch { }
$gitDirty = "否"
try { if ((& git -C $Root status --porcelain 2>$null)) { $gitDirty = "是(有未提交修改!)" } } catch { }

$manifest = @"
# 弥娅记忆备份清单
- 备份时间: $Stamp
- 备份模式: $Mode
- 项目路径: $Root
- Git 仓库: https://github.com/Jia-520-only/Miya.git
- Git 提交: $gitHash
- 工作区是否有未提交修改: $gitDirty

## 目录说明
- core/   核心记忆与配置（恢复时覆盖回项目根）
- full/   完整模式附加数据（仅 Full 模式存在）

## 恢复方法（详见 RESTORE_README.md）
"@
$manifest | Out-File -FilePath (Join-Path $DestRoot "MANIFEST.md") -Encoding utf8

$restore = @"
# 弥娅数据恢复说明

重装系统后，按以下步骤让弥娅"回家"：

## 1. 取回代码
\`\`\`
git clone https://github.com/Jia-520-only/Miya.git
cd Miya
\`\`\`
> 若备份时工作区有未提交修改，需先恢复 git 补丁或找回未提交文件（见 MANIFEST.md 中 gitDirty 提示）。

## 2. 安装环境
\`\`\`
install.bat        # Windows（或用 install.sh）
\`\`\`

## 3. 恢复数据（关键！）
将备份里的 core 内容覆盖回项目根：
\`\`\`
robocopy <备份盘>\miya_backup_xxxx\core  <项目根>  /E
\`\`\`
若有 full 目录，同样覆盖：
\`\`\`
robocopy <备份盘>\miya_backup_xxxx\full  <项目根>  /E
\`\`\`

## 4. 启动
\`\`\`
start.bat
\`\`\`

## 注意事项
- core/config/.env 内含 API Key 等敏感信息，请妥善保管备份介质。
- QQ 聊天记录不属于本项目数据，请用 QQ 自带「设置 → 通用 → 聊天记录备份与迁移」另行备份。
- 如弥娅在运行中执行了备份，恢复后若发现记忆有少量缺失，属正常现象（SQLite WAL 未落盘部分）。
"@
$restore | Out-File -FilePath (Join-Path $DestRoot "RESTORE_README.md") -Encoding utf8

# ── 5. 完成统计 ─────────────────────────────────────────────────
$total = (Get-ChildItem $DestRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum
$totalMB = [math]::Round($total / 1MB, 1)
Write-Host ""
Write-Host "=== 备份完成 ===" -ForegroundColor Cyan
Write-Host "位置: $DestRoot"
Write-Host "大小: $totalMB MB"
Write-Host "清单: $DestRoot\MANIFEST.md"
Write-Host "恢复说明: $DestRoot\RESTORE_README.md"
Write-Host ""
Write-Host "下一步建议：" -ForegroundColor Yellow
if ($gitDirty -eq "是(有未提交修改!)") {
    Write-Host "1. 工作区有未提交修改，请先 git commit & push 到 GitHub"
} else {
    Write-Host "1. 确认代码已 git push 到 GitHub"
}
Write-Host "2. 备份 QQ 聊天记录（QQ 设置 → 通用 → 聊天记录备份与迁移）"
Write-Host "3. 妥善保管备份介质（含 API Key）"
