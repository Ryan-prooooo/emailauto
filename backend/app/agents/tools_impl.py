"""
Function Calling 工具实现 - 15个工具函数
"""
from typing import Any, Dict, List, Optional
import logging
from app.agents.tools import Tool, get_registry
from app.db import Email, Event, SessionLocal

logger = logging.getLogger(__name__)


# ================ 查询类工具 ================

def get_emails_func(
    limit: int = 20,
    skip: int = 0,
    category: Optional[str] = None,
    processed: Optional[bool] = None,
    important: Optional[bool] = None
) -> Dict:
    """获取邮件列表"""
    db = SessionLocal()
    try:
        query = db.query(Email)
        if category:
            query = query.filter(Email.category == category)
        if processed is not None:
            query = query.filter(Email.processed == processed)
        if important is not None:
            query = query.join(Event).filter(Event.important == important)
        
        total = query.count()
        emails = query.order_by(Email.received_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "total": total,
            "emails": [
                {
                    "id": e.id,
                    "subject": e.subject,
                    "sender": e.sender,
                    "sender_email": e.sender_email,
                    "received_at": e.received_at.isoformat() if e.received_at else None,
                    "category": e.category,
                    "summary": e.summary,
                    "processed": e.processed
                }
                for e in emails
            ]
        }
    finally:
        db.close()


def get_email_detail_func(email_id: int) -> Dict:
    """获取邮件详情"""
    db = SessionLocal()
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return {"error": "邮件不存在"}
        
        events = db.query(Event).filter(Event.email_id == email_id).all()
        
        return {
            "id": email.id,
            "message_id": email.message_id,
            "subject": email.subject,
            "sender": email.sender,
            "sender_email": email.sender_email,
            "recipient": email.recipient,
            "content_text": email.content_text[:500] if email.content_text else None,
            "content_html": email.content_html[:500] if email.content_html else None,
            "received_at": email.received_at.isoformat() if email.received_at else None,
            "category": email.category,
            "summary": email.summary,
            "processed": email.processed,
            "is_read": email.is_read,
            "events": [
                {
                    "id": ev.id,
                    "title": ev.title,
                    "event_type": ev.event_type,
                    "important": ev.important
                }
                for ev in events
            ]
        }
    finally:
        db.close()


def get_events_func(
    limit: int = 20,
    skip: int = 0,
    event_type: Optional[str] = None,
    important: Optional[bool] = None,
    actionable: Optional[bool] = None
) -> Dict:
    """获取事件列表"""
    db = SessionLocal()
    try:
        query = db.query(Event)
        if event_type:
            query = query.filter(Event.event_type == event_type)
        if important is not None:
            query = query.filter(Event.important == important)
        if actionable is not None:
            query = query.filter(Event.actionable == actionable)
        
        total = query.count()
        events = query.order_by(Event.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "total": total,
            "events": [
                {
                    "id": e.id,
                    "email_id": e.email_id,
                    "event_type": e.event_type,
                    "title": e.title,
                    "description": e.description,
                    "event_time": e.event_time.isoformat() if e.event_time else None,
                    "location": e.location,
                    "important": e.important,
                    "actionable": e.actionable,
                    "created_at": e.created_at.isoformat() if e.created_at else None
                }
                for e in events
            ]
        }
    finally:
        db.close()


def get_event_detail_func(event_id: int) -> Dict:
    """获取事件详情"""
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return {"error": "事件不存在"}
        
        email = db.query(Email).filter(Email.id == event.email_id).first() if event.email_id else None
        
        return {
            "id": event.id,
            "email_id": event.email_id,
            "event_type": event.event_type,
            "title": event.title,
            "description": event.description,
            "event_time": event.event_time.isoformat() if event.event_time else None,
            "location": event.location,
            "important": event.important,
            "actionable": event.actionable,
            "action_items": event.action_items,
            "processed": event.processed,
            "notification_sent": event.notification_sent,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "email": {
                "subject": email.subject,
                "sender": email.sender
            } if email else None
        }
    finally:
        db.close()


# ================ 同步类工具 ================

def sync_emails_func(days: int = 7, limit: int = 100) -> Dict:
    """同步邮件"""
    from app.imap import sync_emails_to_db
    result = sync_emails_to_db(days=days, limit=limit)
    return result


def parse_email_func(email_id: int) -> Dict:
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

def send_email_func(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None
) -> Dict:
    """发送邮件"""
    from app.mailer import mailer
    # Mailer.send_email 不支持 cc 参数，暂时忽略
    success = mailer.send_email(to, subject, body)
    return {"success": success, "to": to, "subject": subject}


def send_daily_summary_func(to_email: Optional[str] = None) -> Dict:
    """发送每日摘要"""
    from app.mailer import mailer
    success = mailer.send_daily_summary(to_email)
    return {"success": success, "action": "daily_summary"}


def send_notification_func(event_id: int, to_email: Optional[str] = None) -> Dict:
    """发送事件通知"""
    from app.mailer import mailer
    success = mailer.send_event_notification(event_id, to_email)
    return {"success": success, "event_id": event_id}


# ================ 设置类工具 ================

def get_settings_func() -> Dict:
    """获取设置"""
    from app.api import _get_effective_settings
    from app.db import get_db
    db = next(get_db())
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
    from app.db import UserSettings, SessionLocal
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
                record = db.query(UserSettings).filter(UserSettings.key == key).first()
                if record:
                    record.value = str(value)
                else:
                    db.add(UserSettings(key=key, value=str(value)))
        
        db.commit()
        return {"success": True, "updated": [k for k, v in updates.items() if v is not None]}
    finally:
        db.close()


def get_scheduler_status_func() -> Dict:
    """获取调度器状态"""
    from app.scheduler import scheduler
    jobs = scheduler.get_jobs()
    return {"jobs": jobs, "running": scheduler.running if hasattr(scheduler, 'running') else True}


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
                    "important": {"type": "boolean", "description": "是否重要"}
                }
            },
            func=get_emails_func
        ),
        Tool(
            name="get_email_detail",
            description="获取指定邮件的详细信息，包括邮件内容和关联事件",
            parameters={
                "type": "object",
                "properties": {
                    "email_id": {"type": "integer", "description": "邮件ID"}
                },
                "required": ["email_id"]
            },
            func=get_email_detail_func
        ),
        Tool(
            name="get_events",
            description="获取事件列表，支持分页和过滤",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回数量，默认20"},
                    "skip": {"type": "integer", "description": "跳过数量，默认0"},
                    "event_type": {"type": "string", "description": "事件类型过滤"},
                    "important": {"type": "boolean", "description": "是否重要"},
                    "actionable": {"type": "boolean", "description": "是否可操作"}
                }
            },
            func=get_events_func
        ),
        Tool(
            name="get_event_detail",
            description="获取指定事件的详细信息，包括关联邮件",
            parameters={
                "type": "object",
                "properties": {
                    "event_id": {"type": "integer", "description": "事件ID"}
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
            description="使用AI解析指定邮件，提取事件信息",
            parameters={
                "type": "object",
                "properties": {
                    "email_id": {"type": "integer", "description": "邮件ID"}
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
                    "cc": {"type": "string", "description": "抄送人（可选）"}
                },
                "required": ["to", "subject", "body"]
            },
            func=send_email_func
        ),
        Tool(
            name="send_daily_summary",
            description="发送每日邮件摘要给用户",
            parameters={
                "type": "object",
                "properties": {
                    "to_email": {"type": "string", "description": "收件人邮箱（可选，默认发送到配置邮箱）"}
                }
            },
            func=send_daily_summary_func
        ),
        Tool(
            name="send_notification",
            description="发送指定事件的通知给用户",
            parameters={
                "type": "object",
                "properties": {
                    "event_id": {"type": "integer", "description": "事件ID"},
                    "to_email": {"type": "string", "description": "收件人邮箱（可选）"}
                },
                "required": ["event_id"]
            },
            func=send_notification_func
        ),
        Tool(
            name="get_settings",
            description="获取当前系统设置",
            parameters={
                "type": "object",
                "properties": {}
            },
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
            parameters={
                "type": "object",
                "properties": {}
            },
            func=get_scheduler_status_func
        ),
    ]
    
    for tool in tools:
        registry.register(tool)
    
    logger.info(f"Registered {len(tools)} tools")
