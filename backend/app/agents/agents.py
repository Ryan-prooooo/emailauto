"""
邮件智能体 - 实现4个预设智能体
Parser Agent, Summarizer Agent, QA Agent, Notification Agent
"""
from typing import Any, Dict, List, Optional
import logging
from app.agents.base import BaseAgent, AgentResult
from app.agents.tools import Tool, ToolResult, get_registry
from app.config import settings

logger = logging.getLogger(__name__)


class ParserAgent(BaseAgent):
    """解析智能体 - 使用AI解析邮件，提取事件"""

    def __init__(self):
        super().__init__(
            name="parser_agent",
            description="解析邮件内容，提取事件信息、分类、摘要"
        )
        self._setup_tools()

    def _setup_tools(self):
        """设置可用工具"""
        registry = get_registry()
        # Parser Agent 可以使用查询工具
        self.tools = [
            registry.get("get_emails"),
            registry.get("get_email_detail"),
            registry.get("sync_emails"),
            registry.get("parse_email"),
        ]
        self.tools = [t for t in self.tools if t is not None]

    def execute(self, input_data: Any, **kwargs) -> AgentResult:
        """执行解析任务"""
        result = AgentResult(success=False)
        result.add_step({"action": "start_parser", "input": str(input_data)})

        try:
            from app.parser import EmailParser
            parser = EmailParser()

            # 如果输入是邮件ID，解析单封邮件
            if isinstance(input_data, int):
                success = parser.parse_and_save(input_data)
                if success:
                    result.success = True
                    result.data = {"email_id": input_data, "parsed": True}
                    result.add_step({"action": "parse_email", "status": "success"})
                else:
                    result.error = "解析失败"
                    result.add_step({"action": "parse_email", "status": "failed"})

            # 如果是其他输入，构建查询参数
            elif isinstance(input_data, dict):
                limit = input_data.get("limit", 10)
                from app.db import Email, SessionLocal
                db = SessionLocal()
                try:
                    emails = db.query(Email).filter(Email.processed == False).limit(limit).all()
                    parsed_count = 0
                    for email in emails:
                        if parser.parse_and_save(email.id):
                            parsed_count += 1
                    result.success = True
                    result.data = {"total": len(emails), "parsed": parsed_count}
                    result.add_step({"action": "batch_parse", "count": parsed_count})
                finally:
                    db.close()
            else:
                result.error = "无效的输入类型"
        except Exception as e:
            logger.error(f"ParserAgent execution error: {e}")
            result.error = str(e)
            result.add_step({"action": "error", "message": str(e)})

        return result


class SummarizerAgent(BaseAgent):
    """摘要智能体 - 生成邮件和事件的摘要"""

    def __init__(self):
        super().__init__(
            name="summarizer_agent",
            description="生成邮件和事件的摘要信息"
        )
        self._setup_tools()

    def _setup_tools(self):
        """设置可用工具"""
        registry = get_registry()
        self.tools = [
            registry.get("get_emails"),
            registry.get("get_events"),
            registry.get("send_daily_summary"),
        ]
        self.tools = [t for t in self.tools if t is not None]

    def execute(self, input_data: Any, **kwargs) -> AgentResult:
        """执行摘要生成任务"""
        result = AgentResult(success=False)
        result.add_step({"action": "start_summarizer", "input": str(input_data)})

        try:
            from app.db import Email, Event, SessionLocal
            from app.parser import EmailParser
            db = SessionLocal()
            try:
                # 获取最近邮件和事件
                emails = db.query(Email).order_by(Email.received_at.desc()).limit(20).all()
                events = db.query(Event).order_by(Event.created_at.desc()).limit(20).all()

                # 构建摘要
                summary_parts = []

                # 邮件摘要
                if emails:
                    categories = {}
                    for email in emails:
                        cat = email.category or "未分类"
                        categories[cat] = categories.get(cat, 0) + 1

                    summary_parts.append(f"最近收到 {len(emails)} 封邮件")
                    summary_parts.append(f"分类统计: {categories}")

                # 事件摘要
                if events:
                    important_events = [e for e in events if e.important]
                    summary_parts.append(f"提取了 {len(events)} 个事件")
                    summary_parts.append(f"其中 {len(important_events)} 个重要事件")

                # 使用AI生成自然语言摘要
                parser = EmailParser()
                context = "\n".join([
                    f"- {e.title}: {e.description or ''}"
                    for e in events[:10]
                ])

                prompt = f"""请根据以下事件信息生成一份简洁的摘要：

{context}

要求：
1. 总结今天/最近的主要事件
2. 突出重要事件
3. 保持简洁，不超过100字
"""

                from openai import OpenAI
                client = OpenAI(
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_BASE_URL
                )

                response = client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200
                )

                ai_summary = response.choices[0].message.content

                result.success = True
                result.data = {
                    "summary": ai_summary,
                    "stats": {
                        "emails": len(emails),
                        "events": len(events),
                        "important": len(important_events) if events else 0
                    }
                }
                result.add_step({"action": "generate_summary", "status": "success"})

            finally:
                db.close()

        except Exception as e:
            logger.error(f"SummarizerAgent execution error: {e}")
            result.error = str(e)
            result.add_step({"action": "error", "message": str(e)})

        return result


class QAAgent(BaseAgent):
    """问答智能体 - 智能问答和对话交互"""

    def __init__(self):
        super().__init__(
            name="qa_agent",
            description="智能问答，回答用户关于邮件和事件的问题"
        )
        self._setup_tools()

    def _setup_tools(self):
        """设置可用工具"""
        registry = get_registry()
        self.tools = list(registry.get_all().values())
        self.tools = [t for t in self.tools if t is not None]

    def execute(self, input_data: Any, **kwargs) -> AgentResult:
        """执行问答任务"""
        result = AgentResult(success=False)

        if isinstance(input_data, str):
            # 直接问答
            result = self._chat(input_data, **kwargs)
        elif isinstance(input_data, dict):
            # 结构化输入
            message = input_data.get("message", "")
            session_id = input_data.get("session_id")
            result = self._chat(message, session_id=session_id, **kwargs)
        else:
            result.error = "无效的输入类型"

        return result

    def _chat(self, message: str, session_id: Optional[int] = None, **kwargs) -> AgentResult:
        """处理对话"""
        result = AgentResult(success=False)
        result.add_step({"action": "chat_start", "message": message[:50]})

        try:
            from app.db import Email, Event, ChatSession, SessionLocal
            from app.parser import EmailParser
            from app.agents.memory import MemoryManager

            db = SessionLocal()
            try:
                # 获取或创建会话
                if session_id:
                    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

                if not session_id or not session:
                    session = ChatSession(title=message[:50] or "新对话")
                    db.add(session)
                    db.commit()
                    db.refresh(session)
                    session_id = session.id

                # 使用记忆管理器处理消息
                with MemoryManager(session_id, db) as memory:
                    # 添加用户消息（会自动触发记忆整理）
                    memory.add_message("user", message)

                    # 获取对话上下文（近期记忆 + 长期记忆）
                    recent_messages, long_term_summary = memory.get_context_for_llm()

                    # 获取实时上下文（邮件 + 事件）
                    recent_emails = db.query(Email).order_by(Email.received_at.desc()).limit(10).all()
                    recent_events = db.query(Event).order_by(Event.created_at.desc()).limit(20).all()

                    # 构建实时上下文
                    context_parts = []
                    if recent_emails:
                        context_parts.append("=== 最近邮件 ===")
                        for email in recent_emails:
                            context_parts.append(f"- [{email.received_at.strftime('%Y-%m-%d')}] {email.sender}: {email.subject}")
                            if email.summary:
                                context_parts.append(f"  摘要: {email.summary}")

                    if recent_events:
                        context_parts.append("\n=== 最近事件 ===")
                        for event in recent_events:
                            context_parts.append(f"- [{event.event_type}] {event.title}: {event.description or '无描述'}")

                    realtime_context = "\n".join(context_parts)

                    # 构建系统提示词（融合三种上下文）
                    system_prompt = self._build_system_prompt(recent_messages, long_term_summary, realtime_context)

                    # 构建完整的消息列表
                    messages = [{"role": "system", "content": system_prompt}]
                    messages.extend(recent_messages)
                    messages.append({"role": "user", "content": message})

                    # 调用AI
                    parser = EmailParser()
                    response = parser.client.chat.completions.create(
                        model=settings.OPENAI_MODEL,
                        messages=messages,
                        max_tokens=500
                    )

                    ai_response = response.choices[0].message.content

                    # 保存AI响应（使用记忆管理器）
                    memory.add_message("assistant", ai_response)

                result.success = True
                result.data = {
                    "response": ai_response,
                    "session_id": session_id
                }
                result.add_step({"action": "chat_response", "status": "success"})

            finally:
                db.close()

        except Exception as e:
            logger.error(f"QAAgent execution error: {e}")
            result.error = str(e)
            result.add_step({"action": "error", "message": str(e)})

        return result

    def _build_system_prompt(self, recent_messages: List[dict], long_term_summary: str, realtime_context: str) -> str:
        """构建系统提示词，融合三种上下文"""
        prompt_parts = ["你是一个智能邮件助手，可以回答用户关于邮件和事件的问题。"]

        # 1. 添加长期记忆摘要
        if long_term_summary:
            prompt_parts.append(f"\n【历史对话摘要】\n{long_term_summary}")

        # 2. 添加实时上下文
        if realtime_context:
            prompt_parts.append(f"\n【当前数据】\n{realtime_context}")

        prompt_parts.append("\n如果用户问的是关于邮件或事件的问题，基于以上信息回答。如果无法从当前邮件中找到相关信息，请结合历史对话记忆来回答。保持回答简洁明了。")

        return "\n".join(prompt_parts)


class NotificationAgent(BaseAgent):
    """通知智能体 - 管理事件通知"""

    def __init__(self):
        super().__init__(
            name="notification_agent",
            description="发送事件通知和每日摘要"
        )
        self._setup_tools()

    def _setup_tools(self):
        """设置可用工具"""
        registry = get_registry()
        self.tools = [
            registry.get("get_events"),
            registry.get("get_event_detail"),
            registry.get("send_notification"),
            registry.get("send_daily_summary"),
        ]
        self.tools = [t for t in self.tools if t is not None]

    def execute(self, input_data: Any, **kwargs) -> AgentResult:
        """执行通知任务"""
        result = AgentResult(success=False)
        result.add_step({"action": "start_notification", "input": str(input_data)})

        try:
            action = kwargs.get("action", "send_summary")

            if action == "send_summary":
                # 发送每日摘要
                from app.mailer import mailer
                success = mailer.send_daily_summary(kwargs.get("to_email"))
                result.success = success
                result.data = {"action": "daily_summary", "sent": success}
                result.add_step({"action": "send_daily_summary", "status": "success" if success else "failed"})

            elif action == "send_event":
                # 发送事件通知
                event_id = kwargs.get("event_id")
                if not event_id:
                    result.error = "缺少 event_id 参数"
                    return result

                from app.mailer import mailer
                success = mailer.send_event_notification(event_id, kwargs.get("to_email"))
                result.success = success
                result.data = {"action": "event_notification", "event_id": event_id, "sent": success}
                result.add_step({"action": "send_event_notification", "status": "success" if success else "failed"})

            else:
                result.error = f"未知操作: {action}"

        except Exception as e:
            logger.error(f"NotificationAgent execution error: {e}")
            result.error = str(e)
            result.add_step({"action": "error", "message": str(e)})

        return result


# 预设智能体工厂
AGENT_TYPES = {
    "parser": ParserAgent,
    "summarizer": SummarizerAgent,
    "qa": QAAgent,
    "notification": NotificationAgent,
}


def get_agent(agent_type: str) -> Optional[BaseAgent]:
    """获取指定类型的智能体"""
    agent_class = AGENT_TYPES.get(agent_type.lower())
    if agent_class:
        return agent_class()
    return None


def list_agents() -> List[Dict]:
    """列出所有预设智能体"""
    return [
        {
            "type": agent_type,
            "name": agent_class().name,
            "description": agent_class().description
        }
        for agent_type, agent_class in AGENT_TYPES.items()
    ]
