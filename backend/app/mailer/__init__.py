from smtplib import SMTP_SSL
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime

from app.config import settings
from app.db import Event, SessionLocal
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

            text_part = MIMEText(body, "plain", "utf-8")
            msg.attach(text_part)

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

    def send_daily_summary(self, to_email: str = None) -> bool:
        """发送每日摘要"""
        recipient = to_email or self.email
        db = SessionLocal()

        try:
            today = datetime.now().date()
            events = db.query(Event).filter(
                Event.created_at >= datetime.combine(today, datetime.min.time())
            ).all()

            subject = f"MailLife - 每日摘要 ({today})"

            body = f"""您好！

以下是今日事件摘要：

今日共处理 {len(events)} 个事件。
"""

            if events:
                body += "\n事件列表：\n\n"
                for i, event in enumerate(events, 1):
                    body += f"{i}. 【{event.event_type or '其他'}】{event.title}\n"
                    body += f"   时间: {event.start_time.strftime('%Y-%m-%d %H:%M') if event.start_time else '暂无'}\n"
                    body += f"   地点: {event.location if event.location else '暂无'}\n"
                    body += "\n"

            body += """
---
MailLife - 让您的生活更有序
"""

            return self.send_email(recipient, subject, body)

        except Exception as e:
            logger.error(f"发送每日摘要失败: {e}")
            return False
        finally:
            db.close()

    def send_event_notification(self, event_id, to_email: str = None) -> bool:
        """发送事件通知"""
        recipient = to_email or self.email
        db = SessionLocal()

        try:
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                logger.error(f"事件不存在: {event_id}")
                return False

            subject = f"[MailLife] 事件提醒: {event.title}"

            body = f"""您好！

您有一个新的事件提醒：

事件类型：{event.event_type or '其他'}
事件标题：{event.title}
"""

            if event.description:
                body += f"事件描述：{event.description}\n"

            body += f"事件时间：{event.start_time.strftime('%Y-%m-%d %H:%M') if event.start_time else '暂无'}\n"
            if event.location:
                body += f"事件地点：{event.location}\n"

            body += """
---
MailLife - 让您的生活更有序
"""

            return self.send_email(recipient, subject, body)

        except Exception as e:
            logger.error(f"发送事件通知失败: {e}")
            return False
        finally:
            db.close()


# 全局邮件发送器实例
mailer = Mailer()
