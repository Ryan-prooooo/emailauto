"""
数据库模块：连接、会话与模型
"""
from app.db.database import Base, SessionLocal, engine, get_db, init_db
from app.db.models import ChatMessage, Email, Event, Settings

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
    "Email",
    "Event",
    "Settings",
    "ChatMessage",
]

# 兼容旧名称
Reminder = None  # 已移除，数据库无此表
SyncStatus = None  # 已移除，数据库无此表
UserSettings = Settings  # 别名兼容
ChatSession = None  # 已移除，session_id 在 ChatMessage 中
