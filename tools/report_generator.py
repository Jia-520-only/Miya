"""
调研报告生成器 - 弥娅核心模块
支持结构化报告、PPT大纲与内容生成
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ReportGenerator:
    """调研报告生成器"""

    def __init__(self):
        self.report_templates = {
            "research": "调研报告模板",
            "ppt_outline": "PPT大纲模板",
            "executive_summary": "执行摘要模板"
        }

    def generate_research_report(
        self,
        research_data: Dict[str, Any],
        report_config: Dict[str, Any] = None
    ) -> str:
        """
        生成结构化调研报告

        Args:
            research_data: 调研数据（来自WebResearcher）
            report_config:
                {
                    "title": "报告标题",
                    "author": "作者",
                    "include_appendices": True
                }

        Returns:
            Markdown格式报告
        """
        if report_config is None:
            report_config = {}

        title = report_config.get("title", research_data.get("主题", "调研报告"))
        author = report_config.get("author", "弥娅")

        # 报告头部
        report = f"""# {title}

**生成时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}  
**作者**: {author}

---

## 执行摘要

本报告针对{research_data.get("主题", "目标主题")}进行了系统性的调研分析。

**主要发现**:
- 共收集到 {research_data.get("信息来源数", 0)} 个信息来源
- 覆盖了 {len(research_data.get("调研内容", {}))} 个维度的信息
- 通过深度分析识别了关键趋势和挑战

**建议行动**:
- 基于调研结果，建议进一步关注核心发现
- 结合实际业务需求制定行动计划

---

## 目录

1. [调研背景](#调研背景)
2. [调研方法](#调研方法)
3. [核心发现](#核心发现)
4. [详细分析](#详细分析)
5. [结论与建议](#结论与建议)
"""

        # 调研背景
        report += self._generate_background_section(research_data)

        # 调研方法
        report += self._generate_methodology_section(research_data)

        # 核心发现
        report += self._generate_key_findings_section(research_data)

        # 详细分析
        report += self._generate_detailed_analysis_section(research_data)

        # 结论与建议
        report += self._generate_conclusions_section(research_data)

        # 附录
        if report_config.get("include_appendices", True):
            report += self._generate_appendices(research_data)

        return report

    def _generate_background_section(self, research_data: Dict[str, Any]) -> str:
        """生成背景部分"""
        return f"""
## 调研背景

本次调研主要关注以下维度:

{chr(10).join(f"- {category}: {len(research_data.get('调研内容', {}).get(category, []))}条信息" 
                for category in research_data.get('调研内容', {}).keys())}

---

"""

    def _generate_methodology_section(self, research_data: Dict[str, Any]) -> str:
        """生成方法论部分"""
        queries = research_data.get("搜索查询", [])
        depth = research_data.get("深度分析", {})

        return f"""
## 调研方法

### 搜索策略

采用了多维度搜索策略，共执行 {len(queries)} 个搜索查询:

{chr(10).join(f"{i+1}. {q}" for i, q in enumerate(queries[:5]))}

### 信息筛选标准

- 信息来源的权威性（.gov, .edu优先）
- 内容的相关性和时效性
- 数据的可验证性

### 分析深度

{f"- 基础搜索" if not depth else "- 深度分析（{len(depth.get('关键发现', []))}个关键发现）"}

---

"""

    def _generate_key_findings_section(self, research_data: Dict[str, Any]) -> str:
        """生成核心发现部分"""
        section = "## 核心发现\n\n"

        # 从深度分析中提取关键发现
        deep_analysis = research_data.get("深度分析", {})
        key_findings = deep_analysis.get("关键发现", [])

        if key_findings:
            section += "### 主要发现\n\n"
            for finding in key_findings[:8]:
                section += f"""**{finding.get('类别', '未知')}** ({finding.get('重要性', '中')}重要性)

- 来源: {finding.get('来源', '')}
- 关键信息: {finding.get('标题', '')}

---

"""
        else:
            section += "### 关键信息\n\n"

        # 按类别汇总
        content = research_data.get("调研内容", {})
        for category, items in content.items():
            if items:
                section += f"""**{category}**

{chr(10).join(f"- {item.get('标题', item.get('内容', ''))[:100]}" 
                        for item in items[:3])}

---

"""

        return section

    def _generate_detailed_analysis_section(self, research_data: Dict[str, Any]) -> str:
        """生成详细分析部分"""
        section = "## 详细分析\n\n"

        # 信息覆盖度分析
        coverage = research_data.get("深度分析", {}).get("信息覆盖度", {})
        if coverage:
            section += "### 信息覆盖度\n\n"
            section += "| 维度 | 信息量 |\n"
            section += "|------|--------|\n"
            for category, count in coverage.items():
                coverage_level = "充足" if count >= 5 else "一般" if count >= 3 else "不足"
                section += f"| {category} | {count} ({coverage_level}) |\n"
            section += "\n"

        # 信息缺口分析
        gaps = research_data.get("深度分析", {}).get("信息缺口", [])
        if gaps:
            section += "### 信息缺口\n\n"
            for gap in gaps:
                section += f"- {gap}\n"
            section += "\n"

        return section

    def _generate_conclusions_section(self, research_data: Dict[str, Any]) -> str:
        """生成结论与建议部分"""
        return f"""
## 结论与建议

### 主要结论

1. **信息收集情况**: 成功收集了 {research_data.get('信息来源数', 0)} 个信息来源的数据
2. **分析维度**: 覆盖了 {len(research_data.get('调研内容', {}))} 个主要维度
3. **数据质量**: 整体信息质量{["有待提高", "一般", "良好"][1 if research_data.get('信息来源数', 0) > 10 else 0]}

### 行动建议

#### 短期行动（1-2周）
- [ ] 整理和验证收集到的信息
- [ ] 根据核心发现制定初步行动计划
- [ ] 与相关方沟通和确认关键发现

#### 中期行动（1-3个月）
- [ ] 深化分析关键发现
- [ ] 跟踪相关领域的发展趋势
- [ ] 制定详细的实施方案

#### 长期行动（3-6个月）
- [ ] 建立持续的信息收集机制
- [ ] 建立定期复盘和更新机制
- [ ] 基于执行效果调整策略

---

## 附录

### 信息来源清单

| # | 来源 | 可靠性 |
|---|--------|--------|
{chr(10).join(f"| {i+1} | {source[:50]} | {'高' if '.gov' in source or '.edu' in source else '中'} |" 
                for i, source in enumerate(research_data.get('信息来源', [])[:20]))}

---

*报告结束*
"""

    def _generate_appendices(self, research_data: Dict[str, Any]) -> str:
        """生成附录部分"""
        return f"""
## 附录

### A. 搜索查询完整列表

{chr(10).join(f"{i+1}. {q}" for i, q in enumerate(research_data.get('搜索查询', [])))}

### B. 原始数据快照

```json
{json.dumps({k: v for k, v in research_data.items() if k != '深度分析'}, 
            ensure_ascii=False, indent=2)[:5000]}...
```

---

"""

    def generate_ppt_outline(
        self,
        research_data: Dict[str, Any],
        config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        生成PPT大纲

        Args:
            research_data: 调研数据
            config: 配置参数

        Returns:
            PPT大纲结构
        """
        if config is None:
            config = {}

        theme = config.get("theme", research_data.get("主题", "演示主题"))
        slide_count = config.get("slide_count", 15)

        outline = {
            "主题": theme,
            "总页数": slide_count,
            "幻灯片": []
        }

        # 第1页：封面
        outline["幻灯片"].append({
            "页码": 1,
            "类型": "封面",
            "标题": theme,
            "副标题": "调研报告",
            "生成日期": datetime.now().strftime('%Y年%m月%d日')
        })

        # 第2页：目录
        outline["幻灯片"].append({
            "页码": 2,
            "类型": "目录",
            "内容": ["调研背景", "核心发现", "详细分析", "结论建议"]
        })

        # 第3页：调研背景
        outline["幻灯片"].append({
            "页码": 3,
            "类型": "内容页",
            "标题": "调研背景",
            "要点": [
                f"调研主题: {research_data.get('主题', '')}",
                f"信息来源数: {research_data.get('信息来源数', 0)}",
                "研究方法: 多维度搜索+深度分析"
            ]
        })

        # 第4页：核心发现
        content = research_data.get("调研内容", {})
        key_findings = []
        for category, items in content.items():
            if items:
                key_findings.append(f"{category}: {items[0].get('标题', '')}" if items else f"{category}")

        outline["幻灯片"].append({
            "页码": 4,
            "类型": "内容页",
            "标题": "核心发现",
            "要点": key_findings[:6]
        })

        # 第5-8页：详细分析
        for i, (category, items) in enumerate(list(content.items())[:4], start=5):
            if items:
                outline["幻灯片"].append({
                    "页码": i,
                    "类型": "内容页",
                    "标题": category,
                    "要点": [item.get("标题", item.get("content", ""))[:80] for item in items[:4]]
                })

        # 第9-12页：数据图表（预留）
        for i in range(9, 13):
            outline["幻灯片"].append({
                "页码": i,
                "类型": "数据页",
                "标题": f"数据展示 {i-8}",
                "说明": "建议根据实际数据生成图表"
            })

        # 第13-14页：行动建议
        outline["幻灯片"].append({
            "页码": 13,
            "类型": "内容页",
            "标题": "行动建议",
            "要点": [
                "短期行动：信息验证和初步规划",
                "中期行动：深化分析和方案制定",
                "长期行动：机制建立和持续优化"
            ]
        })

        # 第15页：致谢/结束页
        outline["幻灯片"].append({
            "页码": 15,
            "类型": "结束页",
            "标题": "谢谢",
            "副标题": "感谢您的聆听"
        })

        return outline

    def export_ppt_content(
        self,
        outline: Dict[str, Any],
        output_format: str = "markdown"
    ) -> str:
        """
        导出PPT内容

        Args:
            outline: PPT大纲
            output_format: 输出格式 (markdown, json, pptx_notes)

        Returns:
            格式化内容
        """
        if output_format == "markdown":
            return self._outline_to_markdown(outline)
        elif output_format == "json":
            return json.dumps(outline, ensure_ascii=False, indent=2)
        elif output_format == "pptx_notes":
            return self._outline_to_ppt_notes(outline)
        else:
            return outline

    def _outline_to_markdown(self, outline: Dict[str, Any]) -> str:
        """将大纲转换为Markdown"""
        md = f"""# PPT大纲: {outline.get('主题', '')}

**总页数**: {outline.get('总页数', 0)}

---

"""
        for slide in outline.get("幻灯片", []):
            md += f"""## 第 {slide['页码']} 页 - {slide.get('类型', '')}

**标题**: {slide.get('标题', '')}

"""
            if slide.get("类型") == "封面":
                md += f"""
**副标题**: {slide.get('副标题', '')}
**日期**: {slide.get('生成日期', '')}

---

"""
            elif slide.get("类型") == "内容页":
                points = slide.get("要点", [])
                md += f"""
**要点**:

{chr(10).join(f"- {point}" for point in points)}

---

"""
            elif slide.get("类型") == "数据页":
                md += f"""

**说明**: {slide.get('说明', '')}

---

"""

        return md

    def _outline_to_ppt_notes(self, outline: Dict[str, Any]) -> str:
        """将大纲转换为PPT备注"""
        notes = ""
        for slide in outline.get("幻灯片", []):
            notes += f"""
=== Slide {slide['页码']} ===

Title: {slide.get('标题', '')}

Speaker Notes:
"""
            if slide.get("类型") == "内容页":
                points = slide.get("要点", [])
                for i, point in enumerate(points, 1):
                    notes += f"{i}. {point}\n"
            elif slide.get("类型") == "封面":
                notes += f"- 欢迎大家\n- 主题: {outline.get('主题', '')}\n"

            notes += "\n"

        return notes


def generate_report_command(
    research_data: Dict[str, Any],
    output_type: str = "report",
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    报告生成命令统一接口

    Args:
        research_data: 调研数据
        output_type: 输出类型 (report, ppt_outline, ppt_notes)
        config: 配置参数

    Returns:
        生成结果
    """
    generator = ReportGenerator()

    if output_type == "report":
        content = generator.generate_research_report(research_data, config)
        extension = ".md"
    elif output_type == "ppt_outline":
        outline = generator.generate_ppt_outline(research_data, config)
        content = generator.export_ppt_content(outline, "markdown")
        extension = "_大纲.md"
    elif output_type == "ppt_notes":
        outline = generator.generate_ppt_outline(research_data, config)
        content = generator.export_ppt_content(outline, "pptx_notes")
        extension = "_备注.txt"
    else:
        return {"error": f"不支持的输出类型: {output_type}"}

    # 保存文件
    output_path = config.get("output_path", f"./报告{extension}") if config else f"./报告{extension}"

    try:
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"报告已生成: {output_path}")

        return {
            "success": True,
            "输出路径": output_path,
            "输出类型": output_type,
            "内容长度": len(content)
        }

    except Exception as e:
        logger.error(f"保存报告失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }
