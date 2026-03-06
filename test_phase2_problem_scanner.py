"""
第二阶段测试：问题扫描器
"""
import sys
import os
from pathlib import Path

# 设置 UTF-8 输出（Windows 兼容）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_problem_scanner():
    """测试问题扫描器"""
    print("=" * 70)
    print("测试 1: 问题扫描器基本功能")
    print("=" * 70)

    from core.problem_scanner import ProblemScanner, ProblemType, ProblemSeverity

    scanner = ProblemScanner()

    print("\n[1] 初始化扫描器...")
    print(f"已加载扫描器: {list(scanner.scanners.keys())}")

    print("\n[2] 运行扫描...")
    problems = await scanner.scan_all(path='.')

    print(f"\n✅ 扫描完成，发现 {len(problems)} 个问题")

    # 打印问题统计
    stats = scanner.get_statistics(problems)
    print(f"\n📊 统计信息:")
    print(f"   总计: {stats['total']}")
    print(f"   可自动修复: {stats['auto_fixable']}")
    print(f"   需要批准: {stats['requires_approval']}")

    print(f"\n   按严重程度分布:")
    for severity, count in stats['by_severity'].items():
        print(f"     {severity}: {count}")

    print(f"\n   按类型分布:")
    for ptype, count in stats['by_type'].items():
        print(f"     {ptype}: {count}")

    # 生成报告
    print("\n" + "=" * 70)
    print("问题报告")
    print("=" * 70)
    report = scanner.generate_report(problems)
    print(report)

    # 测试问题过滤
    print("\n" + "=" * 70)
    print("测试 2: 问题过滤功能")
    print("=" * 70)

    if problems:
        # 按严重程度过滤
        medium_problems = scanner.filter_problems(problems, severity=ProblemSeverity.MEDIUM)
        print(f"\n🟡 中等严重程度问题: {len(medium_problems)} 个")

        # 按类型过滤
        config_problems = scanner.filter_problems(problems, problem_type=ProblemType.CONFIG)
        print(f"📝 配置问题: {len(config_problems)} 个")

        # 可自动修复的问题
        fixable_problems = scanner.filter_problems(problems, auto_fixable=True)
        print(f"🔧 可自动修复: {len(fixable_problems)} 个")

    # 测试问题优先级排序
    print("\n" + "=" * 70)
    print("测试 3: 问题优先级排序")
    print("=" * 70)

    if problems:
        prioritized = scanner.prioritize_problems(problems, max_count=5)

        print(f"\n📋 Top 5 问题 (按优先级):")
        for i, problem in enumerate(prioritized, 1):
            print(f"\n{i}. {problem.title}")
            print(f"   严重程度: {problem.severity.value}")
            print(f"   类型: {problem.type.value}")
            print(f"   可修复: {'是' if problem.auto_fixable else '否'}")
            print(f"   描述: {problem.description[:80]}...")

    print("\n✅ 测试完成!")


async def test_auto_fixer():
    """测试自动修复器"""
    print("\n" + "=" * 70)
    print("测试 4: 自动修复器")
    print("=" * 70)

    from core.auto_fixer import AutoFixer
    from core.problem_scanner import Problem, ProblemType, ProblemSeverity

    fixer = AutoFixer()

    print("\n[1] 创建测试问题...")

    # 创建一个可修复的配置问题
    test_file = Path(__file__).parent / "test_config.toml"
    test_file.write_text("key1: value1\nkey2: value2\n", encoding='utf-8')

    problem = Problem(
        id="test_001",
        type=ProblemType.CONFIG,
        severity=ProblemSeverity.MEDIUM,
        title="TOML 语法错误",
        description="TOML 文件使用冒号而不是等号",
        file_path=str(test_file),
        line_number=1,
        suggestions=["将冒号 (:) 替换为等号 (=)"],
        auto_fixable=True,
        confidence=0.9
    )

    print(f"   测试文件: {test_file}")
    print(f"   问题: {problem.title}")

    print("\n[2] 检查是否可修复...")
    can_fix = fixer.can_fix(problem)
    print(f"   可修复: {can_fix}")

    if can_fix:
        print("\n[3] 执行修复...")
        result = await fixer.fix_problem(problem, create_backup=True)

        print(f"\n   修复结果:")
        print(f"   成功: {result.success}")
        print(f"   动作: {result.action_taken}")
        print(f"   输出: {result.output}")
        print(f"   耗时: {result.time_taken:.2f} 秒")
        print(f"   备份创建: {result.backup_created}")
        if result.backup_path:
            print(f"   备份路径: {result.backup_path}")

        # 检查修复后的文件
        if result.success:
            fixed_content = test_file.read_text(encoding='utf-8')
            print(f"\n   修复后内容:")
            for line in fixed_content.split('\n'):
                print(f"     {line}")

    # 清理测试文件
    try:
        if test_file.exists():
            test_file.unlink()
            print(f"\n   清理测试文件: {test_file}")

        # 清理备份目录
        backup_dir = Path(__file__).parent.parent / '.backup'
        if backup_dir.exists():
            backups = list(backup_dir.glob('*.backup'))
            for backup in backups:
                backup.unlink()
            if backup_dir.exists() and not list(backup_dir.iterdir()):
                backup_dir.rmdir()
                print(f"   清理备份目录: {backup_dir}")

    except Exception as e:
        print(f"   清理失败: {e}")

    print("\n✅ 自动修复器测试完成!")


async def test_create_fix_plan():
    """测试创建修复计划"""
    print("\n" + "=" * 70)
    print("测试 5: 创建修复计划")
    print("=" * 70)

    from core.auto_fixer import AutoFixer
    from core.problem_scanner import Problem, ProblemType, ProblemSeverity

    fixer = AutoFixer()

    # 创建测试问题列表
    problems = [
        Problem(
            id="p1",
            type=ProblemType.LINTER,
            severity=ProblemSeverity.LOW,
            title="未使用的 import",
            description="删除未使用的 import 语句",
            auto_fixable=True,
            confidence=0.9
        ),
        Problem(
            id="p2",
            type=ProblemType.CONFIG,
            severity=ProblemSeverity.HIGH,
            title="敏感信息泄露",
            description="配置文件包含密码",
            auto_fixable=False,
            confidence=0.9
        ),
        Problem(
            id="p3",
            type=ProblemType.DEPENDENCY,
            severity=ProblemSeverity.MEDIUM,
            title="依赖未锁定版本",
            description="建议锁定依赖版本",
            auto_fixable=True,
            confidence=0.7
        ),
    ]

    print(f"\n[1] 创建修复计划...")
    plan = fixer.create_fix_plan(problems)

    print(f"\n   问题数量: {plan.problem_count}")
    print(f"   可修复: {plan.auto_fixable_count}")
    print(f"   高风险: {plan.high_risk_count}")
    print(f"   预计耗时: {plan.estimated_time:.1f} 秒")
    print(f"   需要批准: {plan.requires_approval}")

    print(f"\n   问题列表:")
    for i, problem in enumerate(plan.problems, 1):
        print(f"   {i}. {problem.title} ({problem.type.value}, {problem.severity.value})")

    print("\n✅ 修复计划测试完成!")


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("开始第二阶段测试")
    print("=" * 70)

    try:
        await test_problem_scanner()
        await test_auto_fixer()
        await test_create_fix_plan()

        print("\n" + "=" * 70)
        print("🎉 所有测试通过!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import asyncio
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
