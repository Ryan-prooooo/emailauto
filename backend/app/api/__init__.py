from pathlib import Path
import json

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.db import Email, Event, SyncStatus, ChatSession, ChatMessage, UserSettings, get_db, init_db
from app.imap import sync_emails_to_db, IMAPClient
from app.parser import EmailParser, process_unprocessed_emails
from app.mailer import mailer
from app.scheduler import scheduler
from app.config import settings
from app.debug_logging import setup_debug_logging, _LOG_FILE

# 配置诊断日志
debug_logger = setup_debug_logging("api")
debug_logger.info(f"诊断日志文件: {_LOG_FILE}")
debug_logger.info("API 模块加载中...")

# API 路由（统一加 /api 前缀，与前端 baseURL 一致）
api_router = APIRouter()


# Pydantic 模型
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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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


# 创建 FastAPI 应用
app = FastAPI(
    title="QQ邮箱智能生活事件助手",
    description="智能分析QQ邮箱中的邮件，提取重要事件并推送通知",
    version="1.0.0"
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有 HTTP 请求"""
    debug_logger.info(f"<<< REQUEST: {request.method} {request.url.path}")
    response = await call_next(request)
    debug_logger.info(f">>> RESPONSE: {request.method} {request.url.path} -> {response.status_code}")
    return response


# 初始化数据库
@app.on_event("startup")
async def startup_event():
    debug_logger.info("=== 应用启动 ===")
    init_db()
    from app.db.migrate import run_migrations
    run_migrations()
    scheduler.start()
    debug_logger.info("启动完成，已注册路由:")
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            debug_logger.info(f"  - {list(route.methods)} {route.path}")
        elif hasattr(route, 'path'):
            debug_logger.info(f"  - {route.path}")


@app.on_event("shutdown")
async def shutdown_event():
    debug_logger.info("=== 应用关闭 ===")
    scheduler.stop()


# 前端静态目录（项目根目录下的 frontend）
# __file__ -> app/api/__init__.py -> parent*3 -> backend -> parent*4 -> 项目根
_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend"


# 根路由：跳转到前端页面
@app.get("/")
async def root():
    if _FRONTEND_DIR.exists() and (_FRONTEND_DIR / "index.html").exists():
        return FileResponse(_FRONTEND_DIR / "index.html")
    return {"message": "QQ邮箱智能生活事件助手 API", "version": "1.0.0"}


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# 邮件相关接口
@api_router.get("/emails", response_model=List[EmailResponse])
async def get_emails(
    skip: int = 0,
    limit: int = 20,
    category: Optional[str] = None,
    processed: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Email)
    if category:
        query = query.filter(Email.category == category)
    if processed is not None:
        query = query.filter(Email.processed == processed)
    return query.order_by(Email.received_at.desc()).offset(skip).limit(limit).all()


@api_router.get("/emails/{email_id}", response_model=EmailResponse)
async def get_email(email_id: int, db: Session = Depends(get_db)):
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="邮件不存在")
    return email


@api_router.post("/emails/sync")
async def sync_emails(request: SyncRequest):
    result = sync_emails_to_db(days=request.days, limit=request.limit)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["errors"])
    return result


@api_router.post("/emails/{email_id}/parse")
async def parse_email(email_id: int):
    parser = EmailParser()
    success = parser.parse_and_save(email_id)
    if not success:
        raise HTTPException(status_code=500, detail="解析失败")
    return {"success": True}


@api_router.post("/emails/parse-all")
async def parse_all_emails():
    result = process_unprocessed_emails()
    return result


# 事件相关接口
@api_router.get("/events", response_model=List[EventResponse])
async def get_events(
    skip: int = 0,
    limit: int = 20,
    event_type: Optional[str] = None,
    important: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Event)
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if important is not None:
        query = query.filter(Event.important == important)
    return query.order_by(Event.created_at.desc()).offset(skip).limit(limit).all()


@api_router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    return event


# 定时任务接口
@api_router.get("/scheduler/jobs")
async def get_scheduler_jobs():
    return scheduler.get_jobs()


@api_router.post("/scheduler/trigger-sync")
async def trigger_sync():
    result = scheduler.trigger_sync()
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["errors"])
    return result


@api_router.post("/scheduler/trigger-parse")
async def trigger_parse():
    result = scheduler.trigger_parse()
    return result


# 邮件发送接口
@api_router.post("/mailer/send-daily-summary")
async def send_daily_summary(to_email: Optional[str] = None):
    success = mailer.send_daily_summary(to_email)
    if not success:
        raise HTTPException(status_code=500, detail="发送失败")
    return {"success": True}


@api_router.post("/mailer/send-event-notification/{event_id}")
async def send_event_notification(event_id: int, to_email: Optional[str] = None):
    success = mailer.send_event_notification(event_id, to_email)
    if not success:
        raise HTTPException(status_code=500, detail="发送失败")
    return {"success": True}


# 设置接口

def _get_setting_from_db(db: Session, key: str) -> Optional[str]:
    """从数据库获取设置值"""
    record = db.query(UserSettings).filter(UserSettings.key == key).first()
    return record.value if record else None


def _load_settings_from_db(db: Session) -> dict:
    """从数据库加载设置，返回字典（不含的key返回None）"""
    return {
        "check_interval": _get_setting_from_db(db, "check_interval"),
        "scheduled_send_hour": _get_setting_from_db(db, "scheduled_send_hour"),
        "scheduled_send_minute": _get_setting_from_db(db, "scheduled_send_minute"),
        "categories": _get_setting_from_db(db, "categories"),
    }


def _get_effective_settings(db: Session) -> SettingsResponse:
    """获取有效设置：优先从数据库读取，不存在则用配置默认值"""
    db_settings = _load_settings_from_db(db)

    check_interval = db_settings["check_interval"]
    scheduled_send_hour = db_settings["scheduled_send_hour"]
    scheduled_send_minute = db_settings["scheduled_send_minute"]
    categories = db_settings["categories"]

    # 如果数据库没有，则用配置默认值
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
        scheduled_send_minute=scheduled_send_minute
    )


@api_router.get("/settings", response_model=SettingsResponse)
async def get_settings(db: Session = Depends(get_db)):
    return _get_effective_settings(db)


@api_router.put("/settings")
async def update_settings(request: SettingsUpdateRequest, db: Session = Depends(get_db)):
    """更新设置到数据库"""
    debug_logger.info(f">>> 调用 PUT /api/settings, data={request}")

    # 定义要保存的设置项
    settings_to_save = {
        "check_interval": request.check_interval,
        "scheduled_send_hour": request.scheduled_send_hour,
        "scheduled_send_minute": request.scheduled_send_minute,
        "categories": json.dumps(request.categories) if request.categories else None,
    }

    for key, value in settings_to_save.items():
        if value is not None:
            # 查找现有记录
            record = db.query(UserSettings).filter(UserSettings.key == key).first()
            if record:
                record.value = str(value)
            else:
                new_record = UserSettings(key=key, value=str(value))
                db.add(new_record)

    db.commit()
    debug_logger.info("设置已保存到数据库")

    return {"success": True, "message": "设置已保存"}


@api_router.post("/settings/test-connection")
async def test_imap_connection():
    debug_logger.info(">>> 调用 /api/settings/test-connection")
    debug_logger.info(f"IMAP 配置: host={settings.IMAP_HOST}, port={settings.IMAP_PORT}, email={settings.QQ_EMAIL}")
    
    try:
        client = IMAPClient()
        debug_logger.info("创建 IMAPClient 实例成功")
        
        success = client.connect()
        debug_logger.info(f"IMAP 连接结果: {success}")
        
        client.disconnect()
        debug_logger.info("IMAP 断开连接成功")
        
        if not success:
            debug_logger.error("IMAP 连接失败")
            raise HTTPException(status_code=500, detail="连接失败")
        
        debug_logger.info("<<< 返回成功")
        return {"success": True, "message": "连接成功"}
    except Exception as e:
        debug_logger.exception(f"IMAP 连接异常: {e}")
        raise HTTPException(status_code=500, detail=f"连接失败: {str(e)}")


# ============ AI 对话接口 ============

class ChatMessageRequest(BaseModel):
    session_id: Optional[int] = None
    message: str


class ChatMessageResponse(BaseModel):
    session_id: int
    messages: List[dict]


def _build_chat_system_prompt(long_term_summary: str, realtime_context: str) -> str:
    """构建对话系统提示词，融合长期记忆和实时上下文"""
    prompt_parts = [
        """你是一个智能邮件助手，可以回答用户关于邮件和事件的问题，并可以调用工具执行操作。"""
    ]

    # 1. 添加长期记忆摘要
    if long_term_summary:
        prompt_parts.append(f"\n【历史对话摘要】\n{long_term_summary}")

    # 2. 添加实时上下文
    if realtime_context:
        prompt_parts.append(f"\n【当前数据】\n{realtime_context}")

    # 3. 添加工具说明和重要提示
    prompt_parts.append("""
可用工具:
- 当用户需要查看邮件详情时，使用 get_email_detail 工具（需要提供 email_id）
- 当用户需要查看事件列表时，使用 get_events 工具
- 当用户需要生成邮件回复草稿时，使用 draft_email_reply 工具
- 当用户需要回复并发送邮件时，使用 reply_email 工具
- 当用户需要获取调度器状态时，使用 get_scheduler_status 工具
- 当用户问的是关于邮件或事件的问题，基于以上信息回答。

重要提示：
- 如果用户要求回复邮件，请先确认要回复的是哪封邮件（可以询问用户或从上下文推断邮件ID）
- 邮件ID是数字格式，如 ID:1, ID:2 等
- 生成回复草稿后，用户确认后才能发送
- 保持回答简洁明了。""")

    return "\n".join(prompt_parts)


@api_router.post("/chat", response_model=ChatMessageResponse)
async def chat(request: ChatMessageRequest, db: Session = Depends(get_db)):
    """AI对话接口 - 支持 Function Calling"""
    debug_logger.info(f">>> 调用 /api/chat, session_id={request.session_id}, message={request.message[:50]}...")

    try:
        from app.parser import EmailParser
        from app.agents.tools import get_registry
        from app.agents.memory import MemoryManager

        # 获取或创建会话
        if request.session_id:
            session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()
        if not request.session_id or not session:
            # 创建新会话
            session = ChatSession(title=request.message[:50] or "新对话")
            db.add(session)
            db.commit()
            db.refresh(session)
            debug_logger.info(f"创建新会话: {session.id}")

        # 使用记忆管理器处理消息
        memory = MemoryManager(session.id, db)
        try:
            # 添加用户消息（会自动触发记忆整理）
            memory.add_message("user", request.message)

            # 获取对话上下文（近期记忆 + 长期记忆）
            recent_messages, long_term_summary = memory.get_context_for_llm()
        finally:
            memory.close()

        # 构建实时上下文（最近 10 封邮件 + 最近 20 个事件）
        context_parts = []

        # 获取最近邮件
        recent_emails = db.query(Email).order_by(Email.received_at.desc()).limit(10).all()
        if recent_emails:
            context_parts.append("=== 最近邮件 ===")
            for email in recent_emails:
                context_parts.append(f"- [ID:{email.id}] [{email.received_at.strftime('%Y-%m-%d')}] {email.sender}: {email.subject}")
                if email.summary:
                    context_parts.append(f"  摘要: {email.summary}")

        # 获取最近事件
        recent_events = db.query(Event).order_by(Event.created_at.desc()).limit(20).all()
        if recent_events:
            context_parts.append("\n=== 最近事件 ===")
            for event in recent_events:
                context_parts.append(f"- [{event.event_type}] {event.title}: {event.description or '无描述'}")

        realtime_context = "\n".join(context_parts)

        # 初始化 AI 客户端
        parser = EmailParser()
        registry = get_registry()
        tools = registry.get_schemas()

        # 构建系统提示词（融合长期记忆和实时上下文）
        system_prompt = _build_chat_system_prompt(long_term_summary, realtime_context)

        # 构建消息列表（融合近期对话历史 + Function Calling）
        messages = [{"role": "system", "content": system_prompt}]
        # 添加近期对话历史（保持对话连贯性）
        messages.extend(recent_messages)
        # 添加当前用户消息
        messages.append({"role": "user", "content": request.message})

        debug_logger.info(f"调用 AI，recent_messages: {len(recent_messages)}, long_term_summary: {len(long_term_summary)} chars")

        # AI 调用循环（最多 5 轮）
        max_iterations = 5
        for iteration in range(max_iterations):
            # 调用 AI（带工具）
            response = parser.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                tools=tools if tools else None,
                max_tokens=1000
            )

            # 获取 AI 回复
            message = response.choices[0].message

            # 检查是否有工具调用
            if message.tool_calls:
                debug_logger.info(f"AI 请求调用工具: {[tc.function.name for tc in message.tool_calls]}")

                # 添加 AI 的消息和工具调用到上下文
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                })

                # 执行每个工具调用
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments)

                    debug_logger.info(f"执行工具: {func_name}, 参数: {func_args}")

                    # 执行工具
                    result = registry.execute(func_name, **func_args)

                    # 添加工具结果到上下文
                    tool_result_str = json.dumps(result.to_dict() if hasattr(result, 'to_dict') else result, ensure_ascii=False)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result_str
                    })

                    debug_logger.info(f"工具执行结果: {tool_result_str[:200]}...")

                # 继续循环，让 AI 根据工具结果生成回复
                continue
            else:
                # 没有工具调用，返回最终回复
                ai_response = message.content or "抱歉，我无法生成回复。"
                debug_logger.info(f"AI 响应: {ai_response[:100]}...")
                break
        else:
            # 达到最大迭代次数
            ai_response = "抱歉，我需要更多时间来处理您的请求。请稍后重试。"

        # 使用记忆管理器保存 AI 响应（会自动触发记忆整理）
        memory = MemoryManager(session.id, db)
        try:
            memory.add_message("assistant", ai_response)
        finally:
            memory.close()

        # 更新会话标题（如果是新会话）
        if not session.title or session.title == "新对话":
            session.title = request.message[:50]
            db.commit()

        # 返回消息列表
        all_messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at).all()

        display_messages = [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in all_messages
        ]

        debug_logger.info("<<< 返回成功")
        return ChatMessageResponse(
            session_id=session.id,
            messages=display_messages
        )

    except Exception as e:
        debug_logger.exception(f"AI 对话异常: {e}")
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


@api_router.get("/chat/sessions")
async def get_chat_sessions(db: Session = Depends(get_db)):
    """获取对话会话列表"""
    sessions = db.query(ChatSession).order_by(ChatSession.updated_at.desc()).limit(50).all()
    return [{"id": s.id, "title": s.title, "updated_at": s.updated_at.isoformat()} for s in sessions]


@api_router.post("/chat/sessions")
async def create_chat_session(db: Session = Depends(get_db)):
    """创建新的对话会话"""
    session = ChatSession(title="新对话")
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "title": session.title, "updated_at": session.updated_at.isoformat()}


@api_router.get("/chat/{session_id}", response_model=ChatMessageResponse)
async def get_chat_session(session_id: int, db: Session = Depends(get_db)):
    """获取指定会话的消息"""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        # 尝试使用记忆管理器
        from app.agents.memory import MemoryManager
        with MemoryManager(session_id, db) as memory:
            recent_messages, long_term_summary = memory.get_context_for_llm()
        
        # 转换格式
        display_messages = []
        for msg in recent_messages:
            display_messages.append({
                "role": msg["role"],
                "content": msg["content"],
                "created_at": None
            })
        
        if long_term_summary:
            display_messages.insert(0, {
                "role": "system",
                "content": f"【历史摘要】{long_term_summary}",
                "created_at": None
            })
    except Exception as e:
        # 如果出错，回退到直接查询
        import logging
        logging.warning(f"get_chat_session use fallback: {e}")
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at).all()
        display_messages = [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in messages
        ]

    return ChatMessageResponse(
        session_id=session.id,
        messages=display_messages
    )


@api_router.delete("/chat/{session_id}")
async def delete_chat_session(session_id: int, db: Session = Depends(get_db)):
    """删除对话会话"""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    db.delete(session)
    db.commit()

    return {"success": True}


# 托管前端静态资源（仅当 frontend 目录存在时）
if _FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")


# 挂载 /api 路由（必须在所有路由定义之后）
app.include_router(api_router, prefix="/api")
debug_logger.info(f"已挂载 api_router，prefix=/api")


# ============ 智能体接口 ============

def _init_agents():
    """初始化智能体系统"""
    from app.agents.tools_impl import register_all_tools
    from app.agents.email_reply import draft_email_reply_func, reply_email_func
    from app.agents.tools import Tool, get_registry

    # 注册工具
    register_all_tools()

    # 注册邮件回复工具
    registry = get_registry()
    registry.register(Tool(
        name="draft_email_reply",
        description="生成邮件回复草稿（不发送，仅生成内容供用户确认）",
        parameters={
            "type": "object",
            "properties": {
                "email_id": {"type": "integer", "description": "要回复的邮件ID"},
                "custom_prompt": {"type": "string", "description": "自定义提示词（可选）"},
                "tone": {"type": "string", "enum": ["professional", "friendly", "casual"], "description": "回复语气"}
            },
            "required": ["email_id"]
        },
        func=draft_email_reply_func
    ))
    registry.register(Tool(
        name="reply_email",
        description="回复邮件（AI生成回复内容并发送）",
        parameters={
            "type": "object",
            "properties": {
                "email_id": {"type": "integer", "description": "要回复的邮件ID"},
                "reply_content": {"type": "string", "description": "回复内容（可选，不提供则自动生成）"},
                "custom_prompt": {"type": "string", "description": "自定义提示词（可选）"},
                "tone": {"type": "string", "enum": ["professional", "friendly", "casual"], "description": "回复语气"}
            },
            "required": ["email_id"]
        },
        func=reply_email_func
    ))

    debug_logger.info(f"已注册 {len(registry)} 个工具")


@app.on_event("startup")
async def init_agents_startup():
    """启动时初始化智能体"""
    _init_agents()


# 智能体路由
agents_router = APIRouter()


@agents_router.get("/list")
async def list_agents():
    """列出所有可用智能体"""
    from app.agents.agents import list_agents
    return {"agents": list_agents()}


@agents_router.post("/{agent_type}/run")
async def run_agent(agent_type: str, request: dict = None):
    """运行指定类型的智能体"""
    from app.agents.orchestrator import get_orchestrator
    orchestrator = get_orchestrator()
    result = orchestrator.execute_task(
        agent_type,
        request.get("input_data") if request else None,
        **(request.get("kwargs", {}) if request else {})
    )
    return {
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "steps": result.steps
    }


# ReAct 路由
react_router = APIRouter()


@react_router.post("/chat")
async def react_chat(request: dict):
    """ReAct 对话接口"""
    from app.agents.react_engine import get_react_engine
    engine = get_react_engine()

    result = engine.chat(
        message=request.get("message", ""),
        conversation_history=request.get("history", []),
        context=request.get("context")
    )

    return {
        "success": result.success,
        "response": result.data.get("response") if result.data else None,
        "steps": result.steps,
        "error": result.error
    }


@react_router.post("/process")
async def react_process(request: dict):
    """ReAct 自动化处理接口"""
    from app.agents.react_engine import get_react_engine
    engine = get_react_engine()

    result = engine.process(
        task=request.get("task", ""),
        initial_input=request.get("input"),
        callbacks=request.get("callbacks")
    )

    return {
        "success": result.success,
        "result": result.data.get("result") if result.data else None,
        "steps": result.steps,
        "error": result.error
    }


# MCP 路由
mcp_router = APIRouter()


@mcp_router.get("/list")
async def list_mcp_servers():
    """列出已连接的 MCP 服务器"""
    from app.mcp import get_mcp_manager
    manager = get_mcp_manager()
    return {"servers": manager.list_clients()}


@mcp_router.post("/connect")
async def connect_mcp_server(request: dict):
    """连接 MCP 服务器"""
    from app.mcp import get_mcp_manager
    manager = get_mcp_manager()
    client = manager.add_client(request.get("name"), request.get("url"))
    if client:
        return {"success": True, "info": client.get_info()}
    return {"success": False, "error": "连接失败"}


@mcp_router.delete("/{server_name}")
async def disconnect_mcp_server(server_name: str):
    """断开 MCP 服务器"""
    from app.mcp import get_mcp_manager
    manager = get_mcp_manager()
    success = manager.remove_client(server_name)
    return {"success": success}


@mcp_router.get("/tools")
async def list_mcp_tools():
    """列出所有 MCP 可用工具"""
    from app.mcp import get_mcp_manager
    manager = get_mcp_manager()
    return {"tools": manager.get_all_tools()}


# 邮件回复路由
reply_router = APIRouter()


@reply_router.post("/draft/{email_id}")
async def create_reply_draft(email_id: int, request: dict = None):
    """生成邮件回复草稿"""
    from app.agents.email_reply import get_email_reply
    reply = get_email_reply()
    result = reply.generate_reply(
        email_id,
        custom_prompt=request.get("custom_prompt") if request else None,
        tone=request.get("tone", "professional") if request else "professional"
    )
    return result


@reply_router.post("/send/{email_id}")
async def send_reply(email_id: int, request: dict = None):
    """发送邮件回复"""
    from app.agents.email_reply import get_email_reply
    reply = get_email_reply()
    result = reply.send_reply(
        email_id,
        reply_content=request.get("reply_content") if request else None,
        custom_prompt=request.get("custom_prompt") if request else None,
        tone=request.get("tone", "professional") if request else "professional"
    )
    return result


# 挂载所有路由
app.include_router(agents_router, prefix="/api/agents", tags=["智能体"])
app.include_router(react_router, prefix="/api/react", tags=["ReAct"])
app.include_router(mcp_router, prefix="/api/mcp", tags=["MCP"])
app.include_router(reply_router, prefix="/api/reply", tags=["邮件回复"])

# ============ LangGraph 路由 ============
langgraph_router = APIRouter()


class LangGraphChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = None
    context: Optional[Dict[str, Any]] = None


@langgraph_router.post("/chat")
async def langgraph_chat(request: LangGraphChatRequest):
    """使用 LangGraph 的 AI 对话"""
    from app.agents.graph import get_email_agent
    
    agent = get_email_agent()
    result = agent.chat(
        message=request.message,
        conversation_history=request.conversation_history,
        context=request.context
    )
    
    return {
        "success": result.success,
        "response": result.response,
        "tool_calls": result.tool_calls,
        "tool_results": result.tool_results,
        "error": result.error
    }


app.include_router(langgraph_router, prefix="/api/agents/langgraph", tags=["LangGraph"])

debug_logger.info("已挂载所有智能体相关路由")
