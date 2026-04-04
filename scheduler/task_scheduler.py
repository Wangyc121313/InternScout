"""
任务调度器 - 定时执行爬虫任务
"""
import asyncio
from datetime import datetime
from typing import Callable, Dict, List, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from utils.logger import get_logger

logger = get_logger(__name__)


class TaskScheduler:
    """
    任务调度器

    基于APScheduler实现定时任务调度
    支持：
    - 定时执行爬虫
    - 增量更新
    - 任务优先级队列
    - 任务状态监控
    """

    def __init__(self, timezone: str = "Asia/Shanghai"):
        self.timezone = timezone
        self.scheduler = None
        self._jobs: Dict[str, Any] = {}
        self._running = False
        self._stats: Dict[str, Dict] = {}

    def start(self, background: bool = True):
        """
        启动调度器

        Args:
            background: 是否以后台模式运行
        """
        if background:
            self.scheduler = BackgroundScheduler(timezone=self.timezone)
        else:
            self.scheduler = AsyncIOScheduler(timezone=self.timezone)

        # 添加事件监听
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR
        )

        self.scheduler.start()
        self._running = True
        logger.info("Task scheduler started")

    def stop(self):
        """停止调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Task scheduler stopped")

    def _on_job_executed(self, event):
        """任务执行完成回调"""
        job_id = event.job_id
        self._stats[job_id] = {
            "last_run": datetime.now(),
            "status": "success",
            "retval": event.retval,
        }
        logger.info(f"Job {job_id} executed successfully")

    def _on_job_error(self, event):
        """任务执行错误回调"""
        job_id = event.job_id
        self._stats[job_id] = {
            "last_run": datetime.now(),
            "status": "error",
            "exception": str(event.exception),
        }
        logger.error(f"Job {job_id} failed: {event.exception}")

    def add_job(
        self,
        job_id: str,
        func: Callable,
        trigger: str = "interval",
        **trigger_args
    ):
        """
        添加任务

        Args:
            job_id: 任务唯一标识
            func: 执行函数
            trigger: 触发器类型 (interval/cron/date)
            **trigger_args: 触发器参数
        """
        if not self.scheduler:
            raise RuntimeError("Scheduler not started")

        # 移除已存在的同名任务
        if job_id in self._jobs:
            self.remove_job(job_id)

        # 创建触发器
        if trigger == "interval":
            trig = IntervalTrigger(**trigger_args)
        elif trigger == "cron":
            trig = CronTrigger(**trigger_args)
        else:
            raise ValueError(f"Unknown trigger type: {trigger}")

        # 添加任务
        job = self.scheduler.add_job(
            func=func,
            trigger=trig,
            id=job_id,
            replace_existing=True,
            max_instances=1,  # 防止任务重叠执行
        )

        self._jobs[job_id] = job
        logger.info(f"Added job {job_id} with {trigger} trigger: {trigger_args}")

    def remove_job(self, job_id: str):
        """移除任务"""
        if job_id in self._jobs:
            self.scheduler.remove_job(job_id)
            del self._jobs[job_id]
            logger.info(f"Removed job {job_id}")

    def pause_job(self, job_id: str):
        """暂停任务"""
        if job_id in self._jobs:
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused job {job_id}")

    def resume_job(self, job_id: str):
        """恢复任务"""
        if job_id in self._jobs:
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed job {job_id}")

    def run_job_now(self, job_id: str):
        """立即执行任务"""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.modify(next_run_time=datetime.now())
            logger.info(f"Scheduled job {job_id} to run now")

    def get_jobs(self) -> List[Dict[str, Any]]:
        """获取所有任务列表"""
        jobs = []
        for job_id, job in self._jobs.items():
            stats = self._stats.get(job_id, {})
            jobs.append({
                "id": job_id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run_time": job.next_run_time,
                "status": "paused" if job.next_run_time is None else "active",
                "last_run": stats.get("last_run"),
                "last_status": stats.get("status"),
            })
        return jobs

    def get_stats(self) -> Dict[str, Any]:
        """获取调度器统计信息"""
        return {
            "running": self._running,
            "job_count": len(self._jobs),
            "jobs": self._stats,
        }


class SpiderScheduler(TaskScheduler):
    """
    爬虫专用调度器

    预配置常用爬虫任务
    """

    SPIDER_MAPPING = {
        "shixiseng": "spiders.shixiseng:ShixisengSpider",
        "boss_zhipin": "spiders.boss_zhipin:BossZhipinSpider",
    }

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        self.spider_instances = {}

    def _import_spider(self, spider_name: str):
        """动态导入爬虫类"""
        import importlib

        module_path, class_name = self.SPIDER_MAPPING[spider_name].split(":")
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    def schedule_spider(
        self,
        spider_name: str,
        job_id: str = None,
        trigger: str = "interval",
        spider_kwargs: Dict[str, Any] = None,
        **trigger_args
    ):
        """
        调度爬虫任务

        Args:
            spider_name: 爬虫名称
            job_id: 任务ID（默认使用spider_name）
            trigger: 触发器类型
            spider_kwargs: 爬虫初始化参数
            **trigger_args: 触发器参数
        """
        job_id = job_id or spider_name
        spider_kwargs = spider_kwargs or {}

        def run_spider():
            try:
                SpiderClass = self._import_spider(spider_name)
                spider = SpiderClass(**spider_kwargs)
                return spider.start()
            except Exception as e:
                logger.error(f"Spider {spider_name} failed: {e}")
                raise

        self.add_job(
            job_id=job_id,
            func=run_spider,
            trigger=trigger,
            **trigger_args
        )

    def load_from_config(self, config: List[Dict[str, Any]]):
        """从配置加载定时任务"""
        for job_config in config:
            if job_config.get("enabled", True):
                self.schedule_spider(
                    spider_name=job_config["spider"],
                    job_id=job_config.get("id"),
                    trigger=job_config.get("trigger", "interval"),
                    spider_kwargs=job_config.get("kwargs", {}),
                    **job_config.get("trigger_args", {"hours": 6})
                )


# 全局调度器实例
_default_scheduler = None


def get_scheduler() -> TaskScheduler:
    """获取默认调度器实例"""
    global _default_scheduler
    if _default_scheduler is None:
        _default_scheduler = SpiderScheduler()
    return _default_scheduler
