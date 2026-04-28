"""
Function Calling 工具实现
"""
from typing import Any, Dict, List, Optional
from app.agents.tools import Tool, get_registry
from app.api.deps import serialize_datetime
from app.db import ChatMessage, Email, Event, SessionLocal, Settings
from app.logger import Logger

logger = Logger.get("tools_impl")


# ================ 查询类工具 ================

def get_emails_func(
    limit: int = 20,
    skip: int = 0,
    category: Optional[str] = None,
    processed: Optional[bool] = None,
) -> Dict:
    """获取邮件列表"""
    db = SessionLocal()
    try:
        query = db.query(Email)
        if category:
            query = query.filter(Email.category == category)
        if processed is not None:
            query = query.filter(Email.is_processed == processed)

        total = query.count()
        emails = query.order_by(Email.date.desc()).offset(skip).limit(limit).all()

        return {
            "total": total,
            "emails": [
                {
                    "id": str(e.id),
                    "subject": e.subject,
                    "sender": e.sender,
                    "date": serialize_datetime(e.date),
                    "category": e.category,
                    "is_processed": e.is_processed,
                    "is_read": e.is_read,
                }
                for e in emails
            ]
        }
    finally:
        db.close()


def get_email_detail_func(email_id: str) -> Dict:
    """获取邮件详情"""
    db = SessionLocal()
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return {"error": "邮件不存在"}

        events = db.query(Event).filter(Event.email_id == email_id).all()

        return {
            "id": str(email.id),
            "message_id": email.message_id,
            "subject": email.subject,
            "sender": email.sender,
            "recipient": email.recipient,
            "body_text": email.body_text[:500] if email.body_text else None,
            "body_html": email.body_html[:500] if email.body_html else None,
            "date": serialize_datetime(email.date),
            "category": email.category,
            "is_processed": email.is_processed,
            "is_read": email.is_read,
            "events": [
                {"id": str(ev.id), "title": ev.title, "event_type": ev.event_type}
                for ev in events
            ]
        }
    finally:
        db.close()


def get_events_func(
    limit: int = 20,
    skip: int = 0,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    rsvp_status: Optional[str] = None,
) -> Dict:
    """获取事件列表

    Args:
        limit: 返回数量限制
        skip: 跳过数量
        event_type: 按事件类型筛选（如 meeting）
        status: 按状态筛选（pending / important）
        rsvp_status: 按 RSVP 状态筛选（pending / accepted / declined / tentative）
    """
    db = SessionLocal()
    try:
        query = db.query(Event)
        if event_type:
            query = query.filter(Event.event_type == event_type)
        if status:
            query = query.filter(Event.status == status)
        if rsvp_status:
            query = query.filter(Event.rsvp_status == rsvp_status)

        total = query.count()
        events = query.order_by(Event.created_at.desc()).offset(skip).limit(limit).all()

        return {
            "total": total,
            "events": [
                {
                    "id": str(e.id),
                    "email_id": str(e.email_id) if e.email_id else None,
                    "event_type": e.event_type,
                    "title": e.title,
                    "description": e.description,
                    "start_time": serialize_datetime(e.start_time),
                    "end_time": serialize_datetime(e.end_time),
                    "location": e.location,
                    "status": e.status,
                    "organizer": e.organizer,
                    "attendees": e.attendees,
                    "rsvp_status": e.rsvp_status,
                    "meeting_link": e.meeting_link,
                    "created_at": serialize_datetime(e.created_at)
                }
                for e in events
            ]
        }
    finally:
        db.close()


def get_event_detail_func(event_id: str) -> Dict:
    """获取事件详情"""
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return {"error": "事件不存在"}

        return {
            "id": str(event.id),
            "email_id": str(event.email_id) if event.email_id else None,
            "event_type": event.event_type,
            "title": event.title,
            "description": event.description,
            "start_time": serialize_datetime(event.start_time),
            "end_time": serialize_datetime(event.end_time),
            "location": event.location,
            "status": event.status,
            "organizer": event.organizer,
            "attendees": event.attendees,
            "rsvp_status": event.rsvp_status,
            "meeting_link": event.meeting_link,
            "created_at": serialize_datetime(event.created_at),
        }
    finally:
        db.close()


# ================ 同步类工具 ================

def sync_emails_func(days: int = 7, limit: int = 100) -> Dict:
    """同步邮件"""
    from app.imap import sync_emails_to_db
    result = sync_emails_to_db(days=days, limit=limit)
    return result


def parse_email_func(email_id: str) -> Dict:
    """解析单封邮件"""
    from app.parser import EmailParser
    parser = EmailParser()
    success = parser.parse_and_save(email_id)
    return {"success": success, "email_id": email_id}


def parse_all_emails_func(limit: int = 50) -> Dict:
    """批量解析未处理邮件"""
    from app.parser import process_unprocessed_emails
    result = process_unprocessed_emails()
    return result


# ================ 发送类工具 ================

def send_email_func(to: str, subject: str, body: str) -> Dict:
    """发送邮件"""
    from app.mailer import mailer
    success = mailer.send_email(to, subject, body)
    return {"success": success, "to": to, "subject": subject}


def send_daily_summary_func(to_email: Optional[str] = None) -> Dict:
    """发送每日摘要"""
    from app.mailer import mailer
    success = mailer.send_daily_summary(to_email)
    return {"success": success, "action": "daily_summary"}


def send_notification_func(event_id: str, to_email: Optional[str] = None) -> Dict:
    """发送事件通知"""
    from app.mailer import mailer
    success = mailer.send_event_notification(event_id, to_email)
    return {"success": success, "event_id": event_id}


# ================ 设置类工具 ================

def get_settings_func() -> Dict:
    """获取设置"""
    from app.api.routes_core import _get_effective_settings
    from app.db import get_db as _get_db
    db = next(_get_db())
    try:
        settings = _get_effective_settings(db)
        return {
            "categories": settings.categories,
            "check_interval": settings.check_interval,
            "scheduled_send_hour": settings.scheduled_send_hour,
            "scheduled_send_minute": settings.scheduled_send_minute
        }
    finally:
        db.close()


def update_settings_func(
    check_interval: Optional[int] = None,
    scheduled_send_hour: Optional[int] = None,
    scheduled_send_minute: Optional[int] = None,
    categories: Optional[List[str]] = None
) -> Dict:
    """更新设置"""
    import json
    db = SessionLocal()
    try:
        updates = {
            "check_interval": check_interval,
            "scheduled_send_hour": scheduled_send_hour,
            "scheduled_send_minute": scheduled_send_minute,
            "categories": json.dumps(categories) if categories else None
        }

        for key, value in updates.items():
            if value is not None:
                record = db.query(Settings).filter(Settings.key == key).first()
                if record:
                    record.value = str(value)
                else:
                    db.add(Settings(key=key, value=str(value)))

        db.commit()
        return {"success": True, "updated": [k for k, v in updates.items() if v is not None]}
    finally:
        db.close()


def get_scheduler_status_func() -> Dict:
    """获取调度器状态"""
    from app.scheduler import scheduler
    jobs = scheduler.get_jobs()
    return {"jobs": jobs, "running": getattr(scheduler, 'running', True)}


# ================ 注册所有工具 ================

def register_all_tools():
    """注册所有工具到全局注册中心"""
    registry = get_registry()

    tools = [
        Tool(
            name="get_emails",
            description="获取邮件列表，支持分页和过滤",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回数量，默认20"},
                    "skip": {"type": "integer", "description": "跳过数量，默认0"},
                    "category": {"type": "string", "description": "邮件分类过滤"},
                    "processed": {"type": "boolean", "description": "是否已处理"},
                }
            },
            func=get_emails_func
        ),
        Tool(
            name="get_email_detail",
            description="获取指定邮件的详细信息",
            parameters={
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "邮件ID"}
                },
                "required": ["email_id"]
            },
            func=get_email_detail_func
        ),
        Tool(
            name="get_events",
            description="获取事件列表",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回数量，默认20"},
                    "skip": {"type": "integer", "description": "跳过数量，默认0"},
                    "event_type": {"type": "string", "description": "事件类型过滤（如 meeting）"},
                    "status": {"type": "string", "description": "事件状态过滤"},
                    "rsvp_status": {"type": "string", "description": "RSVP 状态过滤（pending / accepted / declined / tentative）"},
                }
            },
            func=get_events_func
        ),
        Tool(
            name="get_event_detail",
            description="获取指定事件的详细信息",
            parameters={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "事件ID"}
                },
                "required": ["event_id"]
            },
            func=get_event_detail_func
        ),
        Tool(
            name="sync_emails",
            description="从邮箱服务器同步新邮件到本地数据库",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "同步最近N天的邮件，默认7"},
                    "limit": {"type": "integer", "description": "最多同步数量，默认100"}
                }
            },
            func=sync_emails_func
        ),
        Tool(
            name="parse_email",
            description="使用AI解析指定邮件",
            parameters={
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "邮件ID"}
                },
                "required": ["email_id"]
            },
            func=parse_email_func
        ),
        Tool(
            name="parse_all_emails",
            description="批量解析所有未处理的邮件",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "最多处理数量，默认50"}
                }
            },
            func=parse_all_emails_func
        ),
        Tool(
            name="send_email",
            description="发送邮件给指定收件人",
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "收件人邮箱"},
                    "subject": {"type": "string", "description": "邮件主题"},
                    "body": {"type": "string", "description": "邮件正文"},
                },
                "required": ["to", "subject", "body"]
            },
            func=send_email_func
        ),
        Tool(
            name="send_daily_summary",
            description="发送每日邮件摘要",
            parameters={
                "type": "object",
                "properties": {
                    "to_email": {"type": "string", "description": "收件人邮箱（可选）"}
                }
            },
            func=send_daily_summary_func
        ),
        Tool(
            name="send_notification",
            description="发送事件通知",
            parameters={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "事件ID"},
                    "to_email": {"type": "string", "description": "收件人邮箱（可选）"}
                },
                "required": ["event_id"]
            },
            func=send_notification_func
        ),
        Tool(
            name="get_settings",
            description="获取当前系统设置",
            parameters={"type": "object", "properties": {}},
            func=get_settings_func
        ),
        Tool(
            name="update_settings",
            description="更新系统设置",
            parameters={
                "type": "object",
                "properties": {
                    "check_interval": {"type": "integer", "description": "邮件检查间隔（分钟）"},
                    "scheduled_send_hour": {"type": "integer", "description": "定时发送小时"},
                    "scheduled_send_minute": {"type": "integer", "description": "定时发送分钟"},
                    "categories": {"type": "array", "items": {"type": "string"}, "description": "事件分类列表"}
                }
            },
            func=update_settings_func
        ),
        Tool(
            name="get_scheduler_status",
            description="获取定时任务调度器的状态",
            parameters={"type": "object", "properties": {}},
            func=get_scheduler_status_func
        ),
    ]

    for tool in tools:
        registry.register(tool)

    logger.info(f"Registered {len(tools)} tools")
