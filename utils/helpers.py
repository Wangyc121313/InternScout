import hashlib
import json
import random
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from fake_useragent import UserAgent


def generate_id(url: str) -> str:
    """根据URL生成唯一ID"""
    return hashlib.md5(url.encode()).hexdigest()


def clean_text(text: str) -> str:
    """清理文本内容"""
    if not text:
        return ""
    # 移除多余空白
    text = re.sub(r'\s+', ' ', text)
    # 移除特殊字符
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)
    return text.strip()


def extract_salary(salary_text: str) -> tuple:
    """
    从薪资文本中提取薪资范围

    Args:
        salary_text: 如 "10-20K", "15k-25k", "面议"

    Returns:
        (min_salary, max_salary) 单位：元/月
    """
    if not salary_text or '面议' in salary_text:
        return None, None

    # 匹配数字范围
    pattern = r'(\d+)(?:\s*-\s*|\s*~\s*|\s*到\s*)(\d+)'
    match = re.search(pattern, salary_text)

    if match:
        min_val = int(match.group(1))
        max_val = int(match.group(2))

        # 判断单位
        if 'K' in salary_text.upper() or 'k' in salary_text:
            min_val *= 1000
            max_val *= 1000
        elif '万' in salary_text:
            min_val *= 10000
            max_val *= 10000

        return float(min_val), float(max_val)

    # 单个数字
    single_pattern = r'(\d+)'
    match = re.search(single_pattern, salary_text)
    if match:
        val = int(match.group(1))
        if 'K' in salary_text.upper() or 'k' in salary_text:
            val *= 1000
        elif '万' in salary_text:
            val *= 10000
        return float(val), float(val)

    return None, None


def parse_date(date_text: str) -> Optional[datetime]:
    """
    解析日期文本

    Args:
        date_text: 如 "2024-01-15", "3天前", "刚刚"

    Returns:
        datetime对象或None
    """
    if not date_text:
        return None

    date_text = date_text.strip()
    now = datetime.now()

    # 相对时间
    if '刚刚' in date_text or '刚才' in date_text:
        return now

    if '分钟前' in date_text:
        minutes = int(re.search(r'(\d+)', date_text).group(1))
        return now - timedelta(minutes=minutes)

    if '小时前' in date_text:
        hours = int(re.search(r'(\d+)', date_text).group(1))
        return now - timedelta(hours=hours)

    if '天前' in date_text:
        days = int(re.search(r'(\d+)', date_text).group(1))
        return now - timedelta(days=days)

    # 标准日期格式
    formats = [
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%m-%d',
        '%m月%d日',
        '%Y-%m-%d %H:%M',
        '%Y/%m/%d %H:%M:%S',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_text, fmt)
        except ValueError:
            continue

    # 只有月份和日期，补全年份
    if '月' in date_text and '日' in date_text:
        try:
            dt = datetime.strptime(date_text, '%m月%d日')
            return dt.replace(year=now.year)
        except ValueError:
            pass

    return None


def get_random_user_agent() -> str:
    """获取随机User-Agent"""
    try:
        ua = UserAgent()
        return ua.random
    except Exception:
        # 备选UA列表
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        ]
        return random.choice(user_agents)


def get_common_headers() -> Dict[str, str]:
    """获取通用请求头"""
    return {
        'User-Agent': get_random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }


def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0):
    """随机延迟"""
    time.sleep(random.uniform(min_seconds, max_seconds))


def retry_on_error(max_retries: int = 3, delay: float = 1.0):
    """
    错误重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 重试间隔（秒）
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
                    continue
            raise last_exception
        return wrapper
    return decorator


def extract_tags(text: str, tag_dict: Dict[str, List[str]]) -> List[str]:
    """
    从文本中提取标签

    Args:
        text: 要分析的文本
        tag_dict: 标签字典，如 {'Python': ['python', 'py'], 'Java': ['java']}

    Returns:
        匹配的标签列表
    """
    text_lower = text.lower()
    tags = []

    for tag, keywords in tag_dict.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                tags.append(tag)
                break

    return tags


TECH_TAGS = {
    'Python': ['python', 'django', 'flask', 'fastapi'],
    'Java': ['java', 'spring', 'springboot', 'mybatis'],
    'Go': ['golang', 'go语言'],
    'C++': ['c++', 'cpp', 'cplusplus'],
    'JavaScript': ['javascript', 'js', 'nodejs', 'node.js'],
    'TypeScript': ['typescript', 'ts'],
    'React': ['react', 'react.js'],
    'Vue': ['vue', 'vue.js', 'vue3'],
    'AI/ML': ['machine learning', 'deep learning', 'tensorflow', 'pytorch', 'ai', '机器学习'],
    '大数据': ['hadoop', 'spark', 'flink', '大数据', 'hive'],
    '前端': ['frontend', 'front-end', '前端'],
    '后端': ['backend', 'back-end', '后端'],
    '全栈': ['fullstack', 'full-stack', '全栈'],
    '移动端': ['android', 'ios', 'flutter', 'react native', '移动端'],
    'DevOps': ['docker', 'kubernetes', 'k8s', 'jenkins', 'ci/cd', 'devops'],
    '云计算': ['aws', 'azure', 'gcp', '阿里云', '腾讯云', '云计算'],
    '数据库': ['mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', '数据库'],
}


def extract_tech_tags(text: str) -> List[str]:
    """提取技术标签"""
    return extract_tags(text, TECH_TAGS)


def sanitize_filename(filename: str) -> str:
    """清理文件名中的非法字符"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.strip()


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """将列表分块"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def format_datetime(dt: datetime) -> str:
    """格式化日期时间"""
    if not dt:
        return ""
    return dt.strftime('%Y-%m-%d %H:%M')


def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """截断文本"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(' ', 1)[0] + suffix
