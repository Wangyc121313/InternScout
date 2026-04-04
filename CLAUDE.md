# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

InternScout is a multi-platform internship information collection system that scrapes job postings from recruitment websites like 实习僧 (Shixiseng) and Boss直聘 (Boss Zhipin).

## Common Development Commands

### Setup
```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

### Database Initialization
```bash
python main.py init
```

### Running Spiders
```bash
# Run specific spiders
python main.py crawl shixiseng --pages 3 --keywords Python Java
python main.py crawl boss --pages 2

# Run all spiders
python main.py crawl all --pages 3 --keywords 实习
```

### Web Server
```bash
python main.py web
# Access at http://localhost:8000
```

### Scheduler
```bash
python main.py scheduler
```

### Testing
```bash
pytest tests/
pytest tests/test_helpers.py -v
```

## Architecture

### Spider System
- **BaseSpider** (`core/base_spider.py`): Abstract base class for HTTP-based scraping using requests. Provides retry logic, proxy support, and random delays.
- **PlaywrightSpider** (`core/base_spider.py`): For JavaScript-rendered pages using Playwright async API.
- **SpiderConfig**: Dataclass for spider configuration (delay_range, timeout, retries, proxy settings, playwright options).

Spiders are registered in `main.py`'s `run_spider()` function with a spider_map mapping names to module/class pairs.

### Data Pipeline
- **DataPipeline** (`core/pipeline.py`): Processes scraped items through a chain of processors.
- **Built-in processors**: DataCleaner, DeduplicationProcessor.
- Usage: `pipeline.add_processor(DataCleaner(required_fields=["title", "company"]))`

### Storage Layer
- **Database** (`storage/database.py`): SQLAlchemy-based, supports SQLite (default) and PostgreSQL. Connection configured in `config/settings.yaml`.
- **Repository Pattern**: `JobRepository`, `CompanyRepository`, `InterviewRepository` in `storage/repository.py`.
- **Models**: `Job`, `Company`, `Interview` in `models/` directory.

### Web Interface
- **FastAPI** application in `web/app.py`
- **Templates**: Jinja2 templates in `web/templates/`
- **API Endpoints**: `/api/jobs`, `/api/companies`, `/api/interviews`, `/api/stats`
- **Spider Control**: `POST /api/spiders/{name}/run` to trigger spiders manually

### Scheduler
- **SpiderScheduler** (`scheduler/task_scheduler.py`): APScheduler-based.
- Jobs configured in `config/settings.yaml` under `scheduler.jobs`.

## Configuration

Primary configuration is in `config/settings.yaml`:
- `database`: SQLite/PostgreSQL connection settings
- `crawler`: Concurrent requests, delays, retry settings
- `scheduler`: Job definitions with interval triggers
- `web`: Host, port, debug settings
- `spiders`: Spider-specific settings (URLs, keywords, cities)

Environment variables in `.env` override YAML config.

## Creating a New Spider

1. Create a class inheriting from `BaseSpider` (for simple HTTP) or `PlaywrightSpider` (for JS-rendered pages)
2. Implement `parse(self, response)` to extract data
3. Implement `start(self)` to orchestrate crawling
4. Register in `main.py`'s `spider_map`

Example structure:
```python
from core.base_spider import BaseSpider, SpiderConfig

class MySpider(BaseSpider):
    def __init__(self, max_pages=3, keywords=None):
        config = SpiderConfig(name="my_spider", base_url="https://example.com")
        super().__init__(config)
        self.max_pages = max_pages
        
    def parse(self, response):
        # Extract data from response
        return [{"title": "...", "company": "..."}]
        
    def start(self):
        # Fetch pages and call parse
        results = []
        # ... crawling logic
        return results
```

## Key Implementation Details

- **Anti-detection**: BaseSpider includes User-Agent rotation, random delays (1-3s default), and retry with exponential backoff
- **Playwright usage**: When `use_playwright=True` in config, call `fetch_with_playwright()` which handles browser lifecycle
- **Data flow**: Spider.start() → parse() → save_items() → Pipeline.process() → Repository.save()
- **Logging**: Uses loguru via `utils.logger.get_logger(__name__)`
