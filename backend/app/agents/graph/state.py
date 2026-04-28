"""
LangGraph Agent 状态定义
"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from dataclasses import dataclass, field
from enum import Enum


def _merge_agent_outputs(
    left: Optional[Dict[str, Any]],
    right: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(left or {})
    merged.update(right or {})
    return merged


def _merge_execution_status(
    left: Optional[str],
    right: Optional[str],
) -> str:
    priority = {
        "error": 4,
        "needs_review": 3,
        "interrupted": 3,
        "running": 2,
        "completed": 1,
        "pending": 0,
        None: -1,
    }
    left_score = priority.get(left, -1)
    right_score = priority.get(right, -1)
    return left if left_score >= right_score else (right or left or "pending")


def _append_unique_nodes(
    left: Optional[List[str]],
    right: Optional[List[str]],
) -> List[str]:
    merged: List[str] = list(left or [])
    for item in right or []:
        if item not in merged:
            merged.append(item)
    return merged


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
    REPLY = "reply"      # 生成邮件回复草稿
    MEETING = "meeting"  # 会议 RSVP 决策
    UNKNOWN = "unknown"


class MultiIntentType(str, Enum):
    """
    组合意图路由类型：用于条件边路由的返回值。
    每个 value 对应 conditional_edges 字典的 key。

    只在 _route_intent 返回 string（串行）时使用。
    返回 List[Send]（并行）时不会落入任何 conditional edge。
    """
    PARSE_ONLY = "parser_only"
    SUMMARIZER_ONLY = "summarizer_only"
    REPLY_ONLY = "reply_only"
    MEETING_ONLY = "meeting_only"
    QUERY_ONLY = "query_only"
    GENERAL_ONLY = "general_only"
    UNKNOWN = "unknown"


class EmailAgentState(TypedDict):
    """邮件助手 Agent 的统一状态"""

    # ── 对话消息 ──────────────────────────────────────────────
    messages: List[Dict[str, str]]   # [{"role": "user"|"assistant"|"tool", "content": "..."}]

    # ── Supervisor 意图判断结果 ──────────────────────────────
    intents: List[str]                    # ["parser", "summarizer", "query", ...]
    intent_reasoning: Optional[str]       # LLM 的推理过程
    force_intent: Optional[str] = None   # 前端手动指定意图（覆盖自动分类）

    # ── 从用户消息中提取的操作参数 ────────────────────────────
    action_params: Dict[str, Any]
    # {
    #   limit: int          # 查询/处理数量限制
    #   query_type: str     # 查询类型：all / emails / events
    #   action: str         # 通知动作：send_summary / send_event
    #   to_email: str       # 目标邮箱
    #   event_id: int       # 事件ID
    #   reply_content: str  # 回复内容（reply 节点生成，由 reflect_check 检查）
    #   sender_email: str   # 发件人地址（reflect_check 检查发件人身份）
    #   check_targets: List[str]  # 自检目标：parser / summarizer / reply / meeting
    #   rsvp_status: str   # RSVP 决策：accept / decline / tentative（meeting 节点用）
    # }

    # ── 7 个子 Agent 的统一执行结果 ─────────────────────────
    agent_outputs: Annotated[Dict[str, Any], _merge_agent_outputs]     # {
                                        #   "parser": {...},
                                        #   "summarizer": {...},
                                        #   "reply": {...},
                                        #   "notification": {...},
                                        #   "query": {...},
                                        #   "general": {...},
                                        #   "reflect": {...}  # reflect_check 输出
                                        # }

    # ── 最终自然语言响应 ─────────────────────────────────────
    final_response: Optional[str]

    # ── 执行状态 ─────────────────────────────────────────────
    execution_status: Annotated[str, _merge_execution_status]   # pending | running | completed | error | interrupted

    # ── interrupt 挂起状态 ────────────────────────────────────
    # reply 节点生成草稿后挂起，等用户确认
    pending_draft: Optional[Dict[str, Any]] = None
    # {
    #   "draft_content": str,
    #   "email_id": int,
    #   "sender_email": str,
    #   "tone": str,
    #   "confirmed": Optional[bool]  # None=未确认, True=确认发送, False=取消
    # }

    # meeting 节点 RSVP 决策挂起，等用户确认
    pending_meeting: Optional[Dict[str, Any]] = None
    # {
    #   "event_id": int,
    #   "title": str,
    #   "llm_decision": str,      # accept / decline / tentative
    #   "llm_suggestion": str,    # 建议回复语句
    #   "confirmed": Optional[bool]  # None=未确认, True=确认, False=取消
    # }

    # ── 节点执行记录 ─────────────────────────────────────────
    # 记录已执行的节点名，防止 multi_intent fan-out 时重复执行
    executed_nodes: Annotated[List[str], _append_unique_nodes] = []


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
