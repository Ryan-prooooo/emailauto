"""
智能体模块 - Agent Framework
基于 LangGraph Supervisor 模式统一编排所有 Agent
"""
from app.agents.base import BaseAgent, AgentResult
from app.agents.tools import Tool, ToolResult, ToolRegistry, get_registry
from app.agents.agents import (
    ParserAgent, SummarizerAgent, QAAgent, NotificationAgent,
    get_agent, list_agents, AGENT_TYPES
)
from app.agents.email_reply import EmailReply, get_email_reply
from app.agents.graph import get_email_agent
from app.agents.graph.state import EmailAgentState, EmailAgentOutput, IntentType

__all__ = [
    # 基础
    "BaseAgent",
    "AgentResult",
    "Tool",
    "ToolResult",
    "ToolRegistry",
    "get_registry",
    # Agent 类（节点内部调用）
    "ParserAgent",
    "SummarizerAgent",
    "QAAgent",
    "NotificationAgent",
    "get_agent",
    "list_agents",
    "AGENT_TYPES",
    # 邮件回复
    "EmailReply",
    "get_email_reply",
    # LangGraph 统一入口
    "get_email_agent",
    "EmailAgentState",
    "EmailAgentOutput",
    "IntentType",
]
