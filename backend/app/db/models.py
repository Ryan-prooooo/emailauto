"""
数据库模型 - 对齐到 init.sql 实际表结构
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Email(Base):
    """原始邮件存储"""

    __tablename__ = "emails"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    message_id = Column(String(500), unique=True, nullable=False)
    subject = Column(String(1000))
    sender = Column(String(500))
    recipient = Column(String(500))
    date = Column(DateTime(timezone=True))
    body_text = Column(Text)
    body_html = Column(Text)
    category = Column(String(50))
    is_read = Column(Boolean, default=False)
    is_processed = Column(Boolean, default=False)
    parsed_at = Column(DateTime(timezone=True))
    raw_content = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    events = relationship("Event", back_populates="email", cascade="all, delete-orphan")


class Event(Base):
    """结构化事件"""

    __tablename__ = "events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email_id = Column(PGUUID(as_uuid=True), ForeignKey("emails.id", ondelete="CASCADE"))
    title = Column(String(500), nullable=False)
    description = Column(Text)
    event_type = Column(String(50))
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    location = Column(String(500))
    status = Column(String(20), default="pending")
    organizer = Column(String(500))
    attendees = Column(Text)
    rsvp_status = Column(String(20), default="pending")
    meeting_link = Column(String(1000))
    calendar_event_id = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    email = relationship("Email", back_populates="events")


class Settings(Base):
    """用户设置（键值存储）"""

    __tablename__ = "settings"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    description = Column(String(500))
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)


class ChatMessage(Base):
    """AI对话消息"""

    __tablename__ = "chat_messages"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(String(100))
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(String(20))
    agent_name = Column(String(50))
    meta_data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    memory_type = Column(String(20), default="recent")
    summary = Column(Text)
