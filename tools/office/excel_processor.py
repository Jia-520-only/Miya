"""
Excel数据处理工具 - 弥娅核心模块
支持数据清洗、跨表格匹配、自动生成统计报表
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class ExcelProcessor:
    """Excel数据处理器"""

    def __init__(self):
        self.supported_formats = ['.xlsx', '.xls', '.csv']

    def load_file(self, file_path: str) -> Optional[pd.DataFrame]:
        """加载Excel或CSV文件"""
        path = Path(file_path)
        if not path.exists():
            logger.error(f"文件不存在: {file_path}")
            return None

        if path.suffix.lower() not in self.supported_formats:
            logger.error(f"不支持的文件格式: {path.suffix}")
            return None

        try:
            if path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, engine='openpyxl' if path.suffix == '.xlsx' else 'xlrd')
            else:
                df = pd.read_csv(file_path, encoding='utf-8-sig')

            logger.info(f"成功加载文件: {file_path}, 形状: {df.shape}")
            return df
        except Exception as e:
            logger.error(f"加载文件失败: {e}")
            return None

    def clean_data(self, df: pd.DataFrame, config: Dict[str, Any] = None) -> pd.DataFrame:
        """
        数据清洗
        config示例:
        {
            "remove_duplicates": True,
            "fill_empty": "mean",  # mean, median, mode, forward_fill, drop
            "standardize_case": True,
            "trim_whitespace": True
        }
        """
        if config is None:
            config = {}

        result_df = df.copy()

        # 去重
        if config.get("remove_duplicates", True):
            before = len(result_df)
            result_df = result_df.drop_duplicates()
            after = len(result_df)
            logger.info(f"去重: {before} → {after} 行 (删除 {before - after} 行)")

        # 处理空值
        fill_strategy = config.get("fill_empty", "drop")
        if fill_strategy != "drop":
            for col in result_df.columns:
                if result_df[col].isna().any():
                    if fill_strategy == "mean" and pd.api.types.is_numeric_dtype(result_df[col]):
                        result_df[col].fillna(result_df[col].mean(), inplace=True)
                    elif fill_strategy == "median" and pd.api.types.is_numeric_dtype(result_df[col]):
                        result_df[col].fillna(result_df[col].median(), inplace=True)
                    elif fill_strategy == "mode":
                        result_df[col].fillna(result_df[col].mode()[0], inplace=True)
                    elif fill_strategy == "forward_fill":
                        result_df[col].fillna(method='ffill', inplace=True)
        else:
            before = len(result_df)
            result_df = result_df.dropna()
            after = len(result_df)
            logger.info(f"删除空值: {before} → {after} 行")

        # 标准化大小写（字符串列）
        if config.get("standardize_case", True):
            for col in result_df.columns:
                if pd.api.types.is_string_dtype(result_df[col]):
                    result_df[col] = result_df[col].str.strip().str.title()

        # 去除空白
        if config.get("trim_whitespace", True):
            result_df = result_df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

        logger.info(f"数据清洗完成, 最终形状: {result_df.shape}")
        return result_df

    def cross_table_match(
        self,
        df1: pd.DataFrame,
        df2: pd.DataFrame,
        join_key1: str,
        join_key2: str,
        join_type: str = "inner"
    ) -> pd.DataFrame:
        """
        跨表格数据匹配

        Args:
            df1: 左表
            df2: 右表
            join_key1: 左表连接键
            join_key2: 右表连接键
            join_type: 连接类型 (inner, left, right, outer)
        """
        try:
            result = pd.merge(
                df1,
                df2,
                left_on=join_key1,
                right_on=join_key2,
                how=join_type,
                suffixes=('_left', '_right')
            )
            logger.info(f"跨表匹配完成: df1({df1.shape}) + df2({df2.shape}) → result({result.shape})")
            return result
        except Exception as e:
            logger.error(f"跨表匹配失败: {e}")
            return df1

    def generate_statistics(self, df: pd.DataFrame, columns: List[str] = None) -> Dict[str, Any]:
        """生成统计报表"""
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        stats = {
            "总行数": len(df),
            "总列数": len(df.columns),
            "数值列统计": {}
        }

        for col in columns:
            if col not in df.columns:
                continue

            col_stats = {
                "数据类型": str(df[col].dtype),
                "非空值数": df[col].notna().sum(),
                "空值数": df[col].isna().sum(),
                "唯一值数": df[col].nunique(),
            }

            if pd.api.types.is_numeric_dtype(df[col]):
                col_stats.update({
                    "最小值": df[col].min(),
                    "最大值": df[col].max(),
                    "平均值": df[col].mean(),
                    "中位数": df[col].median(),
                    "标准差": df[col].std(),
                    "总和": df[col].sum(),
                })

            stats["数值列统计"][col] = col_stats

        return stats

    def group_and_aggregate(
        self,
        df: pd.DataFrame,
        group_by: str,
        agg_column: str,
        agg_func: str = "sum"
    ) -> pd.DataFrame:
        """
        分组聚合

        Args:
            df: 数据框
            group_by: 分组列名
            agg_column: 聚合列名
            agg_func: 聚合函数 (sum, mean, median, count, min, max)
        """
        try:
            agg_map = {
                'sum': 'sum',
                'mean': 'mean',
                'median': 'median',
                'count': 'count',
                'min': 'min',
                'max': 'max'
            }

            result = df.groupby(group_by)[agg_column].agg(agg_map.get(agg_func, 'sum')).reset_index()
            result.columns = [group_by, f"{agg_column}_{agg_func}"]

            logger.info(f"分组聚合完成: 按 {group_by} 分组, {agg_func}({agg_column})")
            return result
        except Exception as e:
            logger.error(f"分组聚合失败: {e}")
            return df

    def save_file(self, df: pd.DataFrame, output_path: str, format: str = "excel") -> bool:
        """保存文件"""
        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            if format == "excel":
                df.to_excel(output_path, index=False, engine='openpyxl')
            elif format == "csv":
                df.to_csv(output_path, index=False, encoding='utf-8-sig')

            logger.info(f"文件保存成功: {output_path}")
            return True
        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            return False

    def detect_and_standardize_dates(self, df: pd.DataFrame, date_columns: List[str] = None) -> pd.DataFrame:
        """检测并标准化日期列"""
        result_df = df.copy()

        if date_columns is None:
            # 自动检测日期列
            date_columns = []
            for col in result_df.columns:
                if pd.api.types.is_string_dtype(result_df[col]):
                    try:
                        pd.to_datetime(result_df[col].head(100), errors='coerce')
                        date_columns.append(col)
                    except:
                        pass

        for col in date_columns:
            if col in result_df.columns:
                result_df[col] = pd.to_datetime(result_df[col], errors='coerce')
                logger.info(f"标准化日期列: {col}")

        return result_df

    def add_calculated_column(
        self,
        df: pd.DataFrame,
        new_col_name: str,
        formula: str,
        columns_map: Dict[str, str] = None
    ) -> pd.DataFrame:
        """
        添加计算列

        formula示例: "A + B * 2"
        columns_map示例: {"A": "销售额", "B": "成本"}
        """
        result_df = df.copy()

        try:
            # 替换列名为中文别名
            expr = formula
            if columns_map:
                for eng_name, chn_name in columns_map.items():
                    expr = expr.replace(eng_name, chn_name)

            # 计算新列
            result_df[new_col_name] = result_df.eval(expr)
            logger.info(f"添加计算列: {new_col_name} = {expr}")
            return result_df
        except Exception as e:
            logger.error(f"添加计算列失败: {e}")
            return result_df


# 工具函数
def process_excel_command(
    file_path: str,
    operations: List[Dict[str, Any]],
    output_path: str
) -> Dict[str, Any]:
    """
    执行Excel处理命令

    Args:
        file_path: 输入文件路径
        operations: 操作列表
            [
                {"type": "clean", "config": {...}},
                {"type": "match", "df2": "...", "key1": "...", "key2": "..."},
                {"type": "aggregate", "group_by": "...", "agg_col": "...", "func": "..."}
            ]
        output_path: 输出文件路径

    Returns:
        处理结果和统计信息
    """
    processor = ExcelProcessor()
    df = processor.load_file(file_path)

    if df is None:
        return {"success": False, "error": "无法加载文件"}

    stats = {
        "operations_performed": [],
        "original_shape": df.shape,
    }

    for op in operations:
        op_type = op.get("type")

        if op_type == "clean":
            df = processor.clean_data(df, op.get("config"))
            stats["operations_performed"].append("数据清洗")

        elif op_type == "match":
            df2 = processor.load_file(op.get("df2"))
            if df2 is not None:
                df = processor.cross_table_match(
                    df, df2,
                    op.get("key1"), op.get("key2"),
                    op.get("join_type", "inner")
                )
                stats["operations_performed"].append(f"跨表匹配: {op.get('key1')} <-> {op.get('key2')}")

        elif op_type == "aggregate":
            df = processor.group_and_aggregate(
                df,
                op.get("group_by"),
                op.get("agg_col"),
                op.get("func", "sum")
            )
            stats["operations_performed"].append("分组聚合")

        elif op_type == "add_column":
            df = processor.add_calculated_column(
                df,
                op.get("name"),
                op.get("formula"),
                op.get("columns_map")
            )
            stats["operations_performed"].append(f"添加列: {op.get('name')}")

        elif op_type == "detect_dates":
            df = processor.detect_and_standardize_dates(df, op.get("columns"))
            stats["operations_performed"].append("日期标准化")

    # 生成最终统计
    final_stats = processor.generate_statistics(df)
    stats["final_shape"] = df.shape
    stats["statistics"] = final_stats

    # 保存结果
    success = processor.save_file(df, output_path)

    return {
        "success": success,
        "stats": stats,
        "output_file": output_path
    }
