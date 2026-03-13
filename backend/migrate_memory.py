"""数据库迁移脚本 - 为 ChatMessage 添加记忆类型字段"""
import sys
sys.path.insert(0, '.')

import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

from sqlalchemy import inspect, text
from app.db.database import engine, Base, init_db

def migrate():
    """创建表并添加新字段"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("Database tables:", tables)
    
    # 初始化数据库（创建所有表）
    print("\nCreating missing tables...")
    init_db()
    print("OK - Tables created")
    
    # 检查 chat_messages 表
    if 'chat_messages' not in tables:
        tables = inspector.get_table_names()
    
    if 'chat_messages' not in tables:
        print("ERROR: chat_messages table still not exists")
        return
    
    columns = [col['name'] for col in inspector.get_columns('chat_messages')]
    print("\nCurrent chat_messages columns:", columns)
    
    with engine.connect() as conn:
        # 添加 memory_type 字段
        if 'memory_type' not in columns:
            conn.execute(text("ALTER TABLE chat_messages ADD COLUMN memory_type VARCHAR(20) DEFAULT 'recent'"))
            conn.commit()
            print("+ Added memory_type column")
        else:
            print("+ memory_type column already exists")
        
        # 添加 summary 字段
        if 'summary' not in columns:
            conn.execute(text("ALTER TABLE chat_messages ADD COLUMN summary TEXT"))
            conn.commit()
            print("+ Added summary column")
        else:
            print("+ summary column already exists")
    
    # 验证
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('chat_messages')]
    print("\nUpdated chat_messages columns:", columns)

if __name__ == "__main__":
    migrate()
    print("\nDone! Database migration completed!")
