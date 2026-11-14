# P0-5 工作区 Active Cycles 聚合端点（Implementation Brief）

> 基线：main HEAD `41af2176d7`｜F-ID：**CY-04**｜难度段位：M
> 证据源：17 号考古对象 6（最高价值项之一）、21 号模块对比（U3、D-01-周期）、20 号路线图 P0-5

## 1. 目标与云端形态

把 CE 工作区级 `/active-cycles/` 从"升级营销页"换为真实数据页：跨项目聚合当前进行中的周期（21 号 `cloud-workspace-active-cycles-2026-11-14.png`：标题 Active Cycles + 跨项目周期汇总 + 空态文案）。云端每张周期卡形态以 CE 项目级周期卡为参照（21 号 D-02：云端卡片信息密度更高，Burn-down 大图属项目级形态，工作区级做汇总卡即可，不强行复刻）。

## 2. CE 现状（已实证）

**前端（壳在、只差数据）**

- 页面：`apps/web/app/(all)/[workspaceSlug]/(projects)/active-cycles/page.tsx:27` 仅渲染 `<WorkspaceActiveCyclesUpgrade />`（升级营销组件，`apps/web/components/active-cycles/workspace-active-cycles-upgrade.tsx`）。
- service 已就绪：`apps/web/services/cycle.service.ts:63-75` `workspaceActiveCycles()` 调 `/api/workspaces/{slug}/active-cycles/`（带 cursor/per_page 分页）——**调不存在的端点，一直 404**。
- 侧栏入口：路由存在但侧栏无直接入口（21 号 1.1 表：CE 侧栏无直接入口，扩展面板含视图/分析/归档）——入口挂载归入本条。

**后端（零路由）**

- `apps/api/plane/app/urls/cycle.py` 无 `active-cycles` 注册（rg 零命中）。
- **考古结论引用**（17 号对象 6）：完整实现存在于**未合并分支**——`8ee5ba96ce`（2024-01-16 #3378 "dev: workspace active cycles"，祖先 `77d2e6c701`）新增 `workspaces/<slug>/active-cycles/` → `ActiveCycleEndpoint`、`app/views/cycle.py` +233 行聚合（活跃周期+分布图）、前端 `active-cycle-info.tsx` 254 行；修复链 `eae6be1d45/2fad4e85b6/f55bf61685/e11146a120`；`git merge-base --is-ancestor 8ee5ba96ce main` = 否，现存于 `upstream/chore/project-entities` 等侧分支。main 侧只合了营销壳（`9d9d703c62` #3454 upgrade page + `be62662bb1` #3423 移除侧栏入口）。
- 可复用评估 ★★★：`git show 8ee5ba96ce:apiserver/plane/app/views/cycle.py` 可整块取出，需适配 2025-05 后 cycle queryset 重构与 `allow_permission` 装饰器（17 号）。

## 3. 后端改动面

| 项             | 文件                                                                               | 说明                                                                                                                                                                                                                          |
| -------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 聚合端点       | 新文件 `apps/api/plane/app/views/cycle/active_cycles.py`（或 views/cycle.py 增类） | `ActiveCycleEndpoint`：按 workspace 聚合 `Cycle.objects.filter(start_date__lte=today, end_date__gte=today, project__in=成员可见项目)`；分页 cursor；每周期附基础聚合（总工作项/已完成/进行中计数——参照旧实现 233 行逻辑重写） |
| URL            | `apps/api/plane/app/urls/cycle.py`                                                 | 注册 `workspaces/<slug>/active-cycles/`                                                                                                                                                                                       |
| Serializer     | `apps/api/plane/app/serializers/cycle.py`                                          | 复用 CycleSerializer + 聚合字段（轻量：不加 query 链过重的分布图，二期）                                                                                                                                                      |
| 权限           | `@allow_permission([ADMIN, MEMBER, GUEST], level="WORKSPACE")`                     | Member/Guest 只见成员项目                                                                                                                                                                                                     |
| Celery/feature | 无                                                                                 | 纯查询聚合无新表、无任务                                                                                                                                                                                                      |

迁移：**0 个**。实现方式：`git show 8ee5ba96ce:...` 取块**重写**（不做整文件 cherry-pick，避免 apiserver 旧路径与旧约定带入——17 号同步策略 5）。

## 4. 前端改动面

- `apps/web/app/(all)/[workspaceSlug]/(projects)/active-cycles/page.tsx`：替换 `WorkspaceActiveCyclesUpgrade` 为数据视图（周期卡列表 + 空态）。
- 周期卡组件：复用项目级周期卡（`apps/web/components/cycles/`）或按考古 `active-cycle-info.tsx` 重写工作区版（新目录 `apps/web/components/active-cycles/`，与营销组件并列）。
- store：`apps/web/store/cycle/` 增 workspace active cycles fetcher（SWR 或 MobX，跟随现有 cycle store 模式）。
- 侧栏入口：扩展面板（更多）挂 Active Cycles 项（对齐云端：侧栏"更多"→周期，21 号 1.1）。
- i18n：`cycle.json` 补工作区级键。
- 分页：跟随 service 的 cursor/per_page。

## 5. 测试面

- API：多项目多周期（进行中/未开始/已结束）聚合过滤正确；分页；Guest 仅可见其项目周期；空工作区返回空数组（非 404）。
- 造数：现有 WEB 项目 Sprint 24（进行中）可直接命中；补一个已结束周期与另一项目周期验证跨项目聚合。
- E2E：打开 `/active-cycles/` 显示 Sprint 24 卡片（非营销页）；空态文案；点击卡片跳转项目周期页。

## 6. 依赖与可并行性

- 无前置依赖，可并行。与 P1-4（Analytics 扩展 tab）共享聚合查询工具（`utils/`），但互不阻塞。

## 7. 估算

| 维度              | 值                                                                                     | 依据                                            |
| ----------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------- |
| 新增/修改文件     | 后端 3（视图+urls+serializer 复用）；前端 5-7（页面、卡片组件 2-3、store、侧栏、i18n） | 改动面清单                                      |
| 新增 model / 迁移 | 0 / 0                                                                                  | 纯聚合                                          |
| 后端人天          | 2-2.5                                                                                  | 有 233 行参考实现，主要是适配新版 queryset/权限 |
| 前端人天          | 3-4                                                                                    | 页面替换+卡片复用改造+入口                      |
| **合计**          | **5-6.5 人天（M）**                                                                    | 略低于 20 号 M 中位（考古实现降低了不确定性）   |

## 8. 上游冲突面（风险：低）

- `cycle.py` urls/views 属官方低频区（17 号判定：无提交、升级页与 service 均未动）——冲突面小。
- `active-cycles/page.tsx` 与 `workspace-active-cycles-upgrade.tsx` 是官方付费墙壳（同 P0-1 hook 逻辑）——**不删营销组件文件**（保留 import 可回退），页面改渲染目标；若官方未来重写该文件，diff 冲突限 1 行。
- cycle queryset 2025-05 重构过，恢复旧代码时逐查询核对字段名（17 号考古提示）。

## 9. 风险与未知项

1. 2024 参考实现的聚合逻辑（分布图数据）基于旧模型字段，重写时对不上就砍范围：第一期只做周期列表+基础计数，Burn-down/分布图不做（云端工作区级也未展示完整形态，21 号云端截图为空态+汇总）。
2. 性能：大工作区跨项目聚合需 select_related/limit；先按分页+轻聚合实现，压力测试后定缓存策略（可加 60s 缓存）。
3. 云端工作区 Active Cycles 的有数据态卡片字段未实测（21 号云端截图为空态）——按 CE 项目级卡字段就近实现，验收以"真实数据+空态"为准。

## 10. 验收用例（对照 21 号 U3/D-01-周期）

1. Given WEB 项目有进行中 Sprint 24，When 打开 `/demo-workspace/active-cycles/`，Then 显示 Sprint 24 真实卡片（专业版营销组件不再出现）。
2. Given 工作区无进行中周期，When 打开页面，Then 显示空态文案（对齐云端 `cloud-workspace-active-cycles`）。
3. Given 多项目各有进行中周期，When 打开页面，Then 跨项目聚合按项目分组/标注展示且分页可用。
4. Given Guest 用户仅在某项目为成员，When 打开页面，Then 仅见该项目周期。
5. Given 周期卡，When 点击，Then 跳转对应项目周期视图。
6. Given 侧栏「更多」扩展面板，Then 出现 Active Cycles 入口。
7. Given API 直调 `GET /api/workspaces/{slug}/active-cycles/`，Then 200（现状 404）。
