"""
LangGraph Email Agent 主类
"""
import logging
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.graph.state import EmailAgentState, EmailAgentInput, EmailAgentOutput
from app.agents.graph.nodes import agent_node, execute_tool_node, generate_response_node, should_continue
from app.agents.tools import get_registry
from app.config import settings


logger = logging.getLogger(__name__)


class EmailAgent:
    """
    基于 LangGraph 的邮件助手 Agent
    """
    
    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self.graph = None
        self._build_graph()
    
    def _build_graph(self):
        """构建 LangGraph"""
        # 创建工作流图
        workflow = StateGraph(EmailAgentState)
        
        # 添加节点
        workflow.add_node("agent", agent_node)
        workflow.add_node("execute_tool", execute_tool_node)
        workflow.add_node("generate_response", generate_response_node)
        
        # 设置入口点
        workflow.set_entry_point("agent")
        
        # 添加条件边
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "execute_tool": "execute_tool",
                "end": "generate_response"
            }
        )
        
        # 执行工具后返回 agent 节点继续
        workflow.add_edge("execute_tool", "agent")
        
        # 生成响应后结束
        workflow.add_edge("generate_response", END)
        
        # 编译图
        self.graph = workflow.compile()
        
        logger.info("LangGraph EmailAgent compiled successfully")
    
    def chat(self, message: str, conversation_history: List[Dict[str, str]] = None, context: Dict[str, Any] = None) -> EmailAgentOutput:
        """
        处理对话
        
        Args:
            message: 用户消息
            conversation_history: 对话历史
            context: 额外上下文
        
        Returns:
            EmailAgentOutput: Agent 输出
        """
        logger.info(f"EmailAgent processing message: {message[:50]}...")
        
        # 构建初始状态
        messages = []
        
        # 添加系统提示
        system_prompt = self._build_system_prompt()
        messages.append({"role": "system", "content": system_prompt})
        
        # 添加历史对话
        if conversation_history:
            messages.extend(conversation_history)
        
        # 添加当前消息
        messages.append({"role": "user", "content": message})
        
        # 初始化状态
        initial_state: EmailAgentState = {
            "messages": messages,
            "tool_calls": [],
            "tool_results": [],
            "context": context,
            "current_response": None
        }
        
        try:
            # 执行图
            config = {"configurable": {"thread_id": "email-assistant"}}
            
            result = None
            for step in self.graph.stream(initial_state, config, max_iterations=self.max_iterations):
                logger.info(f"Graph step: {list(step.keys())}")
                result = step
            
            # 获取最终状态
            final_state = result
            if isinstance(result, dict):
                # 找到最后一个节点的状态
                for node_name, node_state in result.items():
                    if isinstance(node_state, dict) and "current_response" in node_state:
                        final_state = node_state
                        break
            
            # 提取响应
            response = ""
            if isinstance(final_state, dict):
                response = final_state.get("current_response", "")
            
            if not response:
                # 尝试从消息历史中获取
                if isinstance(final_state, dict):
                    messages = final_state.get("messages", [])
                    for msg in reversed(messages):
                        if isinstance(msg, dict) and msg.get("role") == "assistant":
                            response = msg.get("content", "")
                            break
            
            return EmailAgentOutput(
                response=response or "处理完成",
                tool_calls=final_state.get("tool_calls", []) if isinstance(final_state, dict) else [],
                tool_results=final_state.get("tool_results", []) if isinstance(final_state, dict) else [],
                success=True
            )
            
        except Exception as e:
            logger.error(f"EmailAgent error: {e}")
            return EmailAgentOutput(
                response=f"处理您的请求时发生错误: {str(e)}",
                success=False,
                error=str(e)
            )
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        registry = get_registry()
        tools = registry.list_tools()
        
        tools_desc = "\n".join([
            f"- {t['name']}: {t['description']}"
            for t in tools
        ])
        
        return f"""你是一个智能邮件助手，可以帮助用户管理邮件和事件。

## 可用工具
{tools_desc}

## 功能说明
- 你可以查询邮件和事件信息
- 你可以同步邮件、解析邮件
- 你可以发送邮件、发送通知
- 你可以查看和修改系统设置

## 使用规则
- 如果需要执行操作，请使用合适的工具
- 保持回答简洁明了
- 如果用户没有指定邮箱，默认使用配置文件中的邮箱
"""
    
    def get_graph(self):
        """获取编译后的图"""
        return self.graph


# 全局实例
_email_agent: Optional[EmailAgent] = None


def get_email_agent() -> EmailAgent:
    """获取全局 EmailAgent 实例"""
    global _email_agent
    if _email_agent is None:
        _email_agent = EmailAgent()
    return _email_agent
