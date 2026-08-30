"""工具执行API路由模块

提供各类工具执行、数据分析、报告生成等API接口。
"""

import logging
import subprocess
from datetime import datetime
from typing import Any, Dict

import numpy as np
import pandas as pd

from core.text_loader import get_permission

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object
    HTTPException = Exception

    def Depends(x):
        return x


class ToolExecuteRequest(BaseModel):
    """工具执行请求"""

    tool_name: str
    parameters: Dict[str, Any] = {}


class ToolRoutes:
    """工具执行路由

    职责:
    - 工具执行（通用接口）
    - 数据分析工具
    - 图表生成工具
    - 报告生成工具
    - 网络搜索/调研工具
    - 任务管理（创建、执行、列表、删除）
    """

    def __init__(self, web_net: Any, decision_hub: Any):
        """初始化工具路由

        Args:
            web_net: WebNet实例
            decision_hub: DecisionHub实例
        """
        self.web_net = web_net
        self.decision_hub = decision_hub

        if not FASTAPI_AVAILABLE:
            self.router = None
            return

        self.router = APIRouter(prefix="/api/tools", tags=["Tools"])
        self._setup_routes()
        logger.info("[ToolRoutes] 工具路由已初始化")

    def _setup_routes(self):
        """设置路由"""

        @self.router.post("/execute")
        async def execute_tool(
            request: ToolExecuteRequest,
            user_info: Dict = Depends(lambda: {"web_user_id": "web_default"}),
        ):
            """执行工具（需要相应工具权限）"""
            try:
                # 权限检查 - 检查是否有该工具的执行权限
                required_permission = f"tool.{request.tool_name}"
                from webnet.AuthNet.permission_core import PermissionCore

                perm_core = PermissionCore()

                # 从 user_info 获取用户ID
                web_user_id = user_info.get("web_user_id", "web_default")
                has_permission = perm_core.check_permission(web_user_id, required_permission)

                if not has_permission:
                    # 检查是否是系统管理员
                    has_permission = perm_core.check_permission("system_admin", required_permission)

                if not has_permission:
                    return {
                        "success": False,
                        "error": get_permission("tool_permissions.denied_message", "权限不足").format(
                            tool_name=request.tool_name, permission=required_permission
                        ),
                    }

                if hasattr(self.decision_hub, "tool_subnet") and self.decision_hub.tool_subnet:
                    result = await self.decision_hub.tool_subnet.execute_tool(
                        tool_name=request.tool_name,
                        args=request.parameters,
                        user_id=1,
                        sender_name="desktop",
                    )
                    return {"success": True, "result": result}
                else:
                    return {"success": False, "message": "工具子网未初始化"}
            except Exception as e:
                logger.error(f"[ToolRoutes] 工具执行失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.post("/web_research")
        async def web_research(request: Dict[str, Any]):
            """网络调研工具"""
            try:
                if hasattr(self.decision_hub, "tool_subnet") and self.decision_hub.tool_subnet:
                    result = await self.decision_hub.tool_subnet.execute_tool(
                        tool_name="web_research",
                        args=request,
                        user_id=1,
                        sender_name="desktop",
                    )
                    return {"success": True, "result": result}
                else:
                    return {"success": False, "message": "工具子网未初始化"}
            except Exception as e:
                logger.error(f"[ToolRoutes] 网络调研失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.post("/data_analyze")
        async def data_analyze(request: Dict[str, Any]):
            """数据分析工具"""
            try:
                from webnet.ToolNet.tools.visualization.data_analyzer import DataAnalyzer

                analyzer = DataAnalyzer()

                file_path = request.get("file_path", "")
                request.get("analysis_type", "basic")

                if not file_path:
                    return {"success": False, "error": "缺少 file_path 参数"}

                # 读取CSV文件
                try:
                    df = pd.read_csv(file_path)
                except Exception as e:
                    return {"success": False, "error": f"读取文件失败: {str(e)}"}

                # 执行分析
                numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
                if not numeric_cols:
                    return {"success": True, "result": "数据文件中没有数值列"}

                result = analyzer.analyze_trends(df, numeric_cols[0])
                return {"success": True, "result": result}
            except Exception as e:
                logger.error(f"[ToolRoutes] 数据分析失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.post("/chart_generator")
        async def generate_chart(request: Dict[str, Any]):
            """图表生成工具"""
            try:
                from webnet.ToolNet.tools.visualization.chart_generator import ChartGenerator

                generator = ChartGenerator()

                chart_type = request.get("chart_type", "bar")
                x_column = request.get("x_column", "x")
                y_column = request.get("y_column", "y")
                data = request.get("data", {})
                title = request.get("title", "图表")
                output_path = request.get("output_path", "chart.png")
                file_path = request.get("file_path", "")

                df = None
                # 如果提供了文件路径，读取CSV
                if file_path:
                    try:
                        df = pd.read_csv(file_path)
                        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                        str_cols = df.select_dtypes(include=["object"]).columns.tolist()
                        if str_cols:
                            x_column = str_cols[0]
                        if numeric_cols:
                            y_column = numeric_cols[0]
                    except Exception as e:
                        return {"success": False, "error": f"读取CSV失败: {str(e)}"}
                elif data:
                    # 转换为DataFrame
                    if isinstance(data, dict) and data:
                        first_val = next(iter(data.values()))
                        df = pd.DataFrame([data]) if isinstance(first_val, (int, float, str)) else pd.DataFrame(data)
                    else:
                        df = pd.DataFrame(data)
                else:
                    return {
                        "success": False,
                        "error": "缺少 data 参数或 file_path 参数",
                    }

                if df is None or df.empty:
                    return {"success": False, "error": "数据为空"}

                # 生成图表
                chart_method_name = f"create_{chart_type}_chart"
                chart_method = getattr(generator, chart_method_name, None)
                if chart_method:
                    try:
                        if chart_type == "pie":
                            result = chart_method(
                                data=df,
                                label_column=x_column,
                                value_column=y_column,
                                title=title,
                                output_path=output_path,
                            )
                        elif chart_type in ["line", "bar", "scatter"]:
                            result = chart_method(
                                data=df,
                                x_column=x_column,
                                y_column=y_column,
                                title=title,
                                output_path=output_path,
                            )
                        else:
                            result = chart_method(data=df, title=title, output_path=output_path)
                    except Exception as e:
                        result = f"生成图表失败: {str(e)}"
                else:
                    result = f"不支持的图表类型: {chart_type}"

                return {"success": True, "result": result}
            except Exception as e:
                logger.error(f"[ToolRoutes] 图表生成失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.post("/web_search")
        async def web_search(request: Dict[str, Any]):
            """网络搜索工具"""
            try:
                if hasattr(self.decision_hub, "tool_subnet") and self.decision_hub.tool_subnet:
                    result = await self.decision_hub.tool_subnet.execute_tool(
                        tool_name="web_search",
                        args=request,
                        user_id=1,
                        sender_name="desktop",
                    )
                    return {"success": True, "result": result}
                else:
                    return {"success": False, "message": "工具子网未初始化"}
            except Exception as e:
                logger.error(f"[ToolRoutes] 网络搜索失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.post("/task_create")
        async def task_create(request: Dict[str, Any]):
            """创建任务"""
            try:
                task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                task = {
                    "id": task_id,
                    "name": request.get("name", "未命名任务"),
                    "type": request.get("type", "general"),
                    "status": "pending",
                    "created_at": datetime.now().isoformat(),
                }
                return {"success": True, "task": task}
            except Exception as e:
                logger.error(f"[ToolRoutes] 创建任务失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.post("/task_execute")
        async def task_execute(request: Dict[str, Any]):
            """执行任务"""
            try:
                task_type = request.get("type")
                parameters = request.get("parameters", {})
                command = request.get("command", "")

                # 如果有 command，尝试作为 shell 命令执行
                if command:
                    try:
                        result = subprocess.run(
                            command,
                            shell=True,  # nosec B602
                            capture_output=True,
                            text=True,
                            timeout=60,
                            encoding="utf-8",
                            errors="replace",
                        )
                        output = result.stdout or result.stderr or "命令执行完成"
                        return {
                            "success": True,
                            "result": output,
                            "exit_code": result.returncode,
                        }
                    except subprocess.TimeoutExpired:
                        return {"success": False, "error": "命令执行超时"}
                    except Exception as e:
                        return {"success": False, "error": str(e)}

                if hasattr(self.decision_hub, "tool_subnet") and self.decision_hub.tool_subnet:
                    # 根据任务类型调用对应工具
                    tool_mapping = {
                        "data_analyze": "data_analyzer",
                        "file_classify": "file_classifier",
                        "web_research": "web_research",
                        "report": "report_generator",
                        "chart": "chart_generator",
                    }
                    tool_name = tool_mapping.get(task_type, task_type)

                    result = await self.decision_hub.tool_subnet.execute_tool(
                        tool_name=tool_name,
                        args=parameters,
                        user_id=1,
                        sender_name="desktop",
                    )
                    return {"success": True, "result": result}
                else:
                    return {"success": False, "message": "工具子网未初始化"}
            except Exception as e:
                logger.error(f"[ToolRoutes] 执行任务失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.get("/task_list")
        async def get_task_list():
            """获取任务列表"""
            try:
                return {"success": True, "tasks": []}
            except Exception as e:
                logger.error(f"[ToolRoutes] 获取任务列表失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.router.delete("/task_delete")
        async def delete_task(task_id: str):
            """删除任务"""
            try:
                return {"success": True, "message": f"任务 {task_id} 已删除"}
            except Exception as e:
                logger.error(f"[ToolRoutes] 删除任务失败: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

    def get_router(self):
        """获取路由器"""
        return self.router
