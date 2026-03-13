"""
智能体编排器 - Agent Orchestrator
负责任务分发和结果聚合
"""
from typing import Any, Dict, List, Optional
import logging
from app.agents.base import BaseAgent, AgentResult
from app.agents.agents import get_agent, list_agents, AGENT_TYPES

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """智能体编排器"""

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.logger = logging.getLogger("orchestrator")
        self._init_default_agents()

    def _init_default_agents(self):
        """初始化默认智能体"""
        for agent_info in list_agents():
            agent_type = agent_info["type"]
            agent = get_agent(agent_type)
            if agent:
                self.agents[agent_type] = agent
                self.logger.info(f"Initialized agent: {agent_type}")

    def get_agent(self, agent_type: str) -> Optional[BaseAgent]:
        """获取指定类型的智能体"""
        return self.agents.get(agent_type.lower())

    def list_available_agents(self) -> List[Dict]:
        """列出所有可用的智能体"""
        return [
            {
                "type": agent_type,
                "name": agent.name,
                "description": agent.description,
                "tools_count": len(agent.tools)
            }
            for agent_type, agent in self.agents.items()
        ]

    def execute_task(self, agent_type: str, input_data: Any, **kwargs) -> AgentResult:
        """执行智能体任务"""
        agent = self.get_agent(agent_type)
        if not agent:
            return AgentResult(
                success=False,
                error=f"Agent '{agent_type}' not found"
            )
        return agent.execute(input_data, **kwargs)

    def execute_multi(self, tasks: List[Dict]) -> List[AgentResult]:
        """执行多个智能体任务"""
        results = []
        for task in tasks:
            agent_type = task.get("agent_type")
            input_data = task.get("input_data")
            kwargs = task.get("kwargs", {})
            result = self.execute_task(agent_type, input_data, **kwargs)
            results.append(result)
        return results

    def route_task(self, user_input: str) -> str:
        """根据用户输入路由到合适的智能体"""
        user_input_lower = user_input.lower()

        # 简单路由逻辑
        if any(kw in user_input_lower for kw in ["解析", "提取", "分析", "parse", "analyze"]):
            return "parser"
        elif any(kw in user_input_lower for kw in ["摘要", "总结", "概览", "summary", "overview"]):
            return "summarizer"
        elif any(kw in user_input_lower for kw in ["通知", "发送", "推送", "notification", "send"]):
            return "notification"
        elif any(kw in user_input_lower for kw in ["问", "什么", "谁", "如何", "?", "how", "what", "who"]):
            return "qa"

        # 默认使用 QA 智能体
        return "qa"


# 全局编排器实例
_orchestrator = AgentOrchestrator()


def get_orchestrator() -> AgentOrchestrator:
    """获取全局编排器"""
    return _orchestrator
