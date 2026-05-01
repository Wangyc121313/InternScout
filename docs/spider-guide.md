# 爬虫开发指南

如何为 InternScout 创建新爬虫。

## 爬虫基类体系

```
BaseSpider (ABC)                    PlaywrightSpider (BaseSpider)
├─ 适合: 纯 HTTP/API 接口          ├─ 适合: JS 渲染页面
├─ 引擎: requests.Session           ├─ 引擎: Playwright (Chromium)
├─ 同步: start()                    ├─ 异步: start_async() → crawl()
└─ 解析: parse(response)            └─ 解析: parse(response)
```

### 何时用哪个

| 场景 | 选型 |
|------|------|
| 目标站返回纯 HTML，无 JS 渲染 | `BaseSpider` |
| 目标站有登录态/Cookie 校验 | `BaseSpider`（用 Session） |
| 目标站是 SPA，数据在 JS 中渲染 | `PlaywrightSpider` |
| 需要模拟点击、滚动、填表 | `PlaywrightSpider` |
| 目标站有严格的 JS 反爬指纹检测 | `PlaywrightSpider` |

---

## SpiderConfig 配置项

```python
from core.base_spider import SpiderConfig

config = SpiderConfig(
    name="my_spider",           # 唯一标识，日志用
    base_url="https://...",     # 目标网站根 URL
    delay_range=(1.0, 3.0),     # 请求间隔（秒），随机取区间内值
    timeout=30,                 # HTTP 超时（秒）
    retries=3,                  # 失败重试次数
    use_proxy=False,            # 是否启用代理
    proxy_pool=[],              # 代理地址列表 ["http://ip:port", ...]
    headers={"Referer": "..."}, # 自定义请求头
    use_playwright=False,       # True 则启用 Playwright
    headless=True,              # Playwright 无头模式
    viewport={"width": 1920, "height": 1080},  # 浏览器视口
)
```

---

## 创建新爬虫（5 步）

### 步骤 1：创建爬虫类

```python
# spiders/my_site.py
from core.base_spider import BaseSpider, SpiderConfig

class MySiteSpider(BaseSpider):
    def __init__(self, max_pages=3, keywords=None):
        config = SpiderConfig(
            name="my_site",
            base_url="https://example.com/jobs",
            delay_range=(2.0, 5.0),  # 对方可能比较敏感，加大延迟
        )
        super().__init__(config)
        self.max_pages = max_pages
        self.keywords = keywords or ["实习"]
```

### 步骤 2：实现 parse()

```python
    def parse(self, response):
        """从 response 中提取职位列表"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'lxml')
        results = []
        for card in soup.select('.job-card'):
            results.append({
                "title": card.select_one('.title').text.strip(),
                "company": card.select_one('.company').text.strip(),
                "location": card.select_one('.location').text.strip(),
                "salary": card.select_one('.salary').text.strip() or "薪资面议",
                "description": card.select_one('.desc').text.strip(),
                "url": card.select_one('a')['href'],
                "source": self.name,  # 必须，用于去重和筛选
            })
        return results
```

### 步骤 3：实现 start()

```python
    def start(self):
        """遍历搜索页，采集数据"""
        results = []
        for page in range(1, self.max_pages + 1):
            for keyword in self.keywords:
                url = f"{self.config.base_url}?q={keyword}&page={page}"
                try:
                    response = self.fetch(url)
                    items = self.parse(response)
                    results.extend(items)
                    self.logger.info(f"Page {page}/{keyword}: {len(items)} items")
                except Exception as e:
                    self.logger.error(f"Failed: {url}, {e}")
                    continue

        # 通过 Pipeline 处理
        from core.pipeline import DataPipeline, DataCleaner, DeduplicationProcessor
        from core.pipeline import DatabaseExporter
        from storage.database import Database

        pipeline = DataPipeline()
        pipeline.add_processor(DataCleaner(
            required_fields=["title", "company", "url"]))
        pipeline.add_processor(DeduplicationProcessor(key_fields=["url"]))
        pipeline.add_exporter(DatabaseExporter(Database(), item_type="job"))

        return pipeline.run(results)
```

### 步骤 4：注册到 main.py

```python
# main.py 的 spider_map 中添加
spider_map = {
    "shixiseng": ("spiders.shixiseng", "ShixisengSpider"),
    "boss": ("spiders.boss_zhipin", "BossZhipinSpider"),
    "my_site": ("spiders.my_site", "MySiteSpider"),  # 新增
}
```

### 步骤 5：测试

```bash
python main.py crawl my_site --pages 1 --keywords Python
```

---

## 反爬策略

### 内置机制（无需配置）

| 机制 | 实现位置 | 说明 |
|------|----------|------|
| User-Agent 轮换 | `utils/helpers.py: get_common_headers()` | 每次请求随机选取 |
| 随机延迟 | `BaseSpider._random_delay()` | 请求间隔 1-3s |
| 指数退避重试 | `@retry_on_error(max_retries=3, delay=1.0)` | 失败后 1s → 2s → 4s |
| 超时保护 | `SpiderConfig.timeout` | 默认 30s |

### 可配置增强

```yaml
# config/settings.yaml
crawler:
  user_agent_rotation: true
  proxy_enabled: true
  proxy_pool:
    - "http://proxy1:8080"
    - "http://proxy2:8080"
  concurrent_requests: 8    # 控制并发
  download_delay: 2.0       # 加大基础延迟
  retry_times: 5            # 增加重试
```

### 进阶技巧

**Cookie 保持**:
```python
# BaseSpider 的 self.session 自动保持 Cookie
self.session.cookies.set('token', 'xxx')
```

**自定义请求头**:
```python
config = SpiderConfig(
    headers={
        "Referer": "https://example.com/",
        "X-Requested-With": "XMLHttpRequest",
    }
)
```

**Playwright 模拟人类行为**:
```python
async def crawl(self):
    result = await self.fetch_with_playwright(
        url="https://example.com",
        wait_for=".job-list",     # 等 job 列表渲染完
        action=lambda page: page.evaluate("window.scrollTo(0, 2000)")
    )
    items = self.parse(result['html'])
    return items
```

---

## Playwright 完整示例

```python
from core.base_spider import PlaywrightSpider, SpiderConfig

class JSSpider(PlaywrightSpider):
    def __init__(self, max_pages=3):
        config = SpiderConfig(
            name="js_spider",
            base_url="https://vue-app.example.com",
            use_playwright=True,  # PlaywrightSpider 自动开启
            headless=True,
        )
        super().__init__(config)
        self.max_pages = max_pages

    def parse(self, html: str) -> list:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        return [{"title": el.text, "source": self.name}
                for el in soup.select('.job-title')]

    async def crawl(self):
        results = []
        for page in range(1, self.max_pages + 1):
            result = await self.fetch_with_playwright(
                url=f"{self.config.base_url}/page/{page}",
                wait_for=".job-title",
                wait_timeout=10000,
            )
            results.extend(self.parse(result['html']))
        return results
```

---

## Pipeline 最佳实践

```python
# 推荐：每个爬虫都走 Pipeline，用链式配置
pipeline = (DataPipeline()
    .add_processor(DataCleaner(
        required_fields=["title", "url"],
        string_fields=["title", "company", "description"],
        date_fields=["posted_at"],
    ))
    .add_processor(DeduplicationProcessor(
        key_fields=["url"],
        use_redis=False,       # 单进程用本地 set
    ))
    .add_processor(NLPProcessor(
        extract_tech_tags=True,
        extract_location=True,
    ))
    .add_exporter(DatabaseExporter(Database(), item_type="job"))
    .add_exporter(JSONExporter("data/jobs.jsonl", append=True))
)
```

## 常见问题

**Q: 提示 `ImportError: No module named 'spiders.xxx'`**  
A: 确保从项目根目录运行，`sys.path.insert(0, str(Path(__file__).parent))` 在 main.py 中处理。

**Q: Playwright 报 `Browser closed unexpectedly`**  
A: 运行 `playwright install chromium` 安装浏览器。

**Q: 爬取结果为 0**  
A: 检查 CSS 选择器是否匹配目标页面的实际结构。先用 `curl` 或浏览器开发者工具查看源码。
