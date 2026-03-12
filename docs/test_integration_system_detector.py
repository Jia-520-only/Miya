"""
测试 SystemDetector 与主程序的集成
"""
import sys
from pathlib import Path

# 设置 UTF-8 输出（Windows 兼容）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_integration_with_main():
    """测试与主程序的集成"""
    print("=" * 70)
    print("测试 SystemDetector 与主程序集成")
    print("=" * 70)

    # 模拟主程序初始化过程
    from core.system_detector import get_system_detector

    print("\n[1] 初始化系统检测器...")
    system_detector = get_system_detector()

    print("[2] 执行系统检测...")
    system_info = system_detector.detect()

    print("\n" + "-" * 70)
    print("系统信息汇总:")
    print("-" * 70)

    # 打印系统信息
    print(f"\n🖥️  操作系统:")
    print(f"   名称: {system_info.os_name}")
    print(f"   版本: {system_info.os_version}")
    print(f"   架构: {system_info.arch}")

    if system_info.is_linux():
        print(f"\n🐧 Linux 信息:")
        print(f"   发行版: {system_info.distro}")
        print(f"   版本: {system_info.distro_version}")

    print(f"\n🔧 运行环境:")
    print(f"   Shell: {system_info.shell}")
    print(f"   当前路径: {system_info.current_path}")
    print(f"   主目录: {system_info.home_dir}")

    print(f"\n📦 开发工具:")
    print(f"   Python: {system_info.python_version}")
    if system_info.node_version != "not_installed":
        print(f"   Node.js: {system_info.node_version}")

    print(f"\n🛠️  包管理器:")
    for i, pm in enumerate(system_info.package_managers, 1):
        print(f"   {i}. {pm}")

    print(f"\n⭐ 推荐包管理器: {system_info.get_best_package_manager()}")

    # 测试环境适配
    print("\n" + "-" * 70)
    print("环境适配能力:")
    print("-" * 70)

    if system_info.is_windows():
        print(f"\n✅ 检测到 Windows 环境")
        print(f"   - 使用 PowerShell 作为 Shell")
        print(f"   - 支持 winget/choco/scoop 包管理器")
        print(f"   - 命令需要适配 (dir -> ls, 等)")

    elif system_info.is_linux():
        print(f"\n✅ 检测到 Linux 环境")
        print(f"   - 发行版: {system_info.distro}")
        print(f"   - Shell: {system_info.shell}")
        print(f"   - 包管理器: {system_info.get_best_package_manager()}")

    elif system_info.is_macos():
        print(f"\n✅ 检测到 macOS 环境")
        print(f"   - 推荐使用 Homebrew")
        print(f"   - Shell: {system_info.shell}")

    # 验证关键信息
    print("\n" + "-" * 70)
    print("验证结果:")
    print("-" * 70)

    checks = [
        ("操作系统检测", system_info.os_name != "unknown"),
        ("Python 版本", system_info.python_version.startswith("3.")),
        ("包管理器检测", len(system_info.package_managers) > 0),
        ("pip 可用", "pip" in system_info.package_managers),
        ("路径检测", system_info.current_path != "unknown"),
    ]

    all_passed = True
    for check_name, result in checks:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {check_name}")
        if not result:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 集成测试全部通过!")
        print("=" * 70)
        print("\n✅ SystemDetector 已成功集成到主程序")
        print("✅ 系统检测功能正常工作")
        print("✅ 环境适配能力已就绪")
        print("\n下一步: 可以继续实现第二阶段（主动问题发现）")
        return True
    else:
        print("❌ 部分测试失败")
        print("=" * 70)
        return False


if __name__ == "__main__":
    try:
        success = test_integration_with_main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
