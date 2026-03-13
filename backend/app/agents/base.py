"""
智能体基类 - Base Agent Framework
所有智能体继承此基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """智能体执行结果"""
    success: bool
    data: Any = None
    error: str = ""
    steps: List[Dict] = field(default_factory=list)  # 执行步骤记录
    
    def add_step(self, step: Dict):
        """添加执行步骤"""
        self.steps.append({
            **step,
            "timestamp": datetime.now().isoformat()
        })


class BaseAgent(ABC):
    """智能体基类"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.tools = []  # 可用工具列表
        self.logger = logging.getLogger(f"agent.{name}")
    
    @abstractmethod
    def execute(self, input_data: Any, **kwargs) -> AgentResult:
        """执行智能体任务"""
        pass
    
    def add_tool(self, tool):
        """添加工具"""
        self.tools.append(tool)
    
    def remove_tool(self, tool_name: str):
        """移除工具"""
        self.tools = [t for t in self.tools if t.name != tool_name]
    
    def get_tools_schema(self) -> List[Dict]:
        """获取工具 schema（用于 Function Calling）"""
        return [tool.get_schema() for tool in self.tools]
    
    def run_tool(self, tool_name: str, **kwargs) -> Any:
        """运行指定工具"""
        for tool in self.tools:
            if tool.name == tool_name:
                return tool.execute(**kwargs)
        raise ValueError(f"Tool '{tool_name}' not found")
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(name={self.name})>"
