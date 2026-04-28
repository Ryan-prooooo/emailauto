"""
统一日志模块 - 单例模式
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class Logger:
    """单例日志管理器"""
    _instance: Optional['Logger'] = None
    _initialized = False

    def __init__(self):
        if Logger._initialized:
            return
        Logger._initialized = True

        self._log_dir = Path(__file__).resolve().parent.parent / "logs"
        self._log_dir.mkdir(exist_ok=True)

        self._log_file = self._log_dir / f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        self._root_logger = logging.getLogger("app")
        self._root_logger.setLevel(logging.DEBUG)
        self._root_logger.handlers.clear()

        file_handler = logging.FileHandler(self._log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        ))

        self._root_logger.addHandler(file_handler)
        self._root_logger.addHandler(console_handler)

    @classmethod
    def get(cls, name: str = "app") -> logging.Logger:
        """获取指定名称的日志器"""
        if cls._instance is None:
            cls._instance = Logger()
        return logging.getLogger(f"app.{name}")

    @classmethod
    def get_root(cls) -> logging.Logger:
        """获取根日志器"""
        if cls._instance is None:
            cls._instance = Logger()
        return cls._instance._root_logger

    @classmethod
    def set_level(cls, level: int, name: str = None):
        """设置日志级别"""
        if cls._instance is None:
            cls._instance = Logger()
        if name:
            logging.getLogger(f"app.{name}").setLevel(level)
        else:
            cls._instance._root_logger.setLevel(level)

    @property
    def log_file(self) -> Path:
        return self._log_file

    @classmethod
    def cleanup_old_logs(cls, days: int = 3):
        """清理旧日志文件，保留最近 N 天"""
        if cls._instance is None:
            cls._instance = Logger()
        log_dir = cls._instance._log_dir
        if not log_dir.exists():
            return
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        for f in log_dir.glob("*.log"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    f.unlink()
                    removed += 1
            except Exception:
                pass
        if removed > 0:
            cls.get("logger").info(f"已清理 {removed} 个旧日志文件")


def getLogger(name: str = "app") -> logging.Logger:
    """快捷获取日志器"""
    return Logger.get(name)


# 便捷函数
def debug(msg: str, *args, **kwargs):
    Logger.get().debug(msg, *args, **kwargs)

def info(msg: str, *args, **kwargs):
    Logger.get().info(msg, *args, **kwargs)

def warning(msg: str, *args, **kwargs):
    Logger.get().warning(msg, *args, **kwargs)

def error(msg: str, *args, **kwargs):
    Logger.get().error(msg, *args, **kwargs)

def exception(msg: str, *args, **kwargs):
    Logger.get().exception(msg, *args, **kwargs)


__all__ = ['Logger', 'getLogger', 'debug', 'info', 'warning', 'error', 'exception']
