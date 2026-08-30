# Live2D 模型文件夹重命名脚本
# 此脚本会将包含特殊字符的文件夹重命名为英文名称

$ErrorActionPreference = "Stop"

$basePath = "D:/AI_MIYA_Facyory/MIYA/Miya/live2d"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Live2D 模型文件夹重命名工具" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 定义重命名映射
$mappings = @(
    # 原文件夹名 -> 新文件夹名
    @{ Old = "白发清冷御姐"; New = "bai_fa_yu_jie" },
    @{ Old = "988小fa限量【红醉】动态皮套"; New = "red_wine" },
    @{ Old = "承"; New = "cheng" },
    @{ Old = "狐仙【皮套】"; New = "fox_spirit" },
    @{ Old = "【夜翎】皮套"; New = "ye_ling" },
    @{ Old = "【时冰】"; New = "shi_bing" },
    @{ Old = "夜蛊【皮套】"; New = "night_witch" },
    @{ Old = "希斯提亚量贩模型-小fa朵 (2)"; New = "hestia" },
    @{ Old = "小fa限定量贩【漫漫】动态皮套"; New = "manman" },
    @{ Old = "灵蝶之狐"; New = "spirit_fox" }
)

Write-Host "准备重命名以下文件夹：" -ForegroundColor Yellow
Write-Host ""

$successCount = 0
$skipCount = 0
$errorCount = 0

foreach ($mapping in $mappings) {
    $oldName = $mapping.Old
    $newName = $mapping.New

    $oldPath = Join-Path $basePath $oldName
    $newPath = Join-Path $basePath $newName

    Write-Host "检查: $oldName" -NoNewline

    # 检查原文件夹是否存在
    if (-not (Test-Path $oldPath)) {
        Write-Host " -> 不存在，跳过" -ForegroundColor Gray
        $skipCount++
        continue
    }

    # 检查目标文件夹是否已存在
    if (Test-Path $newPath) {
        Write-Host " -> 目标已存在，跳过" -ForegroundColor Yellow
        $skipCount++
        continue
    }

    Write-Host ""

    try {
        # 重命名文件夹
        Rename-Item -Path $oldPath -NewName $newName -ErrorAction Stop
        Write-Host "  ✓ 成功: $oldName -> $newName" -ForegroundColor Green
        $successCount++
    }
    catch {
        Write-Host "  ✗ 失败: $($_.Exception.Message)" -ForegroundColor Red
        $errorCount++
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "重命名完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "成功: $successCount 个" -ForegroundColor Green
Write-Host "跳过: $skipCount 个" -ForegroundColor Yellow
Write-Host "失败: $errorCount 个" -ForegroundColor Red
Write-Host ""

# 验证重命名结果
Write-Host "当前 live2d 文件夹内容：" -ForegroundColor Cyan
Get-ChildItem -Path $basePath -Directory | Where-Object { $_.Name -ne ".git" } | Sort-Object Name | ForEach-Object {
    Write-Host "  - $($_.Name)"
}

Write-Host ""
Write-Host "下一步：更新 live2dModels.ts 配置文件" -ForegroundColor Cyan
Write-Host ""
