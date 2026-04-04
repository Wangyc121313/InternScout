"""
实习僧爬虫 - 爬取实习僧网站的实习职位信息
"""
import json
import re
from typing import Any, Dict, List
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup

from core.base_spider import BaseSpider, SpiderConfig
from core.pipeline import (
    DataPipeline, DataCleaner, DeduplicationProcessor,
    NLPProcessor, DatabaseExporter
)
from storage.database import Database
from utils.logger import get_logger
from utils.helpers import extract_salary, parse_date, clean_text

logger = get_logger(__name__)


class ShixisengSpider(BaseSpider):
    """
    实习僧爬虫

    网站: https://www.shixiseng.com
    爬取内容: 实习岗位信息
    """

    name = "shixiseng"
    base_url = "https://www.shixiseng.com"
    search_url = "https://www.shixiseng.com/interns"

    def __init__(self, keywords: List[str] = None, cities: List[str] = None, max_pages: int = 5):
        config = SpiderConfig(
            name=self.name,
            base_url=self.base_url,
            delay_range=(2.0, 5.0),  # 实习僧反爬较严，增加延迟
            timeout=30,
            retries=3,
            headers={
                'Referer': 'https://www.shixiseng.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
        )
        super().__init__(config)

        self.keywords = keywords or ["实习"]
        self.cities = cities or []
        self.max_pages = max_pages
        self.pipeline = self._create_pipeline()

    def _create_pipeline(self) -> DataPipeline:
        """创建数据处理管道"""
        pipeline = DataPipeline()

        # 添加清洗处理器
        pipeline.add_processor(DataCleaner(
            required_fields=["title", "company"],
            string_fields=["title", "company", "location", "salary", "description"],
            date_fields=["posted_at"],
        ))

        # 添加去重处理器
        pipeline.add_processor(DeduplicationProcessor(
            key_fields=["url"],
        ))

        # 添加NLP处理器
        pipeline.add_processor(NLPProcessor())

        # 添加数据库导出器
        db = Database()
        pipeline.add_exporter(DatabaseExporter(db, item_type="job"))

        return pipeline

    def _build_search_url(self, keyword: str, city: str = "", page: int = 1) -> str:
        """
        构建搜索URL

        Args:
            keyword: 搜索关键词
            city: 城市
            page: 页码

        Returns:
            完整的搜索URL
        """
        params = {
            "keyword": keyword,
            "page": page,
        }
        if city:
            params["city"] = city

        query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
        return f"{self.search_url}?{query_string}"

    def parse_list_page(self, html: str) -> List[Dict[str, str]]:
        """
        解析列表页

        Args:
            html: 页面HTML

        Returns:
            职位链接列表
        """
        soup = BeautifulSoup(html, 'html.parser')
        job_links = []

        # 实习僧的职位卡片
        job_items = soup.select('.intern-wrap, .job-item, .position-item')

        for item in job_items:
            try:
                # 获取职位链接
                link_elem = item.select_one('a[href*="/intern/"], a[href*="/job/"]')
                if link_elem:
                    href = link_elem.get('href', '')
                    if href:
                        full_url = urljoin(self.base_url, href)
                        job_links.append({
                            'url': full_url,
                            'title': link_elem.get_text(strip=True),
                        })
            except Exception as e:
                logger.debug(f"Parse list item error: {e}")
                continue

        # 备用选择器
        if not job_links:
            for link in soup.select('a[href*="/intern/"]'):
                href = link.get('href', '')
                if href and '/intern/' in href:
                    full_url = urljoin(self.base_url, href)
                    title = link.get_text(strip=True)
                    if title and len(title) > 3:
                        job_links.append({
                            'url': full_url,
                            'title': title,
                        })

        logger.info(f"Found {len(job_links)} job links on list page")
        return job_links

    def parse_detail_page(self, html: str, url: str) -> Dict[str, Any]:
        """
        解析详情页

        Args:
            html: 页面HTML
            url: 页面URL

        Returns:
            职位数据字典
        """
        soup = BeautifulSoup(html, 'html.parser')
        data = {
            'source': self.name,
            'url': url,
        }

        try:
            # 职位标题
            title_elem = (
                soup.select_one('h1.job-title, h1.position-title, .job-name') or
                soup.select_one('h1.new_job_name, .job-title h1')
            )
            data['title'] = clean_text(title_elem.get_text()) if title_elem else ""

            # 公司名称
            company_elem = (
                soup.select_one('.company-name, .com-name, .job-com-name') or
                soup.select_one('a[href*="/company/"]')
            )
            data['company'] = clean_text(company_elem.get_text()) if company_elem else ""

            # 工作地点
            location_elem = (
                soup.select_one('.job-position, .job-address, .position-area') or
                soup.select_one('.job_det .location')
            )
            data['location'] = clean_text(location_elem.get_text()) if location_elem else ""

            # 薪资
            salary_elem = (
                soup.select_one('.job-salary, .salary, .position-salary') or
                soup.select_one('.job_money')
            )
            salary_text = clean_text(salary_elem.get_text()) if salary_elem else ""
            data['salary'] = salary_text

            # 解析薪资范围
            salary_min, salary_max = extract_salary(salary_text)
            data['salary_min'] = salary_min
            data['salary_max'] = salary_max

            # 职位描述
            desc_elem = (
                soup.select_one('.job-desc, .position-desc, .job-description') or
                soup.select_one('.job_detail, .position-content')
            )
            data['description'] = clean_text(desc_elem.get_text()) if desc_elem else ""

            # 职位要求
            req_elem = (
                soup.select_one('.job-require, .position-require, .requirements') or
                soup.select_one('.job_request')
            )
            data['requirements'] = clean_text(req_elem.get_text()) if req_elem else ""

            # 发布时间
            time_elem = (
                soup.select_one('.job-time, .publish-time, .position-time') or
                soup.select_one('.job_date, .publish-date')
            )
            time_text = clean_text(time_elem.get_text()) if time_elem else ""
            data['posted_at'] = parse_date(time_text)

            # 职位标签
            tags = []
            tag_elems = soup.select('.job-tag, .position-tag, .tag-item, .job_labels span')
            for tag in tag_elems:
                tag_text = clean_text(tag.get_text())
                if tag_text:
                    tags.append(tag_text)
            data['tags'] = tags

            # 职位类型
            data['job_type'] = '实习'

            # 生成source_id
            data['source_id'] = self._extract_job_id(url)

        except Exception as e:
            logger.error(f"Parse detail page error: {e}")

        return data

    def _extract_job_id(self, url: str) -> str:
        """从URL中提取职位ID"""
        match = re.search(r'/intern/(\w+)', url)
        if match:
            return match.group(1)
        match = re.search(r'/job/(\w+)', url)
        if match:
            return match.group(1)
        return ""

    def crawl_list_pages(self) -> List[Dict[str, str]]:
        """爬取列表页获取所有职位链接"""
        all_links = []

        for keyword in self.keywords:
            for city in (self.cities or [""]):
                for page in range(1, self.max_pages + 1):
                    try:
                        url = self._build_search_url(keyword, city, page)
                        logger.info(f"Crawling list: {url}")

                        html = self.fetch_html(url)
                        links = self.parse_list_page(html)

                        if not links:
                            logger.info(f"No more jobs found at page {page}")
                            break

                        all_links.extend(links)

                    except Exception as e:
                        logger.error(f"Crawl list page error: {e}")
                        continue

        # 去重
        seen_urls = set()
        unique_links = []
        for link in all_links:
            if link['url'] not in seen_urls:
                seen_urls.add(link['url'])
                unique_links.append(link)

        logger.info(f"Total unique job links: {len(unique_links)}")
        return unique_links

    def crawl_detail_pages(self, links: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """爬取详情页获取职位详情"""
        all_jobs = []

        for link in links:
            try:
                url = link['url']
                logger.info(f"Crawling detail: {url}")

                html = self.fetch_html(url)
                job_data = self.parse_detail_page(html, url)

                if job_data.get('title') and job_data.get('company'):
                    all_jobs.append(job_data)
                else:
                    logger.warning(f"Incomplete job data: {url}")

            except Exception as e:
                logger.error(f"Crawl detail page error: {e}")
                continue

        return all_jobs

    def start(self) -> List[Dict[str, Any]]:
        """
        启动爬虫

        Returns:
            爬取的职位列表
        """
        logger.info(f"Starting {self.name} spider...")

        # 1. 爬取列表页
        links = self.crawl_list_pages()

        # 2. 爬取详情页
        jobs = self.crawl_detail_pages(links)

        # 3. 数据处理管道
        processed_jobs = self.pipeline.run(jobs)

        logger.info(f"Spider completed: {len(processed_jobs)} jobs saved")
        return processed_jobs


def main():
    """测试运行"""
    spider = ShixisengSpider(
        keywords=["Python", "Java", "前端", "产品经理"],
        cities=["北京", "上海", "深圳"],
        max_pages=3
    )

    # 初始化数据库
    db = Database()
    db.create_tables()

    jobs = spider.start()
    print(f"\nCrawled {len(jobs)} jobs:")
    for job in jobs[:5]:
        print(f"- {job['title']} @ {job['company']} ({job.get('location', 'N/A')})")


if __name__ == "__main__":
    main()
