"""
LangGraph Agent 状态定义
"""
from typing import TypedDict, List, Dict, Any, Optional
from dataclasses import dataclass, field


class EmailAgentState(TypedDict):
    """邮件助手 Agent 的状态"""
    messages: List[Dict[str, str]]  # 对话消息历史
    tool_calls: List[Dict[str, Any]]  # 工具调用记录
    tool_results: List[Dict[str, Any]]  # 工具执行结果
    context: Optional[Dict[str, Any]]  # 额外上下文信息
    current_response: Optional[str]  # 当前响应


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
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response": self.response,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "success": self.success,
            "error": self.error
        }
