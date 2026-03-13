"""
工具系统 - Tools Framework
支持 Function Calling 的工具注册和执行
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
import logging
import json

logger = logging.getLogger(__name__)


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
        self._logger = logging.getLogger("tools.registry")
    
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
    return decorator
