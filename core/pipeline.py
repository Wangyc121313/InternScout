"""
数据处理管道 - 数据清洗、去重、存储
"""
import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime

from storage.database import Database
from storage.repository import JobRepository, CompanyRepository, InterviewRepository
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseProcessor(ABC):
    """基础处理器"""

    @abstractmethod
    def process(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理单个数据项

        Args:
            item: 数据项

        Returns:
            处理后的数据项，None表示丢弃
        """
        pass


class DataCleaner(BaseProcessor):
    """数据清洗处理器"""

    def __init__(
        self,
        required_fields: List[str] = None,
        string_fields: List[str] = None,
        date_fields: List[str] = None,
    ):
        self.required_fields = required_fields or []
        self.string_fields = string_fields or []
        self.date_fields = date_fields or []

    def _clean_string(self, value: Any) -> str:
        """清理字符串"""
        if value is None:
            return ""
        return str(value).strip()

    def _clean_date(self, value: Any) -> Optional[datetime]:
        """清理日期"""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            from utils.helpers import parse_date
            return parse_date(value)
        return None

    def process(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """清洗数据"""
        # 检查必填字段
        for field in self.required_fields:
            if field not in item or not item[field]:
                logger.debug(f"Missing required field: {field}")
                return None

        # 清洗字符串字段
        for field in self.string_fields:
            if field in item:
                item[field] = self._clean_string(item[field])

        # 清洗日期字段
        for field in self.date_fields:
            if field in item:
                item[field] = self._clean_date(item[field])

        return item


class DeduplicationProcessor(BaseProcessor):
    """去重处理器"""

    def __init__(
        self,
        key_fields: List[str],
        use_redis: bool = False,
        redis_client=None,
        ttl: int = 86400 * 7,  # 7天
    ):
        self.key_fields = key_fields
        self.use_redis = use_redis
        self.redis = redis_client
        self.ttl = ttl
        self._local_cache: set = set()

    def _generate_key(self, item: Dict[str, Any]) -> str:
        """生成唯一键"""
        key_parts = []
        for field in self.key_fields:
            value = item.get(field, "")
            key_parts.append(str(value))
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def is_duplicate(self, item: Dict[str, Any]) -> bool:
        """检查是否重复"""
        key = self._generate_key(item)

        if self.use_redis and self.redis:
            return self.redis.exists(f"dedup:{key}")
        else:
            return key in self._local_cache

    def mark_seen(self, item: Dict[str, Any]):
        """标记为已见"""
        key = self._generate_key(item)

        if self.use_redis and self.redis:
            self.redis.setex(f"dedup:{key}", self.ttl, "1")
        else:
            self._local_cache.add(key)

    def process(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """去重处理"""
        if self.is_duplicate(item):
            logger.debug(f"Duplicate item detected: {item}")
            return None

        self.mark_seen(item)
        return item


class NLPProcessor(BaseProcessor):
    """
    NLP解析处理器

    从非结构化文本提取关键信息
    """

    def __init__(self, extract_tech_tags: bool = True, extract_location: bool = True):
        self.extract_tech_tags = extract_tech_tags
        self.extract_location = extract_location

    def _extract_tech_tags(self, text: str) -> List[str]:
        """提取技术标签"""
        from utils.helpers import extract_tech_tags
        return extract_tech_tags(text)

    def _extract_location(self, text: str) -> Optional[str]:
        """提取地点信息"""
        # 简单的地点提取
        import re

        cities = [
            "北京", "上海", "深圳", "广州", "杭州", "成都", "武汉",
            "西安", "南京", "苏州", "重庆", "天津", "长沙", "厦门"
        ]

        for city in cities:
            if city in text:
                return city

        # 匹配 "XX市" 格式
        match = re.search(r'([\u4e00-\u9fa5]{2,5}市)', text)
        if match:
            return match.group(1)

        return None

    def _extract_requirements(self, text: str) -> List[str]:
        """提取职位要求"""
        requirements = []

        # 学历要求
        edu_patterns = [
            r'(本科|硕士|博士|大专|中专)及以上?',
            r'([\u4e00-\u9fa5]+)学历',
        ]
        import re
        for pattern in edu_patterns:
            match = re.search(pattern, text)
            if match:
                requirements.append(f"学历: {match.group(1)}")
                break

        # 经验要求
        exp_patterns = [
            r'(\d+)年以上?工作经验',
            r'经验([\d]+)年',
        ]
        for pattern in exp_patterns:
            match = re.search(pattern, text)
            if match:
                requirements.append(f"经验: {match.group(1)}年以上")
                break

        return requirements

    def process(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """NLP处理"""
        # 合并文本字段进行分析
        text_to_analyze = " ".join([
            str(item.get("title", "")),
            str(item.get("description", "")),
            str(item.get("requirements", ""))
        ])

        if self.extract_tech_tags and not item.get("tags"):
            item["tags"] = self._extract_tech_tags(text_to_analyze)

        if self.extract_location and not item.get("location"):
            item["location"] = self._extract_location(text_to_analyze)

        # 提取职位要求（如果没有的话）
        if not item.get("parsed_requirements"):
            item["parsed_requirements"] = self._extract_requirements(text_to_analyze)

        return item


class DataPipeline:
    """
    数据处理管道

    串联多个处理器，实现数据清洗、去重、存储
    """

    def __init__(self, database: Database = None):
        self.database = database
        self.processors: List[BaseProcessor] = []
        self.exporters: List[Callable] = []
        self._stats = {
            "processed": 0,
            "dropped": 0,
            "errors": 0,
        }

    def add_processor(self, processor: BaseProcessor) -> "DataPipeline":
        """添加处理器"""
        self.processors.append(processor)
        return self

    def add_exporter(self, exporter: Callable) -> "DataPipeline":
        """添加导出器"""
        self.exporters.append(exporter)
        return self

    def process(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理单个数据项

        Args:
            item: 原始数据

        Returns:
            处理后的数据或None
        """
        try:
            for processor in self.processors:
                item = processor.process(item)
                if item is None:
                    self._stats["dropped"] += 1
                    return None

            self._stats["processed"] += 1
            return item

        except Exception as e:
            logger.error(f"Pipeline processing error: {e}")
            self._stats["errors"] += 1
            return None

    def process_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量处理

        Args:
            items: 原始数据列表

        Returns:
            处理后的数据列表
        """
        results = []
        for item in items:
            processed = self.process(item)
            if processed:
                results.append(processed)
        return results

    def export(self, item: Dict[str, Any]):
        """导出数据"""
        for exporter in self.exporters:
            try:
                exporter(item)
            except Exception as e:
                logger.error(f"Export error: {e}")

    def run(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        执行完整管道

        Args:
            items: 原始数据列表

        Returns:
            最终数据列表
        """
        results = self.process_batch(items)

        for item in results:
            self.export(item)

        logger.info(
            f"Pipeline completed: {self._stats['processed']} processed, "
            f"{self._stats['dropped']} dropped, {self._stats['errors']} errors"
        )

        return results

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self._stats.copy()


class DatabaseExporter:
    """数据库导出器"""

    def __init__(self, database: Database, item_type: str = "job"):
        self.database = database
        self.item_type = item_type

    def __call__(self, item: Dict[str, Any]):
        """导出到数据库"""
        with self.database.get_session() as session:
            if self.item_type == "job":
                repo = JobRepository(session)
                if not repo.exists(item.get("url"), item.get("source")):
                    repo.create(item)

            elif self.item_type == "company":
                repo = CompanyRepository(session)
                repo.get_or_create(item.get("name"), item)

            elif self.item_type == "interview":
                repo = InterviewRepository(session)
                if not repo.exists(item.get("url"), item.get("source")):
                    repo.create(item)


class JSONExporter:
    """JSON文件导出器"""

    def __init__(self, filepath: str, append: bool = False):
        self.filepath = filepath
        self.append = append
        self._first_write = not append

    def __call__(self, item: Dict[str, Any]):
        """导出到JSON文件"""
        import os

        mode = "a" if not self._first_write else "w"
        self._first_write = False

        with open(self.filepath, mode, encoding="utf-8") as f:
            if mode == "a":
                f.write("\n")
            json.dump(item, f, ensure_ascii=False, default=str)


class CSVExporter:
    """CSV文件导出器"""

    def __init__(self, filepath: str, fieldnames: List[str] = None):
        self.filepath = filepath
        self.fieldnames = fieldnames
        self._writer = None
        self._file = None

    def _ensure_writer(self, item: Dict[str, Any]):
        """确保writer已创建"""
        import csv

        if self._writer is None:
            fieldnames = self.fieldnames or list(item.keys())
            self._file = open(self.filepath, "w", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file, fieldnames=fieldnames)
            self._writer.writeheader()

    def __call__(self, item: Dict[str, Any]):
        """导出到CSV"""
        self._ensure_writer(item)
        self._writer.writerow(item)

    def close(self):
        """关闭文件"""
        if self._file:
            self._file.close()

    def __del__(self):
        self.close()
