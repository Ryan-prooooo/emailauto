"""
LangGraph Agent 节点定义 v3
意图路由 + 节点编排，支持 parser→summarizer→reply 串行依赖链
reply 节点生成草稿后用 interrupt 挂起，等用户确认后 confirm/cancel
"""
import json
import re
from typing import Dict, Any, List, Optional

from app.agents.graph.state import EmailAgentState, IntentType
from app.agents.tools import get_registry
from app.config import settings
from app.logger import Logger

logger = Logger.get("graph_nodes")

# ═══════════════════════════════════════════════════════════════════════════════
# 全局 LLM client（单例，复用连接）
# ═══════════════════════════════════════════════════════════════════════════════

_llm_client: Optional[Any] = None


def _get_llm(temperature: float = 0.1, max_tokens: int = 500, timeout: int = 60):
    """获取单例 LLM client，避免重复创建连接"""
    global _llm_client
    if _llm_client is None:
        from langchain_openai import ChatOpenAI
        _llm_client = ChatOpenAI(
            model=settings.DASHSCOPE_MODEL,
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.DASHSCOPE_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
        )
    return _llm_client


# ═══════════════════════════════════════════════════════════════════════════════
# classify_intent_node - 意图分类
# ═══════════════════════════════════════════════════════════════════════════════

INTENT_SCHEMA = {
    "name": "classify_intent",
    "description": "分析用户消息，判断用户想要执行的任务类型和参数",
    "parameters": {
        "type": "object",
        "properties": {
            "intents": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["parser", "summarizer", "notification", "query", "general", "reply", "meeting", "meeting_agent"]
                },
                "description": "意图列表，支持多意图。例如：['parser'] 或 ['query', 'reply']。",
                "minItems": 1,
                "maxItems": 5
            },
            "reasoning": {
                "type": "string",
                "description": "判断理由，说明为什么选择这些意图"
            },
            "params": {
                "type": "object",
                "description": "操作参数",
                "properties": {
                    "limit": {"type": "integer", "description": "查询/处理数量限制，默认20"},
                    "action": {"type": "string", "description": "通知动作：send_summary / send_event"},
                    "to_email": {"type": "string", "description": "目标邮箱"},
                    "event_id": {"type": "integer", "description": "事件ID"},
                    "query_type": {
                        "type": "string",
                        "description": "查询类型",
                        "enum": ["all", "emails", "events"]
                    },
                    "email_id": {
                        "type": "integer",
                        "description": "待回复的邮件 ID"
                    },
                    "tone": {
                        "type": "string",
                        "description": "回复语气：professional / friendly / casual"
                    },
                    "custom_prompt": {
                        "type": "string",
                        "description": "自定义提示词"
                    },
                    "sender_email": {
                        "type": "string",
                        "description": "发件人地址（reflect_check 核对收件人身份时使用）"
                    },
                    "rsvp_status": {
                        "type": "string",
                        "description": "RSVP 决策：accept / decline / tentative（meeting 意图时使用）",
                        "enum": ["accept", "decline", "tentative"]
                    }
                }
            }
        },
        "required": ["intents", "reasoning"]
    }
}


def classify_intent_node(state: EmailAgentState) -> Dict[str, Any]:
    """意图分类节点：调用 LLM 结构化输出判断用户意图"""
    messages = state.get("messages", [])
    user_message = _get_last_user_message(messages)

    if not user_message:
        return {
            "intents": [IntentType.GENERAL.value],
            "intent_reasoning": "无法获取用户消息",
            "action_params": {}
        }

    force_intent = state.get("force_intent")
    if force_intent:
        valid_intents = [e.value for e in IntentType]
        if force_intent in valid_intents:
            logger.info(f"ClassifyIntent: force_intent={force_intent}")
            return {
                "intents": [force_intent],
                "intent_reasoning": f"前端手动切换为 {force_intent} 模式",
                "action_params": {}
            }

    try:
        llm = _get_llm(temperature=0.1, max_tokens=500).bind_tools(
            [INTENT_SCHEMA], tool_choice="classify_intent"
        )

        system_prompt = """你是一个智能邮件助手，负责分析用户的请求并选择合适的任务类型。

【意图类型】
- parser: 同步/解析邮件、提取事件
- summarizer: 总结邮件内容、生成摘要
- notification: 发送通知或每日摘要
- query: 查询邮件列表、事件列表（包括按 meeting 类型筛选）
- reply: 生成邮件回复草稿（看完解析和摘要后生成，需用户确认才发送）
- meeting: 会议 RSVP 决策（查看待回复会议、判断是否接受/拒绝）
- general: 通用问答、问候、闲聊

【重要规则】
1. 每次分析必须返回至少一个意图
2. 支持多意图：例如"同步邮件并生成摘要"应返回 ["parser", "summarizer"]
3. 用户要求回复邮件时使用 ["parser", "summarizer", "reply"]
4. 用户询问待回复的会议时使用 ["meeting"] 或 ["query", "meeting"]
5. 优先使用具体意图而不是 general"""

        from langchain_core.messages import SystemMessage, HumanMessage
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])

        args = _parse_llm_response(response, user_message)

        intents = args.get("intents", [IntentType.GENERAL.value])
        reasoning = args.get("reasoning", "")
        params = args.get("params") or {}

        valid_intents = [e.value for e in IntentType]
        intents = [("meeting" if i == "meeting_agent" else i) for i in intents if ("meeting" if i == "meeting_agent" else i) in valid_intents]
        if not intents:
            intents = [IntentType.GENERAL.value]

        logger.info(f"ClassifyIntent: intents={intents}")

        return {
            "intents": intents,
            "intent_reasoning": reasoning,
            "action_params": params
        }

    except Exception as e:
        logger.error(f"ClassifyIntent error: {e}")
        return {
            "intents": [IntentType.GENERAL.value],
            "intent_reasoning": f"意图分类出错: {str(e)}",
            "action_params": {}
        }


def _parse_llm_response(response, user_message: str) -> Dict[str, Any]:
    """解析 LLM 结构化输出"""
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_call = response.tool_calls[0]
        raw_args = tool_call.get("arguments") or tool_call.get("args", "{}")
        if isinstance(raw_args, str):
            raw_args = raw_args.strip()
            if raw_args.startswith("```json"):
                raw_args = re.sub(r"```json\n?", "", raw_args)
                raw_args = raw_args.strip().rstrip("```").strip()
            return json.loads(raw_args)
        return raw_args

    if hasattr(response, "additional_kwargs"):
        kwargs = response.additional_kwargs
        if "function" in kwargs:
            func_call = kwargs["function"]
            args_str = func_call.get("arguments", "{}")
            return json.loads(args_str)

    return _parse_fallback_response(user_message)


def _parse_fallback_response(user_message: str) -> Dict[str, Any]:
    """结构化输出失败时的兜底解析"""
    content_lower = user_message.lower()
    intents = []

    if any(kw in content_lower for kw in ["同步", "解析", "拉取邮件", "fetch", "收取"]):
        intents.append("parser")
    if any(kw in content_lower for kw in ["摘要", "总结", "生成", "summary"]):
        intents.append("summarizer")
    if any(kw in content_lower for kw in ["通知", "发送", "send", "notify"]):
        intents.append("notification")
    if any(kw in content_lower for kw in ["查询", "查看", "列出", "有什么", "list", "邮件列表", "事件列表"]):
        intents.append("query")
    if any(kw in content_lower for kw in ["回复", "reply", "draft", "草稿"]):
        intents.append("reply")
    if any(kw in content_lower for kw in ["你好", "hi", "hello", "帮忙"]):
        intents.append("general")

    if not intents:
        intents = ["general"]

    return {"intents": intents, "reasoning": "Fallback parsing", "params": {}}


# ═══════════════════════════════════════════════════════════════════════════════
# 7 个子 Agent 节点
# ═══════════════════════════════════════════════════════════════════════════════

def parser_agent_node(state: EmailAgentState) -> Dict[str, Any]:
    """Parser 节点：同步邮件 + 解析邮件 + 写 DB"""
    logger.info("Parser agent node executing...")
    params = state.get("action_params") or {}
    limit = params.get("limit", 10)

    try:
        from app.agents.agents import ParserAgent
        parser = ParserAgent()
        sub_result = parser.execute({"limit": limit})

        return {
            "agent_outputs": {"parser": {
                "success": sub_result.success,
                "data": sub_result.data,
                "error": sub_result.error,
                "limit": limit
            }},
            "execution_status": "completed" if sub_result.success else "error"
        }

    except Exception as e:
        logger.error(f"Parser agent error: {e}")
        return {
            "agent_outputs": {"parser": {"success": False, "error": str(e)}},
            "execution_status": "error"
        }


def summarizer_agent_node(state: EmailAgentState) -> Dict[str, Any]:
    """Summarizer 节点：查 DB + 生成 AI 摘要 + 归档 Notion"""
    logger.info("Summarizer agent node executing...")

    try:
        from app.agents.agents import SummarizerAgent
        summarizer = SummarizerAgent()
        sub_result = summarizer.execute({})

        return {
            "agent_outputs": {"summarizer": {
                "success": sub_result.success,
                "data": sub_result.data,
                "error": sub_result.error
            }},
            "execution_status": "completed" if sub_result.success else "error"
        }

    except Exception as e:
        logger.error(f"Summarizer agent error: {e}")
        return {
            "agent_outputs": {"summarizer": {"success": False, "error": str(e)}},
            "execution_status": "error"
        }


def reply_agent_node(state: EmailAgentState) -> Dict[str, Any]:
    """
    Reply 节点：看完解析和摘要后，生成邮件回复草稿，然后 interrupt 挂起等用户确认。

    流程：draft_email_reply（生成草稿）→ interrupt（挂起）
          → 用户点确认/取消 → confirm_reply_node / cancel_reply_node（实际发送/取消）
    """
    logger.info("Reply agent node executing...")
    params = state.get("action_params") or {}
    sender_email = params.get("sender_email", "")
    tone = params.get("tone", "professional")
    custom_prompt = params.get("custom_prompt", "")

    try:
        registry = get_registry()

        # 读取 summarizer 的输出作为上下文
        summarizer_data = state.get("agent_outputs", {}).get("summarizer") or {}
        summarizer_payload = summarizer_data.get("data") or {}
        summary_text = summarizer_payload.get("summary", "")

        # 获取待回复的邮件 ID
        email_id = params.get("email_id")
        if not email_id:
            try:
                from app.db import Email, SessionLocal
                db = SessionLocal()
                try:
                    latest = db.query(Email).order_by(Email.date.desc()).first()
                    email_id = latest.id if latest else None
                finally:
                    db.close()
            except Exception as db_err:
                logger.warning(f"获取最新邮件 ID 失败: {db_err}")

        if not email_id:
            return {
                "agent_outputs": {"reply": {"success": False, "error": "未找到可回复的邮件"}},
                "execution_status": "error"
            }

        # 构建回复上下文
        if summary_text:
            context_note = f"\n\n【邮件摘要上下文】\n{summary_text}"
            custom_prompt = (custom_prompt + context_note).strip()

        # 生成草稿
        result = registry.execute(
            "draft_email_reply",
            email_id=email_id,
            tone=tone,
            custom_prompt=custom_prompt or None
        )

        if not result.success:
            return {
                "agent_outputs": {"reply": {"success": False, "error": result.error}},
                "execution_status": "error"
            }

        draft_content = result.raw_output or ""

        # 写入 pending_draft 供 resume 时读取
        pending_draft = {
            "draft_content": draft_content,
            "email_id": email_id,
            "sender_email": sender_email,
            "tone": tone,
            "confirmed": None
        }

        # interrupt 挂起图执行，通知前端展示草稿等待确认
        from langgraph.types import interrupt
        from app.db import Email as DBEmail, SessionLocal as DBSession
        db = DBSession()
        try:
            email_obj = db.query(DBEmail).filter(DBEmail.id == email_id).first()
            sender_display = email_obj.sender if email_obj else sender_email
            subject_display = email_obj.subject if email_obj else ""
        finally:
            db.close()

        logger.info(f"Reply agent: draft generated, interrupting for confirmation. email_id={email_id}")

        interrupt({
            "type": "confirmation",
            "title": "确认发送邮件",
            "message": f"正在回复：{sender_display} - {subject_display}",
            "email_id": email_id,
            "draft_content": draft_content,
            "sender_email": sender_display,
        })

        # interrupt 后不会执行到这里，此处 return 仅作为类型占位
        return {
            "agent_outputs": {"reply": {"success": True, "draft_content": draft_content}},
            "pending_draft": pending_draft,
            "execution_status": "interrupted"
        }

    except Exception as e:
        logger.error(f"Reply agent error: {e}")
        return {
            "agent_outputs": {"reply": {"success": False, "error": str(e)}},
            "execution_status": "error"
        }


def confirm_reply_node(state: EmailAgentState) -> Dict[str, Any]:
    """
    用户确认发送：从 pending_draft 读取草稿，调用 reply_email 真正发送。
    仅在 user_confirmed=True 时执行。
    """
    logger.info("Confirm reply node executing...")
    draft = state.get("pending_draft", {})

    if draft.get("confirmed") is not True:
        logger.warning("confirm_reply_node called but confirmed != True, skipping")
        return {"execution_status": "completed"}

    try:
        registry = get_registry()
        result = registry.execute(
            "reply_email",
            email_id=draft.get("email_id"),
            reply_content=draft.get("draft_content"),
            tone=draft.get("tone", "professional")
        )

        return {
            "agent_outputs": {"send": {
                "success": result.success,
                "data": result.data,
                "error": result.error if not result.success else "",
                "action": "reply_sent"
            }},
            "execution_status": "completed" if result.success else "error"
        }

    except Exception as e:
        logger.error(f"Confirm reply error: {e}")
        return {
            "agent_outputs": {"send": {"success": False, "error": str(e), "action": "reply_sent"}},
            "execution_status": "error"
        }


def cancel_reply_node(state: EmailAgentState) -> Dict[str, Any]:
    """
    用户取消：不发送邮件，直接返回取消消息。
    仅在 user_confirmed=False 时执行。
    """
    logger.info("Cancel reply node executing...")
    draft = state.get("pending_draft", {})
    sender = draft.get("sender_email", "发件人")

    return {
        "final_response": f"已取消发送回复给 {sender}。如需重新生成，请再次发送「帮我回复这封邮件」。",
        "execution_status": "completed"
    }


def notification_agent_node(state: EmailAgentState) -> Dict[str, Any]:
    """Notification 节点：发送每日摘要邮件或事件通知"""
    logger.info("Notification agent node executing...")
    params = state.get("action_params") or {}
    action = params.get("action", "send_summary")
    to_email = params.get("to_email")
    event_id = params.get("event_id")

    try:
        from app.agents.agents import NotificationAgent
        notif = NotificationAgent()
        sub_result = notif.execute({}, action=action, to_email=to_email, event_id=event_id)

        return {
            "agent_outputs": {"notification": {
                "success": sub_result.success,
                "data": sub_result.data,
                "error": sub_result.error,
                "action": action
            }},
            "execution_status": "completed" if sub_result.success else "error"
        }

    except Exception as e:
        logger.error(f"Notification agent error: {e}")
        return {
            "agent_outputs": {"notification": {"success": False, "error": str(e)}},
            "execution_status": "error"
        }


def query_agent_node(state: EmailAgentState) -> Dict[str, Any]:
    """Query 节点：查询邮件列表 + 事件列表"""
    logger.info("Query agent node executing...")
    params = state.get("action_params", {})
    limit = params.get("limit", 20)
    query_type = params.get("query_type", "all")

    try:
        registry = get_registry()
        emails_data = []
        events_data = []

        if query_type in ("all", "emails"):
            result = registry.execute("get_emails", limit=limit)
            if result.success:
                emails_data = result.data.get("emails", []) if result.data else []

        if query_type in ("all", "events"):
            result = registry.execute("get_events", limit=limit)
            if result.success:
                events_data = result.data.get("events", []) if result.data else []

        return {
            "agent_outputs": {"query": {
                "success": True,
                "emails": emails_data,
                "events": events_data,
                "email_count": len(emails_data),
                "event_count": len(events_data),
                "query_type": query_type
            }},
            "execution_status": "completed"
        }

    except Exception as e:
        logger.error(f"Query agent error: {e}")
        return {
            "agent_outputs": {"query": {"success": False, "error": str(e)}},
            "execution_status": "error"
        }


def general_agent_node(state: EmailAgentState) -> Dict[str, Any]:
    """General 节点：通用问答，LLM 直接回答（不调工具）"""
    logger.info("General agent node executing...")
    messages = state.get("messages", [])
    user_message = _get_last_user_message(messages)

    try:
        from app.db import Email, Event, SessionLocal
        db = SessionLocal()
        try:
            recent_emails = db.query(Email).order_by(Email.date.desc()).limit(5).all()
            recent_events = db.query(Event).order_by(Event.created_at.desc()).limit(5).all()
            context_parts = []
            if recent_emails:
                context_parts.append("=== 最近邮件 ===")
                for e in recent_emails:
                    context_parts.append(f"- {e.sender}: {e.subject}")
            if recent_events:
                context_parts.append("=== 最近事件 ===")
                for e in recent_events:
                    context_parts.append(f"- [{e.event_type}] {e.title}")
            realtime_context = "\n".join(context_parts) if context_parts else "暂无数据"
        finally:
            db.close()

        from langchain_core.messages import SystemMessage, HumanMessage
        response = _get_llm(temperature=0.7, max_tokens=500).invoke([
            SystemMessage(content=f"你是一个友好的智能邮件助手。\n\n【当前数据】\n{realtime_context}\n\n如果用户问的是邮件或事件相关问题，可以结合上面的数据回答。"),
            HumanMessage(content=user_message or "你好")
        ])
        content = response.content if hasattr(response, "content") else str(response)

        return {
            "agent_outputs": {"general": {"success": True, "response": content}},
            "execution_status": "completed"
        }

    except Exception as e:
        logger.error(f"General agent error: {e}")
        return {
            "agent_outputs": {"general": {"success": False, "error": str(e)}},
            "execution_status": "error"
        }


# ═══════════════════════════════════════════════════════════════════════════════
# reflect_check_node - 自检节点
# ═══════════════════════════════════════════════════════════════════════════════

def reflect_check_node(state: EmailAgentState) -> Dict[str, Any]:
    """
    自检节点（精简版）：仅在含 reply 输出的链路执行。
    检查范围：草稿内容安全、收件人地址匹配。
    """
    logger.info("reflect_check_node executing (reply-only)...")
    agent_outputs = state.get("agent_outputs") or {}
    pending_draft = state.get("pending_draft") or {}
    reply_output = agent_outputs.get("reply", {})
    send_output = agent_outputs.get("send", {})

    # 仅在含 reply 的链路执行检查
    if not (reply_output or send_output or pending_draft):
        return {}

    all_passed = True
    concerns: List[str] = []

    # 1. 草稿内容安全检查
    draft_content = (
        pending_draft.get("draft_content")
        or reply_output.get("draft_content")
        or ""
    )
    if draft_content:
        safe_result = _check_content_safety(draft_content)
        if not safe_result.get("passed"):
            all_passed = False
            concerns.extend(safe_result.get("concerns", []))

    # 2. 收件人 + 被回复邮件原文核对
    email_id = pending_draft.get("email_id") or reply_output.get("email_id")
    if email_id and draft_content:
        recipient_result = _check_recipient(email_id, draft_content)
        if not recipient_result.get("passed"):
            all_passed = False
            concerns.extend(recipient_result.get("concerns", []))

    summary = "检查通过。" if all_passed else f"检查未通过：{'；'.join(concerns)}"
    logger.info(f"reflect_check done: all_passed={all_passed}, concerns={concerns}")

    return {
        "agent_outputs": {"reflect": {
            "success": all_passed,
            "passed": all_passed,
            "concerns": concerns,
            "summary": summary,
        }},
        "execution_status": "completed" if all_passed else "needs_review",
    }


def _check_content_safety(content: str) -> Dict[str, Any]:
    """检查草稿内容是否包含敏感信息"""
    concerns: List[str] = []
    sensitive_patterns = {
        "password":  r"(?i)(password|pwd|密码)\s*[:=]",
        "bank_card": r"\b\d{13,19}\b",
        "api_key":   r"(?i)(api[_-]?key|secret)\s*[:=]",
        "injection": r"(?i)(ignore previous|disregard|你是一个)",
    }
    for pattern_name, regex in sensitive_patterns.items():
        if re.search(regex, content):
            concerns.append(f"检测到敏感信息：{pattern_name}")
    if len(content) > 5000:
        concerns.append("内容过长（> 5000 字符）")
    return {"passed": len(concerns) == 0, "concerns": concerns}


def _check_recipient(email_id: int, draft_content: str) -> Dict[str, Any]:
    """从 DB 查出被回复邮件的 sender，核验收件人地址是否匹配"""
    concerns: List[str] = []
    try:
        from app.db import Email as DBEmail, SessionLocal as DBSession
        db = DBSession()
        try:
            email_obj = db.query(DBEmail).filter(DBEmail.id == email_id).first()
            if not email_obj:
                concerns.append(f"无法查到邮件 ID={email_id}，无法核对收件人")
                return {"passed": False, "concerns": concerns}
            original_sender = (email_obj.sender or "").strip()
            if not original_sender:
                concerns.append("被回复邮件缺少 sender 字段")
        finally:
            db.close()
    except Exception as e:
        concerns.append(f"数据库查询失败：{e}")
        return {"passed": False, "concerns": concerns}

    return {"passed": len(concerns) == 0, "concerns": concerns}


# ═══════════════════════════════════════════════════════════════════════════════
# aggregate_and_respond_node - 结果汇总
# ═══════════════════════════════════════════════════════════════════════════════

def aggregate_and_respond_node(state: EmailAgentState) -> Dict[str, Any]:
    """汇总所有节点结果，生成最终自然语言响应"""
    logger.info("Aggregate and respond node executing...")
    outputs = state.get("agent_outputs") or {}
    intents = state.get("intents", [])
    exec_status = state.get("execution_status", "completed")
    pending_draft = state.get("pending_draft") or {}
    pending_meeting = state.get("pending_meeting") or {}
    reflect_output = outputs.get("reflect") or {}

    response_parts = []
    for intent in intents:
        if intent == "parser":
            result = _format_parser_response(outputs.get("parser", {}))
        elif intent == "summarizer":
            result = _format_summarizer_response(outputs.get("summarizer", {}))
        elif intent == "reply":
            result = _format_reply_response(outputs.get("reply", {}))
        elif intent == "notification":
            result = _format_notify_response(outputs.get("notification", {}))
        elif intent == "query":
            result = _format_query_response(outputs.get("query", {}))
        elif intent == "general":
            result = _format_general_response(outputs.get("general", {}))
        elif intent == "meeting":
            result = _format_meeting_response(outputs.get("meeting", {}))
        else:
            continue
        if result.get("final_response"):
            response_parts.append(result["final_response"])

    # send 节点（confirm 后实际发送）
    send_output = outputs.get("send", {})
    if send_output:
        send_result = _format_send_response(send_output)
        if send_result.get("final_response"):
            response_parts.append(send_result["final_response"])

    # meeting_confirmed 节点（confirm 后展示结果）
    meeting_confirmed = outputs.get("meeting_confirmed", {})
    if meeting_confirmed:
        mc_result = _format_meeting_confirmed_response(meeting_confirmed)
        if mc_result.get("final_response"):
            response_parts.append(mc_result["final_response"])

    # reflect 检查不通过：直接拒绝，API 返回错误 + 草稿
    if exec_status == "needs_review" and pending_draft:
        draft_content = pending_draft.get("draft_content", "")
        concerns = reflect_output.get("concerns", [])
        warn_msg = f"【安全检查未通过】邮件未发送，原因：{'；'.join(concerns)}"
        if draft_content:
            warn_msg += f"\n\n当前草稿内容：\n{draft_content}"
        response_parts.append(warn_msg)

    # 兜底：所有节点均失败 → 降级响应，不堆叠错误
    if not response_parts:
        response_parts = [_generate_fallback_response(state)]

    return {
        "final_response": "\n\n".join(response_parts),
        "execution_status": exec_status,
    }


def _generate_fallback_response(state: EmailAgentState) -> str:
    messages = state.get("messages", [])
    user_message = _get_last_user_message(messages)
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        response = _get_llm(temperature=0.7, max_tokens=300).invoke([
            SystemMessage(content="你是一个智能邮件助手。用户的请求已处理，但没有生成具体结果。请简短告知用户当前状态。"),
            HumanMessage(content=user_message or "有什么可以帮你的？")
        ])
        return response.content if hasattr(response, "content") else "处理完成"
    except Exception:
        return "处理完成"


# ═══════════════════════════════════════════════════════════════════════════════
# 格式化函数
# ═══════════════════════════════════════════════════════════════════════════════

def _format_parser_response(parser_data: Dict) -> Dict[str, Any]:
    if not parser_data.get("success"):
        return {"final_response": f"解析失败: {parser_data.get('error', '未知错误')}"}
    data = parser_data.get("data", {})
    total = data.get("total", 0)
    parsed = data.get("parsed", 0)
    if total == 0:
        lines = ["暂无需要解析的邮件"]
    else:
        lines = ["解析完成！", f"共处理 {total} 封邮件，成功解析 {parsed} 封"]
        if parsed > 0:
            lines.append(f"已为你提取了 {parsed} 个事件")
    return {"final_response": "\n".join(lines)}


def _format_summarizer_response(summarizer_data: Dict) -> Dict[str, Any]:
    if not summarizer_data.get("success"):
        return {"final_response": f"摘要生成失败: {summarizer_data.get('error', '未知错误')}"}
    data = summarizer_data.get("data", {})
    summary = data.get("summary", "")
    stats = data.get("stats", {})
    events_list = data.get("events_list", [])
    lines = []
    if summary:
        lines.append(summary)
    lines.append(f"统计：收到 {stats.get('emails', 0)} 封邮件，提取 {stats.get('events', 0)} 个事件")
    if stats.get("important"):
        lines.append(f"其中 {stats.get('important')} 个重要事件")
    if events_list:
        lines.append("\n近期事件：")
        for e in events_list[:8]:
            title = e.get("title", "无标题")
            desc = e.get("description", "")
            suffix = f": {desc[:60]}..." if len(desc) > 60 else (f": {desc}" if desc else "")
            lines.append(f"- {title}{suffix}")
    notion_archive = data.get("notion_archive")
    if notion_archive and notion_archive.get("success"):
        lines.append("\n已同步归档到 Notion")
    return {"final_response": "\n".join(lines)}


def _format_reply_response(reply_data: Dict) -> Dict[str, Any]:
    if not reply_data.get("success"):
        return {"final_response": f"回复生成失败: {reply_data.get('error', '未知错误')}"}
    draft = reply_data.get("draft_content", "")
    if draft:
        return {"final_response": f"回复草稿已生成：\n\n{draft}"}
    return {"final_response": "回复草稿已生成"}


def _format_send_response(send_data: Dict) -> Dict[str, Any]:
    if send_data.get("success"):
        return {"final_response": "邮件已成功发送！"}
    return {"final_response": f"邮件发送失败: {send_data.get('error', '未知错误')}"}


def _format_notify_response(notify_data: Dict) -> Dict[str, Any]:
    if not notify_data.get("success"):
        return {"final_response": f"发送失败: {notify_data.get('error', '未知错误')}"}
    action = notify_data.get("action", "notification")
    msg_map = {"send_summary": "每日摘要已发送！请查收邮件。",
               "send_event": "事件通知已发送！请查收邮件。"}
    return {"final_response": msg_map.get(action, "通知已发送！")}


def _format_query_response(query_data: Dict) -> Dict[str, Any]:
    if not query_data.get("success"):
        return {"final_response": f"查询失败: {query_data.get('error', '未知错误')}"}
    lines = []
    emails = query_data.get("emails", [])
    events = query_data.get("events", [])
    query_type = query_data.get("query_type", "all")
    if query_type in ("all", "emails") and emails:
        lines.append(f"邮件列表（共 {len(emails)} 封）：")
        for email in emails[:10]:
            date = email.get("received_at", "")[:10]
            cat = f"[{email.get('category', '')}]" if email.get("category") else ""
            lines.append(f"  - [{date}] {cat} {email.get('sender', '未知')}: {email.get('subject', '无主题')}")
        if len(emails) > 10:
            lines.append(f"  ... 还有 {len(emails) - 10} 封")
    if query_type in ("all", "events") and events:
        lines.append(f"\n事件列表（共 {len(events)} 个）：")
        for event in events[:10]:
            imp = "*" if event.get("important") else ""
            lines.append(f"  - {imp}[{event.get('event_type', '')}] {event.get('title', '无标题')}")
        if len(events) > 10:
            lines.append(f"  ... 还有 {len(events) - 10} 个")
    if not lines:
        lines = ["暂无数据"]
    return {"final_response": "\n".join(lines)}


def _format_general_response(general_data: Dict) -> Dict[str, Any]:
    if general_data.get("success"):
        return {"final_response": general_data.get("response", "你好，有什么可以帮你的？")}
    return {"final_response": f"处理失败: {general_data.get('error', '未知错误')}"}


# ═══════════════════════════════════════════════════════════════════════════════
# meeting_agent_node - 会议 RSVP 决策
# ═══════════════════════════════════════════════════════════════════════════════

MEETING_PROMPT_TEMPLATE = """你是一个会议助手。根据以下邮件信息，判断是否应该接受会议邀约，并给出理由。

## 邮件信息
- 标题：{title}
- 组织者：{organizer}
- 时间：{start_time}
- 地点/链接：{location} / {meeting_link}
- 参会人：{attendees}
- 正文摘要：{description}

## 当前时间
{current_time}

## 决策要求
请判断是否应该接受这个会议：
- **accept**: 会议时间合适，应该参加
- **decline**: 时间不合适或会议不重要，应该拒绝
- **tentative**: 有一定兴趣但需要进一步确认

请给出你的决策和详细的理由。输出格式为 JSON：
{{"decision": "accept|decline|tentative", "reason": "理由说明（50字以内）", "suggested_reply": "如果接受，生成一句简短的接受回复（英文，30字以内）"}}
"""


def meeting_agent_node(state: EmailAgentState) -> Dict[str, Any]:
    """
    会议 RSVP 决策节点。

    流程：
    1. 从 DB 读取 event_type=meeting 且 rsvp_status=pending 的事件
    2. 如果用户指定了 event_id，聚焦该事件
    3. 调用 LLM 判断是否接受，生成 RSVP 建议
    4. interrupt 挂起，等用户确认
    5. 用户确认 → confirm_meeting_node（写 DB + 发邮件）
       用户取消 → cancel_meeting_node（不操作）
    """
    from app.db import Event, SessionLocal
    from datetime import datetime, timezone as tz

    db = SessionLocal()
    try:
        event_id = state.get("action_params", {}).get("event_id")
        rsvp_decision = state.get("action_params", {}).get("rsvp_status")
        limit = state.get("action_params", {}).get("limit", 5)

        # 读取 pending 会议列表
        query = db.query(Event).filter(
            Event.event_type == "meeting",
            Event.rsvp_status == "pending"
        )
        if event_id:
            query = query.filter(Event.id == event_id)

        meetings = query.order_by(Event.start_time.desc().nullslast()).limit(limit).all()

        if not meetings:
            logger.info("没有待回复的会议")
            return {
                "agent_outputs": {**state.get("agent_outputs", {}), "meeting": {
                    "success": True,
                    "pending_meetings": [],
                    "message": "暂无待回复的会议邀约"
                }},
                "executed_nodes": state.get("executed_nodes", []) + ["meeting_agent"],
            }

        # 取第一封会议邮件做决策（多封时展示列表让用户选）
        meeting = meetings[0]
        start_str = meeting.start_time.strftime("%Y-%m-%d %H:%M") if meeting.start_time else "待定"
        now = datetime.now(tz.utc)

        prompt = MEETING_PROMPT_TEMPLATE.format(
            title=meeting.title,
            organizer=meeting.organizer or "未知",
            start_time=start_str,
            location=meeting.location or "无",
            meeting_link=meeting.meeting_link or "无",
            attendees=meeting.attendees or "未知",
            description=meeting.description or "无",
            current_time=now.strftime("%Y-%m-%d %H:%M %Z"),
        )

        decision_text = "待确认"
        suggestion = ""
        try:
            llm = _get_llm(temperature=0.1, max_tokens=300, timeout=30)
            response = llm.invoke([
                {"role": "system", "content": "你是一个会议决策助手，只输出 JSON。"},
                {"role": "user", "content": prompt}
            ])
            raw = response.content.strip()
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                decision_text = parsed.get("decision", "待确认")
                suggestion = parsed.get("suggested_reply", "")
                logger.info(f"会议决策: title={meeting.title}, decision={decision_text}")
        except Exception as e:
            logger.warning(f"LLM 决策失败: {e}")

        # 写入 pending_meeting，interrupt 挂起等用户确认
        pending_meeting = {
            "event_id": meeting.id,
            "title": meeting.title,
            "organizer": meeting.organizer,
            "start_time": start_str,
            "meeting_link": meeting.meeting_link,
            "llm_decision": decision_text,
            "llm_suggestion": suggestion,
            "confirmed": None,
        }

        meeting_result = {
            "event_id": str(meeting.id),
            "title": meeting.title,
            "organizer": meeting.organizer,
            "start_time": start_str,
            "meeting_link": meeting.meeting_link,
            "location": meeting.location,
            "rsvp_status": meeting.rsvp_status,
            "llm_decision": decision_text,
            "llm_suggestion": suggestion,
        }

        logger.info(f"Meeting agent: RSVP decision made, interrupting for confirmation. event_id={meeting.id}, decision={decision_text}")

        interrupt({
            "type": "meeting_confirmation",
            "title": "会议 RSVP 确认",
            "message": f"针对会议「{meeting.title}」，建议：{decision_text}",
            "event_id": meeting.id,
            "meeting_result": meeting_result,
            "pending_meeting": pending_meeting,
        })

        # interrupt 后不执行到这里
        return {
            "agent_outputs": {**state.get("agent_outputs", {}), "meeting": {
                "success": True,
                "pending_meetings": [meeting_result],
                "message": f"建议 {decision_text}：{suggestion}"
            }},
            "pending_meeting": pending_meeting,
            "execution_status": "interrupted",
            "executed_nodes": state.get("executed_nodes", []) + ["meeting_agent"],
        }

    except Exception as e:
        logger.error(f"meeting_agent 失败: {e}")
        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "meeting": {"success": False, "error": str(e)}
            },
            "execution_status": "error",
            "executed_nodes": state.get("executed_nodes", []) + ["meeting_agent"],
        }
    finally:
        db.close()


def confirm_meeting_node(state: EmailAgentState) -> Dict[str, Any]:
    """
    用户确认 RSVP：从 pending_meeting 读取决策，写 DB + 发邮件。
    仅在 pending_meeting.confirmed=True 时执行。
    """
    logger.info("Confirm meeting node executing...")
    pending = state.get("pending_meeting", {})
    if pending.get("confirmed") is not True:
        logger.warning("confirm_meeting_node called but confirmed != True, skipping")
        return {"execution_status": "completed"}

    event_id = pending.get("event_id")
    decision = pending.get("llm_decision", "accept")
    suggestion = pending.get("llm_suggestion", "")

    try:
        from app.db import Event, SessionLocal
        db = SessionLocal()
        try:
            event = db.query(Event).filter(Event.id == event_id).first()
            if event:
                status_map = {"accept": "accepted", "decline": "declined", "tentative": "tentative"}
                event.rsvp_status = status_map.get(decision, "pending")
                db.commit()
                logger.info(f"RSVP 更新: event_id={event_id}, rsvp_status={event.rsvp_status}")

                # 尝试发邮件回复
                sent = False
                try:
                    registry = get_registry()
                    reply_result = registry.execute(
                        "reply_email",
                        email_id=event.email_id,
                        reply_content=suggestion,
                        tone=f"rsvp_{decision}"
                    )
                    sent = reply_result.success
                    logger.info(f"RSVP 邮件发送: success={sent}")
                except Exception as mail_err:
                    logger.warning(f"RSVP 邮件发送失败（不影响 DB）: {mail_err}")

                return {
                    "agent_outputs": {**state.get("agent_outputs", {}), "meeting_confirmed": {
                        "success": True,
                        "event_id": event_id,
                        "rsvp_status": event.rsvp_status,
                        "email_sent": sent,
                    }},
                    "execution_status": "completed",
                    "executed_nodes": state.get("executed_nodes", []) + ["confirm_meeting"],
                }
            else:
                return {
                    "agent_outputs": {**state.get("agent_outputs", {}), "meeting_confirmed": {
                        "success": False, "error": f"找不到 event_id={event_id}"
                    }},
                    "execution_status": "error",
                }
        finally:
            db.close()

    except Exception as e:
        logger.error(f"confirm_meeting 失败: {e}")
        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "meeting_confirmed": {"success": False, "error": str(e)}
            },
            "execution_status": "error",
        }


def cancel_meeting_node(state: EmailAgentState) -> Dict[str, Any]:
    """
    用户取消：不操作 DB，直接返回取消消息。
    仅在 pending_meeting.confirmed=False 时执行。
    """
    logger.info("Cancel meeting node executing...")
    pending = state.get("pending_meeting", {})
    title = pending.get("title", "该会议")

    return {
        "final_response": f"已取消 RSVP 操作，会议「{title}」保持待回复状态。",
        "execution_status": "completed",
        "executed_nodes": state.get("executed_nodes", []) + ["cancel_meeting"],
    }
    """
    会议 RSVP 决策节点。

    流程：
    1. 从 DB 读取 event_type=meeting 且 rsvp_status=pending 的事件
    2. 如果用户指定了 event_id，聚焦该事件
    3. 调用 LLM 判断是否接受
    4. 结果写入 agent_outputs["meeting"]
    5. 如果用户已确认 RSVP，更新 DB 中的 rsvp_status
    """
    from app.db import Event, SessionLocal
    from datetime import datetime, timezone as tz

    db = SessionLocal()
    try:
        event_id = state.get("action_params", {}).get("event_id")
        rsvp_decision = state.get("action_params", {}).get("rsvp_status")
        limit = state.get("action_params", {}).get("limit", 5)

        # 如果用户已确认 RSVP，更新 DB
        if event_id and rsvp_decision:
            event = db.query(Event).filter(Event.id == event_id).first()
            if event:
                event.rsvp_status = rsvp_decision
                db.commit()
                logger.info(f"RSVP 更新: event_id={event_id}, rsvp_status={rsvp_decision}")

        # 读取 pending 会议列表
        query = db.query(Event).filter(
            Event.event_type == "meeting",
            Event.rsvp_status == "pending"
        )
        if event_id:
            query = query.filter(Event.id == event_id)

        meetings = query.order_by(Event.start_time.desc().nullslast()).limit(limit).all()

        if not meetings:
            logger.info("没有待回复的会议")
            output = {
                "success": True,
                "pending_meetings": [],
                "message": "暂无待回复的会议邀约"
            }
            return {
                "agent_outputs": {**state.get("agent_outputs", {}), "meeting": output}
            }

        meeting_results = []
        for meeting in meetings:
            start_str = meeting.start_time.strftime("%Y-%m-%d %H:%M") if meeting.start_time else "待定"
            now = datetime.now(tz.utc)

            prompt = MEETING_PROMPT_TEMPLATE.format(
                title=meeting.title,
                organizer=meeting.organizer or "未知",
                start_time=start_str,
                location=meeting.location or "无",
                meeting_link=meeting.meeting_link or "无",
                attendees=meeting.attendees or "未知",
                description=meeting.description or "无",
                current_time=now.strftime("%Y-%m-%d %H:%M %Z"),
            )

            decision_text = "待确认"
            suggestion = ""
            try:
                llm = _get_llm(temperature=0.1, max_tokens=300)
                response = llm.invoke([
                    {"role": "system", "content": "你是一个会议决策助手，只输出 JSON。"},
                    {"role": "user", "content": prompt}
                ])
                raw = response.content.strip()
                json_match = re.search(r'\{.*\}', raw, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    decision_text = parsed.get("decision", "待确认")
                    suggestion = parsed.get("suggested_reply", "")
                    logger.info(f"会议决策: title={meeting.title}, decision={decision_text}")
            except Exception as e:
                logger.warning(f"LLM 决策失败: {e}")

            meeting_results.append({
                "event_id": str(meeting.id),
                "title": meeting.title,
                "organizer": meeting.organizer,
                "start_time": start_str,
                "meeting_link": meeting.meeting_link,
                "location": meeting.location,
                "rsvp_status": meeting.rsvp_status,
                "llm_decision": decision_text,
                "llm_suggestion": suggestion,
            })

        output = {
            "success": True,
            "pending_meetings": meeting_results,
            "message": f"找到 {len(meeting_results)} 个待回复的会议"
        }
        return {
            "agent_outputs": {**state.get("agent_outputs", {}), "meeting": output}
        }

    except Exception as e:
        logger.error(f"meeting_agent 失败: {e}")
        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "meeting": {"success": False, "error": str(e)}
            }
        }
    finally:
        db.close()


def _format_meeting_confirmed_response(meeting_confirmed: Dict) -> Dict[str, Any]:
    if meeting_confirmed.get("success"):
        rsvp_status = meeting_confirmed.get("rsvp_status", "")
        email_sent = meeting_confirmed.get("email_sent", False)
        status_map = {
            "accepted": "已接受 ✅",
            "declined": "已拒绝 ❌",
            "tentative": "暂定参加 ❓",
        }
        status_text = status_map.get(rsvp_status, rsvp_status)
        msg = f"RSVP 操作完成：{status_text}"
        if email_sent:
            msg += " 已发送回复邮件。"
        else:
            msg += "（未发送回复邮件）"
        return {"final_response": msg}
    return {"final_response": f"RSVP 操作失败: {meeting_confirmed.get('error', '未知错误')}"}


def _format_meeting_response(meeting_data: Dict) -> Dict[str, Any]:
    if not meeting_data.get("success"):
        return {"final_response": f"会议查询失败: {meeting_data.get('error', '未知错误')}"}

    meetings = meeting_data.get("pending_meetings", [])
    if not meetings:
        return {"final_response": meeting_data.get("message", "暂无待回复的会议")}

    lines = ["📅 待回复的会议："]
    for m in meetings:
        decision_icon = {"accept": "✅", "decline": "❌", "tentative": "❓"}.get(m.get("llm_decision", ""), "⏳")
        lines.append(f"  {decision_icon} **{m['title']}**")
        lines.append(f"      组织者: {m.get('organizer', '未知')}")
        lines.append(f"      时间: {m.get('start_time', '待定')}")
        if m.get("meeting_link"):
            lines.append(f"      链接: {m['meeting_link']}")
        if m.get("llm_decision") != "待确认":
            lines.append(f"      建议: {m['llm_decision']} - {m.get('llm_suggestion', '')}")
        lines.append("")

    return {"final_response": "\n".join(lines).strip()}


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _get_last_user_message(messages: List[Dict[str, str]]) -> str:
    """获取最后一条用户消息"""
    for msg in reversed(messages):
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user" and content:
                return content
        elif hasattr(msg, "role") and msg.role == "user":
            return msg.content or ""
    return ""
