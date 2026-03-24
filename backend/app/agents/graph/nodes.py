"""
LangGraph Agent 节点定义
基于 Supervisor 模式统一编排 6 个子 Agent，支持多意图并行执行
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


def _get_llm(temperature: float = 0.1, max_tokens: int = 500):
    """获取单例 LLM client，避免重复创建连接"""
    global _llm_client
    if _llm_client is None:
        from langchain_openai import ChatOpenAI
        _llm_client = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens
        )
    return _llm_client


# ═══════════════════════════════════════════════════════════════════════════════
# Supervisor 节点 - 意图判断
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
                    "enum": ["parser", "summarizer", "notification", "query", "general", "react"]
                },
                "description": "意图列表，支持多意图并行。例如：['parser'] 或 ['query', 'react']。react 用于复杂多步推理问题。",
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
                    }
                }
            }
        },
        "required": ["intents", "reasoning"]
    }
}


def classify_intent_node(state: EmailAgentState) -> Dict[str, Any]:
    """
    意图分类节点：调用 LLM 结构化输出判断用户意图（支持多意图并行）
    仅负责意图判断，返回 intents/intent_reasoning/action_params。

    force_intent 优先级最高，用于前端手动切换引擎模式。
    """
    messages = state.get("messages", [])
    user_message = _get_last_user_message(messages)

    if not user_message:
        return {
            "intents": [IntentType.GENERAL.value],
            "intent_reasoning": "无法获取用户消息",
            "action_params": {}
        }

    # ── 手动指定意图优先（前端 ReAct 模式切换按钮）──────────────
    force_intent = state.get("force_intent")
    if force_intent:
        valid_intents = [e.value for e in IntentType]
        if force_intent in valid_intents:
            logger.info(f"ClassifyIntent: force_intent={force_intent} (手动切换模式)")
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
- query: 查询邮件列表、事件列表
- general: 通用问答、问候、闲聊
- react: 复杂多步推理、需要组合多个工具的问题

【重要规则】
1. 每次分析必须返回至少一个意图
2. 支持多意图：例如"同步邮件并生成摘要"应返回 ["parser", "summarizer"]
3. 优先使用具体意图（parser/summarizer/notification/query）而不是 general
4. 只有纯粹的问候或闲聊才使用 general
5. 需要同时查询邮件和事件时使用 ["query"]（内部会查 both）
6. 复杂多步问题（如"找出所有未处理的账单并帮我生成回复"）使用 ["react"]

请分析用户消息并返回结构化的意图判断。"""

        from langchain_core.messages import SystemMessage, HumanMessage
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])

        # 解析 LLM 返回的结构化结果
        args = _parse_llm_response(response, user_message)

        intents = args.get("intents", [IntentType.GENERAL.value])
        reasoning = args.get("reasoning", "")
        params = args.get("params", {})

        # 验证意图有效性
        valid_intents = [e.value for e in IntentType]
        intents = [i for i in intents if i in valid_intents]
        if not intents:
            intents = [IntentType.GENERAL.value]

        logger.info(f"ClassifyIntent: intents={intents}, reasoning={reasoning[:50]}...")

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
    """解析 LLM 结构化输出，支持多种 LangChain 版本格式"""
    # 尝试 tool_calls 格式
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

    # 尝试 additional_kwargs 格式
    if hasattr(response, "additional_kwargs"):
        kwargs = response.additional_kwargs
        if "function" in kwargs:
            func_call = kwargs["function"]
            args_str = func_call.get("arguments", "{}")
            return json.loads(args_str)

    # 备用：关键词匹配
    return _parse_fallback_response(user_message)


def _parse_fallback_response(user_message: str) -> Dict[str, Any]:
    """当结构化输出失败时的兜底解析"""
    content_lower = user_message.lower()
    intents = []
    params = {}

    if any(kw in content_lower for kw in ["同步", "解析", "拉取邮件", "fetch", "收取"]):
        intents.append("parser")
    if any(kw in content_lower for kw in ["摘要", "总结", "生成", "summary"]):
        intents.append("summarizer")
    if any(kw in content_lower for kw in ["通知", "发送", "send", "notify"]):
        intents.append("notification")
    if any(kw in content_lower for kw in ["查询", "查看", "列出", "有什么", "list", "邮件列表", "事件列表"]):
        intents.append("query")
    if any(kw in content_lower for kw in ["你好", "hi", "hello", "帮忙"]):
        intents.append("general")
    if any(kw in content_lower for kw in ["分析", "reason", "think", "思考", "推理", "复杂"]):
        intents.append("react")

    if not intents:
        intents = ["general"]

    return {"intents": intents, "reasoning": "Fallback parsing", "params": params}


# ═══════════════════════════════════════════════════════════════════════════════
# 6 个子 Agent 节点
# ═══════════════════════════════════════════════════════════════════════════════

def parser_agent_node(state: EmailAgentState) -> Dict[str, Any]:
    """Parser Agent 节点：同步邮件 + 解析邮件 + 写 DB"""
    logger.info("Parser agent node executing...")
    params = state.get("action_params", {})
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
    """Summarizer Agent 节点：查 DB + 生成 AI 摘要 + 归档 Notion"""
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


def notification_agent_node(state: EmailAgentState) -> Dict[str, Any]:
    """Notification Agent 节点：发送每日摘要邮件或事件通知"""
    logger.info("Notification agent node executing...")
    params = state.get("action_params", {})
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
    """Query Agent 节点：查询邮件列表 + 事件列表"""
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
    """General Agent 节点：通用问答，LLM 直接回答（不调工具）"""
    logger.info("General agent node executing...")
    messages = state.get("messages", [])
    user_message = _get_last_user_message(messages)

    try:
        llm = _get_llm(temperature=0.7, max_tokens=500)

        # 注入实时上下文
        from app.db import Email, Event, SessionLocal
        db = SessionLocal()
        try:
            recent_emails = db.query(Email).order_by(Email.received_at.desc()).limit(5).all()
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

        prompt = f"""你是一个友好的智能邮件助手。请用简洁、亲切的语气回复用户。

【当前数据】
{realtime_context}

如果用户问的是邮件或事件相关问题，可以结合上面的数据回答。
请用自然的方式回复，不要列出功能清单。"""

        from langchain_core.messages import SystemMessage, HumanMessage
        response = llm.invoke([
            SystemMessage(content=prompt),
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
# ReAct Agent 节点（LangGraph 内部内联实现，不依赖外部 react_engine.py）
# ═══════════════════════════════════════════════════════════════════════════════

def react_agent_node(state: EmailAgentState) -> Dict[str, Any]:
    """
    ReAct Agent 节点：在 LangGraph 内部实现 ReAct 循环

    循环：Thought → Action → Observation → ... → Final
    使用 ToolRegistry 执行工具，结果写入 agent_outputs["react"]。
    """
    logger.info("React agent node executing (inline ReAct loop)...")
    messages = state.get("messages", [])
    user_message = _get_last_user_message(messages)
    registry = get_registry()
    max_iterations = 10

    # 构建 ReAct 提示词
    tools_schema = registry.get_schemas()
    tools_desc = json.dumps(tools_schema, ensure_ascii=False, indent=2)

    system_prompt = f"""你是一个智能邮件助手，使用 ReAct (Reasoning + Acting) 模式来完成任务。

## 可用工具
{tools_desc}

## ReAct 模式说明
你可以通过以下步骤来完成任务：
1. THINK: 分析用户问题，决定下一步做什么
2. ACTION: 选择一个工具并提供输入参数来执行
3. OBSERVATION: 观察工具执行的结果
4. FINAL: 基于所有观察给出最终答案

## 输出格式
请严格按照以下 JSON 格式输出：
{{
    "thought": "分析当前情况和决定下一步",
    "action": "工具名称（如果需要执行工具，否则为 null）",
    "action_input": {{"参数": "值"}}  // 如果 action 为 null 则为空对象
}}

## 重要规则
- 如果问题可以一次性回答，直接输出 FINAL（action=null）
- 如果需要获取信息，使用工具来获取
- 每个思考只做一件事，不要一次请求多个工具
- 确保 action_input 中的参数名和类型与工具定义一致
"""

    try:
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        chat_messages = [SystemMessage(content=system_prompt)]
        # 追加历史消息（去掉最后一条 user，等传入 state）
        for msg in messages[:-1]:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant"):
                    chat_messages.append(
                        HumanMessage(content=content) if role == "user"
                        else AIMessage(content=content)
                    )
        chat_messages.append(HumanMessage(content=user_message))

        steps = []
        final_response = None

        for iteration in range(max_iterations):
            logger.info(f"ReAct iteration {iteration + 1}/{max_iterations}")

            response = _get_llm(temperature=0.7, max_tokens=500).invoke(chat_messages)
            response_content = response.content if hasattr(response, "content") else str(response)
            chat_messages.append(AIMessage(content=response_content))

            parsed = _parse_react_response(response_content)
            thought = parsed.get("thought", "")
            action = parsed.get("action")
            action_input = parsed.get("action_input", {})

            steps.append({"type": "think", "content": thought})

            # 无动作 → FINAL
            if action is None:
                steps.append({"type": "final", "content": thought})
                final_response = thought
                break

            # 执行工具
            tool_result = registry.execute(action, **action_input)
            steps.append({
                "type": "action",
                "tool": action,
                "input": action_input,
                "result": tool_result.to_dict()
            })

            observation = tool_result.raw_output if tool_result.success else tool_result.error
            steps.append({"type": "observation", "content": observation[:200]})

            chat_messages.append(HumanMessage(
                content=f"工具执行结果：\n{observation}\n\n请基于以上结果继续思考或给出最终回答。"
            ))

        else:
            steps.append({"type": "error", "content": f"达到最大迭代次数 {max_iterations}"})
            final_response = f"执行超时（超过 {max_iterations} 步推理）"

        step_count = len([s for s in steps if s.get("type") == "action"])

        return {
            "agent_outputs": {"react": {
                "success": True,
                "response": final_response or "ReAct 执行完成",
                "steps": steps,
                "step_count": step_count
            }},
            "execution_status": "completed"
        }

    except Exception as e:
        logger.error(f"React agent error: {e}")
        return {
            "agent_outputs": {"react": {"success": False, "error": str(e)}},
            "execution_status": "error"
        }


def _parse_react_response(response_content: str) -> Dict[str, Any]:
    """解析 ReAct JSON 响应"""
    try:
        json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        pass
    return {"thought": response_content, "action": None, "action_input": {}}


# ═══════════════════════════════════════════════════════════════════════════════
# 结果汇总 + 最终响应生成
# ═══════════════════════════════════════════════════════════════════════════════

def aggregate_and_respond_node(state: EmailAgentState) -> Dict[str, Any]:
    """
    汇总 + 生成最终响应节点

    根据 intents 列表将所有子 Agent 的结果聚合为自然语言响应。
    包含兜底逻辑：如果没有任何 agent_outputs，尝试直接回答。
    """
    logger.info("Aggregate and respond node executing...")
    outputs = state.get("agent_outputs", {})
    intents = state.get("intents", [])

    response_parts = []

    for intent in intents:
        if intent == "parser":
            result = _format_parser_response(outputs.get("parser", {}))
        elif intent == "summarizer":
            result = _format_summarizer_response(outputs.get("summarizer", {}))
        elif intent == "notification":
            result = _format_notify_response(outputs.get("notification", {}))
        elif intent == "query":
            result = _format_query_response(outputs.get("query", {}))
        elif intent == "general":
            result = _format_general_response(outputs.get("general", {}))
        elif intent == "react":
            result = _format_react_response(outputs.get("react", {}))
        else:
            continue

        if result.get("final_response"):
            response_parts.append(result["final_response"])

    # 兜底：如果没有任何结果，尝试直接生成回答
    if not response_parts:
        response_parts = [_generate_fallback_response(state)]

    final_response = "\n\n".join(response_parts)

    return {
        "final_response": final_response,
        "execution_status": "completed"
    }


def _generate_fallback_response(state: EmailAgentState) -> str:
    """兜底响应：没有任何 agent 结果时，LLM 直接生成回答"""
    messages = state.get("messages", [])
    user_message = _get_last_user_message(messages)

    try:
        llm = _get_llm(temperature=0.7, max_tokens=300)
        from langchain_core.messages import SystemMessage, HumanMessage
        response = llm.invoke([
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
    """格式化解析结果"""
    if not parser_data.get("success"):
        return {"final_response": f"解析失败: {parser_data.get('error', '未知错误')}"}

    data = parser_data.get("data", {})
    total = data.get("total", 0)
    parsed = data.get("parsed", 0)

    if total == 0:
        lines = ["暂无需要解析的邮件"]
    else:
        lines = [f"解析完成！"]
        lines.append(f"共处理 {total} 封邮件，成功解析 {parsed} 封")
        if parsed > 0:
            lines.append(f"已为你提取了 {parsed} 个事件")

    return {"final_response": "\n".join(lines)}


def _format_summarizer_response(summarizer_data: Dict) -> Dict[str, Any]:
    """格式化摘要结果"""
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
            if desc:
                lines.append(f"- {title}: {desc[:60]}{'...' if len(desc) > 60 else ''}")
            else:
                lines.append(f"- {title}")

    notion_archive = data.get("notion_archive")
    if notion_archive and notion_archive.get("success"):
        lines.append("\n已同步归档到 Notion")

    return {"final_response": "\n".join(lines)}


def _format_notify_response(notify_data: Dict) -> Dict[str, Any]:
    """格式化通知结果"""
    if not notify_data.get("success"):
        return {"final_response": f"发送失败: {notify_data.get('error', '未知错误')}"}

    action = notify_data.get("action", "notification")

    if action == "send_summary":
        return {"final_response": "每日摘要已发送！请查收邮件。"}
    elif action == "send_event":
        return {"final_response": "事件通知已发送！请查收邮件。"}
    else:
        return {"final_response": "通知已发送！"}


def _format_query_response(query_data: Dict) -> Dict[str, Any]:
    """格式化查询结果"""
    if not query_data.get("success"):
        return {"final_response": f"查询失败: {query_data.get('error', '未知错误')}"}

    lines = []
    emails = query_data.get("emails", [])
    events = query_data.get("events", [])
    query_type = query_data.get("query_type", "all")

    if query_type in ("all", "emails") and emails:
        lines.append(f"邮件列表（共 {len(emails)} 封）：")
        for email in emails[:10]:
            sender = email.get("sender", "未知")
            subject = email.get("subject", "无主题")
            date = email.get("received_at", "")[:10]
            category = email.get("category", "")
            cat_tag = f"[{category}]" if category else ""
            lines.append(f"  - [{date}] {cat_tag} {sender}: {subject}")
        if len(emails) > 10:
            lines.append(f"  ... 还有 {len(emails) - 10} 封")

    if query_type in ("all", "events") and events:
        lines.append(f"\n事件列表（共 {len(events)} 个）：")
        for event in events[:10]:
            title = event.get("title", "无标题")
            event_type = event.get("event_type", "")
            important = "*" if event.get("important") else ""
            lines.append(f"  - {important}[{event_type}] {title}")
        if len(events) > 10:
            lines.append(f"  ... 还有 {len(events) - 10} 个")

    if not lines:
        lines = ["暂无数据"]

    return {"final_response": "\n".join(lines)}


def _format_general_response(general_data: Dict) -> Dict[str, Any]:
    """格式化通用问答结果"""
    if general_data.get("success"):
        return {"final_response": general_data.get("response", "你好，有什么可以帮你的？")}
    return {"final_response": f"处理失败: {general_data.get('error', '未知错误')}"}


def _format_react_response(react_data: Dict) -> Dict[str, Any]:
    """格式化 ReAct Agent 执行结果"""
    if not react_data.get("success"):
        return {"final_response": f"ReAct 执行失败: {react_data.get('error', '未知错误')}"}

    response = react_data.get("response", "")
    step_count = react_data.get("step_count", 0)

    if not response:
        return {"final_response": "ReAct 执行完成，但未生成有效响应"}

    if step_count > 1:
        return {"final_response": f"{response}\n\n（由 ReAct 引擎通过 {step_count} 步推理生成）"}

    return {"final_response": response}


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
