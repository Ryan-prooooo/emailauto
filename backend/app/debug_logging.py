"""
诊断日志模块 - 记录完整的调用链到日志文件
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

# 日志目录
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# 日志文件
_LOG_FILE = _LOG_DIR / f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def setup_debug_logging(name: str = None) -> logging.Logger:
    """
    创建带文件输出的调试日志器
    
    Args:
        name: 日志器名称，默认使用调用者模块名
    
    Returns:
        配置好的日志器
    """
    logger = logging.getLogger(name or __name__)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # 文件 Handler - 记录所有调试信息
    file_handler = logging.FileHandler(_LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    ))
    
    # 控制台 Handler - 记录 INFO 及以上
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def log_call_chain(logger: logging.Logger, func_name: str, *args, **kwargs):
    """
    记录函数调用链
    
    Args:
        logger: 日志器
        func_name: 函数名称
        *args: 位置参数
        **kwargs: 关键字参数
    """
    # 过滤敏感参数
    safe_args = []
    for arg in args:
        if isinstance(arg, str) and len(arg) > 100:
            safe_args.append(f"<str: {len(arg)} chars>")
        else:
            safe_args.append(repr(arg))
    
    safe_kwargs = {}
    for k, v in kwargs.items():
        if k.lower() in ('password', 'token', 'secret', 'auth'):
            safe_kwargs[k] = "<redacted>"
        elif isinstance(v, str) and len(v) > 100:
            safe_kwargs[k] = f"<str: {len(v)} chars>"
        else:
            safe_kwargs[k] = repr(v)
    
    logger.debug(f">>> CALL: {func_name}({', '.join(safe_args)}, {safe_kwargs})")


def log_result(logger: logging.Logger, func_name: str, result, success: bool = True):
    """
    记录函数返回结果
    
    Args:
        logger: 日志器
        func_name: 函数名称
        result: 返回结果
        success: 是否成功
    """
    result_str = repr(result)
    if len(result_str) > 200:
        result_str = f"<result: {len(result_str)} chars>"
    
    level = logging.DEBUG if success else logging.ERROR
    logger.log(level, f"<<< RETURN: {func_name} -> {result_str}")


def log_exception(logger: logging.Logger, func_name: str, exc: Exception):
    """
    记录异常
    
    Args:
        logger: 日志器
        func_name: 函数名称
        exc: 异常对象
    """
    logger.exception(f"!!! EXCEPTION in {func_name}: {type(exc).__name__}: {exc}")


# 默认日志器
default_logger = setup_debug_logging("app")

__all__ = [
    'setup_debug_logging',
    'log_call_chain', 
    'log_result',
    'log_exception',
    'default_logger',
    '_LOG_FILE'
]
