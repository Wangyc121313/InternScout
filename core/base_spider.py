"""
基础爬虫类 - 封装通用爬取逻辑
"""
import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

import requests
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from utils.logger import get_logger
from utils.helpers import get_common_headers, random_delay, retry_on_error

logger = get_logger(__name__)


@dataclass
class SpiderConfig:
    """爬虫配置"""
    name: str
    base_url: str
    delay_range: tuple = (1.0, 3.0)
    timeout: int = 30
    retries: int = 3
    use_proxy: bool = False
    proxy_pool: List[str] = None
    headers: Dict[str, str] = None
    # Playwright配置
    use_playwright: bool = False
    headless: bool = True
    viewport: dict = None


class BaseSpider(ABC):
    """
    基础爬虫类

    提供通用的HTTP请求、重试机制、请求头管理、Playwright支持等功能
    """

    def __init__(self, config: SpiderConfig):
        self.config = config
        self.name = config.name
        self.session = requests.Session()
        self.logger = get_logger(f"spider.{config.name}")

        # 初始化请求头
        self._init_headers()

        # Playwright相关
        self.playwright = None
        self.browser = None
        self.context = None

    def _init_headers(self):
        """初始化请求头"""
        headers = get_common_headers()
        if self.config.headers:
            headers.update(self.config.headers)
        self.session.headers.update(headers)

    def _get_proxy(self) -> Optional[str]:
        """获取代理"""
        if self.config.use_proxy and self.config.proxy_pool:
            return random.choice(self.config.proxy_pool)
        return None

    def _random_delay(self):
        """随机延迟"""
        min_delay, max_delay = self.config.delay_range
        time.sleep(random.uniform(min_delay, max_delay))

    @retry_on_error(max_retries=3, delay=1.0)
    def fetch(self, url: str, method: str = "GET", **kwargs) -> requests.Response:
        """
        发送HTTP请求

        Args:
            url: 请求URL
            method: 请求方法
            **kwargs: 其他requests参数

        Returns:
            Response对象
        """
        # 设置代理
        proxy = self._get_proxy()
        if proxy:
            kwargs['proxies'] = {'http': proxy, 'https': proxy}

        # 设置超时
        kwargs['timeout'] = kwargs.get('timeout', self.config.timeout)

        # 随机延迟
        self._random_delay()

        self.logger.debug(f"Fetching {method} {url}")

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            self.logger.error(f"Request failed: {url}, error: {e}")
            raise

    def fetch_json(self, url: str, method: str = "GET", **kwargs) -> Any:
        """获取JSON数据"""
        response = self.fetch(url, method, **kwargs)
        return response.json()

    def fetch_html(self, url: str, method: str = "GET", **kwargs) -> str:
        """获取HTML内容"""
        response = self.fetch(url, method, **kwargs)
        response.encoding = response.apparent_encoding
        return response.text

    # ===== Playwright 支持 =====

    async def init_playwright(self) -> BrowserContext:
        """初始化Playwright"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.config.headless
        )

        context_options = {}
        if self.config.viewport:
            context_options['viewport'] = self.config.viewport

        self.context = await self.browser.new_context(
            user_agent=self.session.headers.get('User-Agent'),
            **context_options
        )

        # 设置请求头
        await self.context.set_extra_http_headers({
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })

        return self.context

    async def close_playwright(self):
        """关闭Playwright"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def fetch_with_playwright(
        self,
        url: str,
        wait_for: str = None,
        wait_timeout: int = 30000,
        action: Callable[[Page], Any] = None
    ) -> Dict[str, Any]:
        """
        使用Playwright获取页面

        Args:
            url: 页面URL
            wait_for: 等待元素出现的CSS选择器
            wait_timeout: 等待超时时间
            action: 页面操作函数

        Returns:
            包含html和page内容的字典
        """
        if not self.context:
            await self.init_playwright()

        page = await self.context.new_page()

        try:
            self.logger.debug(f"Playwright fetching: {url}")
            await page.goto(url, wait_until='networkidle')

            # 等待特定元素
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=wait_timeout)

            # 执行自定义操作
            if action:
                await action(page)

            # 随机延迟，模拟人类行为
            await asyncio.sleep(random.uniform(1, 3))

            content = await page.content()
            title = await page.title()

            return {
                'html': content,
                'title': title,
                'url': page.url,
            }
        finally:
            await page.close()

    def run_sync(self, coro):
        """同步运行异步函数"""
        return asyncio.run(coro)

    # ===== 抽象方法 =====

    @abstractmethod
    def parse(self, response: Any) -> List[Dict[str, Any]]:
        """
        解析响应数据

        Args:
            response: 响应对象或HTML文本

        Returns:
            解析后的数据列表
        """
        pass

    @abstractmethod
    def start(self) -> List[Dict[str, Any]]:
        """
        启动爬虫

        Returns:
            爬取的数据列表
        """
        pass

    def save_items(self, items: List[Dict[str, Any]]) -> int:
        """
        保存数据项

        Args:
            items: 数据项列表

        Returns:
            保存的数量
        """
        # 默认实现，子类可以覆盖
        self.logger.info(f"Collected {len(items)} items")
        return len(items)

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.session.close()


class PlaywrightSpider(BaseSpider):
    """
    基于Playwright的爬虫基类

    用于需要JavaScript渲染的页面
    """

    def __init__(self, config: SpiderConfig):
        config.use_playwright = True
        super().__init__(config)

    async def start_async(self) -> List[Dict[str, Any]]:
        """异步启动爬虫"""
        await self.init_playwright()
        try:
            return await self.crawl()
        finally:
            await self.close_playwright()

    @abstractmethod
    async def crawl(self) -> List[Dict[str, Any]]:
        """异步爬取逻辑"""
        pass

    def start(self) -> List[Dict[str, Any]]:
        """同步入口"""
        return self.run_sync(self.start_async())
