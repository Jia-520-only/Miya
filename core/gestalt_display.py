"""
格式塔意识显示器 - 青色科幻风格终端展示
"""

import logging

logger = logging.getLogger("Miya.GestaltDisplay")


# 颜色代码
class Colors:
    """终端颜色代码"""

    RESET = "\033[0m"
    CYAN = "\033[96m"  # 青色
    BRIGHT_CYAN = "\033[93m"  # 亮青色
    GREEN = "\033[92m"  # 绿色
    YELLOW = "\033[93m"  # 黄色
    RED = "\033[91m"  # 红色
    MAGENTA = "\033[95m"  # 品红
    DIM = "\033[90m"  # 灰色
    BOLD = "\033[1m"
    ITALIC = "\033[3m"

    # 青色系
    CYAN_DARK = "\033[38;5;30m"
    CYAN_LIGHT = "\033[38;5;45m"
    TEAL = "\033[38;5;35m"


class GestaltDisplay:
    """
    格式塔意识显示器

    青色科幻风格展示弥娅的思考过程
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def print_header(self, title: str = "弥娅意识"):
        """打印标题"""
        if not self.enabled:
            return

        print(f"\n{Colors.CYAN}{Colors.BOLD}╔{'═' * 50}╗{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}║  ◆ {title} {'═' * (50 - len(title) - 6)}║{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}╚{'═' * 50}╝{Colors.RESET}")

    def print_thinking(
        self,
        step: str,
        detail: str = "",
        sub_items: list = None,
        status: str = "processing",
    ):
        """
        打印思考过程

        Args:
            step: 步骤名称
            detail: 详细说明
            sub_items: 子项目列表
            status: 状态 (processing/done/error)
        """
        if not self.enabled:
            return

        icons = {
            "analyzing": "💭",
            "decomposing": "🔍",
            "tool_selecting": "⚡",
            "tool_executing": "🔧",
            "tool_result": "📥",
            "synthesizing": "✨",
            "output": "💬",
            "processing": "⏳",
            "done": "✓",
            "error": "✗",
        }

        status_colors = {
            "processing": Colors.CYAN,
            "done": Colors.GREEN,
            "error": Colors.RED,
            "waiting": Colors.DIM,
        }

        status_icons = {"processing": "◐", "done": "◉", "error": "◉", "waiting": "○"}

        icons.get(step, "•")
        status_icon = status_icons.get(status, "◐")
        color = status_colors.get(status, Colors.CYAN)

        # 打印主步骤
        print(f"\n{color}{status_icon} {step}{Colors.RESET}")

        if detail:
            print(f"   {Colors.DIM}{detail}{Colors.RESET}")

        # 打印子项目
        if sub_items:
            for i, item in enumerate(sub_items):
                is_last = i == len(sub_items) - 1
                prefix = "└─" if is_last else "├─"
                print(f"   {Colors.CYAN}{prefix} {item}{Colors.RESET}")

    def print_tool_call(self, tool_name: str, status: str = "calling"):
        """
        打印工具调用信息
        """
        if not self.enabled:
            return

        status_text = {"calling": "调用中...", "success": "完成", "error": "失败"}

        status_colors = {
            "calling": Colors.CYAN,
            "success": Colors.GREEN,
            "error": Colors.RED,
        }

        status_icon = {"calling": "◐", "success": "◉", "error": "◉"}

        color = status_colors.get(status, Colors.CYAN)
        icon = status_icon.get(status, "◐")
        text = status_text.get(status, "")

        print(f"   {color}{icon} [{tool_name}] {text}{Colors.RESET}")

    def print_result(self, result: str, max_length: int = 200):
        """打印结果"""
        if not self.enabled:
            return

        # 截断过长的结果
        display_result = result[:max_length] + "..." if len(result) > max_length else result

        print(f"\n{Colors.GREEN}▶ 结果:{Colors.RESET}")
        print(f"   {Colors.DIM}{display_result}{Colors.RESET}")

    def print_separator(self, char: str = "─", length: int = 40):
        """打印分隔线"""
        if not self.enabled:
            return

        print(f"{Colors.CYAN}{char * length}{Colors.RESET}")

    def print_agent_tool_info(self, tool_name: str, agent_name: str):
        """打印 Agent 工具信息（格式塔风格）"""
        if not self.enabled:
            return

        print(f"   {Colors.TEAL}⚡ 工具: {tool_name} (来自 {agent_name}){Colors.RESET}")

    def print_complexity_analysis(self, complexity: str, tool_count: int, agent_tools: list):
        """打印复杂度分析"""
        if not self.enabled:
            return

        complexity_text = {
            "simple": "简单任务",
            "medium": "中等任务",
            "complex": "复杂任务",
        }

        complexity_colors = {
            "simple": Colors.GREEN,
            "medium": Colors.YELLOW,
            "complex": Colors.CYAN,
        }

        color = complexity_colors.get(complexity, Colors.CYAN)
        text = complexity_text.get(complexity, complexity)

        print(f"\n{color}◆ 任务类型: {text} ({tool_count}个工具){Colors.RESET}")

        if agent_tools:
            print(f"   {Colors.DIM}Agent工具: {', '.join(agent_tools)}{Colors.RESET}")

    def print_collaboration_info(self, mode: str, models: list):
        """打印协作引擎信息"""
        if not self.enabled:
            return

        print(f"\n{Colors.CYAN}◆ 协作模式: {mode}{Colors.RESET}")
        print(f"   {Colors.DIM}使用模型: {', '.join(models)}{Colors.RESET}")

    def clear(self):
        """清屏"""
        if not self.enabled:
            return
        print("\033[2J\033[H", end="")

    def print_full_thinking(self, steps: list, title: str = "弥娅意识"):
        """
        打印完整思考链

        steps: [
            {"step": "分析任务", "detail": "...", "sub_items": [...], "status": "done"},
            {"step": "选择工具", "detail": "...", "status": "processing"},
        ]
        """
        if not self.enabled:
            return

        self.print_header(title)

        for step_info in steps:
            self.print_thinking(
                step=step_info.get("step", ""),
                detail=step_info.get("detail", ""),
                sub_items=step_info.get("sub_items", []),
                status=step_info.get("status", "processing"),
            )

        self.print_separator()


# 全局单例
_gestalt_display: GestaltDisplay = None


def get_gestalt_display() -> GestaltDisplay:
    """获取格式塔显示器单例"""
    global _gestalt_display
    if _gestalt_display is None:
        _gestalt_display = GestaltDisplay()
    return _gestalt_display


def set_gestalt_display_enabled(enabled: bool):
    """设置显示器是否启用"""
    display = get_gestalt_display()
    display.enabled = enabled
