"""
数据分析器 - 弥娅核心模块
支持趋势分析、异常检测、智能洞察
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import logging
from webnet.ToolNet.registry import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class DataAnalyzer(BaseTool):
    """数据分析器"""

    def __init__(self):
        super().__init__()
        pass

    @property
    def config(self) -> Dict[str, Any]:
        """工具配置（OpenAI Function Calling 格式）"""
        config = {
            "name": "data_analyzer",
            "description": "数据分析器：支持趋势分析、异常检测、相关性分析、聚类分析、智能洞察生成",
            "type": "function",
            "function": {
                "name": "data_analyzer",
                "description": "数据分析器：支持趋势分析、异常检测、相关性分析、聚类分析、智能洞察生成",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "analysis_type": {
                            "type": "string",
                            "description": "分析类型: trend(趋势分析), anomaly(异常检测), correlation(相关性分析), cluster(聚类分析), comprehensive(综合分析)",
                            "enum": ["trend", "anomaly", "correlation", "cluster", "comprehensive"]
                        },
                        "value_column": {
                            "type": "string",
                            "description": "主要数值列名（用于趋势分析、异常检测、综合分析）"
                        },
                        "time_column": {
                            "type": "string",
                            "description": "时间列名（可选，用于时间趋势分析）"
                        },
                        "method": {
                            "type": "string",
                            "description": "检测方法: iqr, zscore, isolation_forest（用于异常检测）",
                            "enum": ["iqr", "zscore", "isolation_forest"]
                        },
                        "threshold": {
                            "type": "number",
                            "description": "阈值参数（默认1.5）"
                        },
                        "features": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "特征列列表（用于聚类分析）"
                        },
                        "n_clusters": {
                            "type": "integer",
                            "description": "聚类数量（默认3）"
                        },
                        "correlation_method": {
                            "type": "string",
                            "description": "相关系数类型: pearson, spearman, kendall",
                            "enum": ["pearson", "spearman", "kendall"]
                        }
                    },
                    "required": []
                }
            }
        }
        return config

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行数据分析"""
        try:
            # 从上下文获取数据（假设数据已传入）
            # 这里简化处理，实际应该从参数中获取数据
            return "数据分析功能已就绪，请提供数据进行分析。"
        except Exception as e:
            self.logger.error(f"数据分析失败: {e}", exc_info=True)
            return f"数据分析失败: {str(e)}"

    def analyze_trends(
        self,
        df: pd.DataFrame,
        value_column: str,
        time_column: str = None
    ) -> Dict[str, Any]:
        """
        趋势分析

        Args:
            df: 数据框
            value_column: 数值列名
            time_column: 时间列名（可选）
        """
        if value_column not in df.columns:
            return {"error": f"列 '{value_column}' 不存在"}

        values = df[value_column].dropna()

        # 计算趋势指标
        trend_analysis = {
            "数据范围": {
                "最小值": values.min(),
                "最大值": values.max(),
                "极差": values.max() - values.min()
            },
            "集中趋势": {
                "平均值": values.mean(),
                "中位数": values.median(),
                "众数": values.mode()[0] if not values.mode().empty else None,
                "标准差": values.std(),
                "变异系数": (values.std() / values.mean()) * 100 if values.mean() != 0 else 0
            },
            "变化趋势": self._calculate_trend(values),
            "分布特征": self._analyze_distribution(values)
        }

        # 如果有时间列，分析时间趋势
        if time_column and time_column in df.columns:
            df_sorted = df.sort_values(time_column)
            trend_analysis["时间趋势"] = self._analyze_time_trend(
                df_sorted[time_column],
                df_sorted[value_column]
            )

        return trend_analysis

    def _calculate_trend(self, values: pd.Series) -> Dict[str, Any]:
        """计算趋势方向"""
        # 简单的线性回归
        x = np.arange(len(values)).reshape(-1, 1)
        y = values.values

        model = LinearRegression()
        model.fit(x, y)

        slope = model.coef_[0]
        r_squared = model.score(x, y)

        # 判断趋势方向
        if abs(slope) < 0.01 * values.mean():
            direction = "平稳"
        elif slope > 0:
            direction = "上升"
        else:
            direction = "下降"

        return {
            "趋势方向": direction,
            "斜率": slope,
            "拟合优度(R²)": r_squared,
            "变化率": f"{(slope / values.mean() * 100):.2f}%" if values.mean() != 0 else "0%"
        }

    def _analyze_time_trend(
        self,
        time_data: pd.Series,
        value_data: pd.Series
    ) -> Dict[str, Any]:
        """分析时间序列趋势"""
        # 计算环比增长率
        growth_rates = []
        for i in range(1, len(value_data)):
            if value_data.iloc[i-1] != 0:
                rate = (value_data.iloc[i] - value_data.iloc[i-1]) / value_data.iloc[i-1] * 100
                growth_rates.append(rate)

        return {
            "平均增长率": np.mean(growth_rates) if growth_rates else 0,
            "增长标准差": np.std(growth_rates) if growth_rates else 0,
            "最高增长": max(growth_rates) if growth_rates else 0,
            "最低增长": min(growth_rates) if growth_rates else 0,
            "波动次数": sum(1 for rate in growth_rates if abs(rate) > 10) if growth_rates else 0
        }

    def _analyze_distribution(self, values: pd.Series) -> Dict[str, Any]:
        """分析数据分布"""
        # 四分位数
        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        # 偏度和峰度
        skewness = stats.skew(values)
        kurtosis = stats.kurtosis(values)

        # 偏度解释
        if abs(skewness) < 0.5:
            skew_desc = "接近正态分布"
        elif skewness > 0.5:
            skew_desc = "右偏（正偏）"
        else:
            skew_desc = "左偏（负偏）"

        # 峰度解释
        if abs(kurtosis) < 0.5:
            kurt_desc = "接近正态分布"
        elif kurtosis > 0.5:
            kurt_desc = "尖峰分布"
        else:
            kurt_desc = "平峰分布"

        return {
            "四分位数": {
                "Q1 (25%)": q1,
                "Q2 (50%)": values.median(),
                "Q3 (75%)": q3,
                "IQR": iqr
            },
            "偏度": skewness,
            "偏度描述": skew_desc,
            "峰度": kurtosis,
            "峰度描述": kurt_desc
        }

    def detect_anomalies(
        self,
        df: pd.DataFrame,
        value_column: str,
        method: str = "iqr",
        threshold: float = 1.5
    ) -> pd.DataFrame:
        """
        检测异常值

        Args:
            df: 数据框
            value_column: 数值列名
            method: 检测方法 (iqr, zscore, isolation_forest)
            threshold: 阈值参数

        Returns:
            包含异常值的行
        """
        if value_column not in df.columns:
            return df.head(0)

        values = df[value_column].dropna()

        if method == "iqr":
            # IQR方法
            q1 = values.quantile(0.25)
            q3 = values.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - threshold * iqr
            upper_bound = q3 + threshold * iqr

            anomalies = df[(df[value_column] < lower_bound) | (df[value_column] > upper_bound)]
            logger.info(f"IQR方法检测到 {len(anomalies)} 个异常值")

        elif method == "zscore":
            # Z-score方法
            z_scores = np.abs(stats.zscore(values))
            anomalies = df[z_scores > threshold]
            logger.info(f"Z-score方法检测到 {len(anomalies)} 个异常值")

        elif method == "isolation_forest":
            # Isolation Forest方法
            from sklearn.ensemble import IsolationForest

            iso_forest = IsolationForest(contamination=0.1, random_state=42)
            iso_forest.fit(values.values.reshape(-1, 1))
            anomaly_labels = iso_forest.predict(values.values.reshape(-1, 1))

            anomalies = df[anomaly_labels == -1]
            logger.info(f"Isolation Forest检测到 {len(anomalies)} 个异常值")
        else:
            logger.error(f"不支持的异常检测方法: {method}")
            return df.head(0)

        return anomalies

    def generate_insights(
        self,
        df: pd.DataFrame,
        analysis_results: Dict[str, Any]
    ) -> List[str]:
        """
        生成智能洞察

        Args:
            df: 原始数据
            analysis_results: 分析结果

        Returns:
            洞察列表
        """
        insights = []

        # 趋势洞察
        if "变化趋势" in analysis_results:
            trend = analysis_results["变化趋势"]
            direction = trend.get("趋势方向", "")
            rate = trend.get("变化率", "")

            if direction == "上升":
                insights.append(f"💡 数据呈现{direction}趋势，平均{rate}增长率，建议关注持续增长的原因。")
            elif direction == "下降":
                insights.append(f"⚠️ 数据呈现{direction}趋势，{rate}负增长，建议检查影响因素。")
            else:
                insights.append(f"📊 数据整体{direction}，变化相对稳定。")

        # 分布洞察
        if "分布特征" in analysis_results:
            dist = analysis_results["分布特征"]
            skew_desc = dist.get("偏度描述", "")

            if "右偏" in skew_desc:
                insights.append("🔍 数据分布右偏，大部分数据集中在较低区间，存在少数高值。")
            elif "左偏" in skew_desc:
                insights.append("🔍 数据分布左偏，大部分数据集中在较高区间，存在少数低值。")

        # 异常值洞察
        anomalies = self.detect_anomalies(df, list(df.select_dtypes(include=[np.number]).columns)[0])
        if len(anomalies) > 0:
            anomaly_count = len(anomalies)
            anomaly_ratio = anomaly_count / len(df) * 100
            insights.append(f"🚨 检测到 {anomaly_count} 个异常值（占 {anomaly_ratio:.1f}%），建议核实这些数据点的准确性。")

        # 相关性洞察（如果是多列数据）
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(numeric_cols) >= 2:
            corr_matrix = df[numeric_cols].corr().abs()

            # 找出高相关列对
            high_corr_pairs = []
            for i in range(len(corr_matrix.columns)):
                for j in range(i+1, len(corr_matrix.columns)):
                    corr = corr_matrix.iloc[i, j]
                    if corr > 0.8:
                        high_corr_pairs.append(
                            f"{corr_matrix.columns[i]} 和 {corr_matrix.columns[j]}"
                        )

            if high_corr_pairs:
                insights.append(f"🔗 发现强相关性：{'、'.join(high_corr_pairs)}，建议分析是否存在因果关系。")

        return insights

    def cluster_analysis(
        self,
        df: pd.DataFrame,
        features: List[str],
        n_clusters: int = 3
    ) -> Dict[str, Any]:
        """
        聚类分析

        Args:
            df: 数据框
            features: 特征列列表
            n_clusters: 聚类数量

        Returns:
            聚类结果和每个簇的统计
        """
        # 准备数据
        feature_data = df[features].dropna()

        # 标准化
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(feature_data)

        # K-means聚类
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(scaled_data)

        # 添加聚类标签
        result_df = df.copy()
        result_df['cluster'] = clusters

        # 分析每个簇
        cluster_stats = {}
        for cluster_id in range(n_clusters):
            cluster_data = result_df[result_df['cluster'] == cluster_id]
            cluster_stats[cluster_id] = {
                "样本数": len(cluster_data),
                "特征均值": cluster_data[features].mean().to_dict(),
                "特征标准差": cluster_data[features].std().to_dict()
            }

        return {
            "clustered_data": result_df,
            "cluster_stats": cluster_stats,
            "cluster_centers": kmeans.cluster_centers_
        }

    def correlation_analysis(
        self,
        df: pd.DataFrame,
        method: str = "pearson"
    ) -> pd.DataFrame:
        """
        相关性分析

        Args:
            df: 数据框
            method: 相关系数类型 (pearson, spearman, kendall)

        Returns:
            相关系数矩阵
        """
        numeric_df = df.select_dtypes(include=[np.number])

        if numeric_df.empty:
            logger.warning("没有数值列进行相关性分析")
            return pd.DataFrame()

        corr_matrix = numeric_df.corr(method=method)

        # 解读相关性强度
        def interpret_corr(r):
            abs_r = abs(r)
            if abs_r >= 0.8:
                return "极强"
            elif abs_r >= 0.6:
                return "强"
            elif abs_r >= 0.4:
                return "中等"
            elif abs_r >= 0.2:
                return "弱"
            else:
                return "极弱或无"

        return corr_matrix

    def comprehensive_analysis(
        self,
        df: pd.DataFrame,
        value_column: str,
        time_column: str = None
    ) -> Dict[str, Any]:
        """
        综合分析报告

        Returns:
            包含趋势、异常、洞察的完整报告
        """
        report = {
            "趋势分析": self.analyze_trends(df, value_column, time_column),
            "异常检测": {
                "方法": "IQR",
                "异常数据": self.detect_anomalies(df, value_column, method="iqr").to_dict('records')
            },
            "洞察": []
        }

        # 生成智能洞察
        insights = self.generate_insights(df, report["趋势分析"])
        report["洞察"] = insights

        # 相关性分析
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(numeric_cols) >= 2:
            corr = self.correlation_analysis(df)
            report["相关性分析"] = corr.to_dict()

        return report


def analyze_data(
    data: pd.DataFrame,
    analysis_type: str = "comprehensive",
    value_column: str = None,
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    数据分析的统一接口

    Args:
        data: 数据框
        analysis_type: 分析类型 (trend, anomaly, correlation, cluster, comprehensive)
        value_column: 主要数值列
        config: 配置参数

    Returns:
        分析结果
    """
    analyzer = DataAnalyzer()

    if analysis_type == "trend":
        if not value_column:
            return {"error": "趋势分析需要指定value_column"}
        return analyzer.analyze_trends(data, value_column, config.get("time_column"))

    elif analysis_type == "anomaly":
        if not value_column:
            return {"error": "异常检测需要指定value_column"}
        anomalies = analyzer.detect_anomalies(
            data, value_column,
            method=config.get("method", "iqr"),
            threshold=config.get("threshold", 1.5)
        )
        return {"异常数据": anomalies.to_dict('records'), "异常数量": len(anomalies)}

    elif analysis_type == "correlation":
        return analyzer.correlation_analysis(data, method=config.get("method", "pearson"))

    elif analysis_type == "cluster":
        features = config.get("features", data.select_dtypes(include=[np.number]).columns.tolist())
        return analyzer.cluster_analysis(data, features, n_clusters=config.get("n_clusters", 3))

    elif analysis_type == "comprehensive":
        return analyzer.comprehensive_analysis(
            data,
            value_column or data.select_dtypes(include=[np.number]).columns[0],
            config.get("time_column") if config else None
        )

    else:
        return {"error": f"不支持的分析类型: {analysis_type}"}
