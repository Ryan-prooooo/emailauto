"""
LangGraph Agent 节点定义
"""
import logging
from typing import Literal, Dict, Any, List
from langgraph.graph import END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.utils.function_calling import convert_to_openai_function

from app.agents.graph.state import EmailAgentState
from app.agents.tools import get_registry
from app.config import settings


logger = logging.getLogger(__name__)


def _get_tools():
    """获取可用的工具列表"""
    registry = get_registry()
    tools = []
    for tool in registry.get_all().values():
        # 转换为 LangChain 格式的工具
        try:
            from langchain_core.tools import tool as langchain_tool
            # 使用 LangChain 的 tool 装饰器包装
            @langchain_tool
            def wrapped_tool(**kwargs):
                return tool.execute(**kwargs).to_dict()
            wrapped_tool.name = tool.name
            wrapped_tool.description = tool.description
            tools.append(wrapped_tool)
        except Exception as e:
            logger.warning(f"Failed to convert tool {tool.name}: {e}")
    return tools


def should_continue(state: EmailAgentState) -> Literal["execute_tool", "end"]:
    """判断是否继续执行工具"""
    messages = state.get("messages", [])
    if not messages:
        return "end"
    
    last_message = messages[-1]
    
    # 检查最后一条消息是否有工具调用
    if isinstance(last_message, dict):
        content = last_message.get("content", "")
        # 如果消息中包含工具调用意图
        if "tool_calls" in last_message or ("action" in last_message and last_message.get("action")):
            return "execute_tool"
    
    # 如果是 AIMessage，检查 function_call 或 tool_calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "execute_tool"
    if hasattr(last_message, "function_call") and last_message.function_call:
        return "execute_tool"
    
    return "end"


def agent_node(state: EmailAgentState) -> EmailAgentState:
    """
    Agent 节点：调用 LLM 进行推理
    """
    logger.info("Agent node executing...")
    
    messages = state.get("messages", [])
    
    # 转换为 LangChain 消息格式
    lc_messages = _convert_messages(messages)
    
    # 获取工具
    tools = _get_tools()
    
    # 创建 LLM 绑定
    from openai import OpenAI
    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )
    
    # 使用 LangChain 的 ChatOpenAI
    try:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            temperature=0.7,
            max_tokens=1000
        )
        
        if tools:
            llm = llm.bind_tools(tools)
        
        # 调用 LLM
        response = llm.invoke(lc_messages)
        
        # 更新状态
        new_messages = messages + [_message_to_dict(response)]
        
        return {
            **state,
            "messages": new_messages,
            "current_response": response.content if hasattr(response, "content") else str(response)
        }
        
    except Exception as e:
        logger.error(f"Agent node error: {e}")
        return {
            **state,
            "messages": messages + [{"role": "assistant", "content": f"抱歉，处理您的请求时发生错误: {str(e)}"}],
            "current_response": f"抱歉，处理您的请求时发生错误: {str(e)}"
        }


def execute_tool_node(state: EmailAgentState) -> EmailAgentState:
    """
    执行工具节点
    """
    logger.info("Execute tool node executing...")
    
    messages = state.get("messages", [])
    tool_results = state.get("tool_results", [])
    tool_calls = state.get("tool_calls", [])
    
    if not messages:
        return state
    
    last_message = messages[-1]
    
    # 提取工具调用
    tool_call_info = _extract_tool_calls(last_message)
    
    if not tool_call_info:
        return {
            **state,
            "tool_results": tool_results + [{"error": "No tool call found"}]
        }
    
    registry = get_registry()
    
    for tc in tool_call_info:
        tool_name = tc.get("name")
        tool_args = tc.get("arguments", {})
        
        logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
        
        # 记录工具调用
        tool_calls.append(tc)
        
        # 执行工具
        result = registry.execute(tool_name, **tool_args)
        
        # 记录结果
        result_dict = {
            "tool": tool_name,
            "arguments": tool_args,
            "result": result.to_dict()
        }
        tool_results.append(result_dict)
        
        # 将工具结果添加到消息历史
        messages.append({
            "role": "tool",
            "content": result.raw_output or result.error or str(result.data),
            "tool_call_id": tc.get("id")
        })
    
    return {
        **state,
        "messages": messages,
        "tool_calls": tool_calls,
        "tool_results": tool_results
    }


def generate_response_node(state: EmailAgentState) -> EmailAgentState:
    """
    生成最终响应节点
    """
    logger.info("Generate response node executing...")
    
    messages = state.get("messages", [])
    tool_results = state.get("tool_results", [])
    
    # 如果已经有响应，直接返回
    if state.get("current_response"):
        return state
    
    # 从消息历史中获取最后一条 AI 响应
    response = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            response = msg.get("content", "")
            break
        elif hasattr(msg, "role") and msg.role == "assistant":
            response = msg.content or ""
            break
    
    # 如果没有响应，尝试生成一个
    if not response and tool_results:
        # 基于工具结果生成响应
        response = "我已经完成了您的请求，以下是结果：\n\n"
        for tr in tool_results:
            tool_name = tr.get("tool", "unknown")
            result_data = tr.get("result", {})
            response += f"**{tool_name}**: "
            if result_data.get("success"):
                response += f"{result_data.get('raw_output', '完成')}\n\n"
            else:
                response += f"失败 - {result_data.get('error', '未知错误')}\n\n"
    
    return {
        **state,
        "current_response": response
    }


def _convert_messages(messages: List[Dict[str, str]]) -> List:
    """将消息字典转换为 LangChain 消息对象"""
    lc_messages = []
    
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            elif role == "tool":
                lc_messages.append({
                    "role": "tool",
                    "content": content,
                    "tool_call_id": msg.get("tool_call_id")
                })
        elif hasattr(msg, "content"):  # 已经是 LangChain 消息对象
            lc_messages.append(msg)
    
    return lc_messages


def _message_to_dict(msg) -> Dict[str, Any]:
    """将 LangChain 消息对象转换为字典"""
    result = {
        "role": msg.type if hasattr(msg, "type") else "assistant",
        "content": msg.content if hasattr(msg, "content") else str(msg)
    }
    
    # 添加工具调用信息
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "name": tc.name,
                "arguments": tc.args
            }
            for tc in msg.tool_calls
        ]
    
    return result


def _extract_tool_calls(message) -> List[Dict[str, Any]]:
    """从消息中提取工具调用信息"""
    tool_calls = []
    
    if isinstance(message, dict):
        # 检查 tool_calls
        if "tool_calls" in message:
            for tc in message.get("tool_calls", []):
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "name": tc.get("name") or tc.get("function", {}).get("name"),
                    "arguments": tc.get("arguments") or tc.get("function", {}).get("arguments", {})
                })
        
        # 检查 action 字段（兼容自定义格式）
        action = message.get("action")
        if action:
            tool_calls.append({
                "id": "",
                "name": action,
                "arguments": message.get("action_input", {})
            })
    
    # 检查 AIMessage 的 tool_calls
    if hasattr(message, "tool_calls") and message.tool_calls:
        for tc in message.tool_calls:
            tool_calls.append({
                "id": tc.id,
                "name": tc.name,
                "arguments": tc.args
            })
    
    return tool_calls
