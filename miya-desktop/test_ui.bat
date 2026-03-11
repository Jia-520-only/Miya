@echo off
chcp 65001 >nul
echo ========================================
echo UI优化 - 快速测试脚本
echo ========================================
echo.

echo 检查修改的文件...
echo.

if exist "src\App.vue" (
    echo ✓ App.vue (主题切换)
) else (
    echo ✗ App.vue 未找到
)

if exist "src\views\ChatView.vue" (
    echo ✓ ChatView.vue (对话侧边栏)
) else (
    echo ✗ ChatView.vue 未找到
)

if exist "src\views\CodeView.vue" (
    echo ✓ CodeView.vue (代码侧边栏)
) else (
    echo ✗ CodeView.vue 未找到
)

if exist "src\views\FilesView.vue" (
    echo ✓ FilesView.vue (文件侧边栏)
) else (
    echo ✗ FilesView.vue 未找到
)

if exist "src\views\MonitorView.vue" (
    echo ✓ MonitorView.vue (监控优化)
) else (
    echo ✗ MonitorView.vue 未找到
)

if exist "src\components\NavigationTabs.vue" (
    echo ✓ NavigationTabs.vue (导航优化)
) else (
    echo ✗ NavigationTabs.vue 未找到
)

echo.
echo ========================================
echo 文件检查完成!
echo ========================================
echo.
echo 优化内容:
echo   1. 主题切换修复 (暗色/亮色背景)
echo   2. ChatView - Live2D信息卡片
echo   3. CodeView - 文件信息+设置+快捷键
echo   4. FilesView - 统计+路径+提示
echo   5. MonitorView - 网络状态+运行信息
echo   6. 导航标签科技感优化
echo.
echo ========================================
echo 接下来请执行:
echo   1. 按 Ctrl+R 刷新页面 (如果应用正在运行)
echo   2. 或运行 quick_refresh.bat 然后重新启动
echo ========================================
echo.
pause
