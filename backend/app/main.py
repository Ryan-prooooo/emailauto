import sys
import os
import uvicorn
import logging
from pathlib import Path

# 自动设置 PYTHONPATH 和工作目录，确保能正确导入 app 模块和加载 .env
_backend_dir = Path(__file__).resolve().parent
_project_root = _backend_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# 切换到 backend 目录作为工作目录，确保 .env 相对路径正确
os.chdir(_backend_dir)

from app.config import settings
from app.api import app
from app.mcp.client import get_mcp_manager

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG 级别
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info("="*50)
logger.info("启动脚本开始执行...")
logger.info(f"PYTHONPATH: {sys.path}")
logger.info(f"工作目录: {os.getcwd()}")
logger.info(f"环境变量 .env 加载成功")
logger.info(f"IMAP_HOST: {settings.IMAP_HOST}")
logger.info(f"IMAP_PORT: {settings.IMAP_PORT}")
logger.info(f"APP_HOST: {settings.APP_HOST}")
logger.info(f"APP_PORT: {settings.APP_PORT}")
logger.info("="*50)


def main():
    """运行应用"""
    logger.info("启动 QQ邮箱智能生活事件助手...")
    logger.info(f"配置信息:")
    logger.info(f"  - IMAP服务器: {settings.IMAP_HOST}:{settings.IMAP_PORT}")
    logger.info(f"  - 检查间隔: {settings.CHECK_INTERVAL_MINUTES} 分钟")
    logger.info(f"  - 定时推送时间: {settings.SCHEDULED_SEND_HOUR}:{settings.SCHEDULED_SEND_MINUTE}")
    logger.info(f"  - 分类标签: {settings.event_categories_list}")

    # 连接 MCP EML Parser（如果已配置）
    if settings.MCP_EML_PARSER_COMMAND:
        mcp_manager = get_mcp_manager()
        command = settings.MCP_EML_PARSER_COMMAND
        args = settings.MCP_EML_PARSER_ARGS.split(",")
        cwd = settings.MCP_EML_PARSER_CWD or str(Path(__file__).resolve().parent.parent)

        logger.info(f"正在连接 MCP EML Parser...")
        logger.info(f"  - 命令: {command}")
        logger.info(f"  - 参数: {args}")
        logger.info(f"  - 工作目录: {cwd}")

        client = mcp_manager.add_stdio_client(
            name="eml-parser",
            command=command,
            args=args,
            cwd=cwd
        )

        if client:
            logger.info("MCP EML Parser 连接成功!")
            tools = client.list_tools()
            logger.info(f"  - 可用工具数量: {len(tools)}")
            for tool in tools:
                logger.info(f"    * {tool.get('name', 'unknown')}")
        else:
            logger.warning("MCP EML Parser 连接失败，请检查配置")

    uvicorn.run(
        app,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()
