"""
LangGraph Email Agent 主类 v2
意图路由 + 节点编排，支持 parser→summarizer→reply 串行依赖链

意图路由策略：
- parser_summarizer: 串行 chain（classify → parser → summarizer → reflect → aggregate）
- parser_only:      parser → aggregate
- summarizer_only:  summarizer → aggregate
- reply_only:       reply → confirm/cancel → reflect → aggregate
- query_only:       query → aggregate
- general_only:     general → aggregate
- multi_intent:     fan-out 并行（只执行请求的 agents，有依赖的串行）
- unknown:          general → aggregate
"""
from typing import Dict, Any, List, Literal, Optional, Union
from langgraph.graph import StateGraph, END
from langgraph.types import Send
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphInterrupt

from app.agents.graph.state import EmailAgentState, EmailAgentOutput, MultiIntentType
from app.agents.graph.nodes import (
    classify_intent_node,
    parser_agent_node, summarizer_agent_node, notification_agent_node,
    query_agent_node, general_agent_node, reply_agent_node,
    confirm_reply_node, cancel_reply_node,
    confirm_meeting_node, cancel_meeting_node,
    reflect_check_node,
    aggregate_and_respond_node,
    meeting_agent_node,
)
from app.logger import Logger

logger = Logger.get("email_agent")


# ═══════════════════════════════════════════════════════════════════════════════
# 意图路由函数（条件边路由函数）
# ═══════════════════════════════════════════════════════════════════════════════

def _route_intent(
    state: EmailAgentState,
) -> Union[str, List[Send]]:
    """
    意图路由：根据 classify_intent 返回的 intents 组合决定流向。

    LangGraph 规范：
    - 返回 string → 串行到该节点
    - 返回 List[Send] → fan-out 并行执行所有 Send 目标节点

    路由规则：
    - parser + summarizer（且无其他） → parser_summarizer（串行）
    - 仅 parser                          → parser_only
    - 仅 summarizer                       → summarizer_only
    - 仅 query                            → query_only
    - 仅 general                          → general_only
    - 仅 reply                            → reply_only
    - 多个不同意图                        → multi_intent（只 fan-out 请求的 agents）
    - 无效                                → unknown
    """
    intents = state.get("intents", [])
    unique_intents = list(dict.fromkeys(intents))

    if not unique_intents:
        return MultiIntentType.UNKNOWN.value

    # 单一意图 → 串行到第一跳节点
    if len(unique_intents) == 1:
        intent = unique_intents[0]
        mapping = {
            "parser":     MultiIntentType.PARSE_ONLY.value,
            "summarizer": MultiIntentType.SUMMARIZER_ONLY.value,
            "query":      MultiIntentType.QUERY_ONLY.value,
            "general":    MultiIntentType.GENERAL_ONLY.value,
            "reply":      MultiIntentType.REPLY_ONLY.value,
            "meeting":    MultiIntentType.MEETING_ONLY.value,
        }
        return mapping.get(intent, MultiIntentType.UNKNOWN.value)

    # 多个意图
    if set(unique_intents) == {"parser", "summarizer"}:
        return "parser_agent"  # 串行链：parser → summarizer → reply → confirm/cancel → reflect → aggregate

    # multi_intent：只 fan-out 用户请求的那些 agent
    logger.info(f"Routing multi_intent: {unique_intents}")
    sends: List[Send] = []

    # parser / summarizer / reply → 串行依赖链，只触发第一个
    if "parser" in unique_intents:
        sends.append(Send("parser_agent", state))
    elif "summarizer" in unique_intents:
        sends.append(Send("summarizer_agent", state))
    elif "reply" in unique_intents:
        sends.append(Send("reply_agent", state))

    # 独立 agent → 并行
    if "notification" in unique_intents:
        sends.append(Send("notification_agent", state))
    if "query" in unique_intents:
        sends.append(Send("query_agent", state))
    if "general" in unique_intents:
        sends.append(Send("general_agent", state))
    if "meeting" in unique_intents:
        sends.append(Send("meeting_agent", state))

    return sends if sends else ["general_agent"]


def _route_after_reply(state: EmailAgentState) -> str:
    """
    reply_agent 执行 interrupt 后，用户确认/取消时决定下一跳。

    从 state["pending_draft"]["confirmed"] 读取用户选择：
    - True  → confirm_reply（实际发送）
    - False → cancel_reply（取消）
    """
    draft = state.get("pending_draft", {})
    confirmed = draft.get("confirmed")
    logger.info(f"Route after reply: confirmed={confirmed}")
    return "confirm" if confirmed is True else "cancel"


def _route_after_meeting(state: EmailAgentState) -> str:
    """
    meeting_agent 执行 interrupt 后，用户确认/取消时决定下一跳。

    从 state["pending_meeting"]["confirmed"] 读取用户选择：
    - True  → confirm_meeting（写 DB + 发邮件）
    - False → cancel_meeting（不操作）
    """
    pending = state.get("pending_meeting", {})
    confirmed = pending.get("confirmed")
    logger.info(f"Route after meeting: confirmed={confirmed}")
    return "confirm_meeting" if confirmed is True else "cancel_meeting"


# ═══════════════════════════════════════════════════════════════════════════════
# EmailAgent 主类
# ═══════════════════════════════════════════════════════════════════════════════

class EmailAgent:
    """
    基于 LangGraph 的邮件助手 Agent v2

    编排 8 个节点：
    - classify_intent: 意图分类
    - parser_agent: 同步/解析邮件
    - summarizer_agent: 生成摘要（依赖 parser）
    - reply_agent: 生成回复草稿（依赖 summarizer）
    - notification_agent: 发送通知
    - query_agent: 查询邮件/事件
    - general_agent: 通用问答
    - reflect_check: 自检节点
    """

    def __init__(self, max_iterations: int = 10, timeout_seconds: int = 60):
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.graph = None
        self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(EmailAgentState)

        # ── 节点定义 ──────────────────────────────────────────────────────
        workflow.add_node("classify_intent", classify_intent_node)

        workflow.add_node("parser_agent",        parser_agent_node)
        workflow.add_node("summarizer_agent",    summarizer_agent_node)
        workflow.add_node("notification_agent",  notification_agent_node)
        workflow.add_node("query_agent",         query_agent_node)
        workflow.add_node("general_agent",        general_agent_node)
        workflow.add_node("reply_agent",          reply_agent_node)
        workflow.add_node("meeting_agent",       meeting_agent_node)
        workflow.add_node("confirm_reply",        confirm_reply_node)
        workflow.add_node("cancel_reply",         cancel_reply_node)
        workflow.add_node("confirm_meeting",     confirm_meeting_node)
        workflow.add_node("cancel_meeting",      cancel_meeting_node)
        workflow.add_node("reflect_check",        reflect_check_node)

        workflow.add_node("aggregate_and_respond", aggregate_and_respond_node)

        # ── 入口 → 意图分类 ─────────────────────────────────────────────
        workflow.set_entry_point("classify_intent")

        # ── 意图分类 → 路由条件边 ─────────────────────────────────────────
        # _route_intent 返回 string → 串行；返回 List[Send] → fan-out 并行
        workflow.add_conditional_edges(
            "classify_intent",
            _route_intent,
            {
                # parser_only: parser → aggregate
                MultiIntentType.PARSE_ONLY.value: "parser_agent",

                # summarizer_only: summarizer → aggregate（不会误触发 reply）
                MultiIntentType.SUMMARIZER_ONLY.value: "summarizer_agent",

                # query_only: query → aggregate
                MultiIntentType.QUERY_ONLY.value: "query_agent",

                # general_only: general → aggregate
                MultiIntentType.GENERAL_ONLY.value: "general_agent",

                # reply_only: reply → confirm/cancel → reflect → aggregate
                MultiIntentType.REPLY_ONLY.value: "reply_agent",

                # meeting_only: meeting → aggregate
                MultiIntentType.MEETING_ONLY.value: "meeting_agent",

                # unknown: general → aggregate
                MultiIntentType.UNKNOWN.value: "general_agent",
            }
        )

        # ── reply → 确认/取消条件边 ───────────────────────────────────
        workflow.add_conditional_edges(
            "reply_agent",
            _route_after_reply,
            {
                "confirm": "confirm_reply",
                "cancel": "cancel_reply",
            }
        )

        # ── meeting → 确认/取消条件边 ──────────────────────────────────
        workflow.add_conditional_edges(
            "meeting_agent",
            _route_after_meeting,
            {
                "confirm_meeting": "confirm_meeting",
                "cancel_meeting": "cancel_meeting",
            }
        )

        # ── 普通边：串行链后续节点 ────────────────────────────────────────

        # parser_summarizer 串行链：parser → summarizer → reply → confirm/cancel → reflect → aggregate
        workflow.add_edge("parser_agent",       "summarizer_agent")
        workflow.add_edge("summarizer_agent",   "reply_agent")

        # summarizer_only: summarizer → aggregate（reply 需单独触发）
        workflow.add_edge("summarizer_agent",   "aggregate_and_respond")

        # parser_only: parser → aggregate（无 reflect）
        workflow.add_edge("parser_agent",       "aggregate_and_respond")

        # confirm/cancel → reflect → aggregate
        workflow.add_edge("confirm_reply",      "reflect_check")
        workflow.add_edge("cancel_reply",       "aggregate_and_respond")

        # confirm/cancel_meeting → reflect → aggregate
        workflow.add_edge("confirm_meeting",   "reflect_check")
        workflow.add_edge("cancel_meeting",    "aggregate_and_respond")

        # query_only / general_only / meeting_only → aggregate
        workflow.add_edge("query_agent",         "aggregate_and_respond")
        workflow.add_edge("general_agent",      "aggregate_and_respond")
        workflow.add_edge("meeting_agent",     "aggregate_and_respond")

        # multi_intent fan-out → reflect → aggregate
        workflow.add_edge("reflect_check",       "aggregate_and_respond")

        # ── 结束 ─────────────────────────────────────────────────────────
        workflow.add_edge("aggregate_and_respond", END)

        # ── 编译 ─────────────────────────────────────────────────────────
        checkpointer = MemorySaver()
        self.graph = workflow.compile(checkpointer=checkpointer)
        logger.info("EmailAgent v2 compiled successfully")

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

        if session_id:
            history = self._load_history(session_id)
        elif conversation_history:
            history = conversation_history
        else:
            history = []

        messages = list(history)
        messages.append({"role": "user", "content": message})

        initial_state: EmailAgentState = {
            "messages": messages,
            "intents": [],
            "intent_reasoning": None,
            "action_params": {},
            "agent_outputs": {},
            "final_response": None,
            "execution_status": "pending",
            "force_intent": force_intent,
            "pending_draft": None,
            "pending_meeting": None,
            "executed_nodes": [],
        }

        try:
            thread_id = f"email-{session_id or 'default'}"
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": self.max_iterations,
            }

            result = self.graph.invoke(initial_state, config)
            final_state = _extract_final_state(result)

            response = final_state.get("final_response", "") or "处理完成"
            intents = final_state.get("intents", [])

            logger.info(f"EmailAgent done: intents={intents}, response={response[:50]}...")

            return EmailAgentOutput(
                response=response,
                success=True,
                intents=intents
            )

        except GraphInterrupt as e:
            # interrupt 触发：reply_agent 生成了草稿，等待用户确认
            interrupt_value = e.args[0] if e.args else {}
            logger.info(f"EmailAgent interrupted: {interrupt_value.get('title', '')}")
            # 抛出给上层（routes_agents）处理，携带 interrupt 数据
            raise GraphInterrupt(interrupt_value)

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

    def get_pending_interrupt(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """读取指定线程的挂起确认状态，供会话恢复时展示确认卡片。"""
        try:
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": self.max_iterations,
            }
            checkpoint_state = self.graph.get_state(config)
            vals = getattr(checkpoint_state, "values", {}) or {}

            pending_draft = vals.get("pending_draft") or {}
            if pending_draft and pending_draft.get("confirmed") is None:
                return {
                    "type": "confirmation",
                    "title": "确认发送邮件",
                    "message": f"正在回复：{pending_draft.get('sender_email', '未知发件人')}",
                    "email_id": pending_draft.get("email_id"),
                    "draft_content": pending_draft.get("draft_content", ""),
                    "sender_email": pending_draft.get("sender_email"),
                }

            pending_meeting = vals.get("pending_meeting") or {}
            if pending_meeting and pending_meeting.get("confirmed") is None:
                decision = pending_meeting.get("llm_decision", "accept")
                return {
                    "type": "confirmation",
                    "title": "确认会议 RSVP",
                    "message": f"会议：{pending_meeting.get('title', '未命名会议')}，建议操作：{decision}",
                    "event_id": pending_meeting.get("event_id"),
                    "draft_content": pending_meeting.get("llm_suggestion", ""),
                    "llm_decision": decision,
                }

            return None
        except Exception as e:
            logger.warning(f"读取挂起 interrupt 失败: {e}")
            return None

    def resume(self, thread_id: str, confirmed: bool) -> EmailAgentOutput:
        """
        用户确认/取消后恢复 LangGraph 执行。

        Args:
            thread_id: 打断点的会话 ID（来自 interrupt 通知的 thread_id）
            confirmed: True = 确认发送，False = 取消

        Returns:
            EmailAgentOutput: 恢复执行后的结果
        """
        logger.info(f"EmailAgent resuming: thread_id={thread_id}, confirmed={confirmed}")

        try:
            # 从 checkpoint 恢复状态，更新 confirmed 字段
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": self.max_iterations,
            }

            # 读取 checkpoint，更新 pending_draft / pending_meeting 的 confirmed
            checkpoint_state = self.graph.get_state(config)
            vals = checkpoint_state.values

            # reply interrupt
            current_draft = vals.get("pending_draft", {})
            if current_draft and confirmed is not None:
                current_draft["confirmed"] = confirmed
                self.graph.update_state(config, {"pending_draft": current_draft})

            # meeting interrupt
            current_meeting = vals.get("pending_meeting", {})
            if current_meeting and confirmed is not None:
                current_meeting["confirmed"] = confirmed
                self.graph.update_state(config, {"pending_meeting": current_meeting})

            # 从断点恢复执行
            result = self.graph.invoke(None, config)
            final_state = _extract_final_state(result)

            response = final_state.get("final_response", "") or "处理完成"
            intents = final_state.get("intents", [])

            logger.info(f"EmailAgent resumed: response={response[:50]}...")

            return EmailAgentOutput(
                response=response,
                success=True,
                intents=intents
            )

        except GraphInterrupt as e:
            logger.error(f"EmailAgent resume interrupted unexpectedly: {e}")
            return EmailAgentOutput(
                response=f"恢复执行时发生错误: {str(e)}",
                success=False,
                error=str(e)
            )
        except Exception as e:
            logger.error(f"EmailAgent resume error: {e}")
            return EmailAgentOutput(
                response=f"恢复执行时发生错误: {str(e)}",
                success=False,
                error=str(e)
            )


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

def _extract_final_state(result: Any) -> Dict[str, Any]:
    """从图执行结果中提取最终状态（按节点名而非 dict 顺序）"""
    if not result:
        return {}

    if isinstance(result, dict):
        if "final_response" in result or "execution_status" in result:
            return result
        if "aggregate_and_respond" in result:
            return result["aggregate_and_respond"]
        for key in ["reflect_check", "general_agent", "parser_agent",
                     "query_agent", "summarizer_agent", "meeting_agent"]:
            if key in result:
                node_state = result[key]
                if isinstance(node_state, dict):
                    if "final_response" in node_state:
                        return node_state
                    if "execution_status" in node_state:
                        return node_state

    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# v1 兼容：保留 fan_out_to_sub_agents（已废弃）
# ═══════════════════════════════════════════════════════════════════════════════

def fan_out_to_sub_agents(state: EmailAgentState) -> List[Send]:
    """[已废弃] 请使用 _route_intent"""
    logger.warning("fan_out_to_sub_agents is deprecated, use _route_intent")
    return [Send("general_agent", state)]
