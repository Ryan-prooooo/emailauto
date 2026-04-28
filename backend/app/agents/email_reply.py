"""
邮件回复功能 - Email Reply
支持草稿生成和自动发送
"""
from typing import Any, Dict, Optional
from app.config import settings
from app.logger import Logger

logger = Logger.get("email_reply")


class EmailReply:
    """邮件回复器"""

    def __init__(self):
        from app.parser import EmailParser
        self.parser = EmailParser()

    def generate_reply(
        self,
        email_id: int,
        custom_prompt: str = None,
        tone: str = "professional"
    ) -> Dict:
        """生成邮件回复草稿，支持 RSVP 场景"""
        from app.db import Email, SessionLocal
        from openai import OpenAI

        db = SessionLocal()
        try:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email:
                return {"success": False, "error": "邮件不存在"}

            tones = {
                "professional": "专业、简洁、正式",
                "friendly": "友好、亲切、轻松",
                "casual": "随意、简洁、友好",
                "rsvp_accept": "正式、友好、确认参加",
                "rsvp_decline": "正式、礼貌、婉拒",
                "rsvp_tentative": "正式、礼貌、待确认"
            }
            tone_desc = tones.get(tone, tones["professional"])

            prompt = custom_prompt or f"""请根据以下邮件内容，生成一封合适的回复邮件。

原始邮件：
- 发件人: {email.sender}
- 主题: {email.subject}
- 正文: {email.body_text or '无正文'}

回复要求：
- 语气: {tone_desc}
- 保持简洁
- 针对邮件内容给出适当的回应
- 生成完整的邮件正文（不需要主题，因为主题通常是"Re: 原主题"）
"""

            client = OpenAI(
                api_key=settings.DASHSCOPE_API_KEY,
                base_url=settings.DASHSCOPE_BASE_URL
            )

            response = client.chat.completions.create(
                model=settings.DASHSCOPE_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的邮件助手，擅长撰写各种场景的邮件回复。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )

            reply_content = response.choices[0].message.content

            return {
                "success": True,
                "email_id": email_id,
                "original_subject": email.subject,
                "reply_subject": f"Re: {email.subject}",
                "reply_to": getattr(email, "sender_email", email.sender),
                "reply_content": reply_content,
                "tone": tone
            }

        except Exception as e:
            logger.error(f"生成回复失败: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def send_reply(
        self,
        email_id: int,
        reply_content: str = None,
        custom_prompt: str = None,
        tone: str = "professional"
    ) -> Dict:
        """发送邮件回复"""
        from app.db import Email, SessionLocal

        db = SessionLocal()
        try:
            # 获取原始邮件
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email:
                return {"success": False, "error": "邮件不存在"}

            # 如果没有提供回复内容，先生成
            if not reply_content:
                result = self.generate_reply(email_id, custom_prompt, tone)
                if not result.get("success"):
                    return result
                reply_content = result["reply_content"]

            # 发送回复
            from app.mailer import mailer
            subject = f"Re: {email.subject}"
            success = mailer.send_email(
                email.sender,
                subject,
                reply_content
            )

            return {
                "success": success,
                "email_id": email_id,
                "reply_to": getattr(email, "sender_email", email.sender),
                "subject": subject
            }

        except Exception as e:
            logger.error(f"发送回复失败: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def batch_generate_replies(
        self,
        email_ids: list,
        tone: str = "professional"
    ) -> Dict:
        """批量生成回复草稿"""
        results = []
        for email_id in email_ids:
            result = self.generate_reply(email_id, tone=tone)
            results.append(result)

        success_count = sum(1 for r in results if r.get("success"))

        return {
            "success": True,
            "total": len(email_ids),
            "generated": success_count,
            "results": results
        }


# 全局邮件回复器
_email_reply = EmailReply()


def get_email_reply() -> EmailReply:
    """获取全局邮件回复器"""
    return _email_reply


# ================ 工具函数 ================

def draft_email_reply_func(
    email_id: int,
    custom_prompt: str = None,
    tone: str = "professional"
) -> Dict:
    """生成邮件回复草稿"""
    reply = get_email_reply()
    return reply.generate_reply(email_id, custom_prompt, tone)


def reply_email_func(
    email_id: int,
    reply_content: str = None,
    custom_prompt: str = None,
    tone: str = "professional"
) -> Dict:
    """发送邮件回复"""
    reply = get_email_reply()
    return reply.send_reply(email_id, reply_content, custom_prompt, tone)
