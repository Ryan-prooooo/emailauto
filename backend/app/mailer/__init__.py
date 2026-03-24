from smtplib import SMTP_SSL
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json

from app.config import settings
from app.db import Email, Event, SessionLocal
from app.logger import Logger

logger = Logger.get("mailer")


class Mailer:
    """邮件发送器"""

    def __init__(self):
        self.smtp_host = "smtp.qq.com"
        self.smtp_port = 465
        self.email = settings.QQ_EMAIL
        self.password = settings.qq_password_or_auth

    def _create_connection(self) -> Optional[SMTP_SSL]:
        """创建SMTP连接"""
        try:
            server = SMTP_SSL(self.smtp_host, self.smtp_port)
            server.login(self.email, self.password)
            return server
        except Exception as e:
            logger.error(f"创建SMTP连接失败: {e}")
            return None

    def send_email(self, to_email: str, subject: str, body: str, html: str = None) -> bool:
        """发送邮件"""
        server = self._create_connection()
        if not server:
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.email
            msg["To"] = to_email

            # 添加纯文本内容
            text_part = MIMEText(body, "plain", "utf-8")
            msg.attach(text_part)

            # 添加HTML内容
            if html:
                html_part = MIMEText(html, "html", "utf-8")
                msg.attach(html_part)

            server.sendmail(self.email, to_email, msg.as_string())
            logger.info(f"邮件发送成功: {subject} -> {to_email}")
            return True

        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
            return False
        finally:
            server.quit()

    def _format_action_items(self, action_items_str: str) -> str:
        """将 JSON 字符串格式的待办事项解析并格式化为多行文本"""
        if not action_items_str:
            return "暂无"
        try:
            items = json.loads(action_items_str)
            if not items:
                return "暂无"
            return "\n   ".join(f"{i + 1}. {item}" for i, item in enumerate(items))
        except (json.JSONDecodeError, TypeError):
            return action_items_str  # fallback，保留原始字符串

    def send_daily_summary(self, to_email: str = None) -> bool:
        """发送每日摘要"""
        recipient = to_email or self.email
        db = SessionLocal()

        try:
            # 获取今日事件
            today = datetime.now().date()
            events = db.query(Event).filter(
                Event.created_at >= datetime.combine(today, datetime.min.time())
            ).all()

            # 获取未处理的重要事件
            important_events = [e for e in events if e.important or e.actionable]

            # 构建邮件内容
            subject = f"📧 邮件智能助手 - 每日摘要 ({today})"

            body = f"""您好！

以下是今日邮件摘要：

今日共处理 {len(events)} 封邮件，其中 {len(important_events)} 封需要关注。

"""

            if important_events:
                body += "需要关注的事件：\n\n"
                for i, event in enumerate(important_events, 1):
                    body += f"{i}. 【{event.event_type}】{event.title}\n"
                    body += f"   时间: {event.event_time.strftime('%Y-%m-%d %H:%M') if event.event_time else '暂无'}\n"
                    body += f"   地点: {event.location if event.location else '暂无'}\n"
                    body += f"   待办: {self._format_action_items(event.action_items)}\n"
                    body += "\n"
            else:
                body += "今日没有需要特别关注的事件。\n"

            body += """
---
邮件智能助手 - 让您的生活更有序
"""

            return self.send_email(recipient, subject, body)

        except Exception as e:
            logger.error(f"发送每日摘要失败: {e}")
            return False
        finally:
            db.close()

    def send_event_notification(self, event_id: int, to_email: str = None) -> bool:
        """发送事件通知"""
        recipient = to_email or self.email
        db = SessionLocal()

        try:
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                logger.error(f"事件不存在: {event_id}")
                return False

            subject = f"⏰ 事件提醒: {event.title}"

            body = f"""您好！

您有一个新的事件提醒：

事件类型：{event.event_type}
事件标题：{event.title}
"""

            if event.description:
                body += f"事件描述：{event.description}\n"

            body += f"事件时间：{event.event_time.strftime('%Y-%m-%d %H:%M') if event.event_time else '暂无'}\n"
            body += f"事件地点：{event.location if event.location else '暂无'}\n"
            body += f"待办事项：{self._format_action_items(event.action_items)}\n"

            body += """
---
邮件智能助手 - 让您的生活更有序
"""

            return self.send_email(recipient, subject, body)

        except Exception as e:
            logger.error(f"发送事件通知失败: {e}")
            return False
        finally:
            db.close()


# 全局邮件发送器实例
mailer = Mailer()
