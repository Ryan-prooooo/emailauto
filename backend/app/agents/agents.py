"""
邮件智能体 - 实现 3 个执行类 Agent
ParserAgent, SummarizerAgent, NotificationAgent
QAAgent 内部委托给 LangGraph EmailAgent 统一编排
"""
from typing import Any, Dict, List, Optional
from app.agents.base import BaseAgent, AgentResult
from app.agents.tools import get_registry
from app.config import settings
from app.logger import Logger

logger = Logger.get("agents")


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
            registry.get("notion_archive_summary"),
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
                    },
                    "events_list": [
                        {"title": e.title, "description": e.description}
                        for e in events[:10]
                    ]
                }
                result.add_step({"action": "generate_summary", "status": "success"})

                # 自动归档到 Notion
                if settings.NOTION_API_KEY and settings.NOTION_DATABASE_ID:
                    self._archive_to_notion(result)

            finally:
                db.close()

        except Exception as e:
            logger.error(f"SummarizerAgent execution error: {e}")
            result.error = str(e)
            result.add_step({"action": "error", "message": str(e)})

        return result

    def _archive_to_notion(self, result: AgentResult):
        """归档摘要到 Notion"""
        from datetime import datetime
        try:
            from app.mcp.notion_adapter import get_notion_adapter
            notion = get_notion_adapter()

            if not notion.is_configured:
                result.add_step({"action": "notion_archive", "status": "skipped", "reason": "Notion 未配置"})
                return

            today = datetime.now().strftime("%Y-%m-%d")
            summary_data = {
                "summary": result.data.get("summary") if result.data else "",
                "stats": result.data.get("stats") if result.data else {},
                "events": result.data.get("events_list", []) if result.data else []
            }

            archive_result = notion.create_or_update_daily_summary(date=today, summary_data=summary_data)

            if archive_result.get("success"):
                result.add_step({"action": "notion_archive", "status": "success", "page_id": archive_result.get("page_id")})
                result.data["notion_archive"] = archive_result
            else:
                result.add_step({"action": "notion_archive", "status": "failed", "error": archive_result.get("error")})

        except Exception as e:
            logger.error(f"Notion 归档失败: {e}")
            result.add_step({"action": "notion_archive", "status": "error", "message": str(e)})


class QAAgent(BaseAgent):
    """问答智能体 — 委托给 LangGraph EmailAgent 执行"""

    def __init__(self):
        super().__init__(
            name="qa_agent",
            description="智能问答，内部委托给 LangGraph Supervisor 统一编排"
        )
        self._setup_tools()

    def _setup_tools(self):
        """设置可用工具"""
        registry = get_registry()
        self.tools = list(registry.get_all().values())
        self.tools = [t for t in self.tools if t is not None]

    def execute(self, input_data: Any, **kwargs) -> AgentResult:
        """执行问答任务 — 委托给 LangGraph EmailAgent"""
        result = AgentResult(success=False)

        try:
            if isinstance(input_data, dict):
                message = input_data.get("message", "")
                session_id = input_data.get("session_id")
            elif isinstance(input_data, str):
                message = input_data
                session_id = kwargs.get("session_id")
            else:
                result.error = "无效的输入类型"
                return result

            from app.agents.graph.email_agent import get_supervisor_agent
            agent = get_supervisor_agent()
            output = agent.chat(message=message, session_id=session_id)

            result.success = output.success
            result.data = {
                "response": output.response,
                "session_id": session_id,
                "intents": output.intents,
                "error": output.error,
            }
            result.add_step({"action": "langgraph_email_agent", "status": "success" if output.success else "failed"})

        except Exception as e:
            logger.error(f"QAAgent execution error: {e}")
            result.error = str(e)
            result.add_step({"action": "error", "message": str(e)})

        return result

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
