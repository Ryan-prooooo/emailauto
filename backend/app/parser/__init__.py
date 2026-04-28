from openai import OpenAI
from typing import Dict, List, Optional
import json
import re
from datetime import datetime

from app.config import settings
from app.db import Email, Event, SessionLocal
from app.logger import Logger

logger = Logger.get("parser")


class EmailParser:
    """邮件解析器 - 使用阿里百炼（DashScope）智能解析邮件内容"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.DASHSCOPE_BASE_URL
        )
        self.model = settings.DASHSCOPE_MODEL

    def _build_prompt(self, subject: str, content: str) -> str:
        """构建解析提示词"""
        current_year = datetime.now().year

        prompt = f"""你是一个智能邮件分析助手。请分析以下邮件内容，提取关键信息。

## 邮件信息
- 主题: {subject}
- 内容: {content[:2000]}
- 当前年份: {current_year}

## 任务要求
1. 判断邮件属于哪个类别（仅从以下列表选择）：购物, 物流, meeting, 其他
2. 提取邮件中的重要事件信息（时间、地点、人物等）
3. 判断是否为重要邮件
4. 判断是否需要采取行动
5. 如果需要行动，列出具体的行动项

## 会议邮件专项提取
如果邮件是会议/邀约类（category=meeting），请额外提取：
- meeting_link：线上会议链接（如 https://zoom.us/... 或 腾讯会议链接）
- organizer：会议组织者（通常为发件人）
- attendees：参会人列表（从正文提取，JSON 数组格式，如 ["张三", "李四"]）
- rsvp_deadline：RSVP 截止时间（如有）

## 重要约束
- 【时间】尽量从邮件中推断出具体时间，填入 event_time。若邮件中有明确日期（如"10月31日截止"）但未写明年份，默认用当前年份 {current_year}。若完全无法推断时间，填 null。
- 【地点】尽量填写具体地点，若无则填 null，不要留空字符串。
- 【会议邮件】必须提取 meeting_link、organizer、attendees，无法提取则填 null。
- 【title】要简洁准确，能概括邮件核心事件，不能为空。

## 输出格式（JSON）
{{
    "category": "类别（仅从 购物/物流/meeting/其他 中选择）",
    "summary": "邮件摘要（50字以内）",
    "important": true/false,
    "actionable": true/false,
    "action_items": ["行动项1", "行动项2"]（如无则空数组）,
    "event": {{
        "title": "事件标题（必填）",
        "description": "事件描述",
        "event_time": "事件时间（ISO格式，如 {current_year}-01-15T10:00:00），无法推断则填 null",
        "location": "地点，无法推断则填 null",
        "meeting_link": "线上会议链接，无法提取则填 null",
        "organizer": "会议组织者，无法提取则填 null",
        "attendees": ["参会人1", "参会人2"]（无法提取则空数组）,
        "rsvp_deadline": "RSVP截止时间，无法提取则填 null"
    }}
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
        """备用解析方法 - 不使用 AI，仅关键词匹配"""
        category = "其他"
        content_lower = (subject + content).lower()

        keywords = {
            "购物": ["订单", "购买", "支付", "发货", "快递", "物流"],
            "物流": ["快递", "物流", "发货", "已发出", "运输中", "签收"],
            "meeting": ["会议", "邀约", "日程", "schedule", "calendar", "参会", "meeting", "conference", "webinar", "腾讯会议", "zoom", "视频会议"],
        }

        for cat, words in keywords.items():
            if any(w in content_lower for w in words):
                category = cat
                break

        return {
            "category": category,
            "summary": subject[:50] if subject else "无标题",
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

            if email_record.is_processed:
                logger.info(f"邮件已处理: {email_id}")
                return True

            # 解析邮件
            result = self.parse_email(
                email_record.subject or "",
                email_record.body_text or ""
            )

            # 更新邮件记录
            email_record.category = result.get("category", "其他")
            email_record.parsed_at = datetime.now()
            email_record.is_processed = True

            # 创建事件记录（防重复：检查是否已存在该邮件的事件）
            event_data = result.get("event", {})
            logger.info(f"AI解析结果: email_id={email_id}, event_data={event_data}")

            existing_event = db.query(Event).filter(Event.email_id == email_id).first()
            if existing_event:
                logger.info(f"事件已存在，跳过创建: email_id={email_id}")
            else:
                title = event_data.get("title") or email_record.subject or "无标题"

                # 会议专项字段
                organizer = event_data.get("organizer") or email_record.sender or None
                attendees_str = None
                attendees_list = event_data.get("attendees")
                if attendees_list:
                    attendees_str = json.dumps(attendees_list, ensure_ascii=False)

                event = Event(
                    email_id=email_id,
                    event_type=result.get("category", "其他"),
                    title=title,
                    description=event_data.get("description", ""),
                    start_time=self._parse_datetime(event_data.get("event_time")),
                    location=event_data.get("location") or None,
                    organizer=organizer,
                    attendees=attendees_str,
                    meeting_link=event_data.get("meeting_link") or None,
                    rsvp_status="pending",
                )
                db.add(event)
                logger.info(f"创建事件: email_id={email_id}, title={title}, category={result.get('category')}")

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
        """解析时间字符串 - 支持多种格式和中文相对时间"""
        if not time_str:
            return None

        time_str = time_str.strip()
        if not time_str:
            return None

        now = datetime.now()
        current_year = now.year

        # ── 1. 精确格式匹配 ──────────────────────────────────────
        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
            "%m月%d日 %H:%M",
            "%m月%d日 %H:%M:%S",
            "%m月%d日",
            "%m月%d日%H:%M",          # 无空格：10月31日14:00
            "%m月%d日%H:%M:%S",       # 无空格带秒
            "%Y年%m月%d日 %H:%M",
            "%Y年%m月%d日 %H:%M:%S",
            "%Y年%m月%d日",
            "%Y年%m月%d日%H:%M",      # 无空格
            "%Y年%m月%d日%H:%M:%S",   # 无空格带秒
            "%d/%m/%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue

        # ── 2. ISO 格式（带时区） ──────────────────────────────
        try:
            return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        except Exception:
            pass

        # ── 3. 提取日期部分（兜底） ────────────────────────────
        date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', time_str)
        if date_match:
            try:
                return datetime(int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3)))
            except Exception:
                pass

        # ── 4. 中文相对时间解析 ─────────────────────────────────
        # 预处理：统一全角符号和空格
        time_str = time_str.replace('\u3000', ' ')  # 全角空格→半角
        time_str = re.sub(r'\s+', ' ', time_str)     # 合并多余空格
        time_str = re.sub(r'：', ':', time_str)       # 全角冒号→半角

        # 年月日数字提取（用于补全）
        month_day_match = re.search(r'(\d{1,2})月(\d{1,2})日?', time_str)
        time_of_day = re.search(r'([上下午傍晚夜]|中午|凌晨)?\s*(\d{1,2})[:：](\d{2})', time_str)
        has_pm = '下午' in time_str or 'pm' in time_str.lower() or '晚' in time_str
        has_am = '上午' in time_str or 'am' in time_str.lower() or '早' in time_str

        # 相对偏移（天）
        days_offset = 0
        if '后天' in time_str or '明后天' in time_str:
            days_offset = 2
        elif '明天' in time_str or '明早' in time_str or '明日上午' in time_str:
            days_offset = 1
        elif re.search(r'\d+天后', time_str):
            m = re.search(r'(\d+)天后', time_str)
            days_offset = int(m.group(1))
        elif '今天' in time_str:
            days_offset = 0

        # 星期偏移
        weekday_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '日': 7, '天': 7}
        week_match = re.search(r'下?下?周([一二三四五六日天])', time_str)
        if week_match:
            target_weekday = weekday_map[week_match.group(1)]
            days_offset = (7 - now.weekday() + target_weekday) % 7
            if days_offset == 0:
                days_offset = 7

        # 组合基准日期
        base = now + __import__('datetime').timedelta(days=days_offset)

        # 有月日信息时优先使用
        if month_day_match:
            m, d = int(month_day_match.group(1)), int(month_day_match.group(2))
            year = current_year
            # 月份已过则用明年
            if m < now.month or (m == now.month and d < now.day):
                year = current_year + 1
            base = base.replace(year=year, month=m, day=d)

        # 有具体时间时设置时分秒
        if time_of_day:
            hour = int(time_of_day.group(2))
            minute = int(time_of_day.group(3))
            if has_pm and 1 <= hour <= 6:
                hour += 12
            if has_am and hour == 12:
                hour = 0
            base = base.replace(hour=hour, minute=minute, second=0)
        else:
            # 只有日期无时间：设为当天 23:59
            base = base.replace(hour=23, minute=59, second=0)

        # 关键字微调（截止/报名等通常理解为当天结束）
        if '截止' in time_str or '报名截止' in time_str or '申请截止' in time_str:
            base = base.replace(hour=23, minute=59, second=0)
        elif '开始' in time_str or '开始时间' in time_str:
            base = base.replace(hour=9, minute=0, second=0)

        return base


def process_unprocessed_emails() -> Dict:
    """处理所有未处理的邮件"""
    db = SessionLocal()
    result = {"processed": 0, "failed": 0}

    try:
        parser = EmailParser()
        emails = db.query(Email).filter(Email.is_processed == False).all()

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
