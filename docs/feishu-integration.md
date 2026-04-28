---
name: feishu-integration.md
owner: Tech Lead
audience: Tech Lead + 后端工程师
last_review: 2026-04-19
review_cycle: quarterly
status: planned
related_docs:
  - docs/backend-architecture.md
  - docs/AI_ENGINEERING_GUIDE.md
summary: 飞书（Lark）集成方案，记录可选的飞书机器人、消息推送和日历同步的实现计划和技术细节。
---

# 飞书集成

> **状态**：规划中（Planned）—— 本文档记录集成方案，正式实现前需 Tech Lead 审批。

## 概述

飞书集成是项目的可选扩展功能，通过飞书机器人实现：

- 推送通知到飞书群（替代 QQ 邮箱摘要推送）
- 日历事件同步到飞书日程
- 飞书小程序入口（可选，长期规划）

## 技术方案

### 飞书开放平台配置

1. 创建企业自建应用，获取 `APP_ID` 和 `APP_SECRET`
2. 配置机器人能力
3. 获取群机器人 Webhook 地址（用于消息推送）

### 环境变量

```env
# 飞书配置（可选）
FEISHU_APP_ID=cli_xxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxx
FEISHU_BOT_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
FEISHU_ENABLE=false  # 是否启用飞书集成，默认 false
```

### 模块规划

```
backend/app/
├── feishu/                  # 飞书集成（待实现）
│   ├── __init__.py
│   ├── client.py          # 飞书 API 客户端
│   ├── bot.py             # 机器人消息推送
│   ├── calendar.py         # 日历同步
│   └── config.py          # 飞书配置加载
```

## 功能设计

### 1. 机器人消息推送

支持富文本消息卡片格式：

```python
# 每日摘要卡片示例
{
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {"tag": "plain_text", "content": "📬 每日邮件摘要"},
            "template": "blue"
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": "**今日收到 12 封邮件**"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "🏷️ 3 个重要事件待处理"}}
        ]
    }
}
```

### 2. 事件通知

当检测到重要事件时，发送飞书消息通知：

- 账单到期提醒
- 物流送达通知
- 会议/约会提醒

### 3. 日历同步（长期）

将提取的事件同步到飞书日历：

- 创建日历事件
- 设置提醒时间
- 更新/删除事件

## 实现优先级

| 优先级 | 功能 | 说明 |
| --- | --- | --- |
| P0 | 飞书机器人 Webhook 推送 | 最简单，快速上线 |
| P1 | 富文本消息卡片 | 提升通知可读性 |
| P2 | 事件通知 | 重要事件实时推送 |
| P3 | 日历同步 | 长期规划 |

## 注意事项

- 飞书集成默认关闭（`FEISHU_ENABLE=false`），用户需主动配置
- Webhook 推送无需用户授权，但消息卡片需要企业自建应用
- 日历同步需要飞书开放平台应用权限
- 不替代 QQ 邮箱功能，作为可选的补充通知渠道

## 相关文档

- [docs/backend-architecture.md](./backend-architecture.md) - 后端架构
- [docs/AI_ENGINEERING_GUIDE.md](./AI_ENGINEERING_GUIDE.md) - 文档索引
- [飞书开放平台文档](https://open.feishu.cn/document/home/index)（外部）
