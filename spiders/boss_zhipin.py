"""
Boss直聘爬虫 - 爬取Boss直聘网站的实习职位信息
"""
import json
import re
from typing import Any, Dict, List
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup

from core.base_spider import PlaywrightSpider, SpiderConfig
from core.pipeline import (
    DataPipeline, DataCleaner, DeduplicationProcessor,
    NLPProcessor, DatabaseExporter
)
from storage.database import Database
from utils.logger import get_logger
from utils.helpers import extract_salary, parse_date, clean_text

logger = get_logger(__name__)


class BossZhipinSpider(PlaywrightSpider):
    """
    Boss直聘爬虫

    网站: https://www.zhipin.com
    爬取内容: 实习岗位信息

    注意: Boss直聘反爬非常严格，需要使用Playwright模拟浏览器
    """

    name = "boss_zhipin"
    base_url = "https://www.zhipin.com"
    search_url = "https://www.zhipin.com/web/geek/job"

    # 城市代码映射
    CITY_CODES = {
        "北京": "101010100",
        "上海": "101020100",
        "广州": "101280100",
        "深圳": "101280600",
        "杭州": "101210100",
        "成都": "101270100",
        "武汉": "101200100",
        "西安": "101110100",
        "南京": "101190100",
        "苏州": "101190400",
    }

    def __init__(self, keywords: List[str] = None, cities: List[str] = None, max_pages: int = 5):
        config = SpiderConfig(
            name="boss_zhipin",
            base_url="https://www.zhipin.com",
            delay_range=(3.0, 6.0),  # Boss反爬更严格
            timeout=30,
            retries=3,
            use_playwright=True,
            headless=True,
            viewport={"width": 1920, "height": 1080},
        )
        super().__init__(config)

        self.keywords = keywords or ["实习"]
        self.cities = cities or []
        self.max_pages = max_pages
        self.pipeline = self._create_pipeline()

    def _create_pipeline(self) -> DataPipeline:
        """创建数据处理管道"""
        pipeline = DataPipeline()

        pipeline.add_processor(DataCleaner(
            required_fields=["title", "company"],
            string_fields=["title", "company", "location", "salary", "description"],
            date_fields=["posted_at"],
        ))

        pipeline.add_processor(DeduplicationProcessor(
            key_fields=["url"],
        ))

        pipeline.add_processor(NLPProcessor())

        db = Database()
        pipeline.add_exporter(DatabaseExporter(db, item_type="job"))

        return pipeline

    def _build_search_url(self, keyword: str, city_code: str = "", page: int = 1) -> str:
        """构建搜索URL"""
        params = {
            "query": keyword,
            "page": page,
        }
        if city_code:
            params["city"] = city_code

        query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
        return f"{self.search_url}?{query_string}"

    async def crawl(self) -> List[Dict[str, Any]]:
        """
        异步爬取入口
        """
        await self.init_playwright()

        all_jobs = []

        try:
            for keyword in self.keywords:
                for city in (self.cities or [""]):
                    city_code = self.CITY_CODES.get(city, "")

                    for page in range(1, self.max_pages + 1):
                        try:
                            url = self._build_search_url(keyword, city_code, page)
                            logger.info(f"Crawling: {url}")

                            result = await self.fetch_with_playwright(
                                url,
                                wait_for=".job-card-wrapper, .search-job-result",
                                wait_timeout=30000,
                            )

                            jobs = self._parse_job_list(result['html'], url)

                            if not jobs:
                                logger.info(f"No more jobs at page {page}")
                                break

                            all_jobs.extend(jobs)

                            # 随机延迟
                            await self._random_delay()

                        except Exception as e:
                            logger.error(f"Error crawling page {page}: {e}")
                            continue

        finally:
            await self.close_playwright()

        # 处理数据
        processed_jobs = self.pipeline.run(all_jobs)
        return processed_jobs

    def _parse_job_list(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """解析职位列表"""
        soup = BeautifulSoup(html, 'html.parser')
        jobs = []

        # Boss直聘的职位卡片
        job_cards = soup.select('.job-card-wrapper, .job-card-default, .search-card')

        for card in job_cards:
            try:
                job = self._parse_job_card(card, base_url)
                if job.get('title') and job.get('company'):
                    jobs.append(job)
            except Exception as e:
                logger.debug(f"Parse job card error: {e}")
                continue

        logger.info(f"Parsed {len(jobs)} jobs from page")
        return jobs

    def _parse_job_card(self, card, base_url: str) -> Dict[str, Any]:
        """解析单个职位卡片"""
        job = {
            'source': self.name,
            'job_type': '实习',
        }

        # 职位名称和链接
        title_elem = card.select_one('.job-name, .job-title, .name')
        if title_elem:
            job['title'] = clean_text(title_elem.get_text())
            link_elem = title_elem.find_parent('a')
            if link_elem:
                href = link_elem.get('href', '')
                job['url'] = urljoin(self.base_url, href)

        # 公司名称
        company_elem = card.select_one('.company-name, .company-title, .comp-name')
        job['company'] = clean_text(company_elem.get_text()) if company_elem else ""

        # 工作地点
        location_elem = card.select_one('.job-area, .area, .job-location')
        job['location'] = clean_text(location_elem.get_text()) if location_elem else ""

        # 薪资
        salary_elem = card.select_one('.salary, .job-salary, .red')
        salary_text = clean_text(salary_elem.get_text()) if salary_elem else ""
        job['salary'] = salary_text

        # 解析薪资范围
        salary_min, salary_max = extract_salary(salary_text)
        job['salary_min'] = salary_min
        job['salary_max'] = salary_max

        # 标签（经验、学历等）
        tag_elems = card.select('.tag-list li, .info-desc, .tag-item')
        tags = [clean_text(tag.get_text()) for tag in tag_elems]
        job['tags'] = [t for t in tags if t]

        # 尝试提取职位描述（如果在列表中有的话）
        desc_elem = card.select_one('.info-desc, .job-desc')
        job['description'] = clean_text(desc_elem.get_text()) if desc_elem else ""

        # 处理实习标签
        if '实习' in str(job.get('tags', [])):
            job['job_type'] = '实习'

        # 生成source_id
        if job.get('url'):
            job['source_id'] = self._extract_job_id(job['url'])

        return job

    def _extract_job_id(self, url: str) -> str:
        """从URL中提取职位ID"""
        match = re.search(r'/job_detail/(\w+)\.html', url)
        if match:
            return match.group(1)
        return ""

    async def _random_delay(self):
        """随机延迟"""
        import asyncio
        import random
        await asyncio.sleep(random.uniform(2, 5))

    def start(self) -> List[Dict[str, Any]]:
        """同步入口"""
        return self.run_sync(self.crawl())


def main():
    """测试运行"""
    spider = BossZhipinSpider(
        keywords=["Python", "前端"],
        cities=["北京", "上海"],
        max_pages=2
    )

    # 初始化数据库
    db = Database()
    db.create_tables()

    jobs = spider.start()
    print(f"\nCrawled {len(jobs)} jobs:")
    for job in jobs[:5]:
        print(f"- {job['title']} @ {job['company']} ({job.get('salary', 'N/A')})")


if __name__ == "__main__":
    main()
