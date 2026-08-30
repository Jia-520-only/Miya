# 弥娅备份打包流水线：SQLite 一致性快照 + 双 zip 打包
# 输出: miya_backup_export/miya_core_<date>.zip 与 miya_data_full_<date>.zip
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Out = Join-Path $Root "miya_backup_export"
$Build = Join-Path $Out "_build"
$Core = Join-Path $Build "core"
$Full = Join-Path $Build "full"
$Date = Get-Date -Format "yyyyMMdd"
$CoreZip = Join-Path $Out "miya_core_$Date.zip"
$FullZip = Join-Path $Out "miya_data_full_$Date.zip"

function Robo([string]$src, [string]$dst, [string]$label) {
    if (-not (Test-Path $src)) { Write-Host "[skip] $label"; return }
    Write-Host "[copy] $label"
    robocopy $src $dst /E /XF *.db *.db-wal *.db-shm /COPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy 失败: $src" }
}

# 清空重来
if (Test-Path $Build) { Remove-Item $Build -Recurse -Force }
New-Item -ItemType Directory -Path $Core, $Full, $Out -Force | Out-Null

Write-Host "===== 阶段 1/3: 复制核心数据 ====="
Robo (Join-Path $Root "data\memory") (Join-Path $Core "data\memory") "记忆库"
Robo (Join-Path $Root "data\conversations") (Join-Path $Core "data\conversations") "对话记录"
Robo (Join-Path $Root "data\dsh\sessions") (Join-Path $Core "data\dsh\sessions") "DSH 会话"
Robo (Join-Path $Root "data\dsh\storages") (Join-Path $Core "data\dsh\storages") "DSH 存储"
Robo (Join-Path $Root "data\lifebook") (Join-Path $Core "data\lifebook") "生命之书"
Robo (Join-Path $Root "data\reflections") (Join-Path $Core "data\reflections") "反思"
Robo (Join-Path $Root "data\user_personas") (Join-Path $Core "data\user_personas") "用户画像"
Robo (Join-Path $Root "data\knowledge") (Join-Path $Core "data\knowledge") "知识库"
Robo (Join-Path $Root "data\knowledge_base") (Join-Path $Core "data\knowledge_base") "知识库2"
Robo (Join-Path $Root "data\knowledge_graph") (Join-Path $Core "data\knowledge_graph") "知识图谱"
Robo (Join-Path $Root "data\interaction_scenarios") (Join-Path $Core "data\interaction_scenarios") "互动场景"
Robo (Join-Path $Root "data\blog") (Join-Path $Core "data\blog") "博客"
Robo (Join-Path $Root "data\blog_cache") (Join-Path $Core "data\blog_cache") "博客缓存"
Robo (Join-Path $Root "config") (Join-Path $Core "config") "配置(含 .env)"
Robo (Join-Path $Root ".miya") (Join-Path $Core ".miya") "弥娅身份"
Robo (Join-Path $Root ".memory") (Join-Path $Core ".memory") "DSH 记忆"
Robo (Join-Path $Root ".dsh") (Join-Path $Core ".dsh") "DSH 回滚"
Robo (Join-Path $Root "logs") (Join-Path $Core "logs") "日志"

New-Item -ItemType Directory -Path (Join-Path $Core "data") -Force | Out-Null
foreach ($f in @("working_memory.json","soul_snapshot.json","miya_birth.json",
                 "memory_anchors_identity.json","memory_anchors_user.json","time_tracker.json",
                 "conversation_context_state.json","diting_state.json","feedback.json",
                 "faq.json","ap_training.json","memory_config.example.json","last_form.json")) {
    $p = Join-Path $Root "data\$f"
    if (Test-Path $p) { Copy-Item $p (Join-Path $Core "data") -Force }
}
New-Item -ItemType Directory -Path (Join-Path $Core "data\dsh") -Force | Out-Null
foreach ($f in @("settings.yaml",".credentials.yaml",".anonymous-user-id")) {
    $p = Join-Path $Root "data\dsh\$f"
    if (Test-Path $p) { Copy-Item $p (Join-Path $Core "data\dsh") -Force }
}
New-Item -ItemType Directory -Path (Join-Path $Core "memory") -Force | Out-Null
$p = Join-Path $Root "memory\meta_thinking_chains.json"
if (Test-Path $p) { Copy-Item $p (Join-Path $Core "memory") -Force }

Write-Host "===== 阶段 2/3: SQLite 在线一致性备份 ====="
Push-Location $Root
.venv\Scripts\python.exe scripts\_backup_sqlite.py $Build
if ($LASTEXITCODE -ne 0) { throw "sqlite 备份失败" }
Pop-Location

Write-Host "===== 阶段 3/3: 复制附加数据 (full) ====="
Robo (Join-Path $Root "data\singing") (Join-Path $Full "data\singing") "唱歌工程"
Robo (Join-Path $Root "data\downloads") (Join-Path $Full "data\downloads") "下载文件"
Robo (Join-Path $Root "data\emoji") (Join-Path $Full "data\emoji") "表情包"
Robo (Join-Path $Root "data\stickers") (Join-Path $Full "data\stickers") "贴纸"
Robo (Join-Path $Root "data\artwork") (Join-Path $Full "data\artwork") "作品"
Robo (Join-Path $Root "data\tts_audio") (Join-Path $Full "data\tts_audio") "TTS音频"
Robo (Join-Path $Root "data\music_workstation") (Join-Path $Full "data\music_workstation") "音乐工作站"
Robo (Join-Path $Root "data\uploads") (Join-Path $Full "data\uploads") "上传"
Robo (Join-Path $Root "data\web_files") (Join-Path $Full "data\web_files") "网页文件"
Robo (Join-Path $Root "data\activity") (Join-Path $Full "data\activity") "活动"
Robo (Join-Path $Root "data\body") (Join-Path $Full "data\body") "身体"
Robo (Join-Path $Root "data\agent_memory") (Join-Path $Full "data\agent_memory") "Agent记忆"
Robo (Join-Path $Root "data\cognitive") (Join-Path $Full "data\cognitive") "认知"
Robo (Join-Path $Root "data\browser") (Join-Path $Full "data\browser") "浏览器"
Robo (Join-Path $Root "data\singing_input") (Join-Path $Full "data\singing_input") "唱歌输入"
Robo (Join-Path $Root "data\singing_bili_dl") (Join-Path $Full "data\singing_bili_dl") "B站下载"
Robo (Join-Path $Root "astrbot") (Join-Path $Full "astrbot") "AstrBot"
Robo (Join-Path $Root "models") (Join-Path $Full "models") "本地模型"
Robo (Join-Path $Root "modelspaddle_ocrofficial_models") (Join-Path $Full "modelspaddle_ocrofficial_models") "PaddleOCR"

$readme = @"
弥娅备份包说明
================
打包时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Git 提交: $(try { & git -C $Root rev-parse --short HEAD 2>$null } catch { '?' })

- miya_core_$Date.zip   核心包 (必须): 记忆库/对话/生命之书/配置/灵魂数据
- miya_data_full_$Date.zip 附加包 (可选): 唱歌工程/下载文件/表情包/模型等

恢复方法:
  1. 重装后 git clone https://github.com/Jia-520-only/Miya.git
  2. install.bat
  3. 解压 core 包, 把 core 目录内容覆盖回项目根 (robocopy 或直接拖拽)
  4. 可选: 解压 full 包同样覆盖
  5. start.bat

注意: core 包内含 config/.env 与 .credentials.yaml 等敏感密钥, 请勿公开分享!
"@
$readme | Out-File (Join-Path $Out "README_备份说明.txt") -Encoding utf8

Write-Host "===== 打包压缩 ====="
Write-Host "[zip] 核心包 ..."
tar -a -c -f $CoreZip -C $Build core
if ($LASTEXITCODE -ne 0) { throw "tar core 失败" }
Write-Host "[zip] 附加包 ..."
tar -a -c -f $FullZip -C $Build full
if ($LASTEXITCODE -ne 0) { throw "tar full 失败" }

Remove-Item $Build -Recurse -Force

Write-Host "===== 打包完成 ====="
Get-ChildItem $Out -File | ForEach-Object {
    Write-Host ("{0}  ({1} MB)" -f $_.FullName, [math]::Round($_.Length / 1MB, 1))
}
