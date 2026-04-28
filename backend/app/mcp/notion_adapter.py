"""Notion 适配器 - 邮件摘要自动归档到 Notion (支持 MCP 或直接 API)"""
from datetime import datetime
from typing import Optional, Dict, Any

from app.core.config import settings
from app.agents.tools import Tool, get_registry
from app.logger import Logger

logger = Logger.get("notion_adapter")

# 延迟导入 notion_client，避免启动时就报错
_notion_client = None


def _get_notion_client():
    """延迟加载 notion_client"""
    global _notion_client
    if _notion_client is None:
        try:
            from notion_client import Client
            _notion_client = Client(auth=settings.NOTION_API_KEY)
        except ImportError:
            logger.warning("notion-client 未安装，请运行: pip install notion-client")
            return None
    return _notion_client


def get_notion_mcp_client():
    """获取 Notion MCP 客户端"""
    from app.mcp.client import get_mcp_manager
    mcp_manager = get_mcp_manager()
    return mcp_manager.get_client("notion")


class NotionAdapter:
    """Notion API 适配器 (支持 MCP 和直接 API 两种方式)"""

    def __init__(self):
        self.api_key = settings.NOTION_API_KEY
        self.database_id = settings.NOTION_DATABASE_ID
        self.client = None
        self.mcp_client = None
        self._use_mcp = False

        # 检查 MCP 是否可用
        self.mcp_client = get_notion_mcp_client()
        if self.mcp_client and self.mcp_client._connected:
            self._use_mcp = True
            logger.info("Notion 适配器使用 MCP 方式")
        elif self.api_key:
            # 回退到直接 API
            self.client = _get_notion_client()
            logger.info("Notion 适配器使用直接 API 方式")

    @property
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.database_id and (self._use_mcp or self.client))

    def _get_date_page_id(self, date: str) -> Optional[str]:
        """查询指定日期的页面是否已存在"""
        if not self.is_configured:
            return None

        try:
            if self._use_mcp:
                # 使用 MCP 搜索
                response = self.mcp_client.call_tool("search", {
                    "query": f"{date} 邮件摘要",
                    "filter": {"value": "page", "property": "object"}
                })
                if response and response.get("results"):
                    for page in response["results"]:
                        if page.get("properties", {}).get("日期", {}).get("date", {}).get("start") == date:
                            return page["id"]
            else:
                # 使用直接 API
                response = self.client.databases.query(
                    database_id=self.database_id,
                    filter={
                        "property": "日期",
                        "date": {"equals": date}
                    }
                )
                results = response.get("results", [])
                if results:
                    return results[0]["id"]
        except Exception as e:
            logger.error(f"查询 Notion 日期页面失败: {e}")
        return None

    def create_or_update_daily_summary(self, date: str, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建或更新每日摘要页面"""
        if not self.is_configured:
            return {"success": False, "error": "Notion 未配置"}

        try:
            # 格式化日期
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                date_formatted = date_obj.strftime("%Y年%m月%d日")
            except ValueError:
                date_formatted = date

            # 检查是否已存在
            existing_id = self._get_date_page_id(date)

            # 构建页面内容
            content_blocks = self._build_summary_blocks(summary_data)

            if existing_id:
                # 更新现有页面
                if self._use_mcp:
                    self.mcp_client.call_tool("append_block_children", {
                        "block_id": existing_id,
                        "children": content_blocks
                    })
                else:
                    self.client.blocks.children.append(
                        block_id=existing_id,
                        children=content_blocks
                    )
                page_id = existing_id
                action = "updated"
            else:
                # 创建新页面
                page_properties = {
                    "名称": {"title": [{"text": {"content": f"{date_formatted} 邮件摘要"}}]},
                    "日期": {"date": {"start": date}},
                }

                if self._use_mcp:
                    response = self.mcp_client.call_tool("create_page", {
                        "parent": {"database_id": self.database_id},
                        "properties": page_properties,
                        "children": content_blocks
                    })
                    page_id = response.get("id") if response else None
                else:
                    page = self.client.pages.create(
                        parent={"database_id": self.database_id},
                        properties=page_properties,
                        children=content_blocks
                    )
                    page_id = page["id"]

                action = "created"

            logger.info(f"Notion 页面 {action}: {page_id}")
            return {"success": True, "page_id": page_id, "action": action}

        except Exception as e:
            logger.error(f"创建 Notion 页面失败: {e}")
            return {"success": False, "error": str(e)}

    def _build_summary_blocks(self, summary_data: Dict[str, Any]) -> list:
        """构建 Notion 块内容"""
        blocks = []

        # AI 摘要
        if summary_data.get("summary"):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "📝 AI 摘要"}}]
                }
            })
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": summary_data["summary"]}}]
                }
            })

        # 统计信息
        if summary_data.get("stats"):
            stats = summary_data["stats"]
            stats_text = f"- 邮件数量: {stats.get('emails', 0)}\n"
            stats_text += f"- 提取事件: {stats.get('events', 0)}\n"
            stats_text += f"- 重要事件: {stats.get('important', 0)}"

            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "📊 统计"}}]
                }
            })
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": stats_text}}]
                }
            })

        # 事件列表
        if summary_data.get("events"):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"text": {"content": "📅 事件列表"}}]
                }
            })
            for event in summary_data["events"][:10]:
                event_title = event.get("title", "无标题")
                event_desc = event.get("description", "")
                content = f"{event_title}"
                if event_desc:
                    content += f" - {event_desc}"
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"text": {"content": content}}]
                    }
                })

        return blocks


# 全局单例
_notion_adapter = None


def get_notion_adapter() -> NotionAdapter:
    """获取 Notion 适配器实例"""
    global _notion_adapter
    if _notion_adapter is None:
        _notion_adapter = NotionAdapter()
    return _notion_adapter


def register_notion_tools():
    """注册 Notion 工具到工具注册中心"""
    adapter = get_notion_adapter()
    registry = get_registry()

    # 注册工具（如果未注册）
    if not registry.get("notion_archive_summary"):
        registry.register(Tool(
            name="notion_archive_summary",
            description="将邮件摘要归档到 Notion 数据库（按日期）",
            parameters={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "日期，格式 YYYY-MM-DD，默认今天"},
                    "summary": {"type": "string", "description": "摘要内容"},
                    "stats": {"type": "object", "description": "统计信息"},
                    "events": {"type": "array", "description": "事件列表"}
                },
                "required": ["date", "summary"]
            },
            func=adapter.create_or_update_daily_summary
        ))
