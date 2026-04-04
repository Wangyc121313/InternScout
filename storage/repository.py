from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import desc, func, and_
from sqlalchemy.orm import Session

from models.job import Job
from models.company import Company
from models.interview import Interview
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseRepository:
    """基础仓储类"""

    def __init__(self, session: Session):
        self.session = session


class JobRepository(BaseRepository):
    """职位数据操作"""

    def create(self, job_data: Dict[str, Any]) -> Job:
        """创建职位记录"""
        job = Job(**job_data)
        self.session.add(job)
        self.session.flush()
        logger.debug(f"Created job: {job.title} @ {job.company}")
        return job

    def get_by_id(self, job_id: int) -> Optional[Job]:
        """根据ID获取职位"""
        return self.session.query(Job).filter(Job.id == job_id).first()

    def get_by_url(self, url: str, source: str) -> Optional[Job]:
        """根据URL和来源获取职位（去重检查）"""
        return self.session.query(Job).filter(
            and_(Job.url == url, Job.source == source)
        ).first()

    def exists(self, url: str, source: str) -> bool:
        """检查职位是否已存在"""
        return self.get_by_url(url, source) is not None

    def list_jobs(
        self,
        skip: int = 0,
        limit: int = 20,
        location: str = None,
        company: str = None,
        keyword: str = None,
        source: str = None,
        is_active: bool = None,
    ) -> List[Job]:
        """列表查询"""
        query = self.session.query(Job)

        if location:
            query = query.filter(Job.location.contains(location))
        if company:
            query = query.filter(Job.company.contains(company))
        if keyword:
            query = query.filter(
                and_(
                    Job.title.contains(keyword),
                    Job.description.contains(keyword)
                )
            )
        if source:
            query = query.filter(Job.source == source)
        if is_active is not None:
            query = query.filter(Job.is_active == (1 if is_active else 0))

        return query.order_by(desc(Job.created_at)).offset(skip).limit(limit).all()

    def get_unnotified(self, limit: int = 100) -> List[Job]:
        """获取未通知的职位"""
        return self.session.query(Job).filter(
            Job.is_notified == 0,
            Job.is_active == 1
        ).order_by(desc(Job.created_at)).limit(limit).all()

    def mark_notified(self, job_ids: List[int]):
        """标记职位为已通知"""
        self.session.query(Job).filter(
            Job.id.in_(job_ids)
        ).update({"is_notified": 1}, synchronize_session=False)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.session.query(func.count(Job.id)).scalar()
        active = self.session.query(func.count(Job.id)).filter(Job.is_active == 1).scalar()

        # 按来源统计
        source_stats = self.session.query(
            Job.source, func.count(Job.id)
        ).group_by(Job.source).all()

        # 今日新增
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = self.session.query(func.count(Job.id)).filter(
            Job.created_at >= today
        ).scalar()

        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "today_new": today_count,
            "by_source": {s: c for s, c in source_stats},
        }

    def update(self, job_id: int, job_data: Dict[str, Any]) -> Optional[Job]:
        """更新职位信息"""
        job = self.get_by_id(job_id)
        if job:
            for key, value in job_data.items():
                setattr(job, key, value)
            self.session.flush()
        return job

    def delete(self, job_id: int) -> bool:
        """删除职位"""
        job = self.get_by_id(job_id)
        if job:
            self.session.delete(job)
            self.session.flush()
            return True
        return False


class CompanyRepository(BaseRepository):
    """公司数据操作"""

    def create(self, company_data: Dict[str, Any]) -> Company:
        """创建公司记录"""
        company = Company(**company_data)
        self.session.add(company)
        self.session.flush()
        return company

    def get_by_id(self, company_id: int) -> Optional[Company]:
        """根据ID获取公司"""
        return self.session.query(Company).filter(Company.id == company_id).first()

    def get_by_name(self, name: str) -> Optional[Company]:
        """根据名称获取公司"""
        return self.session.query(Company).filter(Company.name == name).first()

    def get_or_create(self, name: str, defaults: Dict[str, Any] = None) -> Company:
        """获取或创建公司"""
        company = self.get_by_name(name)
        if not company:
            data = defaults or {}
            data["name"] = name
            company = self.create(data)
        return company

    def list_companies(
        self,
        skip: int = 0,
        limit: int = 20,
        industry: str = None,
    ) -> List[Company]:
        """列表查询"""
        query = self.session.query(Company)
        if industry:
            query = query.filter(Company.industry == industry)
        return query.order_by(desc(Company.created_at)).offset(skip).limit(limit).all()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.session.query(func.count(Company.id)).scalar()

        # 按行业统计
        industry_stats = self.session.query(
            Company.industry, func.count(Company.id)
        ).group_by(Company.industry).all()

        return {
            "total": total,
            "by_industry": {i: c for i, c in industry_stats if i},
        }


class InterviewRepository(BaseRepository):
    """面经数据操作"""

    def create(self, interview_data: Dict[str, Any]) -> Interview:
        """创建面经记录"""
        interview = Interview(**interview_data)
        self.session.add(interview)
        self.session.flush()
        return interview

    def get_by_id(self, interview_id: int) -> Optional[Interview]:
        """根据ID获取面经"""
        return self.session.query(Interview).filter(
            Interview.id == interview_id
        ).first()

    def get_by_url(self, url: str, source: str) -> Optional[Interview]:
        """根据URL和来源获取面经（去重检查）"""
        return self.session.query(Interview).filter(
            and_(Interview.url == url, Interview.source == source)
        ).first()

    def exists(self, url: str, source: str) -> bool:
        """检查面经是否已存在"""
        return self.get_by_url(url, source) is not None

    def list_interviews(
        self,
        skip: int = 0,
        limit: int = 20,
        company: str = None,
        position: str = None,
        source: str = None,
    ) -> List[Interview]:
        """列表查询"""
        query = self.session.query(Interview)

        if company:
            query = query.filter(Interview.company.contains(company))
        if position:
            query = query.filter(Interview.position.contains(position))
        if source:
            query = query.filter(Interview.source == source)

        return query.order_by(desc(Interview.created_at)).offset(skip).limit(limit).all()

    def get_by_company(self, company: str, limit: int = 20) -> List[Interview]:
        """获取指定公司的面经"""
        return self.session.query(Interview).filter(
            Interview.company == company
        ).order_by(desc(Interview.created_at)).limit(limit).all()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.session.query(func.count(Interview.id)).scalar()

        # 按来源统计
        source_stats = self.session.query(
            Interview.source, func.count(Interview.id)
        ).group_by(Interview.source).all()

        # 按公司统计（前10）
        company_stats = self.session.query(
            Interview.company, func.count(Interview.id)
        ).group_by(Interview.company).order_by(
            desc(func.count(Interview.id))
        ).limit(10).all()

        return {
            "total": total,
            "by_source": {s: c for s, c in source_stats},
            "top_companies": [{"name": n, "count": c} for n, c in company_stats],
        }
