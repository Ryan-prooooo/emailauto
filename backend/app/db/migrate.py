"""
数据库迁移脚本 - 为聊天消息添加记忆字段
"""
from sqlalchemy import text
from app.db.database import engine
from app.logger import Logger

logger = Logger.get("db_migrate")


def migrate_add_memory_fields():
    """添加记忆相关字段到 chat_messages 表"""
    with engine.connect() as conn:
        # 获取表结构
        result = conn.execute(text("PRAGMA table_info(chat_messages)"))
        columns = {row[1] for row in result}

        migrations_applied = []

        # 添加 memory_type 字段
        if "memory_type" not in columns:
            conn.execute(text(
                "ALTER TABLE chat_messages ADD COLUMN memory_type VARCHAR(20) DEFAULT 'recent'"
            ))
            migrations_applied.append("memory_type")

        # 添加 summary 字段
        if "summary" not in columns:
            conn.execute(text(
                "ALTER TABLE chat_messages ADD COLUMN summary TEXT"
            ))
            migrations_applied.append("summary")

        if migrations_applied:
            conn.commit()
            logger.info(f"数据库迁移完成: 添加字段 {migrations_applied}")
        else:
            logger.info("数据库迁移检查: 无需添加新字段")


def run_migrations():
    """运行所有迁移"""
    migrate_add_memory_fields()
