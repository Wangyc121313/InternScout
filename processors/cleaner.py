"""
数据清洗模块 - 清理和标准化爬取的数据
"""
from typing import Any, Dict, List, Optional
import re

from utils.logger import get_logger

logger = get_logger(__name__)


class DataCleaner:
    """数据清洗器"""

    def __init__(
        self,
        required_fields: List[str] = None,
        string_fields: List[str] = None,
        remove_html: bool = True,
        dedupe_fields: List[str] = None,
    ):
        self.required_fields = required_fields or []
        self.string_fields = string_fields or []
        self.remove_html = remove_html
        self.dedupe_fields = dedupe_fields or []

    def clean(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        清洗单个数据项

        Args:
            item: 原始数据

        Returns:
            清洗后的数据，None表示数据无效
        """
        # 检查必填字段
        for field in self.required_fields:
            if not item.get(field):
                logger.debug(f"Missing required field: {field}")
                return None

        # 清洗字符串字段
        for field in self.string_fields:
            if field in item and item[field]:
                item[field] = self._clean_string(item[field])

        # 移除HTML标签
        if self.remove_html:
            for key, value in item.items():
                if isinstance(value, str):
                    item[key] = self._remove_html_tags(value)

        return item

    def clean_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量清洗"""
        results = []
        for item in items:
            cleaned = self.clean(item)
            if cleaned:
                results.append(cleaned)
        return results

    def _clean_string(self, text: str) -> str:
        """清理字符串"""
        if not text:
            return ""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除首尾空白
        text = text.strip()
        return text

    def _remove_html_tags(self, text: str) -> str:
        """移除HTML标签"""
        if not text:
            return ""
        # 简单的HTML标签移除
        text = re.sub(r'<[^>]+>', '', text)
        # 解码HTML实体
        import html
        text = html.unescape(text)
        return text

    def deduplicate(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """根据指定字段去重"""
        if not self.dedupe_fields:
            return items

        seen = set()
        results = []

        for item in items:
            key_parts = [str(item.get(f, '')) for f in self.dedupe_fields]
            key = '|'.join(key_parts)

            if key not in seen:
                seen.add(key)
                results.append(item)

        logger.info(f"Deduplicated: {len(items)} -> {len(results)}")
        return results
