# P1-2 Dashboards 可配置仪表盘 · 改造切入点 Implementation Brief

> 批次 3 · 任务 A（R5）· P1 组 ｜ 基线 main `41af2176d7` ｜ 编号按本批次指令（对应 20 号路线图 5.2 节「P1-3 Dashboards」；F-ID：AN-03/AN-04/AN-05/AN-06）
> 模块依据：59.Dashboards深测/对比.md（26 widget 目录+7 类实测+发布公开页）；18 号域文档 04；**17 号考古对象 2（最高价值：CE 曾完整开源 13 个月）**

## 1. 目标与云端形态

工作区级可配置仪表盘（59 号实测）：

- **列表页** `/dashboards/`：公开/私有/共享三 tab+搜索+「添加仪表板」；侧边栏一级入口。
- **创建弹窗**：名称\*+选择项目\*（多项目数据源，无「全工作区」选项）+数据源筛选（Basic/PQL 双 tab）+可见性（公开默认/私有）。
- **详情页**：编辑/查看双模式；工具栏=数据源/分享/筛选/添加组件/查看⇄编辑/更多操作（编辑/复制链接/新标签页/创建副本/导出/删除）；自动 2 列网格布局（拖拽换位/拖角调高/悬停工具条）。
- **Widget 目录 9 组 26 种**（40/59 号全清单）：柱状 3/线形 2/区域 3/饼环形 3/计数器 2/统计 2/工作项 3/周期 2/Intake 5；配置=X 轴 15 种属性×Y 轴 2 种指标（计数/估算）、最大柱数 20、样式（颜色 #049BDC/图例/提示框）、widget 级 Basic/PQL 筛选。
- **分享/发布/导出**：成员级分享+常规访问；发布=`sites.plane.so/dashboards/{32hex}` 匿名只读公开页（实测可访问、全 widget 渲染、可重新生成/取消发布）；导出=PDF（纵/横向）。
- 与固定 Analytics 并列独立（无互相跳转，数据同源）。
- 深测文档：`docs/01.追赶正式版/01.功能调研/59.Dashboards深测/对比.md`；规格草案：`18.数据模型与API规格草案/04.Dashboards与Widgets.md`（整体可信度中——SDK v2 无 dashboards op）。

## 2. CE 现状（已验证）与**恢复 vs 重写评估**

- **前端死代码（可复用骨架）**：`apps/web/services/dashboard.service.ts:19-21`（`getHomeDashboardWidgets` → `/api/workspaces/{slug}/dashboard/?dashboard_type=home`，此端点后端存在）；`:35`、`:44-45`（`getDashboardDetails` → `/api/dashboard/{id}/`）、`:52-53`（`updateDashboardWidget`）指向不存在端点（直连实测 404）；`apps/web/store/dashboard.store.ts:28,70-74`（DashboardStore/homeDashboardId 骨架）。
- **后端仅首页只读端点**：`apps/api/plane/app/urls/user.py:79-83`（`users/me/workspaces/<slug>/dashboard/`）；无 Dashboard/Widget 模型（`db/models/` grep 零命中）。
- **路由 404 实拍**：CE `/demo-workspace/dashboards/` → 404 错误页（59 号 ce-dashboards-404 截图）。
- **考古（17 号对象 2，★★★）**：完整旧实现曾开源 13 个月（2024-01 `c9337d4a41` 引入 → 2025-02 `fbbf58481d` 删除，commit stat -955 行/9 文件）。`git show fbbf58481d^:apiserver/plane/app/views/dashboard/base.py`（812 行视图）、`.../db/models/dashboard.py`（92 行 Dashboard+DashboardWidget）、urls/serializers（21 行）、packages/types dashboard.d.ts（175 行类型）均可整块取出。
- **恢复 vs 重写——明确建议：后端「恢复为骨架+适配重写」，前端「重写」**：
  1. 后端模型（92 行）与视图聚合逻辑（812 行）可直接取块恢复——聚合查询与 2024 至今的 issue 模型兼容面可控；需适配：目录 `apiserver/`→`apps/api/`、2025 后权限装饰器（`allow_permission`）与 serializer allowlist 约定（#10211）、与 user.py:80 首页端点去重（旧实现可能挂同名路径）。按 17 号纪律：`git show` 取块重写，**不做整文件 cherry-pick**。
  2. 前端旧组件不可恢复：2024 版 widget 组件基于已移除的 nivo（CE `14d2d69120` #7131 已移除 nivo）与 propel 前旧 UI 体系；React19+RR8+propel 高危区（17 号）。前端按 59 号实测形态用新目录重写，仅复用 store/service 骨架与 `THomeDashboardResponse/TWidget` 类型。

## 3. 后端改动面

1. **模型（3 新表+迁移）**：`Dashboard`（name/projects M2M/filters JSON/visibility/is_published/publish_anchor char(32) unique/owned_by）、`DashboardWidget`（dashboard FK/name/widget_type 字符串/config JSON/style JSON/filters JSON/sort_order/size）、`DashboardMember`（dashboard/member/access）。anchor 复用 `deploy_board.py:15` `get_anchor()`（uuid4().hex）模式。
2. **API（18 号 §3 端点草案）**：`/api/workspaces/{slug}/dashboards/` CRUD+duplicate+publish(POST/DELETE)+members+widgets CRUD+`widgets/{id}/stats/` 聚合端点。注意 18 号风险条目：官方未来若在 v2 暴露 dashboards，同路径放置可平滑。
3. **聚合引擎**：widget stats 复用 analytics 查询管道（`apps/api/plane/utils/analytics_plot.py` 与 `app/views/analytic/advance.py` 的 queryset 构造模式）；X 轴 15 属性×2 指标（count/estimate）×group_by 聚合；图表类/计数器/统计/二维表/工作项表格五类查询形状（59 号 §4.2 配置面反推）。
4. **发布**：POST `/dashboards/{id}/publish/` 生成 anchor；公开只读投影 API 挂 space 域匿名路由（复用 DeployBoard 公开 API 模式）；PDF 导出：`POST /dashboards/{id}/export/` 走 Exporter 模式（`db/models/exporter.py` ExporterHistory 已有），服务端无头渲染 PDF（新增渲染 worker，方向参数）。
5. 隔离：新增 `app/views/dashboard/`、`app/serializers/dashboard/`、独立 urls 模块（避开安全修复高密度既有 viewset）。

## 4. 前端改动面（apps/web + apps/space）

1. **路由**：工作区级 `/dashboards/`（列表三 tab）+ `/dashboards/{id}/` 详情；侧边栏一级入口（侧栏组件加项——注意 20 号 D-15 提醒侧栏属改造区）。
2. **详情页**：编辑/查看双模式；网格布局用 react-grid-layout 类库（59 号 D-03 建议）；widget 悬停工具条+8 调整手柄；空态文案按实测。
3. **Widget 渲染与配置**：图表库选型（nivo 已移除，建议 recharts/visx 自选）；一期高频 7 种（柱状/线形/饼形/智能计数器/统计/二维表格/工作项表格——59 号已实测全字段配置面）；目录 9 组 26 种全注册、未实现类型显示「即将支持」；配置面板（X/Y/样式/筛选）。
4. **分享/发布/导出弹层**：59 号 3.4 步骤逐字对照（发布 tab 生成 URL/重新生成/取消发布/查看站点；导出弹窗另存为/格式 PDF/方向）。
5. **Space 公开页**：`/dashboards/[anchor]` 匿名只读渲染（复用 space 匿名路由模式）；i18n 问题注意 59 号发现——公开页图例混英文（Count/Showing 1-2 of 2），追赶时公开页走 i18n locale。
6. store/service 骨架接新端点（`dashboard.service.ts:44-53` 的死端点改为新路径）；`THomeDashboardResponse/TWidget` 类型扩展。

## 5. 测试面

- 后端：dashboard CRUD 权限（private 仅本人/public 全员）、widget stats 聚合口径 vs analytics 一致（59 号「工作项总数 11 ↔ Done 2+Backlog 2」旁证）、publish anchor 唯一+重新生成停用旧链、公开 API 匿名鉴权豁免+数据泄露面审计、duplicate 复制。
- 前端：网格拖拽重排/调高、双模式切换、widget 配置状态机（Y vs X 自动命名规则）。
- 集成：公开 URL 匿名访问渲染全 widget；PDF 导出产物。

## 6. 依赖与并行性

- **前置**：无硬依赖。软依赖：P1-5（Analytics 扩展 tab）先行可让聚合查询形状先成熟（59 号 D-08：先补 analytics tab 再做 dashboards 更顺）；PQL 筛选（P1-7）是 dashboard 数据源 PQL tab 的可选增强，一期 Basic 筛选即可。
- **可并行**：后端聚合引擎与前端网格/渲染全并行。
- **被依赖**：P1-9（站点体验：公开页 i18n/主题）依赖本条的公开页；PDF 导出与 65 号导出体系共享 Exporter 底座。

## 7. 估算

| 项                                   | 量                 | 依据                                                                         |
| ------------------------------------ | ------------------ | ---------------------------------------------------------------------------- |
| 文件数                               | 后端 ~18、前端 ~30 | 18 号端点表 12 op+3 表；59 号页面/弹层 6 区块                                |
| model 数                             | 3（新）            | 18 号 §1.1-1.3                                                               |
| 迁移数                               | 1                  | 全新表                                                                       |
| 后端人天                             | 14                 | 812 行旧视图取块适配（约省 5 人天 vs 纯重写）+聚合引擎 5+发布/导出 3         |
| 前端人天                             | 20                 | 网格画布 4+widget 渲染与配置 7 种 8+列表/分享/发布/导出弹层 5+space 公开页 3 |
| **合计（一期：框架+高频 7 widget）** | **34 人天**        | XL 拆步：框架 L → 高频 widget M → 二期 widget 批次（19 种）另计 ~10-14 人天  |

## 8. 上游冲突面（风险：低）

- 后端新增目录+独立 urls，**低**；唯一注意点是恢复代码时避开 `fbbf58481d` 之后的同名路径（17 号 M1 对照表明示），且不与 user.py:80 首页端点撞路由。
- 前端 `/dashboards/` 新路由+新组件=低；侧边栏入口项修改=低-中（侧栏组件被 propel 迁移触碰过）。**隔离策略**：入口用配置数组追加，不改布局主体。
- 官方先做掉风险：17 号判定无回补迹象（2025-02 删除后 90 天零提交）。

## 9. 风险与未知

1. SDK v2 无 dashboards op——云端 dashboards 走 web 内部 API，规格整体为 UI 反推（18 号最大不确定点）；端点路径可能与官方内部实现不一致，追赶自定即可。
2. 旧 812 行视图的聚合逻辑与 2025-05 analytics 重构（b435ceedfc）口径差异需逐段核对。
3. PDF 无头渲染引入新依赖（playwright/chromium）——部署体积与 CI 面需评估，可降级为浏览器端打印方案二期。
4. 私有/共享 tab 语义与「常规访问受限档位」未实测（59 号待验证 1/2）——先按 public/private/shared 三态实现，档位留扩展。
5. 二维表/计数器/Intake/周期类 widget（19 种）的查询形状未实测配置面，二期逐类对齐。
6. 与 P1-7 的 PQL 筛选耦合：一期先落 Basic 筛选 JSON 结构，PQL 值留同构字段。

## 10. 验收用例（对照 59 号 §3）

| #   | Given       | When                                | Then                                                                 |
| --- | ----------- | ----------------------------------- | -------------------------------------------------------------------- |
| 1   | 无仪表板    | 打开 /dashboards/                   | 公开 tab 空态文案（59 号 1.1）；CE 不再 404                          |
| 2   | 创建弹窗    | 只填名称不选项目                    | 创建按钮置灰                                                         |
| 3   | 建成仪表板  | 添加基础柱状图：X=状态 Y=工作项计数 | 保存成功；自动命名「工作项计数 vs 状态」；渲染分组柱状+图例+分页脚标 |
| 4   | 编辑模式    | 拖拽手柄换位/拖角调高               | 网格自动重排、高度自适应（59 号 3.3）                                |
| 5   | 点「查看」  | —                                   | 工具条/手柄消失，只读渲染                                            |
| 6   | 点发布      | 生成公开 URL                        | 匿名新标签可访问，全 widget 只读渲染；重新生成后旧链失效             |
| 7   | 成员分享    | 被分享成员打开                      | 可见；未分享成员不可见（private 态）                                 |
| 8   | 导出        | 选 PDF+纵向                         | 收到导出任务并完成，产物含全部 widget                                |
| 9   | 创建副本    | 更多操作                            | 副本含全部 widget 且独立 id                                          |
| 10  | 删除 widget | widget 菜单删除                     | 网格重排，无确认弹窗（对齐云端）                                     |
