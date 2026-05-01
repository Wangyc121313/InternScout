# 配置参考

InternScout 所有配置项说明。

## 配置优先级

```
.env 环境变量  >  config/settings.yaml
```

环境变量设置为空字符串不会覆盖 YAML。只有非空值才会生效。

---

## database

数据库连接配置。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `type` | string | `sqlite` | `sqlite` 或 `postgresql` |
| `url` | string | `sqlite:///./data/internscout.db` | SQLite 文件路径 |
| `host` | string | - | PostgreSQL 主机 |
| `port` | int | 5432 | PostgreSQL 端口 |
| `database` | string | - | PostgreSQL 数据库名 |
| `user` | string | - | PostgreSQL 用户名 |
| `password` | string | - | PostgreSQL 密码 |
| `pool_size` | int | 10 | 连接池大小 |
| `max_overflow` | int | 20 | 最大溢出连接 |

**环境变量**:

```bash
DATABASE_URL=sqlite:///./data/internscout.db
# 或 PostgreSQL:
DATABASE_URL=postgresql://user:password@localhost:5432/internscout
```

**YAML 示例**:

```yaml
database:
  type: postgresql
  host: localhost
  port: 5432
  database: internscout
  user: postgres
  password: your_password
  pool_size: 10
```

---

## redis

Redis 连接配置（可选，用于去重持久化）。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `host` | string | `localhost` | Redis 主机 |
| `port` | int | 6379 | Redis 端口 |
| `db` | int | 0 | 数据库编号 |
| `password` | string | null | 密码 |

**环境变量**:

```bash
REDIS_URL=redis://localhost:6379/0
```

---

## crawler

爬虫行为控制。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `concurrent_requests` | int | 16 | 最大并发请求数 |
| `download_delay` | float | 1.0 | 基础下载延迟（秒） |
| `randomize_download_delay` | float | 0.5 | 延迟随机浮动范围 |
| `retry_times` | int | 3 | 失败重试次数 |
| `retry_delay` | float | 1.0 | 重试基础延迟 |
| `timeout` | int | 30 | 请求超时（秒） |
| `user_agent_rotation` | bool | true | 启用 UA 轮换 |
| `proxy_enabled` | bool | false | 启用代理 |
| `proxy_pool` | list | [] | 代理地址列表 |

**YAML 示例**:

```yaml
crawler:
  concurrent_requests: 8
  download_delay: 2.0
  retry_times: 5
  proxy_enabled: true
  proxy_pool:
    - "http://proxy1:8080"
    - "http://proxy2:8080"
```

---

## playwright

Playwright 浏览器配置。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `headless` | bool | true | 无头模式 |
| `timeout` | int | 30000 | 页面加载超时（毫秒） |
| `viewport_width` | int | 1920 | 视口宽度 |
| `viewport_height` | int | 1080 | 视口高度 |

**环境变量**:

```bash
PLAYWRIGHT_TIMEOUT=60000
PLAYWRIGHT_HEADLESS=true
```

---

## scheduler

定时任务调度配置。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | true | 启用调度器 |
| `timezone` | string | `Asia/Shanghai` | 时区 |
| `jobs` | list | - | 任务列表 |

**Job 配置项**:

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `id` | string | 任务唯一标识 |
| `spider` | string | 爬虫名称 |
| `trigger` | string | `interval` / `cron` / `date` |
| `hours` | int | (interval) 间隔小时 |
| `minutes` | int | (interval) 间隔分钟 |
| `kwargs` | dict | 爬虫初始化参数 |

**YAML 示例**:

```yaml
scheduler:
  timezone: "Asia/Shanghai"
  jobs:
    - id: shixiseng_6h
      spider: shixiseng
      trigger: interval
      hours: 6
    - id: boss_daily_9am
      spider: boss_zhipin
      trigger: cron
      hour: 9
      minute: 0
      kwargs:
        max_pages: 5
        keywords: ["Python", "Java"]
```

---

## web

Web 服务配置。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `host` | string | `0.0.0.0` | 监听地址 |
| `port` | int | 8000 | 监听端口 |
| `debug` | bool | false | 调试模式 |
| `secret_key` | string | - | 会话密钥（生产环境务必修改） |
| `page_size` | int | 20 | 默认分页大小 |

**环境变量**:

```bash
HOST=0.0.0.0
PORT=8000
DEBUG=false
SECRET_KEY=random-string-here
```

---

## notification

通知系统配置。

### email

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | false | 启用邮件通知 |
| `smtp_host` | string | smtp.gmail.com | SMTP 服务器 |
| `smtp_port` | int | 587 | SMTP 端口 |
| `smtp_user` | string | - | 发件人邮箱 |
| `smtp_password` | string | - | SMTP 密码（Gmail 需应用专用密码） |
| `recipients` | list | [] | 收件人列表 |

### webhook

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | false | 启用 Webhook |
| `url` | string | - | Webhook URL |
| `type` | string | dingtalk | `dingtalk` / `wechat` / `feishu` |

### rss

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | true | 启用 RSS 生成 |
| `max_items` | int | 100 | 最大条目数 |

**完整 YAML 示例**:

```yaml
notification:
  email:
    enabled: true
    smtp_host: smtp.gmail.com
    smtp_port: 587
    smtp_user: your-email@gmail.com
    smtp_password: your-app-password
    recipients:
      - you@example.com
  webhook:
    enabled: true
    url: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
    type: dingtalk
  rss:
    enabled: true
    max_items: 200
```

---

## spiders

爬虫特定配置（URL、关键词、城市等）。

| 爬虫 | 配置项 | 默认值 |
|------|--------|--------|
| shixiseng | `base_url` | `https://www.shixiseng.com` |
| shixiseng | `search_url` | `https://www.shixiseng.com/interns` |
| shixiseng | `max_pages` | 10 |
| shixiseng | `keywords` | `["实习", " intern ", "实习生"]` |
| shixiseng | `cities` | `["北京", "上海", "深圳", "杭州", "广州", "成都"]` |
| boss_zhipin | `base_url` | `https://www.zhipin.com` |
| boss_zhipin | `search_url` | `https://www.zhipin.com/web/geek/job` |
| boss_zhipin | `max_pages` | 10 |
| boss_zhipin | `keywords` | `["实习", " intern "]` |
| boss_zhipin | `cities` | `[101010100, 101020100, ...]` |

> Boss 直聘的城市代码为数字编码，见 `config/settings.yaml`。

---

## logging

日志配置。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `level` | string | `INFO` | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `format` | string | - | loguru 格式字符串 |
| `file` | string | `logs/internscout.log` | 日志文件路径 |
| `rotation` | string | `10 MB` | 轮转大小 |
| `retention` | string | `30 days` | 保留时间 |

**环境变量**:

```bash
LOG_LEVEL=DEBUG
LOG_FILE=logs/internscout.log
```
