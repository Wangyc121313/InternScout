# API 文档

InternScout Web API 参考。

## 基础信息

| 项目 | 值 |
|------|-----|
| Base URL | `http://localhost:8000` |
| 响应格式 | JSON |
| 编码 | UTF-8 |
| 分页 | `skip` + `limit` 参数 |

---

## 职位 API

### `GET /api/jobs`

获取职位列表。

**查询参数**:

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `skip` | int | 0 | 偏移量，≥0 |
| `limit` | int | 20 | 每页数量，1-100 |
| `location` | string | - | 城市筛选（北京/上海/深圳...） |
| `company` | string | - | 公司名模糊匹配 |
| `keyword` | string | - | 标题关键词搜索 |
| `source` | string | - | 来源平台（shixiseng/boss_zhipin） |

**响应示例**:

```json
{
  "data": [
    {
      "id": 1,
      "title": "Python后端实习生",
      "company": "字节跳动",
      "location": "北京",
      "salary": "400-500元/天",
      "salary_min": 8800.0,
      "salary_max": 11000.0,
      "requirements": "熟悉Django/Flask",
      "description": "负责后端API开发...",
      "tags": ["Python", "Django", "MySQL"],
      "category": "技术",
      "job_type": "实习",
      "source": "shixiseng",
      "url": "https://www.shixiseng.com/intern/xxx",
      "posted_at": "2024-01-15T10:30:00",
      "is_active": true
    }
  ],
  "skip": 0,
  "limit": 20
}
```

### `GET /api/jobs/{job_id}`

获取单个职位详情。

**响应**: 返回单个 Job 对象，不存在返回 404。

```json
{
  "detail": "Job not found"
}
```

---

## 公司 API

### `GET /api/companies`

获取公司列表。

**查询参数**:

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `skip` | int | 0 | 偏移量 |
| `limit` | int | 20 | 每页数量 |
| `industry` | string | - | 行业筛选 |

**响应示例**:

```json
{
  "data": [
    {
      "id": 1,
      "name": "字节跳动",
      "industry": "互联网",
      "size": "10000人以上",
      "stage": "D轮及以上",
      "website": "https://bytedance.com",
      "description": "字节跳动是一家...",
      "tags": ["弹性工作", "免费三餐"],
      "rating": 4.5
    }
  ],
  "skip": 0,
  "limit": 20
}
```

---

## 面经 API

### `GET /api/interviews`

获取面经列表。

**查询参数**:

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `skip` | int | 0 | 偏移量 |
| `limit` | int | 20 | 每页数量 |
| `company` | string | - | 公司名筛选 |
| `position` | string | - | 职位筛选 |

**响应示例**:

```json
{
  "data": [
    {
      "id": 1,
      "company": "字节跳动",
      "position": "后端开发实习生",
      "content": "面试共三轮...",
      "result": "通过",
      "difficulty": "中等",
      "process": "笔试 + 3轮技术面 + HR面",
      "questions": ["TCP三次握手", "Python GIL机制"],
      "author": "匿名用户",
      "source": "nowcoder",
      "posted_at": "2024-01-10T14:00:00"
    }
  ],
  "skip": 0,
  "limit": 20
}
```

---

## 统计 API

### `GET /api/stats`

获取聚合统计数据。

**响应示例**:

```json
{
  "jobs": {
    "total": 1500,
    "by_source": {"shixiseng": 800, "boss_zhipin": 700},
    "by_location": {"北京": 500, "上海": 400, "深圳": 300}
  },
  "companies": {
    "total": 200,
    "by_industry": {"互联网": 100, "金融": 50}
  },
  "interviews": {
    "total": 300
  }
}
```

---

## 爬虫管理 API

### `POST /api/spiders/{spider_name}/run`

手动触发爬虫。

**路径参数**:

| 参数 | 说明 |
|------|------|
| `spider_name` | `shixiseng` 或 `boss_zhipin` |

**响应**:

```json
{
  "success": true,
  "count": 42
}
```

**错误响应**:

```json
// 404 - 爬虫不存在
{"detail": "Spider not found"}

// 500 - 执行失败
{"detail": "Runtime error details..."}
```

### `GET /api/scheduler/jobs`

获取定时任务列表。

**响应示例**:

```json
[
  {
    "id": "shixiseng_daily",
    "name": "shixiseng_daily",
    "trigger": "interval[0:06:00]",
    "next_run_time": "2024-01-15T18:00:00+08:00",
    "status": "active",
    "last_run": "2024-01-15T12:00:00+08:00",
    "last_status": "success"
  }
]
```

### `POST /api/scheduler/jobs/{job_id}/pause`

暂停定时任务。

**响应**: `{"success": true}`

### `POST /api/scheduler/jobs/{job_id}/resume`

恢复定时任务。

**响应**: `{"success": true}`

---

## 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

| HTTP 状态码 | 含义 |
|-------------|------|
| 200 | 成功 |
| 404 | 资源不存在 |
| 422 | 参数校验失败 |
| 500 | 服务器内部错误 |
