"""
对话路由 - Chat API
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from langgraph.errors import GraphInterrupt
from sqlalchemy.orm import Session

from app.api.deps import get_db, logger
from app.api.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatResumeRequest,
    ChatSessionResponse,
)
from app.db import ChatMessage


router = APIRouter()


def _new_session_id() -> str:
    return uuid4().hex


def _thread_id_for_session(session_id: str) -> str:
    return f"email-{session_id}"


def _session_id_from_thread_id(thread_id: str) -> str:
    prefix = "email-"
    if not thread_id.startswith(prefix):
        raise HTTPException(status_code=400, detail="无效的 thread_id")
    return thread_id[len(prefix):]


def _build_session_title(messages: List[ChatMessage], session_id: str) -> str:
    for message in messages:
        if message.role == "user" and message.content:
            return message.content.strip().replace("\n", " ")[:30] or "新建对话"
    return f"会话 {session_id[:8]}"


def _serialize_session(session_id: str, messages: List[ChatMessage]) -> Dict[str, str]:
    updated_at = max((message.created_at for message in messages), default=datetime.now())
    return {
        "id": session_id,
        "title": _build_session_title(messages, session_id),
        "updated_at": updated_at.isoformat(),
    }


def _load_display_messages(db: Session, session_id: str) -> List[dict]:
    all_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    return [
        {"role": message.role, "content": message.content, "created_at": message.created_at.isoformat()}
        for message in all_messages
    ]


@router.get("/chat/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(db: Session = Depends(get_db)):
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id.isnot(None))
        .order_by(ChatMessage.created_at.desc())
        .all()
    )

    grouped: Dict[str, List[ChatMessage]] = {}
    for message in messages:
        if not message.session_id:
            continue
        grouped.setdefault(message.session_id, []).append(message)

    sessions = [
        _serialize_session(session_id, session_messages)
        for session_id, session_messages in grouped.items()
    ]
    sessions.sort(key=lambda item: item["updated_at"], reverse=True)
    return sessions


@router.post("/chat/sessions", response_model=ChatSessionResponse)
async def create_chat_session():
    session_id = _new_session_id()
    return {
        "id": session_id,
        "title": "新建对话",
        "updated_at": datetime.now().isoformat(),
    }


@router.post("/chat", response_model=ChatMessageResponse)
async def chat(request: ChatMessageRequest, db: Session = Depends(get_db)):
    logger.info(
        f">>> 调用 /api/chat, session_id={request.session_id}, message={request.message[:50]}..."
    )

    try:
        session_id = request.session_id or _new_session_id()
        thread_id = _thread_id_for_session(session_id)

        # 统一走 LangGraph Supervisor
        from app.agents.graph.email_agent import get_supervisor_agent

        recent = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(20)
            .all()
        )

        history = [
            {"role": m.role, "content": m.content}
            for m in reversed(recent)
            if m.role in ("user", "assistant")
        ]

        agent = get_supervisor_agent()
        try:
            result = agent.chat(
                request.message,
                conversation_history=history,
                force_intent=request.force_intent,
            )
        except GraphInterrupt as interrupt:
            db.add(ChatMessage(
                session_id=session_id,
                role="user",
                content=request.message,
                message_type="user",
                agent_name="user",
            ))
            db.commit()

            logger.info("<<< 返回 interrupt 响应")
            return ChatMessageResponse(
                session_id=session_id,
                messages=_load_display_messages(db, session_id),
                status="interrupted",
                thread_id=thread_id,
                interrupt=interrupt.args[0] if interrupt.args else {},
            )

        ai_response = result.response

        # 保存用户消息
        db.add(ChatMessage(
            session_id=session_id,
            role="user",
            content=request.message,
            message_type="user",
            agent_name="user",
        ))

        # 保存 AI 回复
        db.add(ChatMessage(
            session_id=session_id,
            role="assistant",
            content=ai_response,
            message_type="agent",
            agent_name="supervisor",
        ))

        db.commit()

        logger.info("<<< 返回成功")
        return ChatMessageResponse(
            session_id=session_id,
            messages=_load_display_messages(db, session_id),
            status="completed",
            thread_id=thread_id,
        )

    except Exception as e:
        logger.exception(f"AI 对话异常: {e}")
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


@router.post("/chat/resume", response_model=ChatMessageResponse)
async def resume_chat(request: ChatResumeRequest, db: Session = Depends(get_db)):
    from app.agents.graph.email_agent import get_supervisor_agent

    session_id = _session_id_from_thread_id(request.thread_id)
    agent = get_supervisor_agent()

    try:
        result = agent.resume(request.thread_id, request.confirmed)
    except GraphInterrupt as interrupt:
        return ChatMessageResponse(
            session_id=session_id,
            messages=_load_display_messages(db, session_id),
            status="interrupted",
            thread_id=request.thread_id,
            interrupt=interrupt.args[0] if interrupt.args else {},
        )

    db.add(ChatMessage(
        session_id=session_id,
        role="assistant",
        content=result.response,
        message_type="agent",
        agent_name="supervisor",
    ))
    db.commit()

    return ChatMessageResponse(
        session_id=session_id,
        messages=_load_display_messages(db, session_id),
        status="completed",
        thread_id=request.thread_id,
    )


@router.get("/chat/{session_id}", response_model=ChatMessageResponse)
async def get_chat_session(session_id: str, db: Session = Depends(get_db)):
    from app.agents.graph.email_agent import get_supervisor_agent

    thread_id = _thread_id_for_session(session_id)
    interrupt = get_supervisor_agent().get_pending_interrupt(thread_id)
    return ChatMessageResponse(
        session_id=session_id,
        messages=_load_display_messages(db, session_id),
        status="interrupted" if interrupt else "completed",
        thread_id=thread_id,
        interrupt=interrupt,
    )


@router.delete("/chat/{session_id}")
async def delete_chat_session(session_id: str, db: Session = Depends(get_db)):
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.commit()
    return {"success": True}
