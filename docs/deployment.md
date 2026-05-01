# 部署指南

将 InternScout 部署到生产环境。

## 环境要求

| 依赖 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.11+ | 建议使用 pyenv 或 conda 管理 |
| Chromium | - | Playwright 依赖，带 JS 渲染的站点需要 |
| SQLite | 3.x | 默认数据库，无需额外安装 |
| PostgreSQL | 14+ | 可选，生产环境推荐 |
| Redis | 6+ | 可选，用于去重持久化 |

---

## 安装

```bash
# 1. 克隆仓库
git clone https://github.com/Wangyc121313/InternScout.git
cd InternScout

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装 Playwright 浏览器
playwright install chromium

# 5. 配置环境变量
cp .env.example .env
vim .env  # 修改数据库、密钥等

# 6. 初始化数据库
python main.py init
```

---

## 数据库选择

| 场景 | 推荐 | 连接串 |
|------|------|--------|
| 个人使用 | SQLite | `sqlite:///./data/internscout.db` |
| 团队使用 | PostgreSQL | `postgresql://user:pass@host:5432/db` |

**迁移到 PostgreSQL**:

```bash
# 1. 创建数据库
createdb internscout

# 2. 修改 .env
DATABASE_URL=postgresql://postgres:password@localhost:5432/internscout

# 3. 重新初始化
python main.py init
```

---

## systemd 服务

### Web 服务

```ini
# /etc/systemd/system/internscout-web.service
[Unit]
Description=InternScout Web Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/InternScout
Environment="PATH=/opt/InternScout/venv/bin"
ExecStart=/opt/InternScout/venv/bin/python main.py web
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 调度器

```ini
# /etc/systemd/system/internscout-scheduler.service
[Unit]
Description=InternScout Spider Scheduler
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/InternScout
Environment="PATH=/opt/InternScout/venv/bin"
ExecStart=/opt/InternScout/venv/bin/python main.py scheduler
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now internscout-web internscout-scheduler
sudo systemctl status internscout-web
```

---

## Nginx 反向代理

```nginx
server {
    listen 80;
    server_name internscout.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 静态文件
    location /static {
        alias /opt/InternScout/web/static;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
# 启用站点
sudo ln -s /etc/nginx/sites-available/internscout /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# HTTPS (Certbot)
sudo certbot --nginx -d internscout.example.com
```

---

## Docker 部署（可选）

```dockerfile
# Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    chromium \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .
RUN mkdir -p data logs

ENV DATABASE_URL=sqlite:///./data/internscout.db
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

# 初始化数据库后启动 Web
CMD python main.py init && python main.py web
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/internscout
    depends_on:
      - db

  scheduler:
    build: .
    command: python main.py scheduler
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - db

  db:
    image: postgres:14
    environment:
      POSTGRES_DB: internscout
      POSTGRES_PASSWORD: password
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

```bash
docker-compose up -d
```

---

## 日志轮转

配置在 `config/settings.yaml` 中：

```yaml
logging:
  level: "INFO"
  file: "logs/internscout.log"
  rotation: "10 MB"     # 超过 10MB 自动轮转
  retention: "30 days"  # 保留 30 天
```

生产环境建议配合 logrotate：

```bash
# /etc/logrotate.d/internscout
/opt/InternScout/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

---

## 监控

```bash
# 健康检查
curl http://localhost:8000/api/stats

# 查看调度器状态
curl http://localhost:8000/api/scheduler/jobs

# 查看日志
tail -f logs/internscout.log

# 检查服务状态
systemctl status internscout-web internscout-scheduler
```

---

## 常见问题

**Q: `playwright install chromium` 报权限错误**  
A: 使用 `playwright install --with-deps chromium` 安装系统依赖，或手动安装 `libnss3` 等包。

**Q: SQLite 并发写入报 `database is locked`**  
A: SQLite 不支持高并发写入。切换到 PostgreSQL，或在代码中使用 `timeout` 参数。

**Q: systemd 服务启动失败**  
A: 检查日志 `journalctl -u internscout-web -f`，确认 Python 路径和虚拟环境正确。

**Q: 内存占用过高**  
A: Playwright 每个页面约消耗 100-200MB。减少 `concurrent_requests` 或在 `headless: true` 模式下运行。
