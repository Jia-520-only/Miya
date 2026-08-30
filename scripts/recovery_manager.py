#!/usr/bin/env python3
"""
故障恢复管理器
提供完整的弥娅系统故障恢复方案
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict

import psutil

logger = logging.getLogger(__name__)


class RecoveryManager:
    """故障恢复管理器"""

    def __init__(self, project_root: str = None):
        self.project_root = project_root or os.getcwd()
        self.recovery_log = os.path.join(self.project_root, "recovery_log.json")
        self.services_to_monitor = [
            {"name": "API Server", "port": 8001, "script": "run/runtime_api_start.py"},
            {"name": "Web Server", "port": 8000, "script": "web_interface_start.py"},
            {"name": "Terminal System", "port": None, "script": "run/multi_terminal_main_v2.py"},
        ]

        self.setup_logging()
        logger.info(f"故障恢复管理器初始化 - 项目根目录: {self.project_root}")

    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("recovery_manager.log", encoding="utf-8"), logging.StreamHandler()],
        )

    def check_service_status(self) -> Dict:
        """检查服务状态"""
        logger.info("检查服务状态...")

        status = {"timestamp": datetime.now().isoformat(), "services": {}, "overall": "unknown", "issues": []}

        all_running = True
        any_running = False

        for service in self.services_to_monitor:
            service_name = service["name"]
            port = service["port"]
            script = service["script"]

            service_info = {
                "port": port,
                "script": script,
                "script_exists": os.path.exists(os.path.join(self.project_root, script)),
                "process_running": False,
                "port_open": False,
                "pid": None,
            }

            # 检查脚本是否存在
            if not service_info["script_exists"]:
                status["issues"].append(f"{service_name}: 脚本不存在 - {script}")
                status["services"][service_name] = service_info
                all_running = False
                continue

            # 检查进程是否运行
            try:
                for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                    try:
                        cmdline = proc.info.get("cmdline", [])
                        if any(script in str(cmd) for cmd in cmdline):
                            service_info["process_running"] = True
                            service_info["pid"] = proc.info["pid"]
                            any_running = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception as e:
                logger.error(f"检查进程失败: {e}")

            # 检查端口是否开放
            if port:
                try:
                    import socket

                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex(("localhost", port))
                    service_info["port_open"] = result == 0
                    sock.close()

                    if service_info["process_running"] and not service_info["port_open"]:
                        status["issues"].append(f"{service_name}: 进程运行但端口未开放 - {port}")
                        all_running = False
                    elif not service_info["process_running"] and service_info["port_open"]:
                        status["issues"].append(f"{service_name}: 端口开放但无对应进程 - {port}")
                except Exception as e:
                    logger.error(f"检查端口失败: {e}")

            status["services"][service_name] = service_info

            # 检查服务是否完全运行
            if port and not (service_info["process_running"] and service_info["port_open"]):
                all_running = False

        # 确定整体状态
        if all_running:
            status["overall"] = "healthy"
        elif any_running:
            status["overall"] = "partial"
        else:
            status["overall"] = "down"

        logger.info(f"服务状态: {status['overall']}")
        if status["issues"]:
            logger.warning(f"发现问题: {len(status['issues'])} 个")

        # 保存状态
        self.save_status(status)

        return status

    def save_status(self, status: Dict):
        """保存状态"""
        try:
            # 读取现有日志
            log_data = []
            if os.path.exists(self.recovery_log):
                try:
                    with open(self.recovery_log, "r", encoding="utf-8") as f:
                        log_data = json.load(f)
                        if not isinstance(log_data, list):
                            log_data = []
                except:
                    log_data = []

            # 添加新状态
            log_data.append(status)

            # 只保留最近100条记录
            if len(log_data) > 100:
                log_data = log_data[-100:]

            # 保存
            with open(self.recovery_log, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"状态已保存到 {self.recovery_log}")

        except Exception as e:
            logger.error(f"保存状态失败: {e}")

    def restart_service(self, service_name: str) -> bool:
        """重启单个服务"""
        logger.info(f"重启服务: {service_name}")

        service = next((s for s in self.services_to_monitor if s["name"] == service_name), None)
        if not service:
            logger.error(f"服务不存在: {service_name}")
            return False

        script = service["script"]
        script_path = os.path.join(self.project_root, script)

        if not os.path.exists(script_path):
            logger.error(f"脚本不存在: {script_path}")
            return False

        # 停止服务
        stop_success = self.stop_service(service_name)

        if not stop_success:
            logger.warning(f"停止服务 {service_name} 失败，尝试强制启动")

        # 等待一下
        time.sleep(2)

        # 启动服务
        try:
            logger.info(f"启动服务: {service_name}")

            # 使用后台进程启动
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.Popen(
                    [sys.executable, script_path],
                    cwd=self.project_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    startupinfo=startupinfo,
                )
            else:
                process = subprocess.Popen(
                    [sys.executable, script_path],
                    cwd=self.project_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                )

            logger.info(f"服务 {service_name} 已启动 (PID: {process.pid})")

            # 等待服务启动
            if service["port"]:
                logger.info(f"等待服务 {service_name} 启动完成...")
                time.sleep(5)

                # 检查端口
                import socket

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex(("localhost", service["port"]))
                sock.close()

                if result == 0:
                    logger.info(f"服务 {service_name} 启动成功，端口 {service['port']} 已开放")
                    return True
                else:
                    logger.warning(f"服务 {service_name} 启动但端口未开放")
                    return False
            else:
                logger.info(f"服务 {service_name} 已启动 (无端口检查)")
                return True

        except Exception as e:
            logger.error(f"启动服务 {service_name} 失败: {e}")
            return False

    def stop_service(self, service_name: str) -> bool:
        """停止单个服务"""
        logger.info(f"停止服务: {service_name}")

        service = next((s for s in self.services_to_monitor if s["name"] == service_name), None)
        if not service:
            logger.error(f"服务不存在: {service_name}")
            return False

        script = service["script"]
        stopped_count = 0

        try:
            # 查找并停止相关进程
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = proc.info.get("cmdline", [])
                    if any(script in str(cmd) for cmd in cmdline):
                        pid = proc.info["pid"]
                        logger.info(f"找到进程 {service_name} (PID: {pid})")

                        # 优雅停止
                        try:
                            if sys.platform == "win32":
                                proc.terminate()
                            else:
                                proc.send_signal(signal.SIGTERM)

                            # 等待进程结束
                            proc.wait(timeout=10)
                            logger.info(f"进程 {pid} 已停止")
                            stopped_count += 1

                        except psutil.TimeoutExpired:
                            logger.warning(f"进程 {pid} 未响应，强制终止")
                            proc.kill()
                            proc.wait()
                            stopped_count += 1

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if stopped_count > 0:
                logger.info(f"已停止 {stopped_count} 个 {service_name} 进程")
                return True
            else:
                logger.info(f"未找到运行中的 {service_name} 进程")
                return True  # 未找到进程也视为成功

        except Exception as e:
            logger.error(f"停止服务 {service_name} 失败: {e}")
            return False

    def restart_all_services(self) -> bool:
        """重启所有服务"""
        logger.info("重启所有服务...")

        status = self.check_service_status()
        all_success = True

        # 先停止所有服务
        for service_name in status["services"]:
            if status["services"][service_name]["process_running"] and not self.stop_service(service_name):
                logger.warning(f"停止服务 {service_name} 失败")

        # 等待一下
        time.sleep(3)

        # 启动所有服务
        for service in self.services_to_monitor:
            service_name = service["name"]
            if not self.restart_service(service_name):
                logger.error(f"启动服务 {service_name} 失败")
                all_success = False

        # 最终检查
        final_status = self.check_service_status()
        if final_status["overall"] != "healthy":
            logger.warning(f"重启后服务状态: {final_status['overall']}")
            all_success = False

        return all_success

    def diagnose_issues(self) -> Dict:
        """诊断问题"""
        logger.info("运行系统诊断...")

        diagnosis = {
            "timestamp": datetime.now().isoformat(),
            "system_check": {},
            "service_check": {},
            "common_issues": [],
            "solutions": [],
            "recommendations": [],
        }

        # 系统检查
        try:
            import psutil

            diagnosis["system_check"] = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage(self.project_root).percent,
                "python_version": sys.version,
                "platform": sys.platform,
            }
        except Exception as e:
            logger.error(f"系统检查失败: {e}")

        # 服务检查
        status = self.check_service_status()
        diagnosis["service_check"] = status

        # 常见问题检测
        if status["overall"] == "down":
            diagnosis["common_issues"].append("所有服务都未运行")
            diagnosis["solutions"].append("运行 'recovery_manager.py --restart-all' 重启所有服务")

        elif status["overall"] == "partial":
            diagnosis["common_issues"].append("部分服务未运行")
            diagnosis["solutions"].append("运行 'recovery_manager.py --restart-failed' 重启失败的服务")

        # 检查端口冲突
        for service_name, service_info in status["services"].items():
            if service_info.get("port") and not service_info.get("port_open") and service_info.get("process_running"):
                diagnosis["common_issues"].append(f"{service_name}: 进程运行但端口未开放")
                diagnosis["solutions"].append(f"检查端口 {service_info['port']} 是否被其他程序占用")

        # 检查文件完整性
        for service in self.services_to_monitor:
            script_path = os.path.join(self.project_root, service["script"])
            if not os.path.exists(script_path):
                diagnosis["common_issues"].append(f"{service['name']}: 脚本不存在 - {service['script']}")
                diagnosis["solutions"].append(f"恢复或重新安装 {service['script']}")

        # 生成建议
        if diagnosis["system_check"].get("memory_percent", 0) > 85:
            diagnosis["recommendations"].append("内存使用率较高，建议关闭不必要的程序")

        if diagnosis["system_check"].get("disk_percent", 0) > 90:
            diagnosis["recommendations"].append("磁盘空间不足，建议清理空间")

        if len(diagnosis["common_issues"]) == 0 and status["overall"] == "healthy":
            diagnosis["recommendations"].append("系统运行正常，无需修复")

        logger.info("诊断完成")
        return diagnosis

    def apply_quick_fix(self) -> bool:
        """应用快速修复"""
        logger.info("应用快速修复...")

        diagnosis = self.diagnose_issues()

        if not diagnosis["common_issues"]:
            logger.info("未发现问题，无需修复")
            return True

        print("\n" + "=" * 60)
        print("🔧 快速修复")
        print("=" * 60)

        print(f"发现问题: {len(diagnosis['common_issues'])} 个")

        all_fixed = True

        # 根据问题应用修复
        for issue in diagnosis["common_issues"]:
            print(f"\n处理问题: {issue}")

            if "所有服务都未运行" in issue:
                print("重启所有服务...")
                if self.restart_all_services():
                    print("✅ 所有服务已重启")
                else:
                    print("❌ 重启失败")
                    all_fixed = False

            elif "部分服务未运行" in issue:
                print("检查并重启失败的服务...")
                status = self.check_service_status()

                for service_name, service_info in status["services"].items():
                    port = service_info.get("port")
                    if port and not (service_info.get("process_running") and service_info.get("port_open")):
                        print(f"重启 {service_name}...")
                        if self.restart_service(service_name):
                            print(f"✅ {service_name} 已重启")
                        else:
                            print(f"❌ {service_name} 重启失败")
                            all_fixed = False

            elif "脚本不存在" in issue:
                # 提取服务名
                service_name = issue.split(":")[0]
                print(f"无法自动修复缺失脚本: {service_name}")
                print("请手动恢复或重新安装相关文件")
                all_fixed = False

            elif "端口被占用" in issue or "端口未开放" in issue:
                # 尝试重启相关服务
                for service in issue.split(":"):
                    if any(s["name"] in service for s in self.services_to_monitor):
                        service_name = next(s["name"] for s in self.services_to_monitor if s["name"] in service)
                        print(f"重启 {service_name}...")
                        if self.restart_service(service_name):
                            print(f"✅ {service_name} 已重启")
                        else:
                            print(f"❌ {service_name} 重启失败")
                            all_fixed = False
                        break

        # 最终检查
        final_diagnosis = self.diagnose_issues()
        remaining_issues = len(final_diagnosis["common_issues"])

        if remaining_issues == 0:
            print("\n✅ 所有问题已修复！")
            all_fixed = True
        else:
            print(f"\n⚠️ 仍有 {remaining_issues} 个问题未解决")
            print("请参考以下建议手动修复:")
            for solution in final_diagnosis["solutions"]:
                print(f"  • {solution}")
            all_fixed = False

        return all_fixed

    def create_recovery_guide(self) -> str:
        """创建恢复指南"""
        logger.info("创建恢复指南...")

        guide_content = f"""# 弥娅系统故障恢复指南

创建时间: {datetime.now().isoformat()}
项目目录: {self.project_root}

## 📋 系统状态

"""

        # 添加当前状态
        diagnosis = self.diagnose_issues()

        guide_content += f"### 当前状态: {diagnosis['service_check']['overall'].upper()}\n\n"

        # 添加服务状态表格
        guide_content += "| 服务 | 进程运行 | 端口开放 | 状态 |\n"
        guide_content += "|------|----------|----------|------|\n"

        for service_name, service_info in diagnosis["service_check"]["services"].items():
            process_emoji = "✅" if service_info.get("process_running") else "❌"
            port_emoji = "✅" if service_info.get("port_open") else "❌" if service_info.get("port") else "➖"
            status_emoji = (
                "✅"
                if (
                    service_info.get("process_running")
                    and (not service_info.get("port") or service_info.get("port_open"))
                )
                else "❌"
            )

            guide_content += f"| {service_name} | {process_emoji} | {port_emoji} | {status_emoji} |\n"

        # 添加问题和解决方案
        if diagnosis["common_issues"]:
            guide_content += "\n## ⚠️ 发现问题\n\n"
            for issue in diagnosis["common_issues"]:
                guide_content += f"• {issue}\n"

        if diagnosis["solutions"]:
            guide_content += "\n## 🔧 解决方案\n\n"
            for solution in diagnosis["solutions"]:
                guide_content += f"1. {solution}\n"

        if diagnosis["recommendations"]:
            guide_content += "\n## 💡 优化建议\n\n"
            for rec in diagnosis["recommendations"]:
                guide_content += f"• {rec}\n"

        # 添加恢复命令
        guide_content += f"""
## 🚀 快速恢复命令

1. **检查状态**: `python {os.path.basename(__file__)} --status`
2. **快速修复**: `python {os.path.basename(__file__)} --quick-fix`
3. **重启所有**: `python {os.path.basename(__file__)} --restart-all`
4. **诊断问题**: `python {os.path.basename(__file__)} --diagnose`

## 📞 手动恢复步骤

1. **停止所有服务**: 运行 `python {os.path.basename(__file__)} --stop-all`
2. **清理环境**: 删除日志文件、临时文件
3. **检查依赖**: 确保所有Python包已安装
4. **启动服务**: 运行 `python {os.path.basename(__file__)} --start-all`
5. **验证功能**: 检查API和终端是否正常工作

## 📊 日志文件

- 恢复日志: {self.recovery_log}
- 诊断日志: recovery_manager.log
- 服务日志: 查看各服务的日志文件

---
**提示**: 如果自动恢复失败，请参考上述步骤手动恢复系统。
"""

        guide_path = os.path.join(self.project_root, "RECOVERY_GUIDE.md")
        try:
            with open(guide_path, "w", encoding="utf-8") as f:
                f.write(guide_content)

            logger.info(f"恢复指南已创建: {guide_path}")
            return guide_path

        except Exception as e:
            logger.error(f"创建恢复指南失败: {e}")
            return ""


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="弥娅系统故障恢复管理器")
    parser.add_argument("--project-root", default=".", help="项目根目录")
    parser.add_argument("--status", action="store_true", help="检查服务状态")
    parser.add_argument("--diagnose", action="store_true", help="诊断问题")
    parser.add_argument("--quick-fix", action="store_true", help="快速修复")
    parser.add_argument("--restart-all", action="store_true", help="重启所有服务")
    parser.add_argument("--restart-failed", action="store_true", help="重启失败的服务")
    parser.add_argument("--stop-all", action="store_true", help="停止所有服务")
    parser.add_argument("--create-guide", action="store_true", help="创建恢复指南")

    args = parser.parse_args()

    # 确定项目根目录
    project_root = os.path.abspath(args.project_root)

    print("=" * 60)
    print("🚑 弥娅系统故障恢复管理器")
    print("=" * 60)
    print(f"项目目录: {project_root}")

    manager = RecoveryManager(project_root)

    if args.status:
        print("\n🔍 检查服务状态...")
        status = manager.check_service_status()

        print(f"\n📊 整体状态: {status['overall'].upper()}")
        print("\n服务详情:")

        for service_name, service_info in status["services"].items():
            process_status = "✅ 运行中" if service_info["process_running"] else "❌ 未运行"
            port_status = "✅ 开放" if service_info["port_open"] else "❌ 关闭" if service_info["port"] else "➖ 无端口"

            print(f"  {service_name}:")
            print(f"    进程: {process_status}")
            print(f"    端口: {port_status}")
            if service_info["pid"]:
                print(f"    PID: {service_info['pid']}")

        if status["issues"]:
            print(f"\n⚠️ 发现问题 ({len(status['issues'])}):")
            for issue in status["issues"]:
                print(f"  • {issue}")

        print(f"\n📋 详细日志: {manager.recovery_log}")

    elif args.diagnose:
        print("\n🔧 运行系统诊断...")
        diagnosis = manager.diagnose_issues()

        print("\n📊 诊断结果:")
        print(f"  系统状态: {diagnosis['service_check']['overall'].upper()}")

        if diagnosis["common_issues"]:
            print("\n⚠️ 发现问题:")
            for issue in diagnosis["common_issues"]:
                print(f"  • {issue}")

        if diagnosis["solutions"]:
            print("\n🔧 解决方案:")
            for solution in diagnosis["solutions"]:
                print(f"  1. {solution}")

        if diagnosis["recommendations"]:
            print("\n💡 建议:")
            for rec in diagnosis["recommendations"]:
                print(f"  • {rec}")

        print("\n📋 系统信息:")
        sys_info = diagnosis["system_check"]
        if sys_info:
            print(f"  CPU使用率: {sys_info.get('cpu_percent', 0):.1f}%")
            print(f"  内存使用率: {sys_info.get('memory_percent', 0):.1f}%")
            print(f"  磁盘使用率: {sys_info.get('disk_percent', 0):.1f}%")

    elif args.quick_fix:
        print("\n⚡ 应用快速修复...")
        success = manager.apply_quick_fix()

        if success:
            print("\n✅ 快速修复完成！")
        else:
            print("\n⚠️ 快速修复完成，但仍有问题需要手动处理")

    elif args.restart_all:
        print("\n🔄 重启所有服务...")
        success = manager.restart_all_services()

        if success:
            print("\n✅ 所有服务已重启")
        else:
            print("\n⚠️ 重启完成，但部分服务可能有问题")

    elif args.restart_failed:
        print("\n🔧 重启失败的服务...")
        status = manager.check_service_status()

        restarted = 0
        for service_name, service_info in status["services"].items():
            port = service_info.get("port")
            if port and not (service_info.get("process_running") and service_info.get("port_open")):
                print(f"重启 {service_name}...")
                if manager.restart_service(service_name):
                    print(f"  ✅ {service_name} 已重启")
                    restarted += 1
                else:
                    print(f"  ❌ {service_name} 重启失败")

        if restarted > 0:
            print(f"\n✅ 已重启 {restarted} 个服务")
        else:
            print("\n📋 没有需要重启的服务")

    elif args.stop_all:
        print("\n🛑 停止所有服务...")

        status = manager.check_service_status()
        stopped = 0

        for service_name, service_info in status["services"].items():
            if service_info.get("process_running"):
                print(f"停止 {service_name}...")
                if manager.stop_service(service_name):
                    print(f"  ✅ {service_name} 已停止")
                    stopped += 1
                else:
                    print(f"  ❌ {service_name} 停止失败")

        print(f"\n📋 已停止 {stopped} 个服务")

    elif args.create_guide:
        print("\n📖 创建恢复指南...")
        guide_path = manager.create_recovery_guide()

        if guide_path:
            print(f"\n✅ 恢复指南已创建: {guide_path}")
            print("请查看该文件获取详细的恢复步骤")
        else:
            print("\n❌ 创建恢复指南失败")

    else:
        # 默认显示帮助
        print("\n📋 可用命令:")
        print("  --status         检查服务状态")
        print("  --diagnose       诊断系统问题")
        print("  --quick-fix      应用快速修复")
        print("  --restart-all    重启所有服务")
        print("  --restart-failed 重启失败的服务")
        print("  --stop-all       停止所有服务")
        print("  --create-guide   创建恢复指南")
        print("\n📖 示例:")
        print(f"  python {os.path.basename(__file__)} --status")
        print(f"  python {os.path.basename(__file__)} --quick-fix")

    print("\n📋 日志文件: recovery_manager.log")
    print("=" * 60)


if __name__ == "__main__":
    main()
