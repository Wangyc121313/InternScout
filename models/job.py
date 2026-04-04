from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, JSON, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Job(Base):
    """职位信息模型"""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    location = Column(String(100), nullable=True, index=True)
    salary = Column(String(100), nullable=True)
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    requirements = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    # 标签和分类
    tags = Column(JSON, default=list)
    category = Column(String(50), nullable=True)
    job_type = Column(String(50), default="实习")  # 实习/校招/社招

    # 来源信息
    source = Column(String(50), nullable=False, index=True)  # shixiseng, boss_zhipin等
    url = Column(String(500), nullable=True, unique=True)
    source_id = Column(String(100), nullable=True)  # 原始ID

    # 时间信息
    posted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 状态
    is_active = Column(Integer, default=1)  # 1=有效, 0=已下架
    is_notified = Column(Integer, default=0)  # 是否已发送通知

    __table_args__ = (
        Index('ix_jobs_source_url', 'source', 'url'),
        Index('ix_jobs_location_type', 'location', 'job_type'),
    )

    def __repr__(self):
        return f"<Job(id={self.id}, title='{self.title}', company='{self.company}')>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "salary": self.salary,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "requirements": self.requirements,
            "description": self.description,
            "tags": self.tags,
            "category": self.category,
            "job_type": self.job_type,
            "source": self.source,
            "url": self.url,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": bool(self.is_active),
        }
