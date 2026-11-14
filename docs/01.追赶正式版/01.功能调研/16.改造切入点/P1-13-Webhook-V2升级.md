# P1-13 Webhook V2 升级（事件树 14 组+观测 UI+项目级接线）· 改造切入点 Implementation Brief

> 批次 3 · 任务 A（R5）· P1 组 ｜ 基线 main `41af2176d7` ｜ 编号按本批次指令（20 号路线图无独立条目——本条为本批次新增立项；F-ID：AP-03/AP-04/AP-05 邻域+IG-12；50 号 D-05、62 号 D-03/D-05/D-06）
> 模块依据：62.集成导入深测/对比.md（Webhook 深测全量）；50.集成生态/对比.md；17 号考古对象 8（ProjectWebhook 模型已加未接线）

## 1. 目标与云端形态

工作区 Webhook 从 V1（5 布尔事件）升级到云端 V2 形态（62 号 §1.3/§3.5 实测）：

- **事件全集**：**V1 scopes（deprecated，5 组）**：Projects/Cycles/Work items/Modules/Work item comments；**V2 scopes（14 组树）**：Projects(4)/Modules(4)/Cycles(4)/Milestones(3，无 Archived)/Pages(4)/Page comments(3)/Work items(4)/Work item comments(3)/Work item links(3)/Work item votes(2)/Work item attachments(3)/Work item relations(2)/Work item dependencies(2)/Work item page links(2)——子事件 Created/Updated/Archived/Deleted 按组增减（62 号 4.4 全枚举）。
- **事件选择器**：父组复选框+子事件树形复选（缩进树）；**Work item v2 filters**（「Filter which work items trigger this webhook. Applies to work item v2 events only.」+内嵌 Basic/PQL 筛选器——依赖 P1-7，可后置）。
- **详情/编辑页**：`/settings/webhooks/<uuid>/`：头部「禁用 Webhook」toggle+**Configuration/Activity 双 tab**；Configuration=标题/Payload URL/事件树/v2 filters/**密钥+重新生成密钥**/取消/更新。
- **Activity 观测**：统计卡（Total deliveries/Successful/Failed/Success rate）+Recent deliveries 表（Events/Status/Response time/Event time，Failed=danger 徽标）+Prev/Next 翻页；投递行**无展开无重试**（62 号 D-06：观测止步于表格行——就现状对齐）。
- **列表列**：名称/状态/Events（数字）/Success rate/Last triggered（云端有数据态表格；CE 无数据态仅空态）。
- **项目级 webhook（IG-12）**：CE 仅工作区级；云端项目设置内有 webhook（50 号实测修正 #2：CE 项目级不存在）。
- 深测文档：`docs/01.追赶正式版/01.功能调研/62.集成导入深测/对比.md`（§1.3/§3.5/§4.4）；`50.集成生态/对比.md`。

## 2. CE 现状（已验证）

- **模型层三件全在**：`apps/api/plane/db/models/webhook.py:34` `Webhook`（事件字段为 5 个 BooleanField：:39 project 等——**V1 5 布尔形态的实体层**）、`:65` `WebhookLog`（event_type CharField 等）、`:94` `ProjectWebhook`（webhook FK+unique(project,webhook)+db_table project_webhooks :108——**2025-09-15 `116c8118ab` 已进 main 但零接线**：无路由无 UI 无投递逻辑，17 号对象 8「模型就绪，挂路由即可」）。
- **投递任务**：`apps/api/plane/bgtasks/webhook_task.py:59-67` 事件→serializer/model 映射表（8 类：project/issue/cycle/module/cycle_issue/module_issue/issue_comment/intake_issue）；`:93` save_webhook_log；`:242` webhook_send_task（:297 secret_key HMAC 签名）；`:393` webhook_activity（活动分发入口）；`:172` 投递失败自动停用+邮件通知（send_webhook_deactivation_email）。
- **API**：`apps/api/plane/app/urls/webhook.py:15-30`——webhooks CRUD+:22 regenerate（WebhookSecretRegenerateEndpoint，views/webhook/base.py:114）+:30 webhook-logs（WebhookLogsEndpoint，base.py:124）——**logs API 已实现，无消费方**。
- **前端**：`packages/types/src/webhook.ts:7-20` IWebhook 5 布尔事件+TWebhookEventTypes="all"|"individual"；`apps/web/components/web-hooks/form/event-types.tsx:18` 单选 all/individual 后展开 5 复选框；**无 logs/Activity 组件**（grep 零命中）；列表页无 Success rate/Last triggered 列。
- **考古引用**：17 号对象 8——ProjectWebhook 非被删而是从未接线（★★★ 模型就绪）；62 号 D-03：CE 事件全集=云端 V1 的 5 组（分叉点即 V1 时代）；云端 V1 已标 deprecated=官方正迁移 V2，CE 追赶直达 V2 结构（兼容 V1 存量）。

## 3. 后端改动面

1. **事件模型升级（1 迁移）**：Webhook 加 `events` JSONField（结构 `{"work_items": ["created","updated"], "pages": ["created",…]}` 子事件树）或规范化 `WebhookEvent` 子表——**建议 JSONField+应用层常量**（对齐 18 号域 03 对 handler 的「字符串不设 choices」策略，官方事件组扩展免迁移）；5 布尔字段保留读写兼容（V1 存量双写：布尔 true=该组全部子事件）。Milestones 组：CE 无 Milestone 实体（17 号对象 11b）——枚举预留、运行时空实现。
2. **投递改造**：`webhook_task.py` 扩展：a) 事件常量表（14 组×子事件→event_type 字符串如 `work_item.created`）；b) 各新实体的信号挂接（page/comment/link/vote/attachment/relation/dependency 的 CRUD 触发点——`webhook_activity` 分发处按事件常量路由到对应 serializer）；c) 投递时合并**项目级订阅**（ProjectWebhook 查询加入 receiver 集）；d) v2 filters 钩子（有 filter 配置时对 work item 事件先过 issue_filters——P1-7 落地后接 PQL）。
3. **项目级 webhook 接线（IG-12）**：`app/urls/` 挂 `/api/workspaces/{slug}/projects/{id}/webhooks/` 路由（复用 WebhookViewSet 模式，17 号评估）；ProjectWebhook 关联创建（项目设置内建 webhook=建 Webhook+ProjectWebhook 绑定）；投递面=该项目的实体事件。
4. **观测 API 增强**：WebhookLogsEndpoint 已可查——补聚合统计端点（Total/Successful/Failed/Success rate+响应时间）与 Events/Last triggered 列数据（现列表端点补聚合注解）。
5. **新路由隔离**：V2 端点与 logs 统计放独立 urls 模块，减少对既有 webhook.py urls 的 diff。

## 4. 前端改动面（apps/web）

1. **事件选择器重构**：`event-types.tsx` 从「all/individual 单选+5 复选」改为 **V1 deprecated 分组+V2 14 组树形复选**（父组框+子事件缩进树——62 号 3.5 步 6 形态：子事件为自绘复选）；类型层 `IWebhook` 扩 events 树结构。
2. **详情页双 tab**：Configuration（既有表单+密钥+重新生成密钥按钮——regenerate API 已在）+Activity（统计卡×4+Recent deliveries 表：Events/Status 徽标/Response time/Event time+Prev/Next 翻页+空态 No logs）——消费 webhook-logs API+新统计端点。
3. **列表升级**：webhooks-list.tsx 加 Events 数字/Success rate/Last triggered 列。
4. **项目级 webhook UI**：项目设置 Developer 分组加 Webhooks 项+复用工作区组件（workspaceSlug 参数化）。
5. **v2 filters UI**：内嵌筛选器（先 Basic；PQL tab 待 P1-7）——可后置为二期增量。
6. i18n：webhooks 命名空间扩展（V2 事件组名/统计卡/空态）。

## 5. 测试面

- 后端 pytest：14 组事件触发矩阵（每组至少 1 子事件端到端投递+log 记录）、V1 存量兼容（旧 5 布尔仍投递）、HMAC 签名+secret 不回读（#9382 上游修复语义保持）、失败停用+通知邮件、项目级订阅合并投递、logs 分页与统计聚合、Milestones 组空实现不报错。
- 前端：事件树状态联动（父组勾选=全子事件）、双 tab、统计卡数字。
- 集成：对照 62 号 §3.5 全流程（webhook.site 假 URL→触发→Failed 行+统计）。

## 6. 依赖与并行性

- **前置**：无硬依赖。软依赖：**P1-7（PQL）**→v2 filters 的 PQL tab；**P1-2/P0-2**（Pages 实体投递面更完整——page 事件依赖页面功能活跃，但 Page 模型/事件本体 CE 已有）；P1-3（集成安装即建 webhook 的自动注册可复用本条事件体系）。
- **可并行**：后端事件表/投递改造与前端事件树/Activity UI 并行；项目级接线独立可并行。
- **被依赖**：P1-3（安装联动）；审计日志（P2-5）可复用 webhook_activity 分发面。

## 7. 估算

| 项       | 量                                                                                                   | 依据                                                                            |
| -------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| 文件数   | 后端 ~12（事件常量表+投递扩展+项目级 urls+统计端点+迁移）、前端 ~10（事件树+双 tab+列表+项目级入口） | 62 号 4.4 全枚举+17 号对象 8 评估                                               |
| model 数 | 0-1 新表（建议 events JSONField 免新表；若规范化则+WebhookEvent 表）                                 |                                                                                 |
| 迁移数   | 1（webhook 表加 events JSON+存量布尔回填）                                                           |                                                                                 |
| 后端人天 | 12                                                                                                   | 14 组×子事件挂接与 serializer 路由 6+项目级接线 2+统计聚合 2+V1 兼容/签名安全 2 |
| 前端人天 | 7                                                                                                    | 事件树 2.5+Activity 双 tab 2.5+列表列/项目级入口 2                              |
| **合计** | **19 人天**                                                                                          | L 段位（62 号 D-03 M+D-05 M+IG-12+观测 UI 合并）                                |

## 8. 上游冲突面（风险：中）

- **`webhook_task.py` 是官方近期触碰过的文件**（#9232 webhook payload 加 workspace_slug、#9382 secret 不回读均为 5-8 月提交）——投递逻辑扩展需在其分发点**外围加路由层**而非改写函数体；独立 `automation 事件常量文件+dispatch wrapper` 减小 diff。
- `db/models/webhook.py` 加字段=低-中（模型近期刚被动过：ProjectWebhook 2025-09）——加列向后兼容。
- 前端 web-hooks 组件目录长期未动（仅空态/表单）=低。
- 迁移 lockfile：官方迁移编号持续推进（17 号 §3.3），合并后立即 makemigrations 刷 lockfile。
- 官方先做掉风险：低（17 号判定 webhook 域无 M1 交叠；但 V1→V2 是官方自身演进方向，**留意官方开源侧未来自行落地 V2 的可能**——先到先得，结构对齐 62 号实测枚举可降低后续冲突）。

## 9. 风险与未知

1. **V2 事件 payload schema 未抓包**（62 号只到假 URL 投递，未见 payload 内容）——payload 结构自定（参照既有 webhook payload 模式+workspace_slug #9232）；云端 V1 标 deprecated 的过渡期语义（V1/V2 双订阅）以双写兼容。
2. **Activity 统计口径疑点**（62 号待验证 1：1 条 Failed 后统计仍 0）——CE 按 log 全量聚合实现（语义更合理），不逐字仿疑似 bug。
3. **ProjectWebhook 的产品形态未实测**（CE 项目设置无入口、云端项目级 webhook 由 50 号修正 #2 确认云端有）——表单复用工作区组件，事件面一致。
4. Milestones/Page votes/page links 等组在 CE 的实体部分缺失（Milestone 无、page link 无）——枚举预留空实现，实体落地（P2-15 等）后点亮。
5. 投递行无展开/无重试为云端现状（62 号 D-6 判 S 对齐）——CE 不自加重试按钮（可作内部任务层重试但不暴露 UI）。

## 10. 验收用例（对照 62 号 §3.5）

| #   | Given                        | When                                    | Then                                                                         |
| --- | ---------------------------- | --------------------------------------- | ---------------------------------------------------------------------------- |
| 1   | 工作区 Webhooks 页           | 创建 webhook（URL=webhook.site 假地址） | 创建成功；列表行=状态活动/Events 数/Success rate/Last triggered 列可见       |
| 2   | 详情页                       | 打开                                    | Configuration/Activity 双 tab；Configuration 含密钥+重新生成密钥             |
| 3   | Configuration                | 勾 V2「Work items→Created」树形项       | 更新成功；事件树状态持久                                                     |
| 4   | 建「调研-webhook投递测试项」 | 触发 created                            | Activity 出现投递行：Work item Created/Failed/响应耗时/时间戳（danger 徽标） |
| 5   | 换真实接收端                 | 触发事件                                | payload 含 workspace_slug+事件数据；HMAC 签名头存在                          |
| 6   | Activity                     | 查看统计卡                              | Total/Successful/Failed/Success rate 按日志全量聚合；Prev/Next 翻页          |
| 7   | 连续失败                     | 达到停用阈值                            | webhook 自动禁用+管理员收停用邮件（既有 :172 行为不回退）                    |
| 8   | 项目设置                     | Developer 分组                          | Webhooks 项出现；项目级创建后仅该项目事件投递到该 URL                        |
| 9   | 同一 webhook 绑定两项目      | 项目内事件                              | 投递合并去重（一 URL 一投递）                                                |
| 10  | V1 存量 webhook（布尔形态）  | 触发 issue created                      | 兼容投递不中断（双写期）                                                     |
