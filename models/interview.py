from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Interview(Base):
    """面经信息模型"""
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 基本信息
    company = Column(String(255), nullable=False, index=True)
    position = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)

    # 面试结果和难度
    result = Column(String(50), nullable=True)  # 通过/未通过/等待中
    difficulty = Column(String(20), nullable=True)  # 简单/一般/困难
    experience = Column(String(20), nullable=True)  # 负面/中性/正面

    # 面试流程和问题
    process = Column(Text, nullable=True)  # 面试流程描述
    questions = Column(JSON, default=list)  # 面试问题列表

    # 作者信息
    author = Column(String(100), nullable=True)
    author_title = Column(String(100), nullable=True)  # 作者职位/身份

    # 统计信息
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)

    # 标签
    tags = Column(JSON, default=list)

    # 来源信息
    source = Column(String(50), nullable=False)  # xiaohongshu, nowcoder等
    url = Column(String(500), nullable=True)
    source_id = Column(String(100), nullable=True)

    # 时间信息
    posted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_interviews_company_position', 'company', 'position'),
        Index('ix_interviews_source_url', 'source', 'url'),
    )

    def __repr__(self):
        return f"<Interview(id={self.id}, company='{self.company}', position='{self.position}')>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "company": self.company,
            "position": self.position,
            "content": self.content,
            "result": self.result,
            "difficulty": self.difficulty,
            "experience": self.experience,
            "process": self.process,
            "questions": self.questions,
            "author": self.author,
            "author_title": self.author_title,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "tags": self.tags,
            "source": self.source,
            "url": self.url,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
