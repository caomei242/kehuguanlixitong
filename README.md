# 草莓客户管理系统

本地 Mac 桌面客户管理工具，面向主业客户的轻量 CRM 工作台。

## 一期目标

- 读取和更新 Obsidian `主业助手/客户管理/` 下的 Markdown
- 展示客户总览、客户详情
- 结构化快速录入新客户和新沟通沉淀
- 打包为本地可点击启动的 `.app`

## 本地启动

```bash
PYTHONPATH=src python3 -m strawberry_customer_management.app
```

## AI 快速整理

- 快速录入页支持先粘贴客户聊天、需求或推进原文，再点击 `AI 整理到表单`。
- AI 只负责填充表单字段；写入 Obsidian 前仍需要人工确认并点击 `保存并更新客户`。
- 当前接入 MiniMax OpenAI 兼容接口，默认 Base URL：`https://api.minimax.io/v1`
- MiniMax API Key 只保存在本机用户配置，或通过环境变量 `MINIMAX_API_KEY` 读取；不要写入仓库、README 或 `.env` 提交。

## 测试

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen python3 -m pytest tests -q
```

## 默认数据源

- 客户管理根路径：`/Users/gd/Library/Mobile Documents/iCloud~md~obsidian/Documents/主业助手/客户管理/`
- 主业文件根路径：`/Users/gd/Desktop/主业`

## 本地图片预览规则

- 给用户预览本地图片时，先复制一份到纯英文路径，再用绝对路径写入 Markdown 图片。
- 当前默认预览目录：`/Users/gd/Desktop/customer-icon-options/`
- 避免直接引用中文项目路径或带空格路径下的图片，例如 `主业--草莓客户管理系统/docs/icon-options/`，否则 Codex 桌面预览可能显示为损坏图片。
