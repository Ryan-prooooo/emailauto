from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.api.deps import serialize_datetime


class EmailResponse(BaseModel):
    id: int
    message_id: str
    subject: str
    sender: str
    sender_email: str
    received_at: datetime
    category: Optional[str]
    summary: Optional[str]
    processed: bool

    model_config = {"from_attributes": True, "json_encoders": {datetime: serialize_datetime}}


class EventResponse(BaseModel):
    id: int
    email_id: int
    event_type: str
    title: str
    description: Optional[str]
    event_time: Optional[datetime]
    location: Optional[str]
    important: bool
    actionable: bool
    action_items: Optional[str]
    processed: bool
    email_subject: Optional[str] = None
    email_sender: Optional[str] = None

    model_config = {"from_attributes": True, "json_encoders": {datetime: serialize_datetime}}


class SyncRequest(BaseModel):
    days: int = 7
    limit: int = 100


class SettingsResponse(BaseModel):
    categories: List[str]
    check_interval: int
    scheduled_send_hour: int
    scheduled_send_minute: int


class SettingsUpdateRequest(BaseModel):
    check_interval: Optional[int] = None
    scheduled_send_hour: Optional[int] = None
    scheduled_send_minute: Optional[int] = None
    categories: Optional[List[str]] = None


class ChatMessageRequest(BaseModel):
    session_id: Optional[int] = None
    message: str
    force_intent: Optional[str] = None  # 强制使用指定意图（如 "react" 启用 ReAct 推理模式）


class ChatMessageResponse(BaseModel):
    session_id: int
    messages: List[dict]


class LangGraphChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = None
    context: Optional[Dict[str, Any]] = None
    force_intent: Optional[str] = None  # 强制使用指定意图（如 "react"）

