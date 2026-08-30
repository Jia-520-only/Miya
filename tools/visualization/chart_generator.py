"""
图表生成器 - 弥娅核心模块
支持多种图表类型：柱状图、折线图、饼图、热力图、雷达图
"""

import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import logging
from webnet.ToolNet.registry import BaseTool, ToolContext

logger = logging.getLogger(__name__)


# 配置中文字体
def setup_chinese_font():
    """设置中文字体"""
    try:
        # Windows常见中文字体
        chinese_fonts = [
            'Microsoft YaHei',
            'SimHei',
            'KaiTi',
            'FangSong',
            'STXihei',
            'PingFang SC',  # macOS
        ]
        available_fonts = [f.name for f in fm.fontManager.ttflist]

        for font_name in chinese_fonts:
            if font_name in available_fonts:
                plt.rcParams['font.sans-serif'] = [font_name]
                plt.rcParams['axes.unicode_minus'] = False
                logger.info(f"使用中文字体: {font_name}")
                return font_name

        logger.warning("未找到中文字体，使用默认字体")
        return None
    except Exception as e:
        logger.error(f"设置中文字体失败: {e}")
        return None


# 初始化中文字体
setup_chinese_font()


class ChartGenerator(BaseTool):
    """图表生成器"""

    def __init__(self):
        super().__init__()
        self.chart_types = {
            'bar': '柱状图',
            'line': '折线图',
            'pie': '饼图',
            'scatter': '散点图',
            'heatmap': '热力图',
            'radar': '雷达图',
            'histogram': '直方图',
            'area': '面积图',
            'box': '箱线图'
        }

    @property
    def config(self) -> Dict[str, Any]:
        """工具配置（OpenAI Function Calling 格式）"""
        config = {
            "name": "chart_generator",
            "description": "图表生成器：支持柱状图、折线图、饼图、热力图、雷达图、散点图等多种图表类型",
            "type": "function",
            "function": {
                "name": "chart_generator",
                "description": "图表生成器：支持柱状图、折线图、饼图、热力图、雷达图、散点图等多种图表类型",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chart_type": {
                            "type": "string",
                            "description": "图表类型",
                            "enum": ["bar", "line", "pie", "scatter", "heatmap", "radar", "histogram", "area", "box"]
                        },
                        "title": {
                            "type": "string",
                            "description": "图表标题"
                        },
                        "output_path": {
                            "type": "string",
                            "description": "输出路径（可选）"
                        },
                        "style": {
                            "type": "string",
                            "description": "图表样式（可选）"
                        }
                    },
                    "required": ["chart_type"]
                }
            }
        }
        return config

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行图表生成"""
        try:
            # 简化处理，实际应该从参数中获取数据
            chart_type = args.get('chart_type', 'bar')
            title = args.get('title', f'{chart_type}图表')
            return f"图表生成功能已就绪，类型: {chart_type}, 标题: {title}"
        except Exception as e:
            self.logger.error(f"图表生成失败: {e}", exc_info=True)
            return f"图表生成失败: {str(e)}"

    def set_style(self, style: str = 'seaborn'):
        """设置图表样式"""
        try:
            plt.style.use(style)
            logger.info(f"图表样式设置为: {style}")
        except:
            plt.style.use('default')
            logger.warning(f"样式 {style} 不存在，使用默认样式")

    def create_bar_chart(
        self,
        data: pd.DataFrame,
        x_column: str,
        y_column: str,
        title: str = "柱状图",
        color: str = '#2dd4bf',
        output_path: str = None
    ) -> Optional[str]:
        """创建柱状图"""
        fig, ax = plt.subplots(figsize=(10, 6))

        x_data = data[x_column]
        y_data = data[y_column]

        bars = ax.bar(x_data, y_data, color=color, alpha=0.8, edgecolor='white', linewidth=1.5)

        # 添加数值标签
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}',
                   ha='center', va='bottom', fontsize=10)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(x_column, fontsize=12)
        ax.set_ylabel(y_column, fontsize=12)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        return self._save_chart(fig, output_path, "bar_chart")

    def create_line_chart(
        self,
        data: pd.DataFrame,
        x_column: str,
        y_columns: List[str],
        title: str = "折线图",
        colors: List[str] = None,
        output_path: str = None
    ) -> Optional[str]:
        """创建折线图（支持多条线）"""
        fig, ax = plt.subplots(figsize=(12, 6))

        if colors is None:
            colors = ['#2dd4bf', '#f97316', '#8b5cf6', '#10b981', '#f59e0b']

        for i, y_col in enumerate(y_columns):
            if y_col in data.columns:
                color = colors[i % len(colors)]
                ax.plot(data[x_column], data[y_col],
                       marker='o', linewidth=2, markersize=6,
                       color=color, label=y_col)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(x_column, fontsize=12)
        ax.set_ylabel('数值', fontsize=12)
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3, linestyle='--')

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        return self._save_chart(fig, output_path, "line_chart")

    def create_pie_chart(
        self,
        data: pd.DataFrame,
        label_column: str,
        value_column: str,
        title: str = "饼图",
        colors: List[str] = None,
        output_path: str = None
    ) -> Optional[str]:
        """创建饼图"""
        fig, ax = plt.subplots(figsize=(10, 10))

        labels = data[label_column]
        values = data[value_column]

        if colors is None:
            colors = ['#2dd4bf', '#f97316', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444']

        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct='%1.1f%%',
            colors=colors[:len(labels)], startangle=90,
            wedgeprops={'linewidth': 2, 'edgecolor': 'white'}
        )

        # 设置文本样式
        for text in texts:
            text.set_fontsize(11)
        for autotext in autotexts:
            autotext.set_fontsize(10)
            autotext.set_fontweight('bold')
            autotext.set_color('white')

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        plt.tight_layout()

        return self._save_chart(fig, output_path, "pie_chart")

    def create_heatmap(
        self,
        data: pd.DataFrame,
        title: str = "热力图",
        cmap: str = 'YlGnBu',
        output_path: str = None
    ) -> Optional[str]:
        """创建热力图"""
        fig, ax = plt.subplots(figsize=(12, 8))

        im = ax.imshow(data.values, cmap=cmap, aspect='auto')

        # 添加颜色条
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('数值', rotation=270, labelpad=20)

        # 设置坐标轴
        ax.set_xticks(np.arange(len(data.columns)))
        ax.set_yticks(np.arange(len(data.index)))
        ax.set_xticklabels(data.columns, rotation=45, ha='right')
        ax.set_yticklabels(data.index)

        # 添加数值标签
        for i in range(len(data)):
            for j in range(len(data.columns)):
                value = data.iloc[i, j]
                text_color = 'white' if value > data.values.max() / 2 else 'black'
                ax.text(j, i, f'{value:.1f}',
                       ha='center', va='center',
                       color=text_color, fontsize=9)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        plt.tight_layout()

        return self._save_chart(fig, output_path, "heatmap")

    def create_radar_chart(
        self,
        data: pd.DataFrame,
        categories: List[str],
        title: str = "雷达图",
        colors: List[str] = None,
        output_path: str = None
    ) -> Optional[str]:
        """创建雷达图"""
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))

        # 计算角度
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]  # 闭合

        if colors is None:
            colors = ['#2dd4bf', '#f97316', '#8b5cf6']

        # 绘制每个数据行
        for idx, row in data.iterrows():
            values = row.tolist()
            values += values[:1]  # 闭合

            color = colors[idx % len(colors)]
            label = data.index[idx] if hasattr(data, 'index') else f'系列{idx}'

            ax.plot(angles, values, 'o-', linewidth=2, color=color, label=label)
            ax.fill(angles, values, alpha=0.15, color=color)

        # 设置雷达图属性
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_ylim(0, data.values.max() * 1.1)
        ax.set_yticks(np.linspace(0, data.values.max(), 5))
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        ax.grid(True)

        plt.tight_layout()

        return self._save_chart(fig, output_path, "radar_chart")

    def create_scatter_plot(
        self,
        data: pd.DataFrame,
        x_column: str,
        y_column: str,
        color_column: str = None,
        title: str = "散点图",
        output_path: str = None
    ) -> Optional[str]:
        """创建散点图"""
        fig, ax = plt.subplots(figsize=(10, 6))

        if color_column and color_column in data.columns:
            # 按颜色分组绘制
            unique_colors = data[color_column].unique()
            for i, color_val in enumerate(unique_colors):
                subset = data[data[color_column] == color_val]
                colors = plt.cm.Set3(i)
                ax.scatter(subset[x_column], subset[y_column],
                          c=[colors], alpha=0.7, s=100,
                          label=str(color_val), edgecolors='white', linewidths=1)
            ax.legend()
        else:
            ax.scatter(data[x_column], data[y_column],
                      color='#2dd4bf', alpha=0.7, s=100,
                      edgecolors='white', linewidths=1.5)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(x_column, fontsize=12)
        ax.set_ylabel(y_column, fontsize=12)
        ax.grid(True, alpha=0.3, linestyle='--')

        plt.tight_layout()

        return self._save_chart(fig, output_path, "scatter_plot")

    def _save_chart(
        self,
        fig,
        output_path: str = None,
        default_name: str = "chart"
    ) -> str:
        """保存图表"""
        if output_path is None:
            output_path = f"./output/{default_name}.png"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        save_format = Path(output_path).suffix[1:].lower()
        if save_format not in ['png', 'jpg', 'jpeg', 'svg', 'pdf']:
            save_format = 'png'

        fig.savefig(output_path, dpi=300, bbox_inches='tight', format=save_format)
        plt.close(fig)

        logger.info(f"图表已保存: {output_path}")
        return output_path

    def create_dashboard(
        self,
        charts: List[Dict[str, Any]],
        title: str = "数据看板",
        output_path: str = None
    ) -> str:
        """
        创建多图表看板

        Args:
            charts: 图表配置列表
                [
                    {"type": "bar", "data": df, "x": "...", "y": "..."},
                    {"type": "pie", "data": df, "label": "...", "value": "..."}
                ]
            title: 看板标题
            output_path: 输出路径

        Returns:
            看板图片路径
        """
        n_charts = len(charts)
        n_cols = 2 if n_charts > 1 else 1
        n_rows = (n_charts + 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 6 * n_rows))

        if n_charts == 1:
            axes = [axes]
        else:
            axes = axes.flatten()

        for i, chart_config in enumerate(charts):
            ax = axes[i] if i < len(axes) else None
            if ax is None:
                continue

            chart_type = chart_config.get("type")
            data = chart_config.get("data")

            if chart_type == "bar":
                x, y = chart_config["x"], chart_config["y"]
                ax.bar(data[x], data[y], color=chart_config.get("color", '#2dd4bf'))
                ax.set_title(chart_config.get("title", f"图表 {i+1}"))

            elif chart_type == "line":
                x, ys = chart_config["x"], chart_config["y"]
                for j, y_col in enumerate(ys):
                    colors = ['#2dd4bf', '#f97316', '#8b5cf6']
                    ax.plot(data[x], data[y_col], marker='o', color=colors[j % 3], label=y_col)
                ax.legend()

            elif chart_type == "pie":
                label, value = chart_config["label"], chart_config["value"]
                ax.pie(data[value], labels=data[label], autopct='%1.1f%%')
                ax.set_title(chart_config.get("title", f"图表 {i+1}"))

            ax.grid(True, alpha=0.3)

        # 隐藏未使用的子图
        for i in range(n_charts, len(axes)):
            axes[i].axis('off')

        fig.suptitle(title, fontsize=20, fontweight='bold', y=0.995)
        plt.tight_layout()

        return self._save_chart(fig, output_path, "dashboard")


def generate_chart(
    chart_type: str,
    data: pd.DataFrame,
    config: Dict[str, Any],
    output_path: str = None
) -> Dict[str, Any]:
    """
    生成图表的统一接口

    Args:
        chart_type: 图表类型 (bar, line, pie, heatmap, radar, scatter)
        data: 数据框
        config: 图表配置
        output_path: 输出路径

    Returns:
        生成结果
    """
    generator = ChartGenerator()

    chart_methods = {
        'bar': generator.create_bar_chart,
        'line': generator.create_line_chart,
        'pie': generator.create_pie_chart,
        'heatmap': generator.create_heatmap,
        'radar': generator.create_radar_chart,
        'scatter': generator.create_scatter_plot
    }

    method = chart_methods.get(chart_type.lower())

    if method is None:
        logger.error(f"不支持的图表类型: {chart_type}")
        return {"success": False, "error": f"不支持的图表类型: {chart_type}"}

    try:
        result_path = method(data=data, output_path=output_path, **config)
        return {
            "success": True,
            "chart_path": result_path,
            "chart_type": chart_type
        }
    except Exception as e:
        logger.error(f"生成图表失败: {e}")
        return {"success": False, "error": str(e)}
