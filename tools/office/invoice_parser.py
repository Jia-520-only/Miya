"""
票据提取工具 - 弥娅核心模块
支持发票信息提取与报销表格生成
"""

import re
import pandas as pd
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class InvoiceParser:
    """发票解析器"""

    def __init__(self):
        # 发票关键词模式
        self.patterns = {
            "发票代码": r'(?:发票代码|Invoice\s*Code)[:：:\s]*([A-Z0-9]+)',
            "发票号码": r'(?:发票号码|No\.|Number)[:：:\s]*([0-9]+)',
            "开票日期": r'(?:开票日期|Date|日期)[:：:\s]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)',
            "价税合计": r'(?:价税合计|合计金额|Total)[:：:\s]*¥?([0-9,]+\.[0-9]{2})',
            "税额": r'(?:税额|Tax)[:：:\s]*¥?([0-9,]+\.[0-9]{2})',
            "购买方": r'(?:购买方|Buyer|买方)[:：:\s]*(.{2,30}?)(?:\n|销售方)',
            "销售方": r'(?:销售方|Seller|卖方)[:：:\s]*(.{2,30}?)(?:\n|开票日期)',
            "金额": r'(?:金额|Amount)[:：:\s]*¥?([0-9,]+\.[0-9]{2})',
        }

    def parse_invoice_from_text(self, text: str) -> Dict[str, Any]:
        """
        从文本中解析发票信息

        Args:
            text: 发票文本内容

        Returns:
            解析的发票信息字典
        """
        invoice_data = {
            "解析状态": "失败",
            "提取字段": {},
            "置信度": 0
        }

        # 提取各字段
        extracted_fields = {}
        matched_fields = 0
        total_fields = len(self.patterns)

        for field_name, pattern in self.patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                extracted_fields[field_name] = match.group(1).strip()
                matched_fields += 1

        # 计算置信度
        confidence = matched_fields / total_fields

        if confidence > 0.5:
            invoice_data["解析状态"] = "成功"
            invoice_data["置信度"] = confidence

            # 标准化日期格式
            if "开票日期" in extracted_fields:
                date_str = extracted_fields["开票日期"]
                try:
                    # 尝试多种日期格式
                    date_formats = ['%Y-%m-%d', '%Y年%m月%d日', '%Y/%m/%d']
                    for fmt in date_formats:
                        try:
                            extracted_fields["开票日期_标准化"] = datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
                            break
                        except:
                            pass
                except:
                    pass

            # 提取金额（数值）
            if "金额" in extracted_fields:
                try:
                    extracted_fields["金额_数值"] = float(extracted_fields["金额"].replace(',', '').replace('¥', ''))
                except:
                    pass

            invoice_data["提取字段"] = extracted_fields
            logger.info(f"成功解析发票，置信度: {confidence:.2f}")
        else:
            logger.warning(f"发票解析置信度较低: {confidence:.2f}")

        return invoice_data

    def parse_invoice_from_file(self, file_path: str) -> Dict[str, Any]:
        """
        从文件解析发票

        Args:
            file_path: 发票文件路径（支持PDF、图片、文本）

        Returns:
            解析结果
        """
        path = Path(file_path)

        if not path.exists():
            return {"error": "文件不存在"}

        try:
            # PDF文件
            if path.suffix.lower() == '.pdf':
                text = self._extract_text_from_pdf(file_path)
                return self.parse_invoice_from_text(text)

            # 图片文件（需要OCR）
            elif path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
                return {
                    "error": "图片文件需要OCR支持，请先转换为文本",
                    "建议": "使用其他工具识别图片中的文字后再解析"
                }

            # 文本文件
            elif path.suffix.lower() == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                return self.parse_invoice_from_text(text)

            else:
                return {"error": f"不支持的文件格式: {path.suffix}"}

        except Exception as e:
            logger.error(f"解析发票文件失败: {e}")
            return {"error": str(e)}

    def _extract_text_from_pdf(self, file_path: str) -> str:
        """从PDF提取文本"""
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except ImportError:
            logger.error("PyPDF2未安装")
            return ""
        except Exception as e:
            logger.error(f"PDF提取失败: {e}")
            return ""

    def create_expense_table(
        self,
        invoices: List[Dict[str, Any]],
        output_path: str
    ) -> bool:
        """
        创建报销表格

        Args:
            invoices: 发票数据列表
            output_path: 输出Excel路径

        Returns:
            是否成功
        """
        if not invoices:
            logger.warning("没有发票数据")
            return False

        # 标准化发票数据
        expense_data = []
        total_amount = 0

        for i, invoice in enumerate(invoices, 1):
            fields = invoice.get("提取字段", {})

            expense_data.append({
                "序号": i,
                "发票代码": fields.get("发票代码", ''),
                "发票号码": fields.get("发票号码", ''),
                "开票日期": fields.get("开票日期_标准化", fields.get("开票日期", '')),
                "销售方": fields.get("销售方", ''),
                "购买方": fields.get("购买方", ''),
                "价税合计": fields.get("价税合计", ''),
                "金额(元)": fields.get("金额_数值", 0),
                "税额": fields.get("税额", ''),
                "置信度": f"{invoice.get('置信度', 0):.1%}"
            })

            if "金额_数值" in fields:
                total_amount += fields["金额_数值"]

        # 创建DataFrame
        df = pd.DataFrame(expense_data)

        # 添加汇总行
        summary_row = {
            "序号": "合计",
            "发票代码": f"共 {len(invoices)} 张",
            "发票号码": '',
            "开票日期": '',
            "销售方": '',
            "购买方": '',
            "价税合计": f"¥{total_amount:,.2f}",
            "金额(元)": f"¥{total_amount:,.2f}",
            "税额": '',
            "置信度": ''
        }
        df = pd.concat([df, pd.DataFrame([summary_row])], ignore_index=True)

        # 保存到Excel
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            df.to_excel(output_path, index=False, engine='openpyxl')

            logger.info(f"报销表格已保存: {output_path}")
            logger.info(f"总金额: ¥{total_amount:,.2f}")

            return True
        except Exception as e:
            logger.error(f"保存报销表格失败: {e}")
            return False

    def batch_parse_invoices(
        self,
        directory: str,
        patterns: List[str] = None
    ) -> Dict[str, Any]:
        """
        批量解析目录中的发票

        Args:
            directory: 目录路径
            patterns: 文件匹配模式 (如 ['*.pdf', '*.jpg'])

        Returns:
            批量解析结果
        """
        dir_path = Path(directory)

        if not dir_path.exists():
            return {"error": "目录不存在"}

        if patterns is None:
            patterns = ['*.pdf', '*.jpg', '*.jpeg', '*.png', '*.txt']

        # 查找文件
        all_files = []
        for pattern in patterns:
            all_files.extend(dir_path.glob(pattern))

        # 解析每个文件
        results = {
            "总文件数": len(all_files),
            "成功解析": 0,
            "失败解析": 0,
            "发票列表": []
        }

        for file_path in all_files:
            result = self.parse_invoice_from_file(str(file_path))

            if "error" not in result:
                results["发票列表"].append({
                    "文件": file_path.name,
                    **result
                })
                results["成功解析"] += 1
            else:
                results["发票列表"].append({
                    "文件": file_path.name,
                    "错误": result.get("error", "未知错误")
                })
                results["失败解析"] += 1

        logger.info(f"批量解析完成: {results['成功解析']}/{results['总文件数']} 成功")

        return results

    def generate_report(
        self,
        invoices: List[Dict[str, Any]],
        report_path: str
    ) -> bool:
        """
        生成报销报告

        Args:
            invoices: 发票数据列表
            report_path: 报告输出路径

        Returns:
            是否成功
        """
        # 统计汇总
        total_amount = 0
        high_confidence = 0
        low_confidence = 0

        for invoice in invoices:
            fields = invoice.get("提取字段", {})
            if "金额_数值" in fields:
                total_amount += fields["金额_数值"]

            confidence = invoice.get("置信度", 0)
            if confidence > 0.8:
                high_confidence += 1
            elif confidence < 0.5:
                low_confidence += 1

        # 生成报告
        report = f"""
# 报销统计报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 统计摘要

| 项目 | 数值 |
|------|------|
| 发票总数 | {len(invoices)} |
| 总金额 | ¥{total_amount:,.2f} |
| 平均金额 | ¥{total_amount/len(invoices):,.2f} |
| 高置信度(>80%) | {high_confidence} |
| 低置信度(<50%) | {low_confidence} |

## 📋 详细信息

"""

        for i, invoice in enumerate(invoices, 1):
            fields = invoice.get("提取字段", {})
            report += f"""
### 发票 {i}
- **文件**: {invoice.get('文件', '未知')}
- **解析状态**: {invoice.get('解析状态', '未知')}
- **置信度**: {invoice.get('置信度', 0):.1%}

**关键信息**:
- 发票代码: {fields.get('发票代码', '未提取')}
- 发票号码: {fields.get('发票号码', '未提取')}
- 开票日期: {fields.get('开票日期_标准化', fields.get('开票日期', '未提取'))}
- 销售方: {fields.get('销售方', '未提取')}
- 购买方: {fields.get('购买方', '未提取')}
- 金额: ¥{fields.get('金额_数值', 0):,.2f}

---

"""

        # 保存报告
        try:
            Path(report_path).parent.mkdir(parents=True, exist_ok=True)

            # 根据扩展名保存
            ext = Path(report_path).suffix
            if ext == '.md':
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report)
            else:
                # 默认保存为markdown
                md_path = str(Path(report_path).with_suffix('.md'))
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(report)
                logger.info(f"报告已保存为Markdown: {md_path}")

            logger.info(f"报销报告已生成: {report_path}")
            return True

        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return False


def process_invoice_command(
    files: List[str],
    operations: List[str],
    output_path: str = "./expense_report.xlsx"
) -> Dict[str, Any]:
    """
    执行发票处理命令

    Args:
        files: 文件列表
        operations: 操作列表 ["parse", "batch", "create_table", "generate_report"]
        output_path: 输出路径

    Returns:
        处理结果
    """
    parser = InvoiceParser()
    results = {
        "成功": True,
        "处理文件数": 0,
        "发票数据": [],
        "输出文件": []
    }

    for file_path in files:
        if "parse" in operations:
            result = parser.parse_invoice_from_file(file_path)
            if "error" not in result:
                result["文件"] = Path(file_path).name
                results["发票数据"].append(result)
                results["处理文件数"] += 1
            else:
                results["成功"] = False
                results["错误"] = result.get("error")

    if "create_table" in operations and results["发票数据"]:
        table_path = output_path.replace('.xlsx', '_table.xlsx')
        if parser.create_expense_table(results["发票数据"], table_path):
            results["输出文件"].append(table_path)

    if "generate_report" in operations and results["发票数据"]:
        report_path = output_path.replace('.xlsx', '_report.md')
        if parser.generate_report(results["发票数据"], report_path):
            results["输出文件"].append(report_path)

    return results
