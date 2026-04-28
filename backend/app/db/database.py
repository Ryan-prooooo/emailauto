"""
数据库连接与会话
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

try:
    from app.core.config import settings
except Exception:
    from app.config import settings

Base = declarative_base()

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库（所有表由 init.sql 创建，跳过 ORM create_all）"""
    from app.db import models  # noqa: F401 - 仅注册模型到 Base.metadata，供迁移脚本使用
