"""CLI Runner"""

from .commands import CLIRunner as BaseCLIRunner


class CLIRunner(BaseCLIRunner):
    """CLI运行器"""

    def run_interactive(self):
        """交互式运行"""
        print("MIYA CLI - 输入命令帮助获取可用命令")
        while True:
            try:
                cmd = input("> ").strip()
                if not cmd:
                    continue
                if cmd in ["exit", "quit"]:
                    break

                parts = cmd.split()
                name = parts[0]
                args = parts[1:]

                import asyncio

                result = asyncio.run(self.run(name, args))
                print(result)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"错误: {e}")

    def run_script(self, script_path: str):
        """脚本运行"""
        with open(script_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                name = parts[0]
                args = parts[1:]
                import asyncio

                result = asyncio.run(self.run(name, args))
                print(result)
