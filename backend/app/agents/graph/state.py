"""
LangGraph Agent 状态定义
"""
from typing import TypedDict, List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class EngineType(str, Enum):
    """Agent 引擎类型"""
    LANGGRAPH = "langgraph"


class IntentType(str, Enum):
    """用户意图类型（与子 Agent 节点名一一对应）"""
    PARSE = "parser"
    SUMMARIZE = "summarizer"
    NOTIFY = "notification"
    QUERY = "query"
    GENERAL = "general"
    REACT = "react"      # ReAct 引擎（复杂多步推理）
    UNKNOWN = "unknown"


class EmailAgentState(TypedDict):
    """邮件助手 Agent 的统一状态"""

    # ── 对话消息 ──────────────────────────────────────────────
    messages: List[Dict[str, str]]   # [{"role": "user"|"assistant"|"tool", "content": "..."}]

    # ── Supervisor 意图判断结果 ──────────────────────────────
    intents: List[str]                    # ["parser", "summarizer", "query", ...]
    intent_reasoning: Optional[str]       # LLM 的推理过程
    force_intent: Optional[str] = None    # 前端手动指定意图（覆盖自动分类）

    # ── 从用户消息中提取的操作参数 ────────────────────────────
    action_params: Dict[str, Any]

    # ── 6 个子 Agent 的统一执行结果 ─────────────────────────
    agent_outputs: Dict[str, Any]     # {
                                        #   "parser": {...},
                                        #   "summarizer": {...},
                                        #   "notification": {...},
                                        #   "query": {...},
                                        #   "general": {...},
                                        #   "react": {...}
                                        # }

    # ── 最终自然语言响应 ─────────────────────────────────────
    final_response: Optional[str]

    # ── 执行状态 ─────────────────────────────────────────────
    execution_status: str   # pending | running | completed | error


@dataclass
class EmailAgentInput:
    """Agent 输入数据"""
    message: str
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    context: Optional[Dict[str, Any]] = None


@dataclass
class EmailAgentOutput:
    """Agent 输出数据"""
    response: str
    success: bool = True
    error: str = ""
    intents: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response": self.response,
            "success": self.success,
            "error": self.error,
            "intents": self.intents,
        }
