# 数据流走向

InternScout 数据从目标网站到用户界面的完整链路。

## 总览

```
外部招聘网站 → Spider → Pipeline → Storage → Web/API → 用户
                    ↓                        ↓
                 Notifier                 Scheduler
                 (邮件/钉钉)              (定时触发)
```

---

## 一、采集层

### 1.1 触发入口

- **手动**: `python main.py crawl <spider_name>`
- **定时**: `Scheduler` 按 `config/settings.yaml` 中的 interval 自动触发
- **Web**: `POST /api/spiders/{name}/run`

### 1.2 Spider 构造

```
main.py: run_spider()
  → importlib.import_module(spider_module)
  → SpiderClass(**kwargs)
```

### 1.3 页面获取

**同步 HTTP（BaseSpider）**:

```
start() → fetch() → requests.Session.request()
  ├─ User-Agent 轮换（utils/helpers.py: get_common_headers()）
  ├─ 代理池随机选取（SpiderConfig.proxy_pool）
  └─ 随机延迟 1-3s（_random_delay）
```

**异步 JS 渲染（PlaywrightSpider）**:

```
start() → run_sync(start_async())
  → init_playwright() → chromium.launch(headless=True)
  → fetch_with_playwright() → page.goto(wait_until='networkidle')
  → page.content()
  → close_playwright()
```

### 1.4 数据解析

```
parse(response) → List[Dict]
  e.g. {"title": "Python实习生", "company": "字节跳动", "url": "..."}
```

每个 Spider 自行实现 `parse()`，返回标准化 dict 列表。

---

## 二、处理层

### 2.1 Pipeline 链式处理

```python
pipeline = DataPipeline()
pipeline.add_processor(DataCleaner(required_fields=["title", "company"]))
pipeline.add_processor(DeduplicationProcessor(key_fields=["url"]))
pipeline.add_processor(NLPProcessor())
pipeline.add_exporter(DatabaseExporter(db))
```

### 2.2 处理步骤

| 步骤 | 处理器 | 输入 | 输出 |
|------|--------|------|------|
| 清洗 | `DataCleaner` | 原始 dict | 清洗后 dict 或 None（缺少必填字段） |
| 去重 | `DeduplicationProcessor` | 清洗后 dict | 非重复 dict 或 None（已存在） |
| NLP | `NLPProcessor` | 去重后 dict | 补充 tags/location/requirements |

### 2.3 去重机制

- **本地模式**: `set()` 内存缓存，进程重启后失效
- **Redis 模式**: `SETEX dedup:{md5_key} 604800 1`，7 天 TTL
- **唯一键**: `md5(url|source)` 作为去重指纹

---

## 三、存储层

### 3.1 数据库写入

```
DatabaseExporter.__call__()
  → Database.get_session()
  → JobRepository.create(item)  或 CompanyRepository.get_or_create()
  → session.commit()
```

### 3.2 文件导出

- `JSONExporter`: 追加模式写入 `.jsonl` 文件
- `CSVExporter`: 自动检测字段名，写入 `.csv`

### 3.3 数据模型

```
Job ─────────────── Company ─────────────── Interview
├─ title           ├─ name                 ├─ company
├─ company         ├─ industry             ├─ position
├─ location        ├─ size                 ├─ content
├─ salary          ├─ stage                ├─ result
├─ requirements    ├─ website              ├─ difficulty
├─ description     ├─ description          ├─ process
├─ tags (JSON)     ├─ logo_url             ├─ questions (JSON)
├─ category        ├─ tags (JSON)          ├─ author
├─ job_type        ├─ benefits (JSON)      ├─ source
├─ source          └─ rating               ├─ url
├─ url                                    └─ posted_at
├─ posted_at
└─ is_active
```

---

## 四、消费层

### 4.1 Web 界面

```
浏览器请求 → FastAPI 路由 → get_db_session() → Repository 查询 → JSON/HTML
```

关键路由：
- `/jobs` → `JobRepository.list_jobs()` → `jobs.html`
- `/api/jobs` → `JobRepository.list_jobs()` → JSON
- `/api/stats` → 聚合三个 Repository 的 `get_stats()`

### 4.2 定时调度

```
APScheduler (BackgroundScheduler)
  ├─ Event Listener: on_job_executed / on_job_error
  ├─ SpiderScheduler.load_from_config()
  └─ run_spider() → SpiderClass(**kwargs).start()
```

### 4.3 通知系统

```
NotificationManager.notify_new_jobs()
  ├─ EmailNotifier.send_jobs_notification()  → SMTP 发送 HTML 邮件
  ├─ WebhookNotifier.send()                  → POST JSON 到钉钉/企业微信/飞书
  └─ RSSNotifier.send()                      → 添加条目 → generate_feed() 输出 XML
```

---

## 五、一个职位的完整旅程

以实习僧爬取"Python 实习生"为例：

```
1. 用户: python main.py crawl shixiseng --pages 1 --keywords Python

2. main.py → run_spider("shixiseng", max_pages=1, keywords=["Python"])

3. ShixisengSpider.__init__()
   → SpiderConfig(base_url="https://www.shixiseng.com", ...)

4. ShixisengSpider.start()
   → fetch(search_url + keyword) × pages
   → parse(response): 从 HTML 提取 title/company/location/salary/url

5. 原始数据:
   {"title": " Python实习生 ", "company": " 字节跳动 ",
    "salary": "200-250元/天", "url": "https://...", "source": "shixiseng"}

6. DataCleaner.process()
   → " Python实习生 " → "Python实习生"
   → " 字节跳动 " → "字节跳动"

7. DeduplicationProcessor.process()
   → md5("https://...|shixiseng") → 查 set，未命中 → 标记为已见

8. NLPProcessor.process()
   → text = "Python实习生 ..."
   → tags: ["Python"] (从 tech_tags 词典匹配)
   → requirements: [] (未匹配到特定模式)

9. DatabaseExporter.__call__()
   → JobRepository.create(item) → session.add(job) → session.commit()

10. 用户访问 http://localhost:8000/jobs?keyword=Python
    → JobRepository.list_jobs(keyword="Python") → SQL LIKE 查询
    → jobs.html 渲染列表
```
