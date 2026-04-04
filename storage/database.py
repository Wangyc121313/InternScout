import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from models.job import Base as JobBase
from models.company import Base as CompanyBase
from models.interview import Base as InterviewBase
from utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    """数据库连接管理器"""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "sqlite:///./data/internscout.db"
        )
        self.engine = None
        self.SessionLocal = None
        self._init_engine()

    def _init_engine(self):
        """初始化数据库引擎"""
        if self.database_url.startswith("sqlite"):
            # SQLite 配置
            self.engine = create_engine(
                self.database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False,
            )
        else:
            # PostgreSQL 或其他数据库
            self.engine = create_engine(
                self.database_url,
                pool_size=10,
                max_overflow=20,
                echo=False,
            )

        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        logger.info(f"Database engine initialized: {self.database_url}")

    def create_tables(self):
        """创建所有表"""
        # 确保数据目录存在
        if self.database_url.startswith("sqlite"):
            db_path = self.database_url.replace("sqlite:///", "")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

        JobBase.metadata.create_all(bind=self.engine)
        CompanyBase.metadata.create_all(bind=self.engine)
        InterviewBase.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")

    def drop_tables(self):
        """删除所有表"""
        JobBase.metadata.drop_all(bind=self.engine)
        CompanyBase.metadata.drop_all(bind=self.engine)
        InterviewBase.metadata.drop_all(bind=self.engine)
        logger.info("Database tables dropped")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """获取数据库会话的上下文管理器"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def get_db(self) -> Generator[Session, None, None]:
        """FastAPI 依赖使用的生成器"""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()


# 全局数据库实例
db = Database()
