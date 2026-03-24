"""
LangGraph Email Agent 主类
基于 Supervisor 模式统一编排 6 个子 Agent，支持多意图并行执行
"""
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.types import Send
from langgraph.checkpoint.memory import MemorySaver

from app.agents.graph.state import EmailAgentState, EmailAgentOutput
from app.agents.graph.nodes import (
    classify_intent_node,
    parser_agent_node, summarizer_agent_node, notification_agent_node,
    query_agent_node, general_agent_node, react_agent_node,
    aggregate_and_respond_node,
)
from app.logger import Logger

logger = Logger.get("email_agent")


# ═══════════════════════════════════════════════════════════════════════════════
# EmailAgent 主类
# ═══════════════════════════════════════════════════════════════════════════════

class EmailAgent:
    """
    基于 LangGraph Supervisor 模式的邮件助手 Agent

    编排 6 个子 Agent：
    - parser_agent: 同步/解析邮件
    - summarizer_agent: 生成摘要
    - notification_agent: 发送通知
    - query_agent: 查询邮件/事件
    - general_agent: 通用问答
    - react_agent: ReAct 引擎（复杂多步推理）
    """

    def __init__(self, max_iterations: int = 10, timeout_seconds: int = 60):
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.graph = None
        self._build_graph()

    def _build_graph(self):
        """
        构建 LangGraph：

        1. classify_intent  - 调用 LLM 判断用户意图
        2. [并行子 Agent]   - 根据 intents 并行执行所有匹配的子 Agent（Send API）
        3. aggregate_and_respond - 汇总所有子 Agent 结果，生成最终自然语言响应
        """
        workflow = StateGraph(EmailAgentState)

        # ── 节点定义 ──────────────────────────────────────────────────────────
        workflow.add_node("classify_intent", classify_intent_node)
        workflow.add_node("aggregate_and_respond", aggregate_and_respond_node)

        workflow.add_node("parser_agent",        parser_agent_node)
        workflow.add_node("summarizer_agent",    summarizer_agent_node)
        workflow.add_node("notification_agent",  notification_agent_node)
        workflow.add_node("query_agent",         query_agent_node)
        workflow.add_node("general_agent",        general_agent_node)
        workflow.add_node("react_agent",          react_agent_node)

        # ── 入口 → 意图分类 ─────────────────────────────────────────────────
        workflow.set_entry_point("classify_intent")

        # ── 意图分类 → [并行子 Agent]（Send API 真正实现并行）────────────────
        workflow.add_conditional_edges(
            "classify_intent",
            fan_out_to_sub_agents,
            [
                "parser_agent",
                "summarizer_agent",
                "notification_agent",
                "query_agent",
                "general_agent",
                "react_agent",
            ]
        )

        # ── 所有子 Agent → 汇总 → 结束 ──────────────────────────────────────
        for agent in ["parser_agent", "summarizer_agent", "notification_agent",
                       "query_agent", "general_agent", "react_agent"]:
            workflow.add_edge(agent, "aggregate_and_respond")

        workflow.add_edge("aggregate_and_respond", END)

        # ── 编译 ─────────────────────────────────────────────────────────────
        checkpointer = MemorySaver()
        self.graph = workflow.compile(checkpointer=checkpointer)
        logger.info("EmailAgent compiled successfully")

    def _load_history(self, session_id: int) -> List[Dict[str, str]]:
        """从数据库加载对话历史"""
        try:
            from app.db import ChatMessage, SessionLocal
            db = SessionLocal()
            try:
                recent = (
                    db.query(ChatMessage)
                    .filter(ChatMessage.session_id == session_id)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(20)
                    .all()
                )
                history = [
                    {"role": m.role, "content": m.content}
                    for m in reversed(recent)
                    if m.role in ("user", "assistant")
                ]
                return history
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"加载对话历史失败: {e}")
            return []

    def chat(self, message: str, session_id: int = None,
             conversation_history: List[Dict[str, str]] = None,
             force_intent: str = None) -> EmailAgentOutput:
        """
        处理对话

        Args:
            message: 用户消息
            session_id: 会话 ID（用于加载历史，优先于 conversation_history）
            conversation_history: 直接传入的历史记录
            force_intent: 强制使用指定意图（覆盖自动分类，用于前端手动切换引擎模式）

        Returns:
            EmailAgentOutput: Agent 输出
        """
        logger.info(f"EmailAgent processing: {message[:50]}...")

        # 优先从 DB 加载历史，其次用传入的 history
        if session_id:
            history = self._load_history(session_id)
        elif conversation_history:
            history = conversation_history
        else:
            history = []

        # 构建消息列表
        messages = list(history)
        messages.append({"role": "user", "content": message})

        # 初始化状态
        initial_state: EmailAgentState = {
            "messages": messages,
            "intents": [],
            "intent_reasoning": None,
            "action_params": {},
            "agent_outputs": {},
            "final_response": None,
            "execution_status": "pending",
            "force_intent": force_intent,
        }

        try:
            config = {
                "configurable": {"thread_id": f"email-{session_id or 'default'}"},
                "recursion_limit": self.max_iterations,
            }

            result = None
            for step in self.graph.stream(initial_state, config):
                step_name = list(step.keys())[0] if step else "unknown"
                logger.debug(f"Graph step: {step_name}")
                result = step

            # 提取最终状态
            final_state = _extract_final_state(result)

            response = final_state.get("final_response", "") or "处理完成"
            intents = final_state.get("intents", [])

            logger.info(f"EmailAgent done: intents={intents}, response={response[:50]}...")

            return EmailAgentOutput(
                response=response,
                success=True,
                intents=intents
            )

        except Exception as e:
            logger.error(f"EmailAgent error: {e}")
            return EmailAgentOutput(
                response=f"处理请求时发生错误: {str(e)}",
                success=False,
                error=str(e)
            )

    def get_graph(self):
        """获取编译后的图"""
        return self.graph


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例缓存
# ═══════════════════════════════════════════════════════════════════════════════

_supervisor_agent: Optional[EmailAgent] = None


def get_supervisor_agent() -> EmailAgent:
    """获取全局 Supervisor Agent 实例"""
    global _supervisor_agent
    if _supervisor_agent is None:
        _supervisor_agent = EmailAgent()
    return _supervisor_agent


def get_email_agent() -> EmailAgent:
    """获取 EmailAgent 实例（别名）"""
    return get_supervisor_agent()


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def fan_out_to_sub_agents(state: EmailAgentState) -> List[Send]:
    """
    Supervisor 路由函数：返回 List[Send] 实现真正的并行执行

    根据 intents 列表，为每个匹配的意图返回一个 Send 对象。
    LangGraph 会并行触发所有 Send 对应的子 Agent，
    每个子 Agent 的结果写入 agent_outputs 字典的对应 key。
    """
    intents = state.get("intents", [])

    node_map = {
        "parser":       "parser_agent",
        "summarizer":   "summarizer_agent",
        "notification": "notification_agent",
        "query":        "query_agent",
        "general":      "general_agent",
        "react":        "react_agent",
    }

    # 收集所有需要执行的 agent（去重）
    agents_to_run = []
    seen = set()
    for intent in intents:
        node_name = node_map.get(intent)
        if node_name and node_name not in seen:
            agents_to_run.append(Send(node_name, state))
            seen.add(node_name)

    # 如果没有任何有效意图，默认执行 general
    if not agents_to_run:
        agents_to_run.append(Send("general_agent", state))

    logger.info(f"Fan-out to agents: {[s.node for s in agents_to_run]}")
    return agents_to_run


def _extract_final_state(result: Any) -> Dict[str, Any]:
    """从图执行结果中提取最终状态"""
    if not result:
        return {}

    if isinstance(result, dict):
        for node_name, node_state in result.items():
            if isinstance(node_state, dict) and "final_response" in node_state:
                return node_state
            if isinstance(node_state, dict) and "execution_status" in node_state:
                return node_state

    return {}
