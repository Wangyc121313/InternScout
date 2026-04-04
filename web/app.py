"""
FastAPI Web 应用 - 数据展示和爬虫管理
"""
import os
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from storage.database import Database
from storage.repository import JobRepository, CompanyRepository, InterviewRepository
from scheduler.task_scheduler import SpiderScheduler
from utils.logger import get_logger

logger = get_logger(__name__)

# 全局数据库实例
db = Database()

# 全局调度器实例
scheduler = SpiderScheduler()


def get_db_session():
    """获取数据库会话依赖"""
    with db.get_session() as session:
        yield session


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="InternScout",
        description="实习信息搜集系统",
        version="0.1.0",
    )

    # 模板
    templates = Jinja2Templates(directory="web/templates")

    # 启动事件
    @app.on_event("startup")
    async def startup():
        db.create_tables()
        logger.info("Application started")

    # ===== 页面路由 =====

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """首页"""
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/jobs", response_class=HTMLResponse)
    async def jobs_page(
        request: Request,
        page: int = Query(1, ge=1),
        location: str = "",
        keyword: str = "",
        session: Session = Depends(get_db_session)
    ):
        """职位列表页"""
        repo = JobRepository(session)
        skip = (page - 1) * 20
        jobs = repo.list_jobs(skip=skip, limit=20, location=location, keyword=keyword)
        total = len(jobs)  # 简化处理，实际需要count查询

        return templates.TemplateResponse("jobs.html", {
            "request": request,
            "jobs": [j.to_dict() for j in jobs],
            "page": page,
            "total": total,
            "location": location,
            "keyword": keyword,
        })

    @app.get("/companies", response_class=HTMLResponse)
    async def companies_page(
        request: Request,
        page: int = Query(1, ge=1),
        session: Session = Depends(get_db_session)
    ):
        """公司列表页"""
        repo = CompanyRepository(session)
        skip = (page - 1) * 20
        companies = repo.list_companies(skip=skip, limit=20)

        return templates.TemplateResponse("companies.html", {
            "request": request,
            "companies": [c.to_dict() for c in companies],
            "page": page,
        })

    @app.get("/interviews", response_class=HTMLResponse)
    async def interviews_page(
        request: Request,
        page: int = Query(1, ge=1),
        company: str = "",
        session: Session = Depends(get_db_session)
    ):
        """面经列表页"""
        repo = InterviewRepository(session)
        skip = (page - 1) * 20
        interviews = repo.list_interviews(skip=skip, limit=20, company=company)

        return templates.TemplateResponse("interviews.html", {
            "request": request,
            "interviews": [i.to_dict() for i in interviews],
            "page": page,
            "company": company,
        })

    # ===== API 路由 =====

    @app.get("/api/jobs")
    async def api_jobs(
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        location: Optional[str] = None,
        company: Optional[str] = None,
        keyword: Optional[str] = None,
        source: Optional[str] = None,
        session: Session = Depends(get_db_session)
    ):
        """获取职位列表API"""
        repo = JobRepository(session)
        jobs = repo.list_jobs(
            skip=skip,
            limit=limit,
            location=location,
            company=company,
            keyword=keyword,
            source=source,
        )
        return {
            "data": [j.to_dict() for j in jobs],
            "skip": skip,
            "limit": limit,
        }

    @app.get("/api/jobs/{job_id}")
    async def api_job_detail(
        job_id: int,
        session: Session = Depends(get_db_session)
    ):
        """获取职位详情API"""
        repo = JobRepository(session)
        job = repo.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.to_dict()

    @app.get("/api/companies")
    async def api_companies(
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        industry: Optional[str] = None,
        session: Session = Depends(get_db_session)
    ):
        """获取公司列表API"""
        repo = CompanyRepository(session)
        companies = repo.list_companies(skip=skip, limit=limit, industry=industry)
        return {
            "data": [c.to_dict() for c in companies],
            "skip": skip,
            "limit": limit,
        }

    @app.get("/api/interviews")
    async def api_interviews(
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        company: Optional[str] = None,
        position: Optional[str] = None,
        session: Session = Depends(get_db_session)
    ):
        """获取面经列表API"""
        repo = InterviewRepository(session)
        interviews = repo.list_interviews(
            skip=skip,
            limit=limit,
            company=company,
            position=position,
        )
        return {
            "data": [i.to_dict() for i in interviews],
            "skip": skip,
            "limit": limit,
        }

    @app.get("/api/stats")
    async def api_stats(session: Session = Depends(get_db_session)):
        """获取统计数据API"""
        job_repo = JobRepository(session)
        company_repo = CompanyRepository(session)
        interview_repo = InterviewRepository(session)

        return {
            "jobs": job_repo.get_stats(),
            "companies": company_repo.get_stats(),
            "interviews": interview_repo.get_stats(),
        }

    # ===== 爬虫管理 API =====

    @app.post("/api/spiders/{spider_name}/run")
    async def run_spider(spider_name: str):
        """手动运行爬虫"""
        try:
            import importlib

            if spider_name == "shixiseng":
                module = importlib.import_module("spiders.shixiseng")
                spider = module.ShixisengSpider(max_pages=3)
            elif spider_name == "boss_zhipin":
                module = importlib.import_module("spiders.boss_zhipin")
                spider = module.BossZhipinSpider(max_pages=2)
            else:
                raise HTTPException(status_code=404, detail="Spider not found")

            result = spider.start()
            return {"success": True, "count": len(result)}

        except Exception as e:
            logger.error(f"Run spider error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/scheduler/jobs")
    async def get_scheduler_jobs():
        """获取调度任务列表"""
        return scheduler.get_jobs()

    @app.post("/api/scheduler/jobs/{job_id}/pause")
    async def pause_job(job_id: str):
        """暂停任务"""
        scheduler.pause_job(job_id)
        return {"success": True}

    @app.post("/api/scheduler/jobs/{job_id}/resume")
    async def resume_job(job_id: str):
        """恢复任务"""
        scheduler.resume_job(job_id)
        return {"success": True}

    return app


# 创建应用实例
app = create_app()


def main():
    """运行Web服务器"""
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
