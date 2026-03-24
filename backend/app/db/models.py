"""
数据库模型
Email: 原始邮件存储
Event: 结构化事件
Reminder: 提醒记录
SyncStatus: 同步状态
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base  # Base 定义在 database，避免循环导入


class Email(Base):
    """原始邮件存储"""

    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(500), unique=True, index=True, nullable=False)
    subject = Column(String(500))
    sender = Column(String(255))
    sender_email = Column(String(255))
    recipient = Column(String(255))
    content_text = Column(Text)
    content_html = Column(Text)
    received_at = Column(DateTime)
    processed = Column(Boolean, default=False)
    category = Column(String(50))
    summary = Column(Text)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    events = relationship("Event", back_populates="email", cascade="all, delete-orphan")


class Event(Base):
    """结构化事件"""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"))
    event_type = Column(String(50))  # 账单、预约、物流、出行、通知、其他
    title = Column(String(255))
    description = Column(Text)
    event_time = Column(DateTime)
    location = Column(String(255))
    important = Column(Boolean, default=False)
    actionable = Column(Boolean, default=False)
    action_items = Column(Text)  # JSON string
    processed = Column(Boolean, default=False)
    notification_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    email = relationship("Email", back_populates="events")
    reminders = relationship("Reminder", back_populates="event", cascade="all, delete-orphan")


class Reminder(Base):
    """提醒记录"""

    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    remind_at = Column(DateTime, nullable=False)
    message = Column(Text)
    sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    event = relationship("Event", back_populates="reminders")


class SyncStatus(Base):
    """同步状态"""

    __tablename__ = "sync_status"

    id = Column(Integer, primary_key=True, index=True)
    last_sync_time = Column(DateTime)
    last_uid = Column(Integer, default=0)
    total_emails = Column(Integer, default=0)
    status = Column(String(50))  # success, failed, in_progress
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


class UserSettings(Base):
    """用户设置（键值存储，兼容现有逻辑）"""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ChatSession(Base):
    """AI对话会话"""

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))  # 会话标题
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """AI对话消息"""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    role = Column(String(20))  # user, assistant
    content = Column(Text)
    memory_type = Column(String(20), default="recent")  # 记忆类型：recent=近期, summarized=已摘要
    summary = Column(Text, nullable=True)  # 长期记忆摘要
    created_at = Column(DateTime, default=datetime.now)

    session = relationship("ChatSession", back_populates="messages")
