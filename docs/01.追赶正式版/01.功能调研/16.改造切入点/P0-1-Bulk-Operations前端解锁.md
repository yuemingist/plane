# P0-1 Bulk Operations 前端解锁（Implementation Brief）

> 基线：main HEAD `41af2176d7`（2026-11-14）｜F-ID：**WI-07**｜难度段位（20 号路线图）：M
> 证据源：17 号考古对象 4、20 号模块对比（D-05-工作项、U4）、55 号补测遗留 1、13 号基线 WI-07 行

## 1. 目标与云端形态

让 CE 工作项列表/看板恢复多选与批量操作能力，达到云端 Business 形态（20 号 `cloud-work-items-bulk-toolbar-2026-11-14.png`）：行首复选框可勾选，多选后底部出现批量操作工具栏——编辑 / 复制 / 归档 / 删除 + 属性批量设置（状态、优先级、负责人、日期、标签、模块）。范围：列表、看板、表格（spreadsheet）三个布局；甘特/日历不做（云端也不做）。

## 2. CE 现状（均已 rg/Read 实证）

**后端（端点一直在，考古★★★）**

- `apps/api/plane/app/urls/issue.py:89-101`：`bulk-create-labels/`、`bulk-delete-issues/`、`bulk-archive-issues/` 三条路由注册中（17 号考古：自 2022 仓库合并起即存在）。
- 对应 Endpoint 类 `BulkDeleteIssuesEndpoint`/`BulkArchiveIssuesEndpoint` 在 `apps/api/plane/app/urls/issue.py:9/24` 导入。
- 缺：**批量改属性**（状态/优先级/负责人/日期/模块）没有 bulk 端点——云端工具栏有此能力，需新增或在端点内循环。

**前端（从未 true 过，考古：无被删实现，需自建）**

- `apps/web/hooks/use-bulk-operation-status.ts:7`：全部内容即 `export const useBulkOperationStatus = () => false;`（硬关闭，17 号考古确认 2024-06 诞生即为升级横幅、2024-07 落位 web/ce 覆盖层、2025-07 迁入 apps/web/hooks，从未有可用实现）。
- `apps/web/components/issues/bulk-operations/root.tsx:29-56`：`IssueBulkOperationsRoot` 在多选激活时只渲染 `BulkOperationsUpgradeBanner`（i18n key `bulk_operations.upgrade_banner.*`，外链 MARKETING_PLANE_ONE_PAGE_LINK）。
- 布局层接线完好：`apps/web/components/issues/issue-layouts/spreadsheet/spreadsheet-header.tsx:15,65`（`MultipleSelectGroupAction`）、`apps/web/components/issues/issue-layouts/list/block.tsx:24,226`（`MultipleSelectEntityAction`）——仅受 `disabled={!isBulkOperationStatus}` 门控。
- 服务层已在：`apps/web/services/issue/issue.service.ts:339-340` `bulkOperations()`（指向 `/bulk-operation-issues/`，注意该端点与后端三条 bulk 路由命名不一致，需核对/对齐）。
- 多选 store（`useMultipleSelectStore`，root.tsx:28 已消费）存在。

**考古结论引用**（17 号对象 4）：后端三条端点"一直在且注册中"；前端"诞生即升级横幅、无被删实现"——点亮 = 后端补 1 个属性批量端点 + 前端自建工具栏替换 Banner。

## 3. 后端改动面

| 项                | 文件                                                            | 说明                                                                                                                                                                                        |
| ----------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 新增 ViewSet/视图 | `apps/api/plane/app/views/issue/issue.py`（或新文件 `bulk.py`） | `BulkOperationsEndpoint`：action=update/delete/archive，支持属性批量（state/priority/assignees/label_ids/target_date/start_date/module）；复用现有三个 Endpoint 的写法与 `allow_permission` |
| URL               | `apps/api/plane/app/urls/issue.py`                              | 新增 `bulk-operation-issues/`（与前端 service 路径对齐）或改造三旧端点聚合                                                                                                                  |
| Serializer        | `apps/api/plane/app/serializers/issue.py`                       | `IssueBulkOperationSerializer`（ids + 属性字典）                                                                                                                                            |
| 权限              | `allow_permission([ROLE.ADMIN, ROLE.MEMBER])`                   | 沿用 issue 现有装饰器模式                                                                                                                                                                   |
| Celery            | 无需                                                            | 批量写可同步（限流 ≤100 条/次）；活动流逐条写 IssueActivity                                                                                                                                 |
| feature 开关      | 无                                                              | 不需要（CE 无付费门控概念）                                                                                                                                                                 |

迁移：**0 个**（无新模型）。

## 4. 前端改动面

- **hook**：`apps/web/hooks/use-bulk-operation-status.ts` → 返回 true（1 行；或改为读 project feature，见风险 1）。
- **组件**：`apps/web/components/issues/bulk-operations/root.tsx` → 把 UpgradeBanner 换成批量工具栏（编辑/复制/归档/删除 + 属性设置弹层）；i18n 键 `bulk_operations.toolbar.*` 需在 `packages/i18n/src/locales/<lang>/work-item.json`（`bulk_operations` 命名空间已存在，330 行起）补工具栏键。
- **布局接线**：`spreadsheet/spreadsheet-header.tsx`、`list/block.tsx`、`kanban` 卡片、`issue-layouts/roots/*` 的 `disabled={!isBulkOperationStatus}` 传递链复核（多数应零改动）。
- **store**：多选 store 已有；新增批量操作执行 action（调 issue.service.ts:339 `bulkOperations`）+ SWR 失效刷新。
- **类型**：`packages/types/src/issues/` 补 bulk payload 类型。
- **复制行为**：批量复制 = 逐条 POST（复用现有 duplicate 逻辑），无需新端点。

## 5. 测试面

- API：bulk update/delete/archive 的权限（Guest 拒绝）、跨项目 id 校验、部分失败回滚语义（建议逐条独立事务，返回 per-item 结果）、活动流留痕。
- 造数：27 条工作项（00.测试数据说明）可直接用；需补跨周期/跨模块属性组合。
- E2E：多选→工具栏出现→批量改状态→列表刷新；批量删除→确认弹窗→计数变化。

## 6. 依赖与可并行性

无前置依赖，可并行。与 P0-4（类型）无耦合（批量属性面板可不含类型列，二期并入）。P1-11（工作项单点包）的批量能力不依赖本条，但 UI 会共享工具栏组件。

## 7. 估算

| 维度              | 值                                                                                                                              | 依据                                              |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| 新增/修改文件     | 后端 3（新视图+urls+serializer）、前端 8-10（root.tsx、hook、1 个服务 action、工具栏组件 3-4、i18n 22 locale ×1 文件、types 1） | 改动面清单第 3/4 节                               |
| 新增 model / 迁移 | 0 / 0                                                                                                                           | 无新表                                            |
| 后端人天          | 1.5-2                                                                                                                           | 端点模式现成，唯一新工作是属性批量聚合写          |
| 前端人天          | 4-5                                                                                                                             | 工具栏 UI + 属性批量弹层是主体；store/hook 接线轻 |
| **合计**          | **6-7 人天（M）**                                                                                                               | 与 20 号 M 段位一致                               |

## 8. 上游冲突面（风险：中）

- `apps/web/hooks/use-bulk-operation-status.ts` 与 `components/issues/bulk-operations/root.tsx` 是官方"付费墙壳"文件——17 号提示 2026-02 官方刚清除 web/ee 壳，商业策略若变化可能回补此文件。**隔离策略**：hook 保持文件不动、新增独立 hook（如 `use-bulk-operations-enabled.ts`）由 root.tsx 消费；工具栏组件全部放新目录 `components/issues/bulk-operations/toolbar/`。
- `apps/api/plane/app/views/issue/` 是近 90 天安全修复密度最高区（17 号：权限域绑定/guest 可见性）——新端点放**新文件**+独立 url 模块，不动现有 viewset。
- i18n：只新增键，不重排（17 号同步策略 3）。

## 9. 风险与未知项

1. hook 改 true 后，官方后续 merge 若重写该文件会静默恢复硬关——建议 CI 加一条 grep 断言（回归哨兵）。
2. 云端工具栏的"属性批量设置"完整字段面（含标签增减语义 add/remove）未逐项实测（20 号仅录截图）——按 Basic 筛选常用属性先行，与云端细节误差可接受。
3. 批量操作的活动流语义：云端是否逐条留痕未实测；建议逐条留痕（与单条操作一致）。
4. 前端 service 现指向 `/bulk-operation-issues/`（issue.service.ts:340），该端点后端不存在——是死路径，方案需统一命名。

## 10. 验收用例（对照 20 号 U4 / D-05-工作项）

1. Given 列表布局多选 3 条工作项，When 勾选行首复选框，Then 底部出现批量工具栏（非升级横幅），显示"已选 3 项"。
2. Given 多选 2 条，When 批量改状态为 Todo，Then 2 条状态变 Todo，各条活动流留痕，列表计数刷新。
3. Given 多选 2 条，When 批量设置负责人/优先级/标签，Then 属性面板与行内展示同步更新。
4. Given 多选 2 条，When 批量归档，Then 条目从列表消失、归档页可查。
5. Given 多选 2 条，When 批量删除并确认，Then 条目删除且删除留痕（回收/活动）。
6. Given 表格布局（spreadsheet），When 表头复选框全选，Then 全部行选中、工具栏计数正确。
7. Given Guest 角色，When 触发批量删除 API，Then 403。
8. Given 只读布局（甘特/日历），When 渲染，Then 无复选框（与云端一致，不在范围）。
