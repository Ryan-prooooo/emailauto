"""
路由模块 - Agents 相关 API
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter


router = APIRouter()


def init_agents() -> None:
    """注册工具（在应用启动时调用一次）"""
    from app.agents.tools_impl import register_all_tools
    from app.api.deps import logger

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
        {"type": "reply",        "name": "reply_agent",         "description": "生成邮件回复草稿"},
        {"type": "meeting",      "name": "meeting_agent",      "description": "会议 RSVP 决策与状态更新"},
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


# Mount sub-routers
router.include_router(agents_router)
router.include_router(mcp_router)
router.include_router(reply_router)
