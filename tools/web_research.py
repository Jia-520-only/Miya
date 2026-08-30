"""
网络调研工具 - 弥娅核心模块
支持行业/竞品分析、多源信息整合
"""

import asyncio
from typing import Dict, List, Optional, Any
from .web_search_enhanced import EnhancedWebSearch
import logging

logger = logging.getLogger(__name__)


class WebResearcher:
    """网络调研器"""

    def __init__(self):
        self.searcher = EnhancedWebSearch()

    async def research_topic(
        self,
        topic: str,
        research_type: str = "general",
        depth: int = 2
    ) -> Dict[str, Any]:
        """
        调研主题

        Args:
            topic: 调研主题
            research_type: 调研类型 (general, industry, competitor, product)
            depth: 调研深度（1=基础，2=深入）

        Returns:
            调研结果
        """
        logger.info(f"开始调研主题: {topic} (类型: {research_type}, 深度: {depth})")

        results = {
            "主题": topic,
            "调研类型": research_type,
            "搜索查询": [],
            "信息来源": [],
            "调研内容": {},
            "时间戳": asyncio.get_event_loop().time()
        }

        # 根据类型设计搜索查询
        if research_type == "general":
            queries = [
                f"{topic} 概念 定义",
                f"{topic} 发展趋势",
                f"{topic} 应用场景",
                f"{topic} 挑战与机遇"
            ]
        elif research_type == "industry":
            queries = [
                f"{topic} 行业现状 市场规模",
                f"{topic} 行业发展趋势",
                f"{topic} 行业龙头企业",
                f"{topic} 行业政策法规"
            ]
        elif research_type == "competitor":
            queries = [
                f"{topic} 竞品对比分析",
                f"{topic} 优劣势分析",
                f"{topic} 市场份额",
                f"{topic} 用户评价"
            ]
        elif research_type == "product":
            queries = [
                f"{topic} 产品功能特性",
                f"{topic} 技术架构",
                f"{topic} 使用案例",
                f"{topic} 定价策略"
            ]
        else:
            queries = [topic]

        results["搜索查询"] = queries

        # 执行搜索
        all_sources = set()

        for query in queries:
            search_results = await self._search_async(query)

            for result in search_results:
                url = result.get("url", "")
                if url and url not in all_sources:
                    all_sources.add(url)

                    # 分类信息
                    category = self._categorize_information(query, result)
                    if category not in results["调研内容"]:
                        results["调研内容"][category] = []

                    results["调研内容"][category].append({
                        "查询": query,
                        "来源": url,
                        "标题": result.get("title", ""),
                        "内容": result.get("snippet", ""),
                        "相关性": result.get("relevance_score", 0)
                    })

        results["信息来源数"] = len(all_sources)
        results["信息来源"] = list(all_sources)[:20]  # 最多保留20个来源

        # 深度调研
        if depth >= 2:
            results["深度分析"] = await self._deep_analyze(results["调研内容"])

        logger.info(f"调研完成: {len(all_sources)} 个信息来源")
        return results

    async def research_competitors(
        self,
        company_name: str
    ) -> Dict[str, Any]:
        """
        调研竞品

        Args:
            company_name: 公司名称或产品名

        Returns:
            竞品调研结果
        """
        logger.info(f"开始调研竞品: {company_name}")

        # 多维度搜索
        search_tasks = [
            self._search_async(f"{company_name} 公司介绍 官网"),
            self._search_async(f"{company_name} 产品功能"),
            self._search_async(f"{company_name} 用户评价 口碑"),
            self._search_async(f"{company_name} 定价 价格"),
            self._search_async(f"{company_name} 市场份额")
        ]

        # 并发执行搜索
        search_results = await asyncio.gather(*search_tasks)

        # 整合结果
        competitor_data = {
            "公司名称": company_name,
            "基本信息": [],
            "产品信息": [],
            "用户评价": [],
            "定价信息": [],
            "市场信息": []
        }

        for i, results in enumerate(search_results):
            if i == 0:  # 基本信息
                competitor_data["基本信息"].extend(results)
            elif i == 1:  # 产品信息
                competitor_data["产品信息"].extend(results)
            elif i == 2:  # 用户评价
                competitor_data["用户评价"].extend(results)
            elif i == 3:  # 定价信息
                competitor_data["定价信息"].extend(results)
            elif i == 4:  # 市场信息
                competitor_data["市场信息"].extend(results)

        # 生成竞品对比总结
        competitor_data["总结"] = self._generate_competitor_summary(competitor_data)

        return competitor_data

    def _categorize_information(
        self,
        query: str,
        result: Dict[str, Any]
    ) -> str:
        """分类信息"""
        title = result.get("title", "").lower()
        snippet = result.get("snippet", "").lower()

        # 根据查询类型分类
        if "定义" in query or "概念" in query:
            return "定义概念"
        elif "趋势" in query or "发展" in query:
            return "发展趋势"
        elif "应用" in query or "场景" in query:
            return "应用场景"
        elif "挑战" in query or "机遇" in query:
            return "挑战机遇"
        elif "功能" in query or "特性" in query:
            return "功能特性"
        elif "评价" in query or "口碑" in query:
            return "用户评价"
        elif "定价" in query or "价格" in query:
            return "定价信息"
        elif "市场份额" in query:
            return "市场信息"
        else:
            return "其他信息"

    async def _deep_analyze(
        self,
        content: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """深度分析调研内容"""
        analysis = {
            "信息覆盖度": {},
            "关键发现": [],
            "信息缺口": []
        }

        # 统计每个类别的信息量
        for category, items in content.items():
            analysis["信息覆盖度"][category] = len(items)

            # 提取关键信息
            for item in items:
                title = item.get("标题", "")
                snippet = item.get("内容", "")
                relevance = item.get("相关性", 0)

                if relevance >= 5:  # 高相关性结果
                    analysis["关键发现"].append({
                        "类别": category,
                        "来源": item.get("来源", ""),
                        "标题": title,
                        "重要性": "高"
                    })

        # 识别信息缺口
        coverage = analysis["信息覆盖度"]
        total_sources = sum(coverage.values())

        if coverage.get("定义概念", 0) < 2:
            analysis["信息缺口"].append("定义和概念信息不足")
        if coverage.get("发展趋势", 0) < 2:
            analysis["信息缺口"].append("发展趋势信息较少")
        if coverage.get("应用场景", 0) < 2:
            analysis["信息缺口"].append("应用场景案例不足")

        return analysis

    def _generate_competitor_summary(
        self,
        competitor_data: Dict[str, Any]
    ) -> str:
        """生成竞品总结"""
        summary_parts = []

        # 基本信息总结
        if competitor_data["基本信息"]:
            summary_parts.append(f"**基本信息**: 收集了 {len(competitor_data['基本信息'])} 条相关信息")

        # 产品功能总结
        if competitor_data["产品信息"]:
            summary_parts.append(f"**产品功能**: 识别了 {len(competitor_data['产品信息'])} 个功能特性")

        # 用户评价总结
        if competitor_data["用户评价"]:
            positive = sum(1 for item in competitor_data["用户评价"] 
                        if any(kw in item.get("内容", "") for kw in ["好", "优秀", "推荐"]))
            negative = sum(1 for item in competitor_data["用户评价"] 
                        if any(kw in item.get("内容", "") for kw in ["差", "不好", "不推荐"]))
            summary_parts.append(f"**用户反馈**: 正面评价 {positive}条，负面评价 {negative}条")

        # 定价总结
        if competitor_data["定价信息"]:
            summary_parts.append(f"**定价信息**: 获取了 {len(competitor_data['定价信息'])} 条定价相关数据")

        return "\n".join(summary_parts)

    async def _search_async(self, query: str) -> List[Dict[str, Any]]:
        """异步搜索"""
        # 在异步上下文中运行搜索
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.searcher.search, query)

    def generate_research_report(
        self,
        research_data: Dict[str, Any],
        output_path: str
    ) -> bool:
        """
        生成调研报告

        Args:
            research_data: 调研数据
            output_path: 报告输出路径

        Returns:
            是否成功
        """
        report = f"""# 调研报告

## 基本信息

- **调研主题**: {research_data.get("主题", "未知")}
- **调研类型**: {research_data.get("调研类型", "常规")}
- **调研时间**: {research_data.get("时间戳", 0)}
- **信息来源数**: {research_data.get("信息来源数", 0)}

## 搜索查询

{chr(10).join(f"{i+1}. {q}" for i, q in enumerate(research_data.get("搜索查询", [])))}

## 调研内容

"""

        # 按类别组织内容
        content = research_data.get("调研内容", {})

        for category, items in content.items():
            if not items:
                continue

            report += f"\n### {category} ({len(items)}条信息)\n\n"

            for i, item in enumerate(items[:10], 1):  # 最多显示10条
                report += f"""**{i}. {item.get("标题", "未知标题")}**

- **来源**: {item.get("来源", "")}
- **相关性**: {item.get("相关性", 0)}/5
- **内容摘要**: {item.get("内容", "")[:200]}{"..." if len(item.get("content", "")) > 200 else ""}

---

"""

        # 深度分析
        if "深度分析" in research_data:
            deep_analysis = research_data["深度分析"]
            report += "\n## 深度分析\n\n"

            report += "### 信息覆盖度\n\n"
            for category, count in deep_analysis.get("信息覆盖度", {}).items():
                report += f"- {category}: {count}条信息\n"

            if deep_analysis.get("关键发现"):
                report += "\n### 关键发现\n\n"
                for finding in deep_analysis["关键发现"][:5]:
                    report += f"- **{finding['类别']}**: {finding['标题']}\n"

            if deep_analysis.get("信息缺口"):
                report += "\n### 信息缺口\n\n"
                for gap in deep_analysis["信息缺口"]:
                    report += f"- {gap}\n"

        # 保存报告
        try:
            from pathlib import Path
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)

            logger.info(f"调研报告已保存: {output_path}")
            return True

        except Exception as e:
            logger.error(f"生成调研报告失败: {e}")
            return False


async def research_command(
    topic: str,
    research_type: str = "general",
    options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    调研命令统一接口

    Args:
        topic: 调研主题
        research_type: 调研类型 (general, industry, competitor, product)
        options:
            {
                "depth": 2,
                "generate_report": True,
                "output_path": "./research_report.md"
            }

    Returns:
        调研结果
    """
    if options is None:
        options = {}

    researcher = WebResearcher()

    # 执行调研
    if research_type == "competitor":
        results = await researcher.research_competitors(topic)
    else:
        results = await researcher.research_topic(
            topic,
            research_type,
            options.get("depth", 2)
        )

    # 生成报告
    if options.get("generate_report", False):
        output_path = options.get("output_path", f"./{topic}_调研报告.md")
        researcher.generate_research_report(results, output_path)
        results["报告路径"] = output_path

    return results
