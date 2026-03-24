"""
路由模块 - Agents 相关 API
统一由 LangGraph Supervisor 编排，所有对话入口为 POST /api/chat
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.api.deps import logger
from app.api.schemas import LangGraphChatRequest


router = APIRouter()


def init_agents() -> None:
    """注册工具（在应用启动时调用一次）"""
    from app.agents.tools_impl import register_all_tools

    register_all_tools()
    from app.agents.tools import get_registry

    registry = get_registry()
    logger.info(f"已注册 {len(registry)} 个工具")


# ── /api/agents ───────────────────────────────────────────────────────────────

agents_router = APIRouter(prefix="/agents", tags=["智能体"])


@agents_router.get("/list")
async def list_agents():
    """返回 LangGraph 中的 6 个 Agent 节点"""
    return {"agents": [
        {"type": "parser",       "name": "parser_agent",       "description": "同步/解析邮件"},
        {"type": "summarizer",   "name": "summarizer_agent",   "description": "生成摘要归档 Notion"},
        {"type": "notification", "name": "notification_agent", "description": "发送每日摘要/事件通知"},
        {"type": "query",        "name": "query_agent",        "description": "查询邮件和事件列表"},
        {"type": "general",      "name": "general_agent",      "description": "通用问答"},
        {"type": "react",        "name": "react_agent",        "description": "ReAct 多步推理"},
    ]}


# ── /api/mcp ──────────────────────────────────────────────────────────────────

mcp_router = APIRouter(prefix="/mcp", tags=["MCP"])


@mcp_router.get("/list")
async def list_mcp_servers():
    from app.mcp import get_mcp_manager
    manager = get_mcp_manager()
    return {"servers": manager.list_clients()}


@mcp_router.post("/connect")
async def connect_mcp_server(request: Dict[str, Any]):
    from app.mcp import get_mcp_manager
    manager = get_mcp_manager()
    client = manager.add_client(request.get("name"), request.get("url"))
    if client:
        return {"success": True, "info": client.get_info()}
    return {"success": False, "error": "连接失败"}


@mcp_router.delete("/{server_name}")
async def disconnect_mcp_server(server_name: str):
    from app.mcp import get_mcp_manager
    manager = get_mcp_manager()
    success = manager.remove_client(server_name)
    return {"success": success}


@mcp_router.get("/tools")
async def list_mcp_tools():
    from app.mcp import get_mcp_manager
    manager = get_mcp_manager()
    return {"tools": manager.get_all_tools()}


# ── /api/reply ────────────────────────────────────────────────────────────────

reply_router = APIRouter(prefix="/reply", tags=["邮件回复"])


@reply_router.post("/draft/{email_id}")
async def create_reply_draft(email_id: int, request: Optional[dict] = None):
    from app.agents.email_reply import get_email_reply
    reply = get_email_reply()
    return reply.generate_reply(
        email_id,
        custom_prompt=request.get("custom_prompt") if request else None,
        tone=request.get("tone", "professional") if request else "professional",
    )


@reply_router.post("/send/{email_id}")
async def send_reply(email_id: int, request: Optional[dict] = None):
    from app.agents.email_reply import get_email_reply
    reply = get_email_reply()
    return reply.send_reply(
        email_id,
        reply_content=request.get("reply_content") if request else None,
        custom_prompt=request.get("custom_prompt") if request else None,
        tone=request.get("tone", "professional") if request else "professional",
    )


# ── /api/agents/langgraph ─────────────────────────────────────────────────────
# LangGraph 调试入口（前端实际走 POST /api/chat）

langgraph_router = APIRouter(prefix="/agents/langgraph", tags=["LangGraph"])


@langgraph_router.post("/chat")
async def langgraph_chat(request: LangGraphChatRequest):
    from app.agents.graph import get_email_agent
    agent = get_email_agent()
    result = agent.chat(
        message=request.message,
        conversation_history=request.conversation_history,
        force_intent=request.force_intent,
    )
    return {
        "success": result.success,
        "response": result.response,
        "intents": result.intents,
        "error": result.error
    }


# Mount sub-routers
router.include_router(agents_router)
router.include_router(mcp_router)
router.include_router(reply_router)
router.include_router(langgraph_router)
