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

## 测试

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen python3 -m pytest tests -q
```

## 默认数据源

- 客户管理根路径：`/Users/gd/Library/Mobile Documents/iCloud~md~obsidian/Documents/主业助手/客户管理/`
- 主业文件根路径：`/Users/gd/Desktop/主业`

