from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import (
    EmailResponse,
    EventResponse,
    SettingsResponse,
    SettingsUpdateRequest,
    SyncRequest,
)
from app.config import settings
from app.db import Email, Event, Settings
from app.imap import IMAPClient, sync_emails_to_db
from app.mailer import mailer
from app.parser import EmailParser, process_unprocessed_emails
from app.scheduler import scheduler
from app.logger import Logger

logger = Logger.get("routes_core")


router = APIRouter()


# ── Emails ────────────────────────────────────────────────────────────────────

@router.get("/emails", response_model=List[EmailResponse])
async def get_emails(
    skip: int = 0,
    limit: int = 20,
    category: Optional[str] = None,
    processed: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Email)
    if category:
        query = query.filter(Email.category == category)
    if processed is not None:
        query = query.filter(Email.is_processed == processed)
    return query.order_by(Email.date.desc()).offset(skip).limit(limit).all()


@router.get("/emails/{email_id}", response_model=EmailResponse)
async def get_email(email_id, db: Session = Depends(get_db)):
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="邮件不存在")
    return email


@router.post("/emails/sync")
async def sync_emails(request: SyncRequest):
    result = sync_emails_to_db(days=request.days, limit=request.limit)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["errors"])
    return result


@router.post("/emails/{email_id}/parse")
async def parse_email(email_id):
    parser = EmailParser()
    success = parser.parse_and_save(email_id)
    if not success:
        raise HTTPException(status_code=500, detail="解析失败")
    return {"success": True}


@router.post("/emails/parse-all")
async def parse_all_emails():
    return process_unprocessed_emails()


# ── Events ────────────────────────────────────────────────────────────────────

@router.get("/events", response_model=List[EventResponse])
async def get_events(
    skip: int = 0,
    limit: int = 20,
    event_type: Optional[str] = None,
    important: Optional[bool] = None,
    rsvp_status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    from sqlalchemy.orm import joinedload

    query = db.query(Event).options(joinedload(Event.email))
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if important is not None:
        # 映射 important 布尔值到 status 字段
        status_filter = "important" if important else "pending"
        query = query.filter(Event.status == status_filter)
    if rsvp_status:
        query = query.filter(Event.rsvp_status == rsvp_status)

    query = query.order_by(
        case((Event.start_time.is_(None), 1), else_=0),
        Event.start_time.desc().nullslast(),
    )

    events = query.offset(skip).limit(limit).all()

    return [
        {
            "id": event.id,
            "email_id": event.email_id,
            "event_type": event.event_type,
            "title": event.title,
            "description": event.description,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "location": event.location,
            "status": event.status,
            "organizer": event.organizer,
            "attendees": event.attendees,
            "rsvp_status": event.rsvp_status,
            "meeting_link": event.meeting_link,
            "email_subject": event.email.subject if event.email else None,
            "email_sender": event.email.sender if event.email else None,
        }
        for event in events
    ]


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    return event


@router.delete("/events/{event_id}")
async def delete_event(event_id, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="浜嬩欢涓嶅瓨鍦?")

    db.query(Event).filter(Event.id == event_id).delete()
    db.commit()
    return {"success": True, "event_id": str(event_id)}


@router.put("/events/{event_id}/rsvp")
async def update_event_rsvp(
    event_id,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    更新事件的 RSVP 状态。

    Args:
        event_id: 事件 UUID
        request body: {"rsvp_status": "accepted"|"declined"|"tentative"}
    """
    rsvp_status = request.get("rsvp_status") if isinstance(request, dict) else None
    valid_statuses = ["accepted", "declined", "tentative"]
    if rsvp_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"无效的 rsvp_status，可选值：{valid_statuses}"
        )

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    event.rsvp_status = rsvp_status
    db.commit()
    logger.info(f"RSVP 更新成功: event_id={event_id}, rsvp_status={rsvp_status}")

    return {
        "success": True,
        "event_id": str(event_id),
        "rsvp_status": rsvp_status
    }


# ── Scheduler ────────────────────────────────────────────────────────────────

@router.get("/scheduler/jobs")
async def get_scheduler_jobs():
    return scheduler.get_jobs()


@router.post("/scheduler/trigger-sync")
async def trigger_sync():
    result = scheduler.trigger_sync()
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["errors"])
    return result


@router.post("/scheduler/trigger-parse")
async def trigger_parse():
    return scheduler.trigger_parse()


# ── Mailer ───────────────────────────────────────────────────────────────────

@router.post("/mailer/send-daily-summary")
async def send_daily_summary(to_email: Optional[str] = None):
    success = mailer.send_daily_summary(to_email)
    if not success:
        raise HTTPException(status_code=500, detail="发送失败")
    return {"success": True}


@router.post("/mailer/send-event-notification/{event_id}")
async def send_event_notification(event_id, to_email: Optional[str] = None):
    success = mailer.send_event_notification(event_id, to_email)
    if not success:
        raise HTTPException(status_code=500, detail="发送失败")
    return {"success": True}


# ── Settings ────────────────────────────────────────────────────────────────

def _get_setting_from_db(db: Session, key: str) -> Optional[str]:
    record = db.query(Settings).filter(Settings.key == key).first()
    return record.value if record else None


def _load_settings_from_db(db: Session) -> dict:
    return {
        "check_interval": _get_setting_from_db(db, "check_interval"),
        "scheduled_send_hour": _get_setting_from_db(db, "scheduled_send_hour"),
        "scheduled_send_minute": _get_setting_from_db(db, "scheduled_send_minute"),
        "categories": _get_setting_from_db(db, "categories"),
    }


def _get_effective_settings(db: Session) -> SettingsResponse:
    db_settings = _load_settings_from_db(db)

    check_interval = db_settings["check_interval"]
    scheduled_send_hour = db_settings["scheduled_send_hour"]
    scheduled_send_minute = db_settings["scheduled_send_minute"]
    categories = db_settings["categories"]

    if check_interval is None:
        check_interval = settings.CHECK_INTERVAL_MINUTES
    else:
        check_interval = int(check_interval)

    if scheduled_send_hour is None:
        scheduled_send_hour = settings.SCHEDULED_SEND_HOUR
    else:
        scheduled_send_hour = int(scheduled_send_hour)

    if scheduled_send_minute is None:
        scheduled_send_minute = settings.SCHEDULED_SEND_MINUTE
    else:
        scheduled_send_minute = int(scheduled_send_minute)

    if categories is None:
        categories = settings.event_categories_list
    else:
        categories = json.loads(categories)

    return SettingsResponse(
        categories=categories,
        check_interval=check_interval,
        scheduled_send_hour=scheduled_send_hour,
        scheduled_send_minute=scheduled_send_minute,
    )


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(db: Session = Depends(get_db)):
    return _get_effective_settings(db)


@router.put("/settings")
async def update_settings(request: SettingsUpdateRequest, db: Session = Depends(get_db)):
    settings_to_save = {
        "check_interval": request.check_interval,
        "scheduled_send_hour": request.scheduled_send_hour,
        "scheduled_send_minute": request.scheduled_send_minute,
        "categories": json.dumps(request.categories) if request.categories else None,
    }

    for key, value in settings_to_save.items():
        if value is not None:
            record = db.query(Settings).filter(Settings.key == key).first()
            if record:
                record.value = str(value)
            else:
                db.add(Settings(key=key, value=str(value)))

    db.commit()
    return {"success": True, "message": "设置已保存"}


@router.post("/settings/test-connection")
async def test_imap_connection():
    try:
        client = IMAPClient()
        success = client.connect()
        client.disconnect()
        if not success:
            raise HTTPException(status_code=500, detail="连接失败")
        return {"success": True, "message": "连接成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"连接失败: {str(e)}")
