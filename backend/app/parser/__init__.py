from openai import OpenAI
from typing import Dict, List, Optional
import json
import re
import logging
from datetime import datetime

from app.config import settings
from app.db import Email, Event, SessionLocal

logger = logging.getLogger(__name__)


class EmailParser:
    """邮件解析器 - 使用 DeepSeek 智能解析邮件内容"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )
        self.model = settings.OPENAI_MODEL

    def _build_prompt(self, subject: str, content: str) -> str:
        """构建解析提示词"""
        categories = ", ".join(settings.event_categories_list)

        prompt = f"""你是一个智能邮件分析助手。请分析以下邮件内容，提取关键信息。

## 邮件信息
- 主题: {subject}
- 内容: {content[:2000]}

## 任务要求
1. 判断邮件属于哪个类别: {categories}
2. 提取邮件中的重要事件信息（包括时间、地点、人物等）
3. 判断是否为重要邮件
4. 判断是否需要采取行动
5. 如果需要行动，列出具体的行动项

## 输出格式（JSON）
{{
    "category": "类别",
    "summary": "邮件摘要（50字以内）",
    "important": true/false,
    "actionable": true/false,
    "action_items": ["行动项1", "行动项2"],
    "event": {{
        "title": "事件标题",
        "description": "事件描述",
        "event_time": "事件时间（ISO格式，如2024-01-15T10:00:00）",
        "location": "地点（如有）"
    }}（如果没有事件则为空对象）
}}

请只输出JSON，不要其他内容。"""
        return prompt

    def parse_email(self, subject: str, content: str) -> Dict:
        """解析单封邮件"""
        try:
            prompt = self._build_prompt(subject, content)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个智能邮件分析助手，擅长提取关键信息。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )

            result_text = response.choices[0].message.content.strip()

            # 尝试提取 JSON
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                logger.info(f"成功解析邮件: {subject}")
                return result
            else:
                logger.warning(f"无法从响应中提取JSON: {result_text}")
                return self._fallback_parse(subject, content)

        except Exception as e:
            logger.error(f"解析邮件失败: {e}")
            return self._fallback_parse(subject, content)

    def _fallback_parse(self, subject: str, content: str) -> Dict:
        """备用解析方法 - 不使用 AI"""
        # 简单关键词匹配
        category = "其他"
        content_lower = (subject + content).lower()

        keywords = {
            "购物": ["订单", "购买", "支付", "发货", "快递", "物流"],
            "账单": ["账单", "缴费", "还款", "费用", "发票"],
            "物流": ["快递", "物流", "发货", "已发出", "运输中", "签收"],
            "社交": ["邀请", "会议", "聚会", "活动"],
            "工作": ["面试", "Offer", "入职", "辞职", "会议", "项目"],
            "订阅": ["订阅", "会员", "续费"]
        }

        for cat, words in keywords.items():
            if any(w in content_lower for w in words):
                category = cat
                break

        return {
            "category": category,
            "summary": subject[:50],
            "important": False,
            "actionable": False,
            "action_items": [],
            "event": {}
        }

    def parse_and_save(self, email_id: int) -> bool:
        """解析邮件并保存到数据库"""
        db = SessionLocal()
        try:
            email_record = db.query(Email).filter(Email.id == email_id).first()
            if not email_record:
                logger.error(f"邮件不存在: {email_id}")
                return False

            if email_record.processed:
                logger.info(f"邮件已处理: {email_id}")
                return True

            # 解析邮件
            result = self.parse_email(
                email_record.subject,
                email_record.content_text or ""
            )

            # 更新邮件记录
            email_record.category = result.get("category", "其他")
            email_record.summary = result.get("summary", "")
            email_record.processed = True

            # 创建事件记录
            event_data = result.get("event", {})
            if event_data and event_data.get("title"):
                event = Event(
                    email_id=email_id,
                    event_type=result.get("category", "其他"),
                    title=event_data.get("title", ""),
                    description=event_data.get("description", ""),
                    event_time=self._parse_datetime(event_data.get("event_time")),
                    location=event_data.get("location", ""),
                    important=result.get("important", False),
                    actionable=result.get("actionable", False),
                    action_items=json.dumps(result.get("action_items", []), ensure_ascii=False),
                    processed=True
                )
                db.add(event)

            db.commit()
            logger.info(f"成功保存解析结果: email_id={email_id}")
            return True

        except Exception as e:
            logger.error(f"保存解析结果失败: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def _parse_datetime(self, time_str: Optional[str]) -> Optional[datetime]:
        """解析时间字符串"""
        if not time_str:
            return None

        try:
            # 尝试解析 ISO 格式
            return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        except:
            return None


def process_unprocessed_emails() -> Dict:
    """处理所有未处理的邮件"""
    db = SessionLocal()
    result = {"processed": 0, "failed": 0}

    try:
        parser = EmailParser()
        emails = db.query(Email).filter(Email.processed == False).all()

        for email_record in emails:
            if parser.parse_and_save(email_record.id):
                result["processed"] += 1
            else:
                result["failed"] += 1

        logger.info(f"批量处理完成: 成功={result['processed']}, 失败={result['failed']}")
    except Exception as e:
        logger.error(f"批量处理邮件失败: {e}")
    finally:
        db.close()

    return result
