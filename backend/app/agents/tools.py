"""
工具系统 - Tools Framework
支持 Function Calling 的工具注册和执行
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
import json

from app.logger import Logger

logger = Logger.get("tools")


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: str = ""
    raw_output: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "raw_output": self.raw_output
        }


class Tool(ABC):
    """工具基类"""
    
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict,
        func: Optional[Callable] = None
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func  # 实际执行的函数
    
    def execute(self, **kwargs) -> ToolResult:
        """执行工具"""
        try:
            if self.func is None:
                return ToolResult(success=False, error="Tool function not implemented")
            
            result = self.func(**kwargs)
            return ToolResult(
                success=True,
                data=result,
                raw_output=json.dumps(result, ensure_ascii=False, default=str)
            )
        except Exception as e:
            logger.error(f"Tool '{self.name}' execution error: {e}")
            return ToolResult(success=False, error=str(e))
    
    def get_schema(self) -> Dict:
        """获取 OpenAI Function Calling 格式的 schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
    
    def __repr__(self):
        return f"<Tool(name={self.name})>"


class ToolRegistry:
    """工具注册中心"""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._logger = Logger.get("tools_registry")
    
    def register(self, tool: Tool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool
        self._logger.info(f"Registered tool: {tool.name}")
    
    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            self._logger.info(f"Unregistered tool: {name}")
            return True
        return False
    
    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)
    
    def get_all(self) -> Dict[str, Tool]:
        """获取所有工具"""
        return self._tools.copy()
    
    def get_schemas(self) -> List[Dict]:
        """获取所有工具的 schema（用于 Function Calling）"""
        return [tool.get_schema() for tool in self._tools.values()]
    
    def execute(self, name: str, **kwargs) -> ToolResult:
        """执行工具"""
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{name}' not found")
        return tool.execute(**kwargs)
    
    def list_tools(self) -> List[Dict]:
        """列出所有工具信息"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for tool in self._tools.values()
        ]
    
    def __len__(self):
        return len(self._tools)
    
    def __contains__(self, name: str):
        return name in self._tools


# 全局工具注册中心
_global_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """获取全局工具注册中心"""
    return _global_registry


def register_tool(
    name: str,
    description: str,
    parameters: Dict,
    func: Callable = None
) -> Tool:
    """装饰器：快速注册工具"""
    def decorator(func_: Callable):
        tool = Tool(name, description, parameters, func_)
        _global_registry.register(tool)
        return func_
    if func:
        tool = Tool(name, description, parameters, func)
        _global_registry.register(tool)
        return tool
# ═══════════════════════════════════════════════════════════════
# 注册邮件回复工具
# ═══════════════════════════════════════════════════════════════
def _register_email_reply_tools():
    """注册邮件回复相关工具"""
    from app.agents.email_reply import draft_email_reply_func, reply_email_func

    _global_registry.register(Tool(
        name="draft_email_reply",
        description="生成邮件回复草稿。当用户要求回复邮件、起草回复时使用，返回回复内容供用户确认。",
        parameters={
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "integer",
                    "description": "要回复的邮件ID"
                },
                "tone": {
                    "type": "string",
                    "enum": ["professional", "friendly", "casual"],
                    "description": "回复语气：professional(专业) / friendly(友好) / casual(随意)",
                    "default": "professional"
                },
                "custom_prompt": {
                    "type": "string",
                    "description": "自定义提示词，用于指导回复内容",
                    "default": None
                }
            },
            "required": ["email_id"]
        },
        func=draft_email_reply_func
    ))

    _global_registry.register(Tool(
        name="reply_email",
        description="直接发送邮件回复（不经过草稿确认）。谨慎使用，建议先调用 draft_email_reply 生成草稿。",
        parameters={
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "integer",
                    "description": "要回复的邮件ID"
                },
                "reply_content": {
                    "type": "string",
                    "description": "回复内容，如果不提供则自动生成",
                    "default": None
                },
                "tone": {
                    "type": "string",
                    "enum": ["professional", "friendly", "casual"],
                    "description": "回复语气",
                    "default": "professional"
                }
            },
            "required": ["email_id"]
        },
        func=reply_email_func
    ))


_register_email_reply_tools()
del _register_email_reply_tools
