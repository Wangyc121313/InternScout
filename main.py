#!/usr/bin/env python3
"""
InternScout - 主入口文件

多平台实习信息搜集系统
"""
import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from storage.database import Database
from scheduler.task_scheduler import SpiderScheduler
from utils.logger import get_logger

logger = get_logger(__name__)


def init_db():
    """初始化数据库"""
    db = Database()
    db.create_tables()
    logger.info("Database initialized")


def run_spider(name: str, **kwargs):
    """运行指定爬虫"""
    import importlib

    spider_map = {
        "shixiseng": ("spiders.shixiseng", "ShixisengSpider"),
        "boss": ("spiders.boss_zhipin", "BossZhipinSpider"),
        "boss_zhipin": ("spiders.boss_zhipin", "BossZhipinSpider"),
    }

    if name not in spider_map:
        logger.error(f"Unknown spider: {name}")
        return

    module_path, class_name = spider_map[name]
    module = importlib.import_module(module_path)
    SpiderClass = getattr(module, class_name)

    spider = SpiderClass(**kwargs)
    results = spider.start()

    logger.info(f"Spider {name} completed: {len(results)} items")
    return results


def run_scheduler():
    """运行调度器"""
    import yaml
    import time

    scheduler = SpiderScheduler()
    scheduler.start(background=True)

    # 加载配置
    config_path = Path(__file__).parent / "config" / "settings.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        jobs_config = config.get("scheduler", {}).get("jobs", [])
        scheduler.load_from_config(jobs_config)

    logger.info("Scheduler started. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        logger.info("Scheduler stopped")


def run_web():
    """运行Web服务"""
    from web.app import main
    main()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="InternScout - 多平台实习信息搜集系统"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # init 命令
    subparsers.add_parser("init", help="初始化数据库")

    # crawl 命令
    crawl_parser = subparsers.add_parser("crawl", help="运行爬虫")
    crawl_parser.add_argument(
        "spider",
        choices=["shixiseng", "boss", "boss_zhipin", "all"],
        help="爬虫名称",
    )
    crawl_parser.add_argument(
        "--pages", type=int, default=3, help="爬取页数"
    )
    crawl_parser.add_argument(
        "--keywords", nargs="+", default=["实习"], help="搜索关键词"
    )

    # scheduler 命令
    subparsers.add_parser("scheduler", help="运行定时调度器")

    # web 命令
    subparsers.add_parser("web", help="启动Web服务")

    # 解析参数
    args = parser.parse_args()

    if args.command == "init":
        init_db()

    elif args.command == "crawl":
        if args.spider == "all":
            for spider_name in ["shixiseng", "boss"]:
                run_spider(spider_name, max_pages=args.pages, keywords=args.keywords)
        else:
            run_spider(
                args.spider,
                max_pages=args.pages,
                keywords=args.keywords,
            )

    elif args.command == "scheduler":
        run_scheduler()

    elif args.command == "web":
        run_web()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
