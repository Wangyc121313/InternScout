# 架构详解

InternScout 的系统设计和设计决策。

## 分层架构

```
┌──────────────────────────────────────────────┐
│                   main.py                     │  ← CLI 入口
├──────────────────────────────────────────────┤
│   Web (FastAPI)    │   Scheduler (APS)        │  ← 消费层
├──────────────────────────────────────────────┤
│              Pipeline (数据处理管道)           │  ← 处理层
├──────────────────────────────────────────────┤
│  ShixisengSpider  │  BossZhipinSpider  │ ... │  ← 采集层
│  PlaywrightSpider │    BaseSpider             │
├──────────────────────────────────────────────┤
│  Repository (Job/Company/Interview)           │  ← 持久化层
│  Database (SQLAlchemy: SQLite/PostgreSQL)     │
├──────────────────────────────────────────────┤
│  Notifier (Email/Webhook/RSS)                 │  ← 通知层
└──────────────────────────────────────────────┘
```

---

## 模块职责

### core/ — 核心框架

| 文件 | 职责 |
|------|------|
| `base_spider.py` | 抽象基类 BaseSpider（HTTP）和 PlaywrightSpider（JS 渲染） |
| `middleware.py` | 反爬中间件和 `@retry_on_error` 装饰器 |
| `pipeline.py` | DataPipeline 管道，内置 DataCleaner/DeduplicationProcessor/NLPProcessor，以及 DatabaseExporter/JSONExporter/CSVExporter |

### spiders/ — 爬虫实现

每个文件一个爬虫，继承 BaseSpider 或 PlaywrightSpider。必须实现 `parse()` 和 `start()`。

当前支持的站点：
- **实习僧**（`shixiseng.py`）：搜索列表页抓取
- **Boss 直聘**（`boss_zhipin.py`）：API 接口抓取

### models/ — 数据模型

SQLAlchemy ORM 模型，定义数据库表结构：
- `Job`：职位信息（title, company, location, salary, tags...）
- `Company`：公司信息（name, industry, size, stage...）
- `Interview`：面经信息（company, position, content, questions...）

### storage/ — 存储层

- `Database`：数据库连接管理，支持 SQLite（默认）和 PostgreSQL
- `Repository`：Repository 模式封装 CRUD 操作
  - `JobRepository`：按关键词/地点/来源筛选，去重检查
  - `CompanyRepository`：`get_or_create` 语义
  - `InterviewRepository`：按公司/职位筛选

### web/ — Web 界面

FastAPI 应用，Jinja2 模板渲染：
- 页面路由：`/` `/jobs` `/companies` `/interviews`
- API 路由：`/api/jobs` `/api/companies` `/api/interviews` `/api/stats`
- 爬虫控制：`POST /api/spiders/{name}/run`

### scheduler/ — 定时调度

基于 APScheduler，支持 interval/cron/date 触发器：
- `TaskScheduler`：通用任务调度
- `SpiderScheduler`：爬虫专用，动态导入 Spider 类并执行

### notifier/ — 通知系统

- `EmailNotifier`：SMTP 发送 HTML 邮件
- `WebhookNotifier`：支持钉钉、企业微信、飞书卡片消息
- `RSSNotifier`：生成 RSS 2.0 XML
- `NotificationManager`：统一管理多渠道分发

### processors/ — 数据处理器

- `cleaner.py`：数据标准化（去除空白、统一日期格式）
- `nlp_parser.py`：技术标签提取、地点识别、学历经验要求提取

### utils/ — 工具函数

- `logger.py`：loguru 日志配置
- `helpers.py`：通用辅助函数（`clean_text`, `extract_salary`, `parse_date`, `extract_tech_tags`）

---

## 设计模式

### 策略模式（Spider）

```
BaseSpider (接口)
├─ ShixisengSpider (策略 A: HTML 解析)
├─ BossZhipinSpider (策略 B: API 调用)
└─ 未来爬虫...
```

在 `main.py` 的 `spider_map` 中注册新策略，运行时动态选择。

### 管道模式（Pipeline）

```
item → [DataCleaner] → [DeduplicationProcessor] → [NLPProcessor] → [Exporter...]
```

每个处理器接收 item，返回处理后 item 或 None（丢弃）。链式调用，可组合。

### Repository 模式（Storage）

```
Web/API → Repository → SQLAlchemy Session → Database
```

隔离业务逻辑与 SQL 细节。Repository 提供领域语义的查询方法，不暴露 SQL。

### 观察者模式（Scheduler）

```
APScheduler 事件 → on_job_executed / on_job_error → 日志 + 状态更新
```

---

## 技术选型理由

| 选择 | 理由 |
|------|------|
| **requests + BeautifulSoup** | 轻量，无需浏览器即可处理大多数页面 |
| **Playwright** | 仅用于 JS 渲染页面，按需启动，非默认依赖 |
| **SQLAlchemy ORM** | 成熟、异步友好、支持 SQLite/PostgreSQL 无缝切换 |
| **FastAPI** | 高性能（基于 Starlette）、自动 OpenAPI 文档、类型安全 |
| **loguru** | 零配置日志，自动轮转，比标准 logging 简洁 |
| **APScheduler** | 支持多种触发器，进程内调度，无需外部依赖 |
| **SQLite 默认** | 零配置，适合个人使用；提升到 PostgreSQL 只需改 URL |

---

## 扩展点

### 新增爬虫
1. 创建 `spiders/xxx.py`，继承 `BaseSpider` 或 `PlaywrightSpider`
2. 注册到 `main.py` 的 `spider_map`

### 新增处理器
1. 继承 `core/pipeline.py: BaseProcessor`
2. 实现 `process(self, item) -> Optional[Dict]`
3. 通过 `pipeline.add_processor()` 添加

### 新增通知渠道
1. 继承 `notifier/notify.py: Notifier`
2. 实现 `send(self, message) -> bool`
3. 通过 `NotificationManager.add_notifier()` 注册

### 新增数据导出
1. 实现 `__call__(self, item)` 方法
2. 通过 `pipeline.add_exporter()` 添加

---

## 测试策略

```
tests/
├── test_helpers.py   # 工具函数单元测试（clean_text, extract_salary...）
└── (未来扩展...)
```

- **工具函数**：纯函数，pytest 参数化测试
- **Spider parse()**：mock HTTP 响应，验证解析输出结构
- **Pipeline**：构造测试数据，验证链式处理正确性
- **Repository**：使用 SQLite 内存数据库测试 CRUD

运行：`pytest tests/ -v`
