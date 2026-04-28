"""
数据库迁移脚本 - 为聊天消息添加记忆字段（PostgreSQL 版本）
"""
from sqlalchemy import text
from app.db.database import engine
from app.logger import Logger

logger = Logger.get("db_migrate")


def _column_exists(conn, table: str, column: str) -> bool:
    """检查 PostgreSQL 表中是否存在指定列"""
    result = conn.execute(
        text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = :table AND column_name = :column
        """),
        {"table": table, "column": column}
    )
    return result.fetchone() is not None


def migrate_add_memory_fields():
    """添加记忆相关字段到 chat_messages 表"""
    try:
        with engine.connect() as conn:
            migrations_applied = []

            # 添加 memory_type 字段
            if not _column_exists(conn, "chat_messages", "memory_type"):
                conn.execute(text(
                    "ALTER TABLE chat_messages ADD COLUMN memory_type VARCHAR(20) DEFAULT 'recent'"
                ))
                migrations_applied.append("memory_type")

            # 添加 summary 字段
            if not _column_exists(conn, "chat_messages", "summary"):
                conn.execute(text(
                    "ALTER TABLE chat_messages ADD COLUMN summary TEXT"
                ))
                migrations_applied.append("summary")

            if migrations_applied:
                conn.commit()
                logger.info(f"数据库迁移完成: 添加字段 {migrations_applied}")
            else:
                logger.info("数据库迁移检查: 无需添加新字段")
    except Exception as e:
        logger.warning(f"数据库迁移跳过: {e}")


def run_migrations():
    """运行所有迁移"""
    migrate_add_memory_fields()
