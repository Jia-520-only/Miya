"""
弥娅 - 中文时域表达式解析器
从VCPToolBox浪潮RAG V3整合
支持解析"前几天"、"前年冬天"、"上周"等模糊时间表达式
"""

import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TimeRange:
    """时间范围"""
    start: datetime
    end: datetime

    def __str__(self):
        return f"[{self.start.isoformat()} ~ {self.end.isoformat()}]"


class ChineseTimeExpressionParser:
    """中文时域表达式解析器"""

    # 中文数字映射
    CHINESE_NUMBERS = {
        '零': 0, '〇': 0,
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10,
        '日': 7, '天': 7  # 星期日/星期天
    }

    def __init__(self, timezone_str: str = 'Asia/Shanghai'):
        """
        初始化解析器

        Args:
            timezone_str: 时区字符串，默认为东八区
        """
        self.timezone = timezone_str
        # 硬编码表达式
        self.hardcoded_patterns = {
            '昨天': {'days': 1},
            '前天': {'days': 2},
            '大前天': {'days': 3},
            '今天': {'days': 0},
            '刚才': {'days': 0},
            '刚刚': {'days': 0},
            '昨天下午': {'days': 1},  # 简化处理
            '今天下午': {'days': 0},
            '昨天晚上': {'days': 1},
            '今天晚上': {'days': 0},

            # 相对日期
            '去年': {'months': 12, 'type': 'lastMonth'},
            '前年': {'months': 24, 'type': 'lastMonth'},

            # 季节性（简化为月份范围）
            '去年冬天': {'type': 'lastSeason', 'season': 'winter'},
            '去年秋天': {'type': 'lastSeason', 'season': 'autumn'},
            '去年夏天': {'type': 'lastSeason', 'season': 'summer'},
            '去年春天': {'type': 'lastSeason', 'season': 'spring'},

            # 相对时间段
            '上周': {'type': 'lastWeek'},
            '上个月': {'type': 'lastMonth'},
            '本月': {'type': 'thisMonth'},
            '这个月': {'type': 'thisMonth'},
            '本周': {'type': 'thisWeek'},
            '这周': {'type': 'thisWeek'},
        }

        # 动态模式（正则表达式）
        self.dynamic_patterns = [
            # N天前
            ('几天前', r'(\d+)天前', 'daysAgo'),
            # N周前
            ('N周前', r'(\d+)周前', 'weeksAgo'),
            # N个月前
            ('N个月前', r'(\d+)个月前', 'monthsAgo'),
            # 上周X
            ('上周X', r'上周([一二三四五六日天])', 'lastWeekday'),
        ]

    def _get_current_time(self) -> datetime:
        """获取当前时间（考虑时区）"""
        import pytz
        tz = pytz.timezone(self.timezone)
        return datetime.now(tz)

    def _get_day_boundaries(self, date: datetime) -> TimeRange:
        """获取一天的开始和结束"""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        return TimeRange(start=start, end=end)

    def _get_week_boundaries(self, date: datetime, offset: int = 0) -> TimeRange:
        """
        获取一周的开始和结束（周一到周日）
        offset: 0=本周, -1=上周
        """
        # 调整到目标周
        target_date = date + timedelta(weeks=offset)

        # 找到周一
        weekday = target_date.weekday()  # 0=周一, 6=周日
        monday = target_date - timedelta(days=weekday)
        sunday = monday + timedelta(days=6)

        start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = sunday.replace(hour=23, minute=59, second=59, microsecond=999999)

        return TimeRange(start=start, end=end)

    def _get_month_boundaries(self, date: datetime, offset: int = 0) -> TimeRange:
        """
        获取一个月的开始和结束
        offset: 0=本月, -1=上月
        """
        target_date = date + timedelta(days=offset * 30)

        # 第一天
        start = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # 最后一天
        if target_date.month == 12:
            next_month = target_date.replace(year=target_date.year + 1, month=1, day=1)
        else:
            next_month = target_date.replace(month=target_date.month + 1, day=1)

        end = next_month - timedelta(seconds=1)

        return TimeRange(start=start, end=end)

    def _get_season_boundaries(self, season: str, year_offset: int = 0) -> Optional[TimeRange]:
        """获取季节范围"""
        current_year = self._get_current_time().year + year_offset

        # 季节月份范围
        seasons = {
            'spring': (3, 5),   # 3-5月
            'summer': (6, 8),   # 6-8月
            'autumn': (9, 11),  # 9-11月
            'winter': (12, 2)   # 12-2月
        }

        if season not in seasons:
            return None

        start_month, end_month = seasons[season]

        # 冬季跨年处理
        if season == 'winter':
            start = datetime(current_year - 1, 12, 1, 0, 0, 0)
            end = datetime(current_year, 2, 28, 23, 59, 59)
        else:
            start = datetime(current_year, start_month, 1, 0, 0, 0)
            # 计算月底
            if end_month in [4, 6, 9, 11]:
                last_day = 30
            elif end_month == 2:
                # 简化处理，不判断闰年
                last_day = 28
            else:
                last_day = 31

            end = datetime(current_year, end_month, last_day, 23, 59, 59)

        return TimeRange(start=start, end=end)

    def _chinese_to_number(self, text: str) -> Optional[int]:
        """中文数字转阿拉伯数字"""
        if text in self.CHINESE_NUMBERS:
            return self.CHINESE_NUMBERS[text]

        if text == '十':
            return 10

        # 处理"十一"到"九十九"
        if '十' in text:
            parts = text.split('十')
            if len(parts) == 2:
                tens_part = parts[0] if parts[0] else ''
                ones_part = parts[1] if parts[1] else '0'

                if not tens_part:
                    total = 10
                else:
                    tens = self.CHINESE_NUMBERS.get(tens_part, 1)
                    total = tens * 10

                if ones_part:
                    ones = self.CHINESE_NUMBERS.get(ones_part, 0)
                    total += ones

                return total

        # 尝试直接解析为数字
        try:
            return int(text)
        except ValueError:
            return None

    def parse(self, text: str) -> List[TimeRange]:
        """
        解析文本中的时间表达式

        Args:
            text: 待解析文本

        Returns:
            List[TimeRange]: 匹配到的所有时间范围
        """
        logger.debug(f"[TimeParser] 解析文本: {text[:100]}...")

        results = []
        now = self._get_current_time()

        # 1. 检查硬编码表达式（从长到短排序）
        sorted_patterns = sorted(self.hardcoded_patterns.keys(), key=len, reverse=True)

        for pattern in sorted_patterns:
            if pattern in text:
                config = self.hardcoded_patterns[pattern]
                logger.debug(f"[TimeParser] 匹配硬编码表达式: '{pattern}'")

                result = None
                if 'days' in config:
                    target_date = now - timedelta(days=config['days'])
                    result = self._get_day_boundaries(target_date)
                elif config['type'] == 'lastWeek':
                    result = self._get_week_boundaries(now, offset=-1)
                elif config['type'] == 'thisWeek':
                    result = self._get_week_boundaries(now, offset=0)
                elif config['type'] == 'lastMonth':
                    result = self._get_month_boundaries(now, offset=-1)
                elif config['type'] == 'thisMonth':
                    result = self._get_month_boundaries(now, offset=0)
                elif config['type'] == 'lastSeason':
                    season = config['season']
                    result = self._get_season_boundaries(season, year_offset=-1)

                if result:
                    results.append(result)

        # 2. 检查动态模式
        for name, pattern, type_name in self.dynamic_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                logger.debug(f"[TimeParser] 匹配动态模式: '{name}' - '{match.group(0)}'")

                result = None
                if type_name == 'daysAgo':
                    num_str = match.group(1)
                    num = self._chinese_to_number(num_str)
                    if num:
                        target_date = now - timedelta(days=num)
                        result = self._get_day_boundaries(target_date)

                elif type_name == 'weeksAgo':
                    num_str = match.group(1)
                    num = self._chinese_to_number(num_str)
                    if num:
                        result = self._get_week_boundaries(now, offset=-num)

                elif type_name == 'monthsAgo':
                    num_str = match.group(1)
                    num = self._chinese_to_number(num_str)
                    if num:
                        result = self._get_month_boundaries(now, offset=-num)

                elif type_name == 'lastWeekday':
                    weekday_char = match.group(1)
                    weekday_map = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}

                    if weekday_char in weekday_map:
                        target_weekday = weekday_map[weekday_char]
                        current_weekday = now.weekday()

                        # 找到上周的目标星期
                        days_diff = current_weekday - target_weekday
                        if days_diff <= 0:
                            days_diff += 7

                        target_date = now - timedelta(days=days_diff)
                        result = self._get_day_boundaries(target_date)

                if result:
                    results.append(result)

        # 3. 去重
        unique_results = []
        seen_keys = set()
        for r in results:
            key = f"{r.start.timestamp()}|{r.end.timestamp()}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_results.append(r)

        if unique_results:
            logger.info(f"[TimeParser] 找到 {len(unique_results)} 个时间范围")
            for i, r in enumerate(unique_results, 1):
                logger.info(f"  [{i}] {r}")
        else:
            logger.debug("[TimeParser] 未找到时间表达式")

        return unique_results


# 全局解析器实例（懒加载）
_parser_instance = None


def get_time_parser(timezone: str = 'Asia/Shanghai') -> ChineseTimeExpressionParser:
    """获取时域解析器单例"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = ChineseTimeExpressionParser(timezone)
    return _parser_instance


def parse_time_expressions(text: str, timezone: str = 'Asia/Shanghai') -> List[TimeRange]:
    """
    解析文本中的时间表达式（便捷函数）

    Args:
        text: 待解析文本
        timezone: 时区

    Returns:
        List[TimeRange]: 匹配到的所有时间范围
    """
    parser = get_time_parser(timezone)
    return parser.parse(text)


# 测试代码
if __name__ == '__main__':
    test_texts = [
        "前几天我去了公园",
        "去年冬天的那件事",
        "上周五的会议",
        "三天前的记录",
        "上个月的项目",
        "昨天下午的聊天"
    ]

    parser = ChineseTimeExpressionParser()
    for text in test_texts:
        print(f"\n文本: {text}")
        ranges = parser.parse(text)
        for r in ranges:
            print(f"  {r}")
