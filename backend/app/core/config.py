"""
配置管理 - 从 .env 加载配置
QQ邮箱 IMAP/SMTP、DeepSeek API、调度间隔等
"""
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env 固定从 backend 目录加载，避免因启动目录不同而读不到配置
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH) if _ENV_PATH.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # QQ邮箱配置 (plan: QQ_EMAIL, QQ_IMAP_*, QQ_SMTP_*, QQ_AUTH_CODE)
    QQ_EMAIL: str = ""
    QQ_IMAP_HOST: str = "imap.qq.com"
    QQ_IMAP_PORT: int = 993
    QQ_SMTP_HOST: str = "smtp.qq.com"
    QQ_SMTP_PORT: int = 465
    QQ_AUTH_CODE: str = ""
    # 兼容旧变量名（QQ 授权码）
    QQ_PASSWORD: str = ""

    # 兼容现有代码的 IMAP 命名（与 QQ_IMAP_* 一致）
    IMAP_HOST: str = "imap.qq.com"
    IMAP_PORT: int = 993

    # DeepSeek 配置
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.deepseek.com/v1"
    OPENAI_MODEL: str = "deepseek-chat"

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./email_assistant.db"

    # 应用配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # 调度 / 同步配置 (plan: SYNC_INTERVAL_MINUTES)
    SYNC_INTERVAL_MINUTES: int = 15
    CHECK_INTERVAL_MINUTES: int = 5  # 邮件检查间隔，兼容现有逻辑

    # 定时推送配置
    SCHEDULED_SEND_HOUR: int = 9
    SCHEDULED_SEND_MINUTE: int = 0

    # 智能分类标签
    EVENT_CATEGORIES: str = "购物,账单,物流,社交,工作,订阅,其他"

    # MCP EML Parser 配置（Stdio 方式）
    MCP_EML_PARSER_COMMAND: str = "uv"
    MCP_EML_PARSER_ARGS: str = "run,eml_parser_mcp.py"
    MCP_EML_PARSER_CWD: str = ""

    @property
    def qq_password_or_auth(self) -> str:
        """优先使用 QQ_AUTH_CODE，否则回退到 QQ_PASSWORD（兼容旧配置）"""
        return self.QQ_AUTH_CODE or self.QQ_PASSWORD

    @property
    def event_categories_list(self) -> List[str]:
        return [cat.strip() for cat in self.EVENT_CATEGORIES.split(",")]


settings = Settings()
