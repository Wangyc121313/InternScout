"""
爬虫中间件 - 反爬处理和重试机制
"""
import random
import time
from typing import Optional, Dict, Any, Callable

from utils.logger import get_logger
from utils.helpers import get_random_user_agent

logger = get_logger(__name__)


class AntiCrawlMiddleware:
    """
    反爬虫中间件

    功能：
    - User-Agent轮换
    - 请求频率控制
    - Cookie管理
    - 代理IP切换
    """

    def __init__(
        self,
        user_agents: list = None,
        proxy_pool: list = None,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
    ):
        self.user_agents = user_agents or []
        self.proxy_pool = proxy_pool or []
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last_request_time = 0
        self._cookies: Dict[str, str] = {}

    def get_user_agent(self) -> str:
        """获取随机User-Agent"""
        if self.user_agents:
            return random.choice(self.user_agents)
        return get_random_user_agent()

    def get_proxy(self) -> Optional[str]:
        """获取随机代理"""
        if self.proxy_pool:
            return random.choice(self.proxy_pool)
        return None

    def apply_delay(self):
        """应用请求延迟"""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        delay = random.uniform(self.min_delay, self.max_delay)

        if elapsed < delay:
            time.sleep(delay - elapsed)

        self._last_request_time = time.time()

    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理请求

        Args:
            request: 请求配置字典

        Returns:
            修改后的请求配置
        """
        # 应用延迟
        self.apply_delay()

        # 设置User-Agent
        headers = request.get('headers', {})
        headers['User-Agent'] = self.get_user_agent()
        request['headers'] = headers

        # 设置代理
        proxy = self.get_proxy()
        if proxy:
            request['proxies'] = {
                'http': proxy,
                'https': proxy,
            }

        # 设置Cookie
        if self._cookies:
            request['cookies'] = self._cookies

        return request

    def process_response(self, response: Any) -> Any:
        """
        处理响应

        Args:
            response: 响应对象

        Returns:
            响应对象
        """
        # 保存Cookie
        if hasattr(response, 'cookies'):
            self._cookies.update(response.cookies.get_dict())

        return response


class RetryMiddleware:
    """
    重试中间件

    功能：
    - 自动重试失败的请求
    - 指数退避策略
    - 特定状态码处理
    """

    DEFAULT_RETRY_CODES = [500, 502, 503, 504, 408, 429]

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        retry_codes: list = None,
        on_retry: Callable = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retry_codes = set(retry_codes or self.DEFAULT_RETRY_CODES)
        self.on_retry = on_retry
        self._retry_count: Dict[str, int] = {}

    def _get_delay(self, attempt: int) -> float:
        """
        计算延迟时间（指数退避）

        Args:
            attempt: 当前尝试次数

        Returns:
            延迟秒数
        """
        # 指数退避: base_delay * 2^attempt + 随机抖动
        delay = self.base_delay * (2 ** attempt)
        delay += random.uniform(0, 1)  # 抖动
        return min(delay, self.max_delay)

    def should_retry(self, response: Any) -> bool:
        """
        判断是否需要重试

        Args:
            response: 响应对象

        Returns:
            是否需要重试
        """
        status_code = getattr(response, 'status_code', 200)

        # HTTP错误状态码
        if status_code in self.retry_codes:
            return True

        # 连接错误
        if status_code == 0:
            return True

        return False

    def get_retry_count(self, url: str) -> int:
        """获取URL的重试次数"""
        return self._retry_count.get(url, 0)

    def increment_retry(self, url: str) -> int:
        """增加重试计数"""
        self._retry_count[url] = self._retry_count.get(url, 0) + 1
        return self._retry_count[url]

    def reset_retry(self, url: str):
        """重置重试计数"""
        self._retry_count.pop(url, None)

    def process_response(self, url: str, response: Any, callback: Callable) -> Any:
        """
        处理响应，执行重试逻辑

        Args:
            url: 请求URL
            response: 响应对象
            callback: 重试回调函数

        Returns:
            最终响应
        """
        if not self.should_retry(response):
            self.reset_retry(url)
            return response

        retry_count = self.increment_retry(url)

        if retry_count >= self.max_retries:
            logger.error(f"Max retries exceeded for {url}")
            self.reset_retry(url)
            return response

        delay = self._get_delay(retry_count)
        logger.warning(
            f"Retry {retry_count}/{self.max_retries} for {url} after {delay:.2f}s"
        )

        if self.on_retry:
            self.on_retry(url, retry_count, response)

        time.sleep(delay)

        # 执行重试
        return callback()


class RateLimiter:
    """
    速率限制器

    用于控制请求频率，避免被封禁
    """

    def __init__(
        self,
        requests_per_second: float = 1.0,
        burst_size: int = 5,
    ):
        self.min_interval = 1.0 / requests_per_second
        self.burst_size = burst_size
        self._last_request_times: list = []
        self._lock = None  # 如果需要线程安全，可以添加锁

    def _clean_old_requests(self):
        """清理过期的请求记录"""
        now = time.time()
        cutoff = now - 1.0  # 1秒窗口
        self._last_request_times = [
            t for t in self._last_request_times if t > cutoff
        ]

    def acquire(self, blocking: bool = True) -> bool:
        """
        获取请求许可

        Args:
            blocking: 是否阻塞等待

        Returns:
            是否获取成功
        """
        self._clean_old_requests()

        if len(self._last_request_times) < self.burst_size:
            self._last_request_times.append(time.time())
            return True

        if not blocking:
            return False

        # 计算需要等待的时间
        oldest = min(self._last_request_times)
        wait_time = self.min_interval - (time.time() - oldest)

        if wait_time > 0:
            time.sleep(wait_time)

        self._last_request_times.append(time.time())
        return True

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        pass


class ProxyPool:
    """
    代理IP池

    管理代理IP的获取、验证和轮换
    """

    def __init__(self, proxies: list = None):
        self.proxies = proxies or []
        self.working_proxies: list = []
        self.failed_proxies: Dict[str, int] = {}
        self.max_failures = 3
        self._current_index = 0

    def add_proxy(self, proxy: str):
        """添加代理"""
        if proxy not in self.proxies:
            self.proxies.append(proxy)

    def remove_proxy(self, proxy: str):
        """移除代理"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)
        if proxy in self.working_proxies:
            self.working_proxies.remove(proxy)

    def get_proxy(self) -> Optional[str]:
        """获取下一个代理（轮询）"""
        if not self.proxies:
            return None

        proxy = self.proxies[self._current_index]
        self._current_index = (self._current_index + 1) % len(self.proxies)
        return proxy

    def get_random_proxy(self) -> Optional[str]:
        """获取随机代理"""
        if not self.proxies:
            return None
        return random.choice(self.proxies)

    def mark_failed(self, proxy: str):
        """标记代理失败"""
        self.failed_proxies[proxy] = self.failed_proxies.get(proxy, 0) + 1

        if self.failed_proxies[proxy] >= self.max_failures:
            logger.warning(f"Removing failed proxy: {proxy}")
            self.remove_proxy(proxy)

    def mark_success(self, proxy: str):
        """标记代理成功"""
        if proxy in self.failed_proxies:
            del self.failed_proxies[proxy]
        if proxy not in self.working_proxies:
            self.working_proxies.append(proxy)

    def validate_proxy(self, proxy: str, test_url: str = "http://httpbin.org/ip") -> bool:
        """
        验证代理是否可用

        Args:
            proxy: 代理地址
            test_url: 测试URL

        Returns:
            是否可用
        """
        import requests

        try:
            response = requests.get(
                test_url,
                proxies={'http': proxy, 'https': proxy},
                timeout=10
            )
            if response.status_code == 200:
                self.mark_success(proxy)
                return True
        except Exception as e:
            logger.debug(f"Proxy validation failed: {proxy}, error: {e}")

        self.mark_failed(proxy)
        return False

    def validate_all(self, test_url: str = "http://httpbin.org/ip"):
        """验证所有代理"""
        for proxy in self.proxies[:]:
            self.validate_proxy(proxy, test_url)
