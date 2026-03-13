"""记忆管理系统 - 实现近期记忆和长期记忆"""
from typing import List, Tuple, Optional
import logging

from sqlalchemy.orm import Session

from app.db import ChatMessage, SessionLocal
from app.config import settings

logger = logging.getLogger(__name__)

# 配置参数
RECENT_WINDOW_SIZE = 10  # 近期记忆保留最近 10 条消息
SUMMARY_THRESHOLD = 20    # 超过 20 条消息时触发摘要
SUMMARY_BATCH_SIZE = 10   # 每批摘要 10 条消息


class MemoryManager:
    """记忆管理器 - 管理近期记忆和长期记忆"""

    def __init__(self, session_id: int, db: Optional[Session] = None):
        self.session_id = session_id
        self._db = db
        self._owns_db = False

    @property
    def db(self) -> Session:
        """获取数据库会话"""
        if self._db is None:
            self._db = SessionLocal()
            self._owns_db = True
        return self._db

    def close(self):
        """关闭数据库会话"""
        if self._owns_db and self._db:
            self._db.close()
            self._db = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_context_for_llm(self) -> Tuple[List[dict], str]:
        """
        获取融合后的上下文
        返回: (近期对话消息列表, 长期记忆摘要)
        """
        # 获取所有消息
        all_messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == self.session_id)
            .order_by(ChatMessage.created_at)
            .all()
        )

        # 分离近期消息和已摘要的消息
        recent_messages = []
        summarized_msgs = []

        for msg in all_messages:
            if hasattr(msg, 'memory_type') and msg.memory_type == 'summarized':
                summarized_msgs.append(msg)
            else:
                recent_messages.append(msg)

        # 限制近期窗口大小
        recent_messages = recent_messages[-RECENT_WINDOW_SIZE:]

        recent_ctx = [
            {"role": msg.role, "content": msg.content}
            for msg in recent_messages
        ]

        # 获取长期记忆摘要
        long_term_summary = self._get_long_term_summary()

        return recent_ctx, long_term_summary

    def _get_long_term_summary(self) -> str:
        """获取长期记忆摘要"""
        summarized_msgs = (
            self.db.query(ChatMessage)
            .filter(
                ChatMessage.session_id == self.session_id,
                ChatMessage.memory_type == 'summarized'
            )
            .order_by(ChatMessage.created_at.desc())
            .all()
        )

        if not summarized_msgs:
            return ""

        # 拼接所有摘要
        summaries = [msg.summary for msg in summarized_msgs if msg.summary]
        return " ".join(summaries)

    def add_message(self, role: str, content: str) -> ChatMessage:
        """添加新消息"""
        msg = ChatMessage(
            session_id=self.session_id,
            role=role,
            content=content,
            memory_type="recent"
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)

        # 检查是否需要整理记忆
        self._organize_memory()

        return msg

    def _organize_memory(self):
        """整理记忆：超过阈值时执行摘要"""
        # 统计当前会话的消息数量
        msg_count = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == self.session_id)
            .count()
        )

        if msg_count >= SUMMARY_THRESHOLD:
            self._summarize_old_messages()

    def _summarize_old_messages(self):
        """对旧消息进行摘要"""
        # 获取最旧的未摘要消息（SUMMARY_BATCH_SIZE 条）
        old_messages = (
            self.db.query(ChatMessage)
            .filter(
                ChatMessage.session_id == self.session_id,
                ChatMessage.memory_type == 'recent'
            )
            .order_by(ChatMessage.created_at)
            .limit(SUMMARY_BATCH_SIZE)
            .all()
        )

        if not old_messages:
            return

        # 拼接旧消息内容
        content_parts = []
        for msg in old_messages:
            role_label = "用户" if msg.role == "user" else "AI"
            content_parts.append(f"{role_label}: {msg.content}")

        content = "\n".join(content_parts)

        # 调用 LLM 生成摘要
        summary = self._generate_summary(content)

        if not summary:
            return

        # 标记旧消息为已归档
        for msg in old_messages:
            msg.memory_type = "archived"

        # 创建摘要消息
        summary_msg = ChatMessage(
            session_id=self.session_id,
            role="system",
            content=f"[历史对话摘要]",
            memory_type="summarized",
            summary=summary
        )
        self.db.add(summary_msg)
        self.db.commit()

        logger.info(f"会话 {self.session_id} 已生成摘要: {summary[:50]}...")

    def _generate_summary(self, content: str) -> Optional[str]:
        """调用 LLM 生成摘要"""
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL
            )

            prompt = f"""请将以下对话历史压缩成简洁的摘要，保留关键信息（用户问题要点、AI回答要点、重要结论）：

{content}

要求：不超过100字，直接给出摘要内容，不要前缀。"""

            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200
            )

            summary = response.choices[0].message.content.strip()
            return summary

        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
            return None


def get_memory_context(session_id: int) -> Tuple[List[dict], str]:
    """便捷函数：获取会话的上下文"""
    with MemoryManager(session_id) as manager:
        return manager.get_context_for_llm()


def add_chat_message(session_id: int, role: str, content: str) -> ChatMessage:
    """便捷函数：添加对话消息"""
    with MemoryManager(session_id) as manager:
        return manager.add_message(role, content)
