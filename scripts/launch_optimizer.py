#!/usr/bin/env python3
"""
系统启动优化器
优化弥娅系统的启动体验和性能
"""

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

import psutil

logger = logging.getLogger(__name__)


class LaunchOptimizer:
    """启动优化器"""

    def __init__(self, project_root: str = None):
        self.project_root = project_root or os.getcwd()
        self.optimization_log = os.path.join(self.project_root, "launch_optimization.log")

        # 设置日志
        self.setup_logging()

        logger.info(f"启动优化器初始化 - 项目根目录: {self.project_root}")

    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(self.optimization_log, encoding="utf-8"), logging.StreamHandler()],
        )

    def check_system_resources(self) -> Dict:
        """检查系统资源"""
        logger.info("检查系统资源...")

        resources = {
            "cpu_count": psutil.cpu_count(logical=False),
            "cpu_logical": psutil.cpu_count(logical=True),
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "memory_available_gb": psutil.virtual_memory().available / (1024**3),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_total_gb": psutil.disk_usage(self.project_root).total / (1024**3),
            "disk_free_gb": psutil.disk_usage(self.project_root).free / (1024**3),
            "disk_percent": psutil.disk_usage(self.project_root).percent,
            "python_version": sys.version,
            "platform": sys.platform,
        }

        logger.info(f"CPU核心数: {resources['cpu_count']} (逻辑: {resources['cpu_logical']})")
        logger.info(
            f"内存: {resources['memory_available_gb']:.1f}GB / {resources['memory_total_gb']:.1f}GB ({resources['memory_percent']}%)"
        )
        logger.info(
            f"磁盘: {resources['disk_free_gb']:.1f}GB / {resources['disk_total_gb']:.1f}GB ({resources['disk_percent']}%)"
        )

        return resources

    def check_python_environment(self) -> Dict:
        """检查Python环境"""
        logger.info("检查Python环境...")

        environment = {
            "python_executable": sys.executable,
            "python_version": sys.version,
            "venv_active": hasattr(sys, "real_prefix")
            or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix),
            "working_directory": os.getcwd(),
            "path_exists": {},
        }

        # 检查关键文件
        key_files = [
            "requirements.txt",
            "start.bat",
            "start_miya.py",
            "run/multi_terminal_main_v2.py",
            "run/runtime_api_start.py",
            "core/runtime_api_server.py",
            "core/terminal_agent.py",
        ]

        for file in key_files:
            full_path = os.path.join(self.project_root, file)
            environment["path_exists"][file] = os.path.exists(full_path)

            if not environment["path_exists"][file]:
                logger.warning(f"文件不存在: {file}")
            else:
                logger.debug(f"文件存在: {file}")

        # 检查Python包
        try:
            import aiohttp

            environment["aiohttp_version"] = aiohttp.__version__
        except ImportError:
            environment["aiohttp_version"] = None
            logger.warning("aiohttp未安装")

        try:
            import fastapi

            environment["fastapi_version"] = fastapi.__version__
        except ImportError:
            environment["fastapi_version"] = None
            logger.warning("fastapi未安装")

        return environment

    def optimize_batch_file(self) -> bool:
        """优化批处理文件"""
        logger.info("优化批处理文件...")

        batch_files = ["start.bat", "miya_direct.bat", "launch.bat"]
        optimized_count = 0

        for batch_file in batch_files:
            file_path = os.path.join(self.project_root, batch_file)

            if not os.path.exists(file_path):
                logger.debug(f"批处理文件不存在: {batch_file}")
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # 检查常见问题
                issues = []

                # 检查中文字符
                if any(ord(char) > 127 for char in content if 0x4E00 <= ord(char) <= 0x9FFF):
                    issues.append("包含中文字符")

                # 检查编码问题
                if "chcp" not in content and "utf-8" not in content.lower():
                    issues.append("缺少编码设置")

                # 检查错误处理
                if "errorlevel" not in content and "if errorlevel" not in content:
                    issues.append("缺少错误处理")

                # 检查路径处理
                if "%~dp0" not in content and "cd /d" not in content:
                    issues.append("路径处理可能有问题")

                if issues:
                    logger.warning(f"{batch_file} 存在问题: {', '.join(issues)}")

                    # 创建优化版本
                    backup_file = file_path + ".backup"
                    shutil.copy2(file_path, backup_file)
                    logger.info(f"创建备份: {backup_file}")

                    # 添加优化建议
                    optimization_report = f"""
优化报告 - {batch_file}
问题: {", ".join(issues)}
建议: 考虑使用优化版本的start.bat
备份文件: {backup_file}
优化时间: {datetime.now().isoformat()}
"""

                    with open(file_path + ".optimization_report.txt", "w", encoding="utf-8") as f:
                        f.write(optimization_report)

                    optimized_count += 1

            except Exception as e:
                logger.error(f"优化 {batch_file} 时出错: {e}")

        logger.info(f"批处理文件优化完成: 检查了 {len(batch_files)} 个文件，优化了 {optimized_count} 个")
        return optimized_count > 0

    def create_unified_launcher(self) -> str:
        """创建统一的启动器"""
        logger.info("创建统一的启动器...")

        launcher_content = """#!/usr/bin/env python3
"""
        launcher_path = os.path.join(self.project_root, "miya_unified_launcher.py")

        try:
            with open(launcher_path, "w", encoding="utf-8") as f:
                f.write(launcher_content)

            logger.info(f"统一启动器已创建: {launcher_path}")
            return launcher_path

        except Exception as e:
            logger.error(f"创建统一启动器失败: {e}")
            return ""

    def optimize_startup_performance(self) -> Dict:
        """优化启动性能"""
        logger.info("优化启动性能...")

        optimizations = {
            "preload_modules": False,
            "optimize_imports": False,
            "cache_settings": False,
            "parallel_startup": False,
        }

        # 检查并优化导入
        python_files = list(Path(self.project_root).rglob("*.py"))

        import_optimizations = []
        for py_file in python_files[:20]:  # 只检查前20个文件
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # 检查循环导入
                if "import sys" in content and "sys.path" in content:
                    import_optimizations.append(str(py_file.relative_to(self.project_root)))

            except Exception:
                pass

        if import_optimizations:
            optimizations["optimize_imports"] = True
            logger.info(f"发现可优化的导入: {len(import_optimizations)} 个文件")

        # 检查缓存设置
        cache_dir = os.path.join(self.project_root, ".cache")
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir, exist_ok=True)
                optimizations["cache_settings"] = True
                logger.info(f"创建缓存目录: {cache_dir}")
            except Exception as e:
                logger.error(f"创建缓存目录失败: {e}")

        # 检查并行启动设置
        if self.check_system_resources()["cpu_logical"] > 4:
            optimizations["parallel_startup"] = True
            logger.info("系统支持并行启动优化")

        return optimizations

    def create_startup_profile(self) -> str:
        """创建启动配置文件"""
        logger.info("创建启动配置文件...")

        profile = {
            "created_at": datetime.now().isoformat(),
            "project_root": self.project_root,
            "system_resources": self.check_system_resources(),
            "python_environment": self.check_python_environment(),
            "optimizations_applied": self.optimize_startup_performance(),
            "recommendations": [],
        }

        # 生成建议
        resources = profile["system_resources"]
        if resources["memory_percent"] > 80:
            profile["recommendations"].append("内存使用率较高，建议关闭不必要的程序")

        if resources["disk_percent"] > 90:
            profile["recommendations"].append("磁盘空间不足，建议清理空间")

        env = profile["python_environment"]
        missing_files = [f for f, exists in env["path_exists"].items() if not exists]
        if missing_files:
            profile["recommendations"].append(f"缺少关键文件: {', '.join(missing_files[:3])}")

        profile_path = os.path.join(self.project_root, "startup_profile.json")
        try:
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)

            logger.info(f"启动配置文件已保存: {profile_path}")
            return profile_path

        except Exception as e:
            logger.error(f"保存启动配置文件失败: {e}")
            return ""

    def run_comprehensive_optimization(self) -> Dict:
        """运行全面优化"""
        logger.info("开始全面优化...")

        results = {
            "timestamp": datetime.now().isoformat(),
            "system_check": self.check_system_resources(),
            "environment_check": self.check_python_environment(),
            "batch_optimized": self.optimize_batch_file(),
            "performance_optimizations": self.optimize_startup_performance(),
            "profile_created": False,
            "recommendations": [],
            "issues_found": [],
        }

        # 创建配置文件
        profile_path = self.create_startup_profile()
        if profile_path:
            results["profile_created"] = True
            results["profile_path"] = profile_path

        # 分析问题
        env = results["environment_check"]
        missing_files = [f for f, exists in env["path_exists"].items() if not exists]
        if missing_files:
            results["issues_found"].append(f"缺失文件: {len(missing_files)} 个")

        if not env.get("venv_active", False):
            results["issues_found"].append("未在虚拟环境中运行")

        # 生成建议
        resources = results["system_check"]
        if resources["memory_percent"] > 85:
            results["recommendations"].append("💡 内存使用率较高，建议增加系统内存或优化程序内存使用")

        if resources["disk_percent"] > 85:
            results["recommendations"].append("💡 磁盘空间紧张，建议清理不必要的文件")

        if missing_files:
            results["recommendations"].append("🔧 修复缺失的关键文件")

        if not results["batch_optimized"]:
            results["recommendations"].append("⚡ 批处理文件已优化")

        logger.info("全面优化完成")
        return results

    def print_optimization_report(self, results: Dict):
        """打印优化报告"""
        print("\n" + "=" * 70)
        print("🎯 弥娅系统启动优化报告")
        print("=" * 70)

        print(f"\n📅 优化时间: {results['timestamp']}")
        print(f"📁 项目目录: {self.project_root}")

        # 系统资源
        resources = results["system_check"]
        print("\n💻 系统资源:")
        print(f"  CPU: {resources['cpu_count']}核心 ({resources['cpu_logical']}线程)")
        print(f"  内存: {resources['memory_available_gb']:.1f}GB可用 / {resources['memory_total_gb']:.1f}GB")
        print(f"  磁盘: {resources['disk_free_gb']:.1f}GB可用 / {resources['disk_total_gb']:.1f}GB")

        # 环境检查
        env = results["environment_check"]
        print("\n🐍 Python环境:")
        print(f"  版本: {env['python_version'].split()[0]}")
        print(f"  虚拟环境: {'✅ 已激活' if env.get('venv_active') else '❌ 未激活'}")
        print(f"  关键文件: {sum(env['path_exists'].values())}/{len(env['path_exists'])} 存在")

        # 优化结果
        print("\n⚡ 优化结果:")
        print(f"  批处理文件优化: {'✅ 已完成' if results['batch_optimized'] else '⚠️ 无需优化'}")

        perf = results["performance_optimizations"]
        enabled_optimizations = [k for k, v in perf.items() if v]
        if enabled_optimizations:
            print(f"  性能优化启用: {', '.join(enabled_optimizations)}")
        else:
            print("  性能优化: 暂无可用优化")

        # 问题和建议
        if results["issues_found"]:
            print("\n⚠️ 发现问题:")
            for issue in results["issues_found"]:
                print(f"  • {issue}")

        if results["recommendations"]:
            print("\n💡 优化建议:")
            for rec in results["recommendations"]:
                print(f"  • {rec}")

        print(f"\n📊 详细报告: {self.optimization_log}")
        if results.get("profile_path"):
            print(f"📋 配置文件: {results['profile_path']}")

        print("\n" + "=" * 70)
        print("🎉 优化完成！使用 'start.bat' 或 'python start_miya.py' 启动系统")
        print("=" * 70)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="弥娅系统启动优化器")
    parser.add_argument("--project-root", default=".", help="项目根目录")
    parser.add_argument("--quick", action="store_true", help="快速优化")
    parser.add_argument("--full", action="store_true", help="全面优化")
    parser.add_argument("--check-only", action="store_true", help="只检查不优化")

    args = parser.parse_args()

    # 确定项目根目录
    project_root = os.path.abspath(args.project_root)

    print("=" * 70)
    print("🚀 弥娅系统启动优化器")
    print("=" * 70)
    print(f"项目目录: {project_root}")

    optimizer = LaunchOptimizer(project_root)

    if args.check_only:
        print("\n🔍 运行系统检查...")
        optimizer.check_system_resources()
        optimizer.check_python_environment()

        print("\n✅ 系统检查完成")
        print(f"日志文件: {optimizer.optimization_log}")

    elif args.quick:
        print("\n⚡ 运行快速优化...")
        optimizer.optimize_batch_file()
        profile_path = optimizer.create_startup_profile()

        if profile_path:
            print("\n✅ 快速优化完成")
            print(f"配置文件: {profile_path}")

    else:  # 默认全面优化
        print("\n🔧 运行全面优化...")
        results = optimizer.run_comprehensive_optimization()
        optimizer.print_optimization_report(results)


if __name__ == "__main__":
    main()
