"""
配置入口：从 app.core.config 统一导出，保持原有 from app.config import settings 可用
"""
from app.core.config import settings

__all__ = ["settings"]
