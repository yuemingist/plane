# P0-4 Epics / Work Item Types 后端路由与设置页（Implementation Brief）

> 基线：main HEAD `41af2176d7`｜F-ID：**WI-01、WI-02、WI-03、WI-16**｜难度段位：M
> 证据源：17 号考古对象 7、57 号模块对比（D-01~D-06-类型）、23 号（U2、D-01-设置）、18 号草案 01/02、20 号 U1 修正

## 1. 目标与云端形态

补齐类型体系的后端 API 与管理面，并完成工作项层的第一阶段贯穿：

- 项目设置「工作项类型」页（57 号：启用门卡+启用确认（不可禁用警告）→ 类型/属性/层级三 tab；启用自动生成 Epic+Task 两类型）；
- IssueType CRUD API（创建/编辑/启停/删除/设为默认，默认类型不可删）；
- **本条只做「类型」tab 的完整管理**；「属性」tab 依赖自定义属性体系（P2-13，XL）——先渲染空态；「层级」tab 做只读可视化（Epic=1 → 普通=0）；
- Epic 后端路由（`/epics/` = Issue 查询 + `type.is_epic` 过滤），点亮已就绪的 CE epic 前端（store/服务/甘特布局/epic-modal）。
- 工作项贯穿（chip/切换/筛选/新建选择，57 号 D-07~D-10）作为本条二期子项，可拆独立排期。

## 2. CE 现状（已实证）

**模型层（零缺口）**

- `apps/api/plane/db/models/issue_type.py:14` `class IssueType`（name/description/logo*props/is_epic/is_default/is_active/level/external*\*，18-01 号：字段与 EE 读模型完全同构）；`:35` `ProjectIssueType`（M2M+level+is_default+软删唯一约束）。
- `apps/api/plane/db/models/project.py:101` `is_issue_type_enabled`（默认 False，无 UI 消费）。
- `Issue.type` FK 已在（api/serializers/issue.py:67 已引用）。

**API 层（零路由）**

- `apps/api/plane/app/urls/`、`apps/api/plane/api/urls/` grep `IssueType/issue-type/epic` **零命中**（57 号 §6.2"可写库、无 API"）；仅 `api/serializers/issue.py:16,67,196` 在 Issue 序列化中引用类型。

**前端（CE 存量即"未点亮"）**

- epic store 已挂载：`apps/web/store/issue/root.store.ts:227-228`（`this.epicDetail = new IssueDetail(this, EIssueServiceType.EPICS)`）+ workspaceIssues/projectEpics 字段（:107-108）。
- epic service 判定已在：`apps/web/services/issue/issue.service.ts:118-120/449-451`（`is_epic` flag 注入）。
- epic 组件存量：`apps/web/components/epic-modal/`、甘特布局 epic 分支（`issue-layouts/gantt/base-gantt-root.tsx:132-133` `t("epic.label")`）、list/block.tsx:89（`isEpic ? EPICS : ISSUES` 服务类型切换）。
- i18n 资产现成：`packages/i18n/src/locales/en/work-item-type.json` 命名空间已存在。
- 设置页：`/settings/projects/{id}/work-item-types/` 路由 404（57 号 ce-work-item-types-404 实拍），`features/` 目录下无 issue-types 页。

**考古结论引用**（17 号对象 7）：main 从未有 `/epics/` 路由；EE 实现存在于公共分支历史的 `plane/ee/*`（仅存在性证据，不引用内容）——**CE 侧从零建**；官方曾用 dummy 脚本（#2660，分支可见）在 CE 结构上演练 epics，可作数据形态参考。

## 3. 后端改动面

| 项                    | 文件                                                                                                                                                       | 说明                                                                                                                                                                             |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| IssueType ViewSet     | 新文件 `apps/api/plane/app/views/issue_type.py`                                                                                                            | CRUD + `mark-default` + 项目启用动作（启用=置 is_issue_type_enabled + 自动建 Epic(is_epic)/Task 两类型，57 号 3.1 步骤 3）；`allow_permission([ADMIN, MEMBER])`                  |
| ProjectIssueType 绑定 | 同上或独立视图                                                                                                                                             | project↔type 绑定/解绑                                                                                                                                                           |
| Epics ViewSet         | 新文件 `apps/api/plane/app/views/epic.py`                                                                                                                  | 复用 IssueViewSet 查询模式，强制过滤 `type__is_epic=true`（20 号路线图建议：参照 archive 中 `type__is_epic` 适配）；子项创建时类型下拉排除父链上位类型（level 规则，57 号 D-05） |
| URL                   | `apps/api/plane/app/urls/` 新 `issue_type.py`+`epic.py` 并注册                                                                                             | kebab-case 路径 `work-item-types/`（对齐 18-01 号端点表）                                                                                                                        |
| Serializer            | 新 `apps/api/plane/app/serializers/issue_type.py`                                                                                                          | IssueType/ProjectIssueType；Issue serializer 的 type 字段读写已有                                                                                                                |
| 权限                  | `allow_permission`                                                                                                                                         | Guest 只读                                                                                                                                                                       |
| feature 开关          | 复用 `Project.is_issue_type_enabled`；workspace 级 `is_work_item_types_enabled` 若要新建见 18-10 号 §5.3（建议先不做 workspace 单例，用 project 字段即可） |                                                                                                                                                                                  |

迁移：**0 个**（模型全在；仅当引入 workspace feature 单例时 +1）。

## 4. 前端改动面

- 设置页（新目录 `apps/web/components/settings/projects/issue-types/`）：启用门卡+确认弹窗（两条警告文案，57 号 4.3）→ 类型 tab 表格（图标+名称+默认 badge+地位+菜单）+ 属性 tab 空态 + 层级 tab 只读可视化（`cloud-hierarchy-tab` DOM 已存档）。
- 路由：`settings/projects/[projectId]/features/` 或工作结构分组下新增 `work-item-types/page.tsx`；设置侧边栏项注册（`packages/constants/src/settings/` 项目设置常量）。
- service/store：新建 `issue-type.service.ts` + workspace/project store（`packages/types` 补 `IIssueType`）。
- Epic 布局入口：类型启用后暴露 Epic 布局开关（`is_epic_enabled` 对齐 18-02 号——建议直接读 `type.is_epic` 存在性，不加新字段）。
- i18n：`work-item-type.json` 已有底子，补管理页键（22 locale）。
- 二期贯穿子项（可拆）：详情类型 chip+切换（57 号 D-07，切换确认文案已有资产）、新建弹窗类型选择（D-08）、显示列/筛选 Type（D-09/D-10）。

## 5. 测试面

- API：启用项目→自动生成 Epic+Task；默认类型不可删（400）；未激活类型设默认被拒；Epic 列表仅返回 is_epic 类型工作项；Epic 下创建子项类型枚举不含 Epic；Guest 只读。
- 造数：现 WEB 项目已直插 Epic/Bug/Feature 类型（57 号 §1.3）——补一条"启用流程"用例覆盖自动建类型路径。
- E2E：启用门卡→确认→类型表格两行；新建类型（图标选择器+默认禁用）→启用→设默认；Epic 工作项在 Epic 布局可见。

## 6. 依赖与可并行性

- 无前置依赖，可并行。**被依赖**：P2-13（自定义属性）复用本条的类型实体与设置页骨架；P2-14（工作流）按类型挂链依赖 WI-02。
- 后端（CRUD+epics 路由）与前端（设置页）可两人并行；贯穿子项可独立拆分。

## 7. 估算

| 维度              | 值                                                                                                                                              | 依据                                                            |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| 新增/修改文件     | 后端 6-7（2 viewset+2 urls+1 serializer+注册）；前端 10-14（设置页 4-5、路由/常量 2、service/store/types 3-4、i18n 1×22 locale、epic 入口 1-2） | 改动面清单                                                      |
| 新增 model / 迁移 | 0 / 0（含 workspace 单例则 1/1）                                                                                                                | 模型层零缺口                                                    |
| 后端人天          | 4-5                                                                                                                                             | 两个新 viewset；epics 路由=查询过滤+规则校验，复杂度中等        |
| 前端人天          | 8-10                                                                                                                                            | 设置页三 tab（属性 tab 空态省工作量）+启用流；epic 入口存量现成 |
| **合计**          | **12-15 人天（M）**                                                                                                                             | 不含贯穿子项（贯穿另计 5-8 人天，S-M）                          |

## 8. 上游冲突面（风险：中）

- `apps/api/plane/app/views/issue/` 是官方安全修复高密度区——epics ViewSet **独立新文件**，不强改 IssueViewSet（17 号同步策略 3）。
- 项目设置侧边栏/常量（`packages/constants/src/settings/`）是官方 propel 同步触碰区——新增项用追加方式。
- `work-item-type.json` locale 官方每月增改翻译——只加键不重排。
- 官方短期不会做 CE 类型管理（17 号判定表：EE 不回开源）——同目录同路径放置风险低，但仍建议 serializer/viewset 均新文件。

## 9. 风险与未知项

1. 层级 tab 是否可编辑未确认（57 号待验证 1）——按只读可视化先行，官方定型后跟进。
2. 启用自动建类型的枚举/字段（Epic 图标、Task 默认）细节按 57 号实测复刻，与官方 seed 未必逐字节一致——升级官方时需数据收敛脚本预案。
3. Epic 与现有 `archived`/profileIssue 等查询面的 `type__is_epic` 适配点数量需开发时盘点（20 号提示参照 archive 实现）。
4. workspace 级 `is_work_item_types_enabled` 与 project 级开关的双层语义（18-01 号 §5.4）：先 project 单层，避免官方 workspace feature 单例表冲突。
5. 「属性」tab 空态文案与云端一致但功能依赖 P2-13——需在 UI 标注"即将支持"避免误导。

## 10. 验收用例（对照 57 号流程表 / 23 号 U2）

1. Given 未启用项目，When 打开 `/settings/projects/{id}/work-item-types/`，Then 显示门卡+「启用」按钮（非 404）。
2. When 点启用并确认，Then toast 成功，类型 tab 出现 Epic（活动）+Task（默认·活动）两行，`is_issue_type_enabled=true`。
3. When 新建类型「调研-缺陷」，Then 新行状态=已禁用；行菜单含 设为默认(禁用)/编辑/启用/删除（57 号 3.2 步骤 4）。
4. Given 默认类型 Task，When 点删除，Then 按钮禁用并提示「无法删除…默认类型」（57 号 4.3 文案）。
5. Given Epic 类型存在，When 创建 Epic 工作项并打开甘特布局，Then Epic 甘特正常渲染（存量组件点亮）。
6. Given Epic 工作项，When 添加子工作项，Then 类型下拉只有 Task/自定义类型，Epic 被排除（57 号 3.4 步骤 9）。
7. Given 层级 tab，Then 显示「层级 1：Epic → 层级 0：Task/自定义」只读可视化（57 号 1.2 Tab3）。
8. Given 未启用项目调 `GET work-item-types/`，Then 403/400（按开关门控）。
