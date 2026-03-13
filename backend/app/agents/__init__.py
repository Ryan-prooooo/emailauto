"""
智能体模块 - Agent Framework
提供多智能体架构、ReAct模式和Function Calling支持
"""
from app.agents.base import BaseAgent, AgentResult
from app.agents.tools import Tool, ToolResult, ToolRegistry, get_registry
from app.agents.agents import (
    ParserAgent, SummarizerAgent, QAAgent, NotificationAgent,
    get_agent, list_agents, AGENT_TYPES
)
from app.agents.orchestrator import AgentOrchestrator, get_orchestrator
from app.agents.react_engine import ReActEngine, ReActStep, get_react_engine
from app.agents.email_reply import EmailReply, get_email_reply

__all__ = [
    "BaseAgent",
    "AgentResult",
    "Tool",
    "ToolResult",
    "ToolRegistry",
    "get_registry",
    "ParserAgent",
    "SummarizerAgent",
    "QAAgent",
    "NotificationAgent",
    "get_agent",
    "list_agents",
    "AGENT_TYPES",
    "AgentOrchestrator",
    "get_orchestrator",
    "ReActEngine",
    "ReActStep",
    "get_react_engine",
    "EmailReply",
    "get_email_reply",
]
