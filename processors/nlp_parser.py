"""
NLP解析模块 - 从非结构化文本提取关键信息
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


class NLPParser:
    """NLP信息提取器"""

    # 技术栈关键词
    TECH_KEYWORDS = {
        'Python': ['python', 'django', 'flask', 'fastapi', 'pandas', 'numpy'],
        'Java': ['java', 'spring', 'springboot', 'mybatis', 'spring cloud'],
        'Go': ['golang', 'go语言', 'gin', 'beego'],
        'C++': ['c++', 'cpp', 'cplusplus'],
        'JavaScript': ['javascript', 'js', 'nodejs', 'node.js', 'vue', 'react'],
        'TypeScript': ['typescript', 'ts'],
        '前端': ['html', 'css', '前端', 'frontend', 'vue.js', 'react.js'],
        '后端': ['后端', 'backend', 'server', 'api'],
        '数据库': ['mysql', 'postgresql', 'mongodb', 'redis', 'sql'],
        'AI/ML': ['机器学习', '深度学习', 'tensorflow', 'pytorch', 'ai', '算法'],
        '大数据': ['hadoop', 'spark', 'flink', 'hive', '大数据'],
        'DevOps': ['docker', 'kubernetes', 'k8s', 'jenkins', 'ci/cd'],
    }

    # 城市列表
    CITIES = [
        "北京", "上海", "深圳", "广州", "杭州", "成都", "武汉",
        "西安", "南京", "苏州", "重庆", "天津", "长沙", "厦门",
        "青岛", "大连", "宁波", "无锡", "佛山", "东莞"
    ]

    # 学历要求
    EDU_LEVELS = ["博士", "硕士", "本科", "大专", "中专"]

    def __init__(self):
        pass

    def parse(self, text: str) -> Dict[str, Any]:
        """
        解析文本，提取关键信息

        Args:
            text: 输入文本

        Returns:
            提取的信息字典
        """
        return {
            'tech_tags': self.extract_tech_tags(text),
            'location': self.extract_location(text),
            'education': self.extract_education(text),
            'experience': self.extract_experience(text),
            'salary_range': self.extract_salary(text),
        }

    def extract_tech_tags(self, text: str) -> List[str]:
        """提取技术标签"""
        if not text:
            return []

        text_lower = text.lower()
        tags = []

        for tag, keywords in self.TECH_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    tags.append(tag)
                    break

        return tags

    def extract_location(self, text: str) -> Optional[str]:
        """提取工作地点"""
        if not text:
            return None

        # 直接匹配城市名
        for city in self.CITIES:
            if city in text:
                return city

        # 匹配 "XX市" 格式
        match = re.search(r'([\u4e00-\u9fa5]{2,5}市)', text)
        if match:
            return match.group(1)

        return None

    def extract_education(self, text: str) -> Optional[str]:
        """提取学历要求"""
        if not text:
            return None

        # 匹配学历要求
        for edu in self.EDU_LEVELS:
            patterns = [
                rf'{edu}及以上',
                rf'{edu}以上',
                rf'{edu}学历',
                rf'要求{edu}',
            ]
            for pattern in patterns:
                if re.search(pattern, text):
                    return edu

        return None

    def extract_experience(self, text: str) -> Optional[str]:
        """提取经验要求"""
        if not text:
            return None

        # 匹配经验要求
        patterns = [
            r'(\d+)年以上?工作经验?',
            r'经验([\d]+)年',
            r'(\d+)\+?年',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                years = match.group(1)
                return f"{years}年经验"

        # 检查应届生相关
        if re.search(r'应届|在校生|无经验', text):
            return "应届/无经验"

        return None

    def extract_salary(self, text: str) -> Optional[Tuple[float, float]]:
        """提取薪资范围"""
        if not text:
            return None

        # 匹配薪资范围
        patterns = [
            r'(\d+)\s*[-~至到]\s*(\d+)\s*[Kk千]',
            r'(\d+)\s*[-~至到]\s*(\d+)\s*万',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                min_val = float(match.group(1))
                max_val = float(match.group(2))

                # 统一转换为月薪
                if '万' in text:
                    min_val *= 10000
                    max_val *= 10000
                else:
                    min_val *= 1000
                    max_val *= 1000

                return (min_val, max_val)

        # 匹配单个数字
        single_match = re.search(r'(\d+)\s*[Kk千]', text)
        if single_match:
            val = float(single_match.group(1)) * 1000
            return (val, val)

        return None

    def extract_requirements(self, text: str) -> List[str]:
        """提取职位要求列表"""
        requirements = []

        # 按常见分隔符分割
        delimiters = ['；', ';', '。', '\n', '•', '·', '-']

        parts = [text]
        for delimiter in delimiters:
            new_parts = []
            for part in parts:
                new_parts.extend([p.strip() for p in part.split(delimiter) if p.strip()])
            parts = new_parts

        # 过滤出符合要求格式的内容
        for part in parts:
            # 长度适中
            if 5 < len(part) < 100:
                requirements.append(part)

        return requirements[:10]  # 最多返回10条

    def classify_job_type(self, text: str) -> str:
        """分类职位类型"""
        text_lower = text.lower()

        if '实习' in text or 'intern' in text_lower:
            return '实习'
        elif '校招' in text or '校园招聘' in text:
            return '校招'
        elif '社招' in text or '全职' in text:
            return '社招'

        return '其他'

    def summarize(self, text: str, max_length: int = 200) -> str:
        """生成文本摘要"""
        if not text or len(text) <= max_length:
            return text

        # 简单摘要：取前max_length个字符，在句子边界截断
        summary = text[:max_length]
        last_period = max(
            summary.rfind('。'),
            summary.rfind('.'),
            summary.rfind('\n')
        )

        if last_period > max_length * 0.5:
            summary = summary[:last_period + 1]

        return summary + '...'
