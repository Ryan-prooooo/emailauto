from imap_tools import MailBox, AND
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
import email
import hashlib
import re
import ssl
from email.header import decode_header

from app.config import settings
from app.db import Email, SessionLocal
from app.logger import Logger

logger = Logger.get("imap")


class IMAPClient:
    """IMAP邮件客户端"""

    def __init__(self):
        self.host = settings.QQ_IMAP_HOST or "imap.qq.com"
        self.port = settings.QQ_IMAP_PORT or 993
        self.ssl = settings.QQ_IMAP_SSL
        self.email = settings.QQ_EMAIL
        self.password = settings.qq_password_or_auth
        self.mailbox = None

    def connect(self) -> bool:
        """连接到IMAP服务器"""
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED

            logger.info(f"正在连接IMAP: host={self.host}, port={self.port}, email={self.email}")
            self.mailbox = MailBox(
                self.host,
                self.port,
                timeout=30,
                ssl_context=ssl_context
            )
            self.mailbox.login(self.email, self.password)
            logger.info(f"成功连接到IMAP服务器: {self.host}:{self.port}")
            return True
        except ssl.SSLCertVerificationError as e:
            logger.error(f"SSL证书验证失败: {e}，尝试跳过证书验证...")
            try:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                self.mailbox = MailBox(
                    self.host,
                    self.port,
                    timeout=30,
                    ssl_context=ssl_context
                )
                self.mailbox.login(self.email, self.password)
                logger.warning("已使用跳过证书验证模式连接成功")
                return True
            except Exception as e2:
                logger.error(f"跳过证书验证后仍失败: {e2}", exc_info=True)
                return False
        except Exception as e:
            logger.error(f"连接IMAP服务器失败: {e}", exc_info=True)
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

    def _get_email_body(self, msg) -> tuple:
        """获取邮件正文"""
        text_content = ""
        html_content = ""

        # imap_tools 提供了更安全的方法来获取内容
        # 尝试使用 msg.text 和 msg.html 属性
        try:
            if hasattr(msg, 'text') and msg.text:
                text_content = msg.text
        except Exception as e:
            logger.debug(f"获取纯文本内容失败: {e}")

        try:
            if hasattr(msg, 'html') and msg.html:
                html_content = msg.html
        except Exception as e:
            logger.debug(f"获取HTML内容失败: {e}")

        # 如果上面的方法失败，尝试传统方法
        if not text_content and not html_content:
            try:
                if msg.is_multipart():
                    for part in msg.walk():
                        try:
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition", ""))

                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    charset = part.get_content_charset() or 'utf-8'
                                    text_content = payload.decode(charset, errors='ignore')
                            elif content_type == "text/html" and "attachment" not in content_disposition:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    charset = part.get_content_charset() or 'utf-8'
                                    html_content = payload.decode(charset, errors='ignore')
                        except Exception:
                            continue
                else:
                    try:
                        content_type = msg.get_content_type()
                        payload = msg.get_payload(decode=True)
                        if payload:
                            charset = msg.get_content_charset() or 'utf-8'
                            content = payload.decode(charset, errors='ignore')
                            if content_type == "text/plain":
                                text_content = content
                            elif content_type == "text/html":
                                html_content = content
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"传统方法解析邮件正文失败: {e}")

        return text_content, html_content

    def fetch_recent_emails(
        self,
        days: Optional[int] = None,
        limit: int = 100,
        folder: str = "INBOX",
        sender_filter: Optional[str] = None,
        subject_filter: Optional[str] = None,
        unread_only: bool = False,
        mark_as_read: bool = False
    ) -> List[Dict]:
        """获取邮件
        
        Args:
            days: 搜索最近多少天的邮件，None 表示不限时间获取最新邮件
            limit: 最大返回数量
            folder: 邮箱文件夹，默认 INBOX
            sender_filter: 发件人过滤关键词
            subject_filter: 主题过滤关键词
            unread_only: 是否只获取未读邮件
            mark_as_read: 获取后是否标记为已读
        
        Returns:
            邮件列表
        """
        if not self.mailbox:
            if not self.connect():
                return []

        emails = []

        try:
            # 切换到指定文件夹
            try:
                self.mailbox.folder.set(folder)
            except Exception as e:
                logger.warning(f"切换文件夹 {folder} 失败: {e}")
                try:
                    self.mailbox.folder.set("INBOX")
                except Exception:
                    pass

            # 先获取最新邮件（不加日期过滤，避免QQ邮箱服务器超时）
            # QQ邮箱对带日期条件的IMAP搜索响应极慢，改用先获取后过滤的策略
            beijing_tz = timezone(timedelta(hours=8))
            since_date = datetime.now(beijing_tz) - timedelta(days=days) if days is not None else None

            logger.info(f"准备获取邮件: folder={folder}, limit={limit}, days={days}")

            # 直接获取最新邮件，不带服务器端日期过滤
            try:
                all_messages = list(self.mailbox.fetch(AND(all=True), limit=limit, reverse=True))
                logger.info(f"fetch 返回 {len(all_messages)} 条记录")
            except Exception as fetch_err:
                logger.error(f"fetch 调用异常: {fetch_err}")
                raise

            logger.debug(f"共 {len(all_messages)} 封邮件待处理")

            for msg in all_messages:
                try:
                    # 规范化 msg.date 为 aware datetime（imap_tools 返回的 date 无时区，假设为 UTC+8）
                    msg_date_aware = msg.date
                    if msg_date_aware.tzinfo is None:
                        beijing_tz = timezone(timedelta(hours=8))
                        msg_date_aware = msg_date_aware.replace(tzinfo=beijing_tz)

                    # 客户端日期过滤：如果指定了 days，则跳过超期邮件
                    if since_date and msg_date_aware < since_date:
                        continue

                    # 客户端过滤：未读邮件
                    is_read_flag = '\\Seen' in (msg.flags or []) or msg.seen if hasattr(msg, 'seen') else False
                    if unread_only and is_read_flag:
                        continue

                    # 客户端过滤：发件人关键词
                    if sender_filter:
                        from_field = self._safe_get_attr(msg, 'from_', '')
                        if sender_filter.lower() not in from_field.lower():
                            continue

                    # 客户端过滤：主题关键词
                    if subject_filter:
                        subject = self._safe_get_attr(msg, 'subject', '')
                        if subject_filter.lower() not in subject.lower():
                            continue

                    # 提取邮件数据
                    email_data = self._extract_email_data(msg)

                    # 标记为已读（如果需要）
                    if mark_as_read and not email_data.get("is_read", False):
                        try:
                            self.mailbox.seen(msg.uid, True)
                            email_data["is_read"] = True
                        except Exception as e:
                            logger.debug(f"标记已读失败: {e}")

                    emails.append(email_data)

                except Exception as e:
                    logger.error(f"解析邮件 UID={msg.uid} 时出错: {e}")
                    continue

            logger.info(f"成功获取 {len(emails)} 封邮件 (folder={folder})")
            
        except Exception as e:
            logger.error(f"获取邮件失败: {e}")

        return emails

    def _extract_email_data(self, msg) -> Dict:
        """提取邮件数据（抽取公共逻辑）
        
        Args:
            msg: imap_tools MailMessage 对象
        
        Returns:
            邮件数据字典
        """
        # 1. 获取邮件正文
        text_content, html_content = self._get_email_body_safe(msg)
        
        # 2. 处理邮件时间（确保时区正确）
        received_time = self._normalize_datetime(msg.date)
        
        # 3. 安全提取各种字段
        subject = self._safe_get_attr(msg, 'subject', '')
        from_field = self._safe_get_attr(msg, 'from_', '')
        sender_email = self._extract_email_address(from_field)
        
        # 4. 处理收件人
        recipient = msg.to
        if isinstance(recipient, (tuple, list)):
            recipient = ", ".join(str(r) for r in recipient)
        elif recipient:
            recipient = str(recipient)
        else:
            recipient = ""

        # 5. 获取消息ID
        message_id = self._get_message_id(msg)
        
        # 6. 判断是否已读
        is_read = '\\Seen' in (msg.flags or []) or msg.seen if hasattr(msg, 'seen') else False

        # 7. 获取附件信息
        attachments = []
        if hasattr(msg, 'attachments') and msg.attachments:
            for att in msg.attachments:
                attachments.append({
                    "filename": att.filename,
                    "content_type": att.content_type,
                    "size": len(att.payload) if hasattr(att, 'payload') else 0
                })

        return {
            "message_id": message_id,
            "uid": msg.uid,
            "subject": subject,
            "sender": from_field,
            "sender_email": sender_email,
            "recipient": recipient,
            "content_text": text_content,
            "content_html": html_content,
            "received_at": received_time,
            "is_read": is_read,
            "attachments": attachments,
            "labels": list(msg.flags) if hasattr(msg, 'flags') and msg.flags else []
        }

    def _get_email_body_safe(self, msg) -> tuple:
        """安全获取邮件正文
        
        Returns:
            (text_content, html_content)
        """
        text_content = ""
        html_content = ""
        
        # 方法1: 使用 imap_tools 的属性
        try:
            if hasattr(msg, 'text') and msg.text:
                text_content = msg.text.strip()
        except Exception as e:
            logger.debug(f"获取纯文本属性失败: {e}")
        
        try:
            if hasattr(msg, 'html') and msg.html:
                html_content = msg.html.strip()
        except Exception as e:
            logger.debug(f"获取HTML属性失败: {e}")
        
        # 方法2: 如果属性为空，尝试原始对象
        if not text_content and not html_content:
            try:
                text_content, html_content = self._get_email_body(msg.obj)
            except Exception as e:
                logger.debug(f"_get_email_body 失败: {e}")
        
        # 兜底：只要 text 为空（无论 HTML 有没有值），都尝试从 HTML 提取纯文本
        if not text_content:
            try:
                from bs4 import BeautifulSoup
                text_content = BeautifulSoup(html_content, "lxml").get_text(separator=" ", strip=True)[:5000]
            except Exception:
                pass

        return text_content, html_content

    def _normalize_datetime(self, dt) -> datetime:
        """规范化日期时间（处理时区）
        
        Args:
            dt: 原始日期时间
        
        Returns:
            带时区的 UTC 时间
        """
        if not dt:
            return datetime.now(timezone.utc)
        
        # 如果没有时区信息，假设是本地时间（UTC+8，中国）
        if dt.tzinfo is None:
            local_tz = timezone(timedelta(hours=8))
            dt = dt.replace(tzinfo=local_tz)
        
        # 转换为 UTC
        return dt.astimezone(timezone.utc)

    def _safe_get_attr(self, obj, attr: str, default: Any = None) -> Any:
        """安全获取对象属性
        
        Args:
            obj: 目标对象
            attr: 属性名
            default: 默认值
        
        Returns:
            属性值或默认值
        """
        try:
            value = getattr(obj, attr, None)
            return value if value else default
        except Exception:
            return default

    def _extract_email_address(self, from_string: str) -> str:
        """从发件人字符串中提取邮箱地址
        
        Args:
            from_string: 发件人字符串，如 "张三 <zhangsan@qq.com>"
        
        Returns:
            邮箱地址
        """
        if not from_string:
            return ""
        
        # 尝试提取 < > 中的内容
        match = re.search(r'<([^>]+)>', from_string)
        if match:
            return match.group(1).strip()
        
        # 如果没有 < >，判断是否是邮箱格式
        if '@' in from_string and '.' in from_string:
            return from_string.strip()
        
        return ""

    def _get_message_id(self, msg) -> str:
        """获取邮件唯一标识
        
        Returns:
            消息ID
        """
        # 优先使用 Message-ID 头
        try:
            if msg.obj and msg.obj.get('Message-ID'):
                return str(msg.obj['Message-ID']).strip()
        except Exception:
            pass
        
        # 其次使用 UID
        try:
            if msg.uid:
                return f"UID:{msg.uid}"
        except Exception:
            pass
        
        # 最后使用 subject + date 的哈希
        try:
            hash_input = f"{msg.subject}_{msg.date}".encode('utf-8')
            return f"Hash:{hashlib.md5(hash_input).hexdigest()}"
        except Exception:
            return f"Fallback:{id(msg)}"

    def fetch_all_unread(self, limit: int = 100, folder: str = "INBOX") -> List[Dict]:
        """获取所有未读邮件
        
        Args:
            limit: 最大返回数量
            folder: 邮箱文件夹，默认 INBOX
        
        Returns:
            未读邮件列表
        """
        return self.fetch_recent_emails(
            days=30,
            limit=limit,
            folder=folder,
            unread_only=True
        )

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
            # 获取 message_id
            msg_id = email_data.get("message_id", "")
            
            # 如果 message_id 为空，尝试使用 subject + sender 作为唯一标识
            if not msg_id:
                msg_id = f"manual_{hash(email_data.get('subject', '') + email_data.get('sender', ''))}"
                logger.info(f"邮件无 message_id，使用备用标识: {msg_id[:20]}...")
            
            existing = db.query(Email).filter(Email.message_id == msg_id).first()
            if existing:
                continue

            new_email = Email(
                message_id=email_data["message_id"],
                subject=email_data["subject"],
                sender=email_data["sender"],
                recipient=email_data["recipient"],
                body_text=email_data["content_text"],
                body_html=email_data["content_html"],
                date=email_data["received_at"],
                is_read=email_data["is_read"]
            )
            db.add(new_email)
            result["synced"] += 1

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
