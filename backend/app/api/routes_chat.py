"""
对话路由 - Chat API
统一由 LangGraph Supervisor 编排，入口为 POST /api/chat
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, logger
from app.api.schemas import ChatMessageRequest, ChatMessageResponse
from app.db import ChatMessage, ChatSession


router = APIRouter()


@router.post("/chat", response_model=ChatMessageResponse)
async def chat(request: ChatMessageRequest, db: Session = Depends(get_db)):
    logger.info(
        f">>> 调用 /api/chat, session_id={request.session_id}, message={request.message[:50]}..."
    )

    try:
        # 获取或创建会话
        session = None
        if request.session_id:
            session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()
        if not request.session_id or not session:
            session = ChatSession(title=request.message[:50] or "新对话")
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info(f"创建新会话: {session.id}")

        # 统一走 LangGraph Supervisor
        from app.agents.graph.email_agent import get_supervisor_agent

        recent = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
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
        result = agent.chat(
            request.message,
            conversation_history=history,
            force_intent=request.force_intent,
        )
        ai_response = result.response

        # 更新会话标题
        if not session.title or session.title == "新对话":
            session.title = request.message[:50]
            db.commit()

        # 查询所有消息返回
        all_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
            .all()
        )

        display_messages = [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in all_messages
        ]

        logger.info("<<< 返回成功")
        return ChatMessageResponse(session_id=session.id, messages=display_messages)

    except Exception as e:
        logger.exception(f"AI 对话异常: {e}")
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


@router.get("/chat/sessions")
async def get_chat_sessions(db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).order_by(ChatSession.updated_at.desc()).limit(50).all()
    return [{"id": s.id, "title": s.title, "updated_at": s.updated_at.isoformat()} for s in sessions]


@router.post("/chat/sessions")
async def create_chat_session(db: Session = Depends(get_db)):
    session = ChatSession(title="新对话")
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "title": session.title, "updated_at": session.updated_at.isoformat()}


@router.get("/chat/{session_id}", response_model=ChatMessageResponse)
async def get_chat_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .all()
        )

        from app.agents.memory import MemoryManager

        with MemoryManager(session_id, db) as memory:
            _, long_term_summary = memory.get_context_for_llm()

        display_messages = [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in messages
        ]

        if long_term_summary:
            display_messages.insert(
                0, {"role": "system", "content": f"【历史摘要】{long_term_summary}", "created_at": None}
            )
    except Exception as e:
        logger.warning(f"get_chat_session use fallback: {e}")
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .all()
        )
        display_messages = [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in messages
        ]

    return ChatMessageResponse(session_id=session.id, messages=display_messages)


@router.delete("/chat/{session_id}")
async def delete_chat_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    db.delete(session)
    db.commit()
    return {"success": True}
