import sys
import os
import uvicorn
from pathlib import Path

from app.config import settings
from app.api import app
from app.mcp.client import get_mcp_manager
from app.logger import Logger

# 配置日志
logger = Logger.get("main")
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

    # 连接 MCP Notion（如果已配置）
    if settings.MCP_NOTION_COMMAND and settings.NOTION_API_KEY and settings.NOTION_DATABASE_ID:
        mcp_manager = get_mcp_manager()
        command = settings.MCP_NOTION_COMMAND
        args = settings.MCP_NOTION_ARGS.split(",")
        cwd = settings.MCP_NOTION_CWD or str(Path(__file__).resolve().parent.parent)

        # 传递 NOTION_API_KEY 作为环境变量
        notion_env = {
            "NOTION_API_KEY": settings.NOTION_API_KEY
        }

        logger.info(f"正在连接 MCP Notion...")
        logger.info(f"  - 命令: {command}")
        logger.info(f"  - 参数: {args}")
        logger.info(f"  - 工作目录: {cwd}")
        logger.info(f"  - 数据库ID: {settings.NOTION_DATABASE_ID[:8]}...")

        client = mcp_manager.add_stdio_client(
            name="notion",
            command=command,
            args=args,
            cwd=cwd,
            env=notion_env
        )

        if client:
            logger.info("MCP Notion 连接成功!")
            tools = client.list_tools()
            logger.info(f"  - 可用工具数量: {len(tools)}")
            for tool in tools:
                logger.info(f"    * {tool.get('name', 'unknown')}")
        else:
            logger.warning("MCP Notion 连接失败，请检查配置")

    # 注册 Notion 工具（如果已配置 MCP 或直接 API）
    if settings.NOTION_API_KEY and settings.NOTION_DATABASE_ID:
        try:
            from app.mcp.notion_adapter import register_notion_tools, get_notion_adapter
            register_notion_tools()
            notion = get_notion_adapter()
            if notion.is_configured:
                logger.info("Notion 集成已配置并就绪")
                logger.info(f"  - 数据库ID: {settings.NOTION_DATABASE_ID[:8]}...")
                logger.info(f"  - 连接方式: {'MCP' if notion._use_mcp else '直接 API'}")
            else:
                logger.warning("Notion 配置不完整，请检查 API_KEY 和 DATABASE_ID")
        except ImportError:
            logger.warning("notion-client 未安装，跳过 Notion 集成。安装命令: pip install notion-client")
        except Exception as e:
            logger.warning(f"Notion 初始化失败: {e}")

    uvicorn.run(
        app,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()
