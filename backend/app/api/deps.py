from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from app.db import get_db, init_db
from app.logger import Logger

# 统一使用 Asia/Shanghai 时区（东八区），与邮件 received_at 业务语义保持一致
SHANGHAI_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc


logger = Logger.get("api")
logger.info(f"日志文件: {Logger._instance._log_file}")


def serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
    """将 datetime 转为 Asia/Shanghai 时区的可读字符串，前端直接展示无需额外时区处理。"""
    if dt is None:
        return None
    # 统一转到东八区
    if dt.tzinfo is None:
        # naive datetime 当作 UTC 处理，再转到东八区（+8小时）
        dt = dt.replace(tzinfo=UTC_TZ)
    dt = dt.astimezone(SHANGHAI_TZ)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

