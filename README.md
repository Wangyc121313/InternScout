# InternScout

多平台实习信息搜集系统，自动从各大招聘网站和社交平台采集实习岗位信息和面试经验。

## 功能特性

- **多数据源支持**: 实习僧、Boss直聘、企业官网、小红书、牛客网、脉脉
- **智能反爬**: IP代理池、请求频率控制、User-Agent轮换、Playwright动态渲染
- **数据处理**: 自动去重、格式标准化、NLP信息提取、智能标签
- **数据存储**: SQLite/PostgreSQL 数据库存储，支持JSON/CSV导出
- **定时调度**: APScheduler 定时执行爬虫，支持增量更新
- **Web界面**: FastAPI + Jinja2 管理界面，支持筛选、搜索、排序
- **通知系统**: 邮件、Webhook（钉钉/企业微信/飞书）、RSS订阅

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt

# 安装Playwright浏览器（如需动态渲染）
playwright install chromium
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库、SMTP等
```

### 3. 初始化数据库

```python
from storage.database import Database
db = Database()
db.create_tables()
```

### 4. 运行爬虫

```bash
# 运行实习僧爬虫
python -m spiders.shixiseng

# 运行Boss直聘爬虫
python -m spiders.boss_zhipin
```

### 5. 启动Web界面

```bash
python -m web.app
```

访问 http://localhost:8000 查看Web界面

## 项目结构

```
InternScout/
├── config/              # 配置文件
│   ├── settings.yaml    # 主配置
│   └── spiders/         # 各爬虫配置
├── core/                # 核心组件
│   ├── base_spider.py   # 基础爬虫类
│   ├── middleware.py    # 中间件（反爬、重试）
│   └── pipeline.py      # 数据处理管道
├── spiders/             # 爬虫实现
│   ├── shixiseng.py     # 实习僧
│   ├── boss_zhipin.py   # Boss直聘
│   └── ...
├── models/              # 数据模型
│   ├── job.py           # 职位信息
│   ├── company.py       # 公司信息
│   └── interview.py     # 面经信息
├── storage/             # 存储层
│   ├── database.py      # 数据库连接
│   └── repository.py    # 数据操作
├── processors/          # 数据处理
│   ├── cleaner.py       # 清洗器
│   └── nlp_parser.py    # NLP解析
├── scheduler/           # 调度系统
│   └── task_scheduler.py
├── web/                 # Web界面
│   ├── app.py           # FastAPI应用
│   └── templates/       # HTML模板
├── notifier/            # 通知系统
│   └── notify.py
└── utils/               # 工具函数
    ├── logger.py
    └── helpers.py
```

## 数据模型

### Job（职位信息）
- id, title, company, location, salary, salary_min, salary_max
- requirements, description, tags, category, job_type
- source, url, posted_at, created_at, is_active

### Company（公司信息）
- id, name, industry, size, stage, website
- description, logo_url, tags, benefits, rating

### Interview（面经信息）
- id, company, position, content, result, difficulty
- process, questions, author, source, posted_at

## 配置说明

编辑 `config/settings.yaml` 或设置环境变量：

```yaml
# 数据库配置
database:
  type: sqlite  # 或 postgresql
  url: "sqlite:///./data/internscout.db"

# Redis配置
redis:
  host: localhost
  port: 6379

# 爬虫配置
crawler:
  concurrent_requests: 16
  download_delay: 1.0
  retry_times: 3

# 调度配置
scheduler:
  enabled: true
  jobs:
    - id: shixiseng_daily
      spider: shixiseng
      trigger: interval
      hours: 6

# 通知配置
notification:
  email:
    enabled: true
    smtp_host: smtp.gmail.com
    smtp_port: 587
    smtp_user: your-email@gmail.com
    recipients: ["recipient@example.com"]
  webhook:
    enabled: true
    url: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
    type: dingtalk
```

## API接口

### 职位相关
- `GET /api/jobs` - 获取职位列表
- `GET /api/jobs/{id}` - 获取职位详情
- `GET /api/companies` - 获取公司列表
- `GET /api/interviews` - 获取面经列表
- `GET /api/stats` - 获取统计数据

### 爬虫管理
- `POST /api/spiders/{name}/run` - 手动运行爬虫
- `GET /api/scheduler/jobs` - 获取定时任务列表
- `POST /api/scheduler/jobs/{id}/pause` - 暂停任务
- `POST /api/scheduler/jobs/{id}/resume` - 恢复任务

## 开发指南

### 创建新爬虫

继承 `BaseSpider` 或 `PlaywrightSpider`：

```python
from core.base_spider import BaseSpider, SpiderConfig

class MySpider(BaseSpider):
    def __init__(self):
        config = SpiderConfig(
            name="my_spider",
            base_url="https://example.com",
            delay_range=(1.0, 3.0),
        )
        super().__init__(config)

    def parse(self, response):
        # 解析逻辑
        pass

    def start(self):
        # 启动逻辑
        pass
```

### 使用数据处理管道

```python
from core.pipeline import DataPipeline, DataCleaner, DeduplicationProcessor

pipeline = DataPipeline()
pipeline.add_processor(DataCleaner(required_fields=["title", "company"]))
pipeline.add_processor(DeduplicationProcessor(key_fields=["url"]))

results = pipeline.run(items)
```

## 注意事项

1. **遵守Robots协议**: 爬虫默认遵守目标网站的robots.txt
2. **请求频率**: 默认配置有1-3秒的随机延迟，避免给目标网站造成压力
3. **代理IP**: 如需大量爬取，建议配置代理池
4. **法律合规**: 请确保爬取行为符合当地法律法规和目标网站使用条款

## License

MIT License
