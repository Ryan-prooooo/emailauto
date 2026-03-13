from imap_tools import MailBox, AND
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import email
from email.header import decode_header
import logging

from app.config import settings
from app.db import Email, SessionLocal, SyncStatus

logger = logging.getLogger(__name__)


class IMAPClient:
    """IMAP邮件客户端"""

    def __init__(self):
        self.host = settings.IMAP_HOST
        self.port = settings.IMAP_PORT
        self.email = settings.QQ_EMAIL
        self.password = settings.qq_password_or_auth
        self.mailbox = None

    def connect(self) -> bool:
        """连接到IMAP服务器"""
        try:
            self.mailbox = MailBox(self.host, self.port)
            self.mailbox.login(self.email, self.password)
            logger.info(f"成功连接到IMAP服务器: {self.host}")
            return True
        except Exception as e:
            logger.error(f"连接IMAP服务器失败: {e}")
            return False

    def disconnect(self):
        """断开IMAP连接"""
        if self.mailbox:
            try:
                self.mailbox.logout()
                logger.info("已断开IMAP连接")
            except Exception as e:
                logger.error(f"断开IMAP连接时出错: {e}")

    def _decode_email_header(self, header: str) -> str:
        """解码邮件头"""
        if not header:
            return ""
        decoded_parts = decode_header(header)
        result = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                result += part
        return result

    def _get_email_body(self, msg: email.message.Message) -> tuple:
        """获取邮件正文"""
        text_content = ""
        html_content = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        text_content = part.get_payload(decode=True).decode(
                            part.get_content_charset() or 'utf-8', errors='ignore'
                        )
                    except:
                        pass
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    try:
                        html_content = part.get_payload(decode=True).decode(
                            part.get_content_charset() or 'utf-8', errors='ignore'
                        )
                    except:
                        pass
        else:
            try:
                content_type = msg.get_content_type()
                if content_type == "text/plain":
                    text_content = msg.get_payload(decode=True).decode(
                        msg.get_content_charset() or 'utf-8', errors='ignore'
                    )
                elif content_type == "text/html":
                    html_content = msg.get_payload(decode=True).decode(
                        msg.get_content_charset() or 'utf-8', errors='ignore'
                    )
            except:
                pass

        return text_content, html_content

    def fetch_recent_emails(self, days: int = 7, limit: int = 100) -> List[Dict]:
        """获取最近N天的邮件"""
        if not self.mailbox:
            if not self.connect():
                return []

        emails = []
        since_date = datetime.now() - timedelta(days=days)

        try:
            for msg in self.mailbox.fetch(
                AND(date_gte=since_date.date(), seen=False),
                limit=limit,
                reverse=True
            ):
                try:
                    text_content, html_content = self._get_email_body(msg.obj)

                    email_data = {
                        "message_id": msg.obj['Message-ID'] or msg.uid or "",
                        "subject": self._decode_email_header(msg.subject) if msg.subject else "",
                        "sender": self._decode_email_header(msg.from_) if msg.from_ else "",
                        "sender_email": msg.from_,
                        "recipient": ", ".join(msg.to) if isinstance(msg.to, (tuple, list)) else str(msg.to) if msg.to else "",
                        "content_text": text_content,
                        "content_html": html_content,
                        "received_at": msg.date or datetime.now(),
                        "is_read": '\\Seen' in msg.flags if hasattr(msg, 'flags') else False
                    }
                    emails.append(email_data)
                except Exception as e:
                    logger.error(f"解析邮件时出错: {e}")
                    continue

            logger.info(f"成功获取 {len(emails)} 封邮件")
        except Exception as e:
            logger.error(f"获取邮件失败: {e}")

        return emails

    def fetch_all_unread(self, limit: int = 100) -> List[Dict]:
        """获取所有未读邮件"""
        if not self.mailbox:
            if not self.connect():
                return []

        emails = []

        try:
            for msg in self.mailbox.fetch(AND(seen=False), limit=limit, reverse=True):
                try:
                    text_content, html_content = self._get_email_body(msg.obj)

                    email_data = {
                        "message_id": msg.obj['Message-ID'] or msg.uid or "",
                        "subject": self._decode_email_header(msg.subject) if msg.subject else "",
                        "sender": self._decode_email_header(msg.from_) if msg.from_ else "",
                        "sender_email": msg.from_,
                        "recipient": ", ".join(msg.to) if isinstance(msg.to, (tuple, list)) else str(msg.to) if msg.to else "",
                        "content_text": text_content,
                        "content_html": html_content,
                        "received_at": msg.date or datetime.now(),
                        "is_read": '\\Seen' in msg.flags if hasattr(msg, 'flags') else False
                    }
                    emails.append(email_data)
                except Exception as e:
                    logger.error(f"解析邮件时出错: {e}")
                    continue

            logger.info(f"成功获取 {len(emails)} 封未读邮件")
        except Exception as e:
            logger.error(f"获取未读邮件失败: {e}")

        return emails

    def mark_as_read(self, message_id: str) -> bool:
        """标记邮件为已读"""
        if not self.mailbox:
            return False

        try:
            self.mailbox.flag(message_id, ["Seen"], True)
            return True
        except Exception as e:
            logger.error(f"标记邮件为已读失败: {e}")
            return False


def sync_emails_to_db(days: int = 7, limit: int = 100) -> Dict:
    """同步邮件到数据库"""
    db = SessionLocal()
    result = {"success": False, "synced": 0, "errors": []}

    try:
        client = IMAPClient()
        if not client.connect():
            result["errors"].append("无法连接到IMAP服务器")
            return result

        emails = client.fetch_recent_emails(days=days, limit=limit)

        for email_data in emails:
            existing = db.query(Email).filter(Email.message_id == email_data["message_id"]).first()
            if existing:
                continue

            new_email = Email(
                message_id=email_data["message_id"],
                subject=email_data["subject"],
                sender=email_data["sender"],
                sender_email=email_data["sender_email"],
                recipient=email_data["recipient"],
                content_text=email_data["content_text"],
                content_html=email_data["content_html"],
                received_at=email_data["received_at"],
                is_read=email_data["is_read"]
            )
            db.add(new_email)
            result["synced"] += 1

        sync_status = SyncStatus(
            last_sync_time=datetime.now(),
            total_emails=result["synced"],
            status="success"
        )
        db.add(sync_status)

        db.commit()
        result["success"] = True
        logger.info(f"成功同步 {result['synced']} 封新邮件到数据库")

    except Exception as e:
        logger.error(f"同步邮件到数据库失败: {e}")
        result["errors"].append(str(e))
        db.rollback()
    finally:
        client.disconnect()
        db.close()

    return result
