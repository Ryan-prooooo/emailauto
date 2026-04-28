from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.api.deps import serialize_datetime


class EmailResponse(BaseModel):
    id: UUID
    message_id: str
    subject: Optional[str]
    sender: Optional[str]
    recipient: Optional[str]
    date: Optional[datetime]
    body_text: Optional[str]
    body_html: Optional[str]
    category: Optional[str]
    is_read: bool
    is_processed: bool
    parsed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True, "json_encoders": {datetime: serialize_datetime}}


class EventResponse(BaseModel):
    id: UUID
    email_id: Optional[UUID]
    event_type: Optional[str]
    title: str
    description: Optional[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    location: Optional[str]
    status: str
    organizer: Optional[str] = None
    attendees: Optional[str] = None
    rsvp_status: Optional[str] = None
    meeting_link: Optional[str] = None
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
    session_id: Optional[str] = None
    message: str
    force_intent: Optional[str] = None


class ChatResumeRequest(BaseModel):
    thread_id: str
    confirmed: bool


class ChatMessageResponse(BaseModel):
    session_id: str
    messages: List[dict]
    status: str = "completed"
    thread_id: Optional[str] = None
    interrupt: Optional[Dict[str, Any]] = None


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    updated_at: str
