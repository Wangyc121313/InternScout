from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Company(Base):
    """公司信息模型"""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, index=True)

    # 公司基本信息
    industry = Column(String(100), nullable=True)  # 行业
    size = Column(String(50), nullable=True)  # 公司规模
    stage = Column(String(50), nullable=True)  # 发展阶段：天使轮/A轮/上市等

    # 联系方式
    website = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)

    # 公司介绍
    description = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)

    # 标签和福利
    tags = Column(JSON, default=list)  # 公司标签
    benefits = Column(JSON, default=list)  # 福利待遇

    # 评分和评价
    rating = Column(Float, nullable=True)  # 综合评分
    rating_count = Column(Integer, default=0)  # 评价数量

    # 来源信息
    source = Column(String(50), nullable=True)
    source_id = Column(String(100), nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_companies_industry_size', 'industry', 'size'),
    )

    def __repr__(self):
        return f"<Company(id={self.id}, name='{self.name}')>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "industry": self.industry,
            "size": self.size,
            "stage": self.stage,
            "website": self.website,
            "address": self.address,
            "description": self.description,
            "logo_url": self.logo_url,
            "tags": self.tags,
            "benefits": self.benefits,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
