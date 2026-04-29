# 草莓客户管理系统

本地 Mac 桌面客户管理工具，面向主业客户的轻量 CRM 工作台。当前主要读写本机和 Obsidian 里的 Markdown 数据，不提供云端同步、后台自动抓取或无人值守自动导入。

## 当前能力

- 客户总览：读取 `客户数据/` 下的客户 Markdown，展示客户列表、客户详情、当前需求、下一步、沟通记录、待归属审批提醒和相关项目。
- 快速录入：把客户聊天、需求、推进记录等原文整理成结构化表单；保存前需要人工确认，点击 `保存并更新客户` 后才会写入客户资料。
- 截图识别：快速录入页支持粘贴截图、拖拽图片或选择图片，调用 MiniMax 识别并整理到客户表单；钉钉审批导入区也支持审批截图 OCR。
- 字段锁定：快速录入表单里的关键字段可以锁定，避免后续 AI 整理时覆盖已经确认过的客户名、类型、需求、下一步等内容。
- 项目管理：按客户查看项目列表和项目详情，支持筛选客户、年份、状态；品牌项目可从桌面主业项目目录同步，网店 KA 客户可沉淀客户运营跟进，博主可沉淀新功能/新产品推广合作。
- 钉钉审批导入箱：项目管理页支持粘贴审批文字、拖入审批文件、扫描固定导入箱，并先预览归属再写入项目或客户的审批记录。
- 设置页：通过 `路径配置` 集中配置客户数据路径、项目数据路径、主业文件根路径、钉钉审批导入箱；通过 AI 配置维护 MiniMax API Key、模型和 Base URL。

## 本地启动

在项目根目录运行：

```bash
PYTHONPATH=src python3 -m strawberry_customer_management.app
```

如果需要通过环境变量提供 MiniMax Key：

```bash
MINIMAX_API_KEY=你的_key PYTHONPATH=src python3 -m strawberry_customer_management.app
```

MiniMax API Key 也可以在设置页保存到本机用户配置。不要把 Key 写进仓库、README 或提交到 `.env`。

## 常用测试

无界面环境下跑全量测试：

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen python3 -m pytest tests -q
```

这个命令会覆盖当前已有的单元测试和 PySide6 UI 冒烟测试。真实截图识别、真实 MiniMax Key、真实 Obsidian 数据写入仍建议在本机界面里人工确认。

离屏生成四个主要页面的 QA 截图：

```bash
PYTHONPATH=src python3 scripts/render_ui_qa.py
```

默认会把 `OverviewPage / QuickCapturePage / ProjectManagementPage / SettingsPage` 在 `1440x900` 和 `1200x760` 下的截图输出到 `/tmp/strawberry-customer-ui-qa/`，适合做页面改版后的快速复核。

## 数据目录

默认路径来自代码里的 `paths.py`，也可以在设置页改成其他本机目录。

- 客户数据：`/Users/gd/Library/Mobile Documents/iCloud~md~obsidian/Documents/项目管理/草莓客户管理系统--主业/客户数据/`
- 项目数据：`/Users/gd/Library/Mobile Documents/iCloud~md~obsidian/Documents/项目管理/草莓客户管理系统--主业/项目数据/`
- 钉钉审批导入箱：`/Users/gd/Desktop/主业/钉钉审批导入/`
- 钉钉审批待处理目录：`/Users/gd/Desktop/主业/钉钉审批导入/待处理/`
- 桌面主业项目来源：`/Users/gd/Desktop/主业/品牌项目/`
- 本机配置文件：`~/.config/strawberry-customer-management/config.json`

## 钉钉审批导入方式

项目管理页的钉钉审批导入区支持三种入口：

1. 复制钉钉审批列表或审批详情文字，粘贴后点击 `预览归属`。
2. 粘贴、拖拽或选择审批截图，识别完成后会把文字放到导入文本框，再预览归属。
3. 把 `xlsx / csv / txt / md / pdf` 文件拖入导入区，或放到导入箱后点击 `扫描导入箱`。

导入流程是先解析、再预览、最后人工点击 `写入审批`。系统会优先写入匹配到的项目；只匹配到客户时写入客户的待归属审批；归属不清时进入待人工确认口径。拖入文件只会复制到导入箱并生成预览，不会静默写入 Obsidian。

PDF 会优先用 `pypdf` 提取真文本。如果 PDF 是扫描图片，仍需要走截图 OCR 或人工确认。

## MiniMax 配置

- 默认模型：`MiniMax-M2.7`
- 中国大陆 Base URL：`https://api.minimaxi.com/v1`
- Global Base URL：`https://api.minimax.io/v1`
- 快速录入、客户截图识别、钉钉审批截图识别共用设置页里的 MiniMax 配置。
- 如果设置页没有填写 API Key，应用会读取环境变量 `MINIMAX_API_KEY`。

## 使用注意

- 写入客户和项目资料前，先检查客户名、项目名、当前需求、下一步和审批归属。
- 客户类型当前支持 `品牌客户`、`网店KA客户`、`网店店群客户`、`博主`，并且支持多选；如果一个对象既能推广新功能/新产品，又可能自己使用软件，不要二选一，客户类型直接写 `博主 / 网店店群客户` 这类并列身份，二级标签写 `小时达 / 微信 / AI商品图` 这类固定渠道或场景。客户类型和二级标签选项可在设置页维护。
- 字段锁定只影响快速录入页当前整理过程，不等于数据权限或版本锁。
- 钉钉审批导入不是后台自动同步；每次都需要手动粘贴、拖入文件或扫描导入箱，并确认预览后写入。
- 桌面项目同步来源是本机 `主业/品牌项目/` 目录，不会自动创建真实业务文件。

## 本地图片预览规则

- 给用户预览本地图片时，先复制一份到纯英文路径，再用绝对路径写入 Markdown 图片。
- 当前默认预览目录：`/Users/gd/Desktop/customer-icon-options/`
- 避免直接引用中文项目路径或带空格路径下的图片，例如 `主业--草莓客户管理系统/docs/icon-options/`，否则 Codex 桌面预览可能显示为损坏图片。
