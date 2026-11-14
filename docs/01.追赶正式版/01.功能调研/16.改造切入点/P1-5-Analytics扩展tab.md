# P1-5 Analytics 扩展 tab（2→7）· 改造切入点 Implementation Brief

> 批次 3 · 任务 A（R5）· P1 组 ｜ 基线 main `41af2176d7` ｜ 编号按本批次指令（对应 20 号路线图 5.2 节「P1-4 Analytics 扩展 tab」；F-ID：AN-02）
> 模块依据：40.Insights与仪表盘/对比.md（D-06）；65 号补充；**17 号考古对象 10（端点已在，扩展点现成）**

## 1. 目标与云端形态

工作区 Analytics 固定页从 2 tab 扩到云端 7 tab（40 号实测）：

- **tab 全集**：概览 / 项目 / 用户 / 工作项 / 周期 / 模块 / 收集（Intake）；顶部保留「所有项目」范围选择（CE 已有，D-08 无差异）。
- **概览**：KPI（用户/管理员/成员/访客/项目/工作项/周期/Intake 总数）+项目洞察+活跃项目；CE 概览已有 KPI+**雷达图（反超项，保留）**+项目洞察+活跃项目。
- **项目/用户/周期/模块/收集** 五个新 tab 的图表形态：云端实测文档 40 号未逐 tab 展开图表细节（仅 tab 集与概览/工作项已录）；工作项 tab 形态两版基本一致（KPI+已创建 vs 已解决+自定义洞察透视+按项目状态汇总表，均带 CSV 导出）。
- 深测文档：`docs/01.追赶正式版/01.功能调研/40.Insights与仪表盘/对比.md`；59 号 §3.5（云端 7 tab 实拍 cloud-analytics-workitems-refresh）。

## 2. CE 现状（已验证）

- **端点扩展点现成（★★★ 增量开发）**：`apps/api/plane/app/views/analytic/advance.py:109-121` —— `AdvanceAnalyticsEndpoint.get()` 的 tab 分支仅 `overview`/`work-items`，其余返回 400 `"Invalid tab"`；配套 `AdvanceAnalyticsStatsEndpoint`、`AdvanceAnalyticsChartEndpoint`（同文件）+ `apps/api/plane/utils/build_chart.py`（205 行）+ `utils/date_utils.py`（197 行）。路由三条已在：`app/urls/analytic.py`（workspaces `<slug>/advance-analytics/{,stats,charts}/` + project 级三条）。
- **前端 tab 注册点**：`packages/types/src/analytics.ts:40` `TAnalyticsTabsBase = "overview" | "work-items"`；`apps/web/components/analytics/tabs.tsx`、`use-analytics-tabs.tsx`、`analytics-wrapper.tsx`、`insight-card.tsx`、`total-insights.tsx`（组件齐备，仅枚举与 tab 内容待扩）。
- **考古引用（17 号对象 10）**：advance-analytics 端点 2025-05 `b435ceedfc`（#6973）已建（397 行），前端 `75d81f9e95`（#7005）；官方是在同一端点上**按套餐收窄 tab**（`--all` 无被删代码）——扩展=加分支，无历史包袱。
- 数据面现状：CE 周期/模块/Intake 数据模型完整（Cycle/Module/IntakeIssue 均在），聚合查询可直接写。

## 3. 后端改动面

1. `advance.py` 三个端点各加 5 个 tab 分支（project/user/cycle/module/intake），每分支一个聚合函数；复用 `get_filtered_counts`/`build_chart` 模式：
   - **项目**：按项目维度的 KPI（工作项数/成员数/周期数）+项目对比图；
   - **用户**：按成员的工作项分布（已分配/已创建/已完成）——注意 guest/成员角色过滤（2026-10 安全波次把 workspace analytics 收口 `ROLE.ADMIN, ROLE.MEMBER`（advance.py:109 `@allow_permission` 已限），用户 tab 数据按权限决定是否全员可见）；
   - **周期**：周期进度/完成度聚合（复用 `apps/web/components/cycles/analytics-sidebar` 对应的后端 `CycleAnalyticsViewSet` 查询模式）；
   - **模块**：模块进度聚合（module.py 的 progress 计算复用）；
   - **收集**：Intake 维度（pending/accepted/rejected 计数、按来源分布——65 号 CSV 列无 intake 字段，按 IntakeIssue 状态聚合）。
2. 类型/序列化：新 tab 返回结构沿用 overview/work-items 的 dict 形状；图表数据走 charts 子端点。
3. 无新表、无迁移（纯查询聚合）。

## 4. 前端改动面

1. `packages/types/src/analytics.ts:40` 枚举扩 5 值；`AnalyticsTab`（analytics.ts:43-45 的 key/label/content 结构）注册 5 个 tab 组件。
2. 新 tab 内容组件（`apps/web/components/analytics/` 新目录）：每 tab KPI 行+图表（复用 trend-piece/insight-card/total-insights）+CSV 导出（工作项 tab 的导出模式复制）。
3. 保留 CE 反超：概览雷达图不动（20 号实测修正 #12 明示勿删）。
4. i18n：5 个 tab 名（概览/项目/用户/工作项/周期/模块/收集——部分已存在）。
5. 云端 5 个新 tab 的图表布局未逐 tab 实测——追赶按 tab 名+现有组件形态先对齐结构，图表细节云端复核后调（见 §9）。

## 5. 测试面

- 后端 pytest：5 tab 聚合正确性（造数校验计数）、无效 tab 仍 400、权限（guest 访问 stats 边界）、性能（大工作项量聚合走索引，参照 work-items 分支的 select_related 模式）。
- 前端：tab 切换渲染、空态、CSV 导出列。
- 对照：与云端同口径数据（CE demo-workspace 27 条工作项）核对计数。

## 6. 依赖与并行性

- **前置**：无。**可并行**：5 tab 可按人拆分；本条是 P1-2 Dashboards 的「先做项」（59 号 D-08：先补 analytics tab 更顺——聚合函数被 widget stats 复用）。
- **被依赖**：P1-2 widget 聚合引擎；P1-10/P1-4 无依赖。

## 7. 估算

| 项       | 量                                                                                 | 依据                                                               |
| -------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| 文件数   | 后端 ~3-4（advance.py 扩展+build_chart 扩展）、前端 ~10-12（5 tab 组件+类型+注册） | 端点 397 行现成，纯加分支                                          |
| model 数 | 0                                                                                  | 纯聚合                                                             |
| 迁移数   | 0                                                                                  |                                                                    |
| 后端人天 | 8                                                                                  | 5 个聚合分支（周期/模块可复用既有 progress 计算，Intake 需新聚合） |
| 前端人天 | 7                                                                                  | 5 tab 组件（复用现有 insight 组件库）                              |
| **合计** | **15 人天**                                                                        | L 段位（20 号 P1-4 判 L）                                          |

## 8. 上游冲突面（风险：中）

- **`advance.py` 与 `build_chart.py` 是既有文件**——恰在 2025-05 建立、近期官方未动（17 号 90 天提交清单无 analytics 命中），但 analytics 域属「权限收口」波及面（#10016/#9972 外部 API 角色收口同类）。**隔离策略**：分支扩展尽量加在类内新方法+新 mixin 文件，`get()` 分支处仅加 5 行分发，减小 diff 面便于 merge。
- 前端 tabs.tsx/use-analytics-tabs.tsx 同为既有文件，propel 迁移可能触碰——改动限于数组/枚举追加。
- 官方先做掉风险：无（17 号 M1 对照表 AN 域无提交）。

## 9. 风险与未知

1. **云端 5 个新 tab 的图表形态未逐 tab 实测**（40/59 号仅记录 tab 集与概览/工作项详情）——thinkym 试用 2026-11-28 到期前可补拍（20 号 §6.3 复核点）；追赶先按「KPI 行+1-2 图表」通用形态。
2. 用户 tab 的隐私/权限边界（普通成员能否看他人工作量）云端未验证——先按 ADMIN/MEMBER 可见（沿用 advance.py:109 权限装饰器）。
3. Intake 聚合维度（按来源分布）依赖 intake source 数据——CE intake 公开提交端三处断裂（U6），来源数据可能不全，P0-2 修复后有完整数据。
4. 收集 tab 术语：中文「收集」=Intake（20 号 P0-8 术语统一条目），i18n 键统一。

## 10. 验收用例

| #   | Given                   | When                          | Then                                                    |
| --- | ----------------------- | ----------------------------- | ------------------------------------------------------- |
| 1   | CE 工作区               | 打开 /analytics/              | 7 tab（概览/项目/用户/工作项/周期/模块/收集），不再 400 |
| 2   | 概览 tab                | 查看                          | KPI+项目洞察+活跃项目+**雷达图仍在**（反超保留）        |
| 3   | 项目 tab                | 查看                          | 项目维度 KPI 与列表正确（与工作项总数 28 口径一致）     |
| 4   | 用户 tab                | ADMIN 查看                    | 成员工作项分布渲染                                      |
| 5   | 周期 tab                | WEB 项目有进行中 Sprint 24    | 周期进度数据正确                                        |
| 6   | 模块 tab                | Authentication 50%/Billing 0% | 模块进度聚合正确                                        |
| 7   | 收集 tab                | 有 intake 数据                | pending/accepted/rejected 计数正确                      |
| 8   | 直调 API `?tab=invalid` | —                             | 400 Invalid tab（现状行为不变）                         |
| 9   | 工作项 tab              | 导出 CSV                      | 导出可用（既有能力不回退）                              |
| 10  | guest 角色              | 打开 analytics                | 权限收口行为与现状一致                                  |
