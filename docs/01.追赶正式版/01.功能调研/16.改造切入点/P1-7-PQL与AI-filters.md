# P1-7 PQL + AI filters · 改造切入点 Implementation Brief

> 批次 3 · 任务 A（R5）· P1 组 ｜ 基线 main `41af2176d7` ｜ 编号按本批次指令（对应 20 号路线图 5.2 节「P1-7 PQL + AI filters」；F-ID：AI-05/AI-06 邻域 + 视图/仪表盘筛选）
> 模块依据：41.AI功能/对比.md（AI filters→PQL 实测）；22 号（视图创建弹窗 PQL tab）；65 号；18 号域文档 13（PQL 查询语言——语法全集高可信）

## 1. 目标与云端形态

过滤 DSL（PQL）+ 自然语言→PQL 转换，三处共用（20 号路线图口径）：

- **AI filters 实测形态**（41 号）：输入自然语言 "priority is high" → 自动转 PQL `priority = "high"` → 应用生效（截图 cloud-ai-filters-input / cloud-ai-filter-result-20261114.png）。
- **三处入口**：①工作项列表筛选条（AI filter 描述框）②视图创建/编辑弹窗（Basic/PQL 双 tab，22 号 D-03：CE 仅 Basic）③仪表盘数据源与 widget 筛选（59 号 Basic/PQL 双 tab）。
- **PQL 能力面**（18 号域 13，依据 MIT 许可 plane-mcp-server `pql_reference.py`）：标量字段（priority/stateGroup/isDraft/isArchived/title/text/dueDate/startDate/createdAt/updatedAt）+UUID 字段（assignee/state/label/cycle/module/project/createdBy/type）+自定义属性 `cf[...]`（CE 无自定义属性，先不实现）；运算符 `= != > >= < <= ~ IN NOT IN IS [NOT] NULL/EMPTY BETWEEN`；逻辑 AND/OR/NOT；函数 today/daysAgo/activeCycle/openStates/currentUser/isOverdue/blockedBy 等谓词与关系函数；**限制：单查询≤5 条件**。
- 深测文档：`docs/01.追赶正式版/01.功能调研/41.AI功能/对比.md`、`22.模块与视图/对比.md`、`18.数据模型与API规格草案/13.PQL查询语言.md`。

## 2. CE 现状（已验证）

- **外部 API 显式拒 PQL**：`apps/api/plane/api/views/issue.py:393` —— `unsupported_filters = [param for param in ("pql", "filters") if request.GET.get(param)]` → 返回错误说明「PQL and structured filters are not supported on this Plane edition」。**外部 API v1 的 PQL 支持点现成（放行+实现即可）**。
- **应用内查询构造**：`apps/api/plane/utils/issue_filters.py`（463 行）——现有 issue_filters JSON 查询构造器（视图 query 落点 `db/models/view.py:61` query JSONField、`:80-81` filters 自动转 query）。PQL 编译目标=映射到该构造器（18 号 §追赶实现方案 1a：Postgres 过渡，OpenSearch 二期）。
- **LLM 底座**：P0-4 后可用——`GPTIntegrationEndpoint`（`plane/app/views/integration/secret.dart` 不对，为 `apps/api/plane/app/views/integration/base.py` 区域，provider 抽象已支持 OpenAI/Anthropic/Gemini，external/base.py:148 三层贯通，20 号 P0-4 依据）；未配 key 返回 400（U7：CE 无 key 时 AI 整体隐藏——PQL 手写模式不受影响，AI 转换按钮隐藏）。
- **前端筛选组件**：三段式 property/operator/value 筛选组件（视图/工作项共用，与自动化条件同构——58 号 D-03 判定「复用现有 filter 组件」）。
- **考古引用**：17 号对象表无 PQL 条目——CE 从未有 PQL 代码；语法规格为 MIT 公开仓库内容（20 号 §6.4 合规清单明示可用）。SDK v2 `View.pql_filters` 字段（18 号）证明云端视图可保存 PQL。

## 3. 后端改动面

1. **PQL 解析层（从零建）**：Python 递归下降 parser（或 lark）→ AST（字段/运算符/函数/逻辑）；语法表照 18 号域 13 全集（一期可裁剪：先标量+UUID 字段+核心运算符+日期/用户/状态组函数；`cf[]` 自定义属性待 P2-13 后补）。
2. **编译目标 a（Postgres）**：AST→`issue_filters.py` 既有 JSON 查询构造（或直接 AST→Django Q 对象新文件 `utils/pql_compiler.py`，避免改 463 行既有文件）；序列号解析（`id = "WEB-11"`→UUID，IssueSequence 已在）；函数实现（today/daysAgo→日期范围；activeCycle/openStates→子查询；currentUser→请求用户）。
3. **执行点**：
   - 应用内：新增 `?pql=` 查询参数于工作项列表端点（`app/views/issue.py` ListAPI）——**只加参数解析与编译调用，不动既有 filter 逻辑**；
   - 外部 API v1：放行 `api/views/issue.py:393` 的 pql 参数（改为支持），filters 参数维持现状；
   - 持久化：`IssueView` 新增 `pql_filters`（JSONField/TextField，1 迁移——SDK v2 字段名对齐）；仪表盘 filters JSON 内嵌 pql 键（P1-2 结构预留）。
4. **NL→PQL 转换服务**：LLM prompt（PQL 语法书=18 号域 13 全文）+现有 LLM 集成端点模式（外部 base.py:148 三层）；输出仅 PQL 字符串+预览确认（云端形态=转换后展示可编辑的 PQL，41 号 D-05）；无 key 时 400 并前端隐藏入口。
5. 安全：PQL 编译产物白名单校验（字段/函数枚举内），防注入（全参数化查询，无原生 SQL 拼接）。

## 4. 前端改动面

1. **PQL 编辑组件**（新）：代码式输入框（等宽字体+错误高亮）+「应用」按钮；转换预览态（NL 输入→PQL 展示→确认）。
2. **AI filter 输入框**：筛选条「Describe your filter in plain language...」入口（三处复用同一组件）；无 LLM key 时隐藏（U7 降级语义一致）。
3. **视图弹窗**：Basic/PQL 双 tab 改造（22 号 D-03）；工作项筛选条 AI 入口；P1-2 dashboard 数据源/筛选 tab 接同一组件。
4. store/service：PQL 应用走列表查询参数；视图保存 pql_filters 字段。
5. i18n：PQL tab/AI 描述框文案（官方形态文案已录：Basic/PQL tab 标签、"Describe your filter in plain language..."）。

## 5. 测试面

- 后端 pytest：语法全集用例（每运算符/函数至少 1 例+错误语法 400）、≤5 条件限制、序列号解析、注入尝试（字符串含 SQL/引号转义）、外部 API 放行后行为、权限（PQL 结果仍受成员可见性过滤）。
- 转换服务：mock LLM 响应→PQL 校验；无 key 降级。
- 前端：双 tab 切换保留 Basic 状态、PQL 错误回显。
- 端到端：NL "priority is high"→PQL→列表过滤结果与 Basic 筛选一致。

## 6. 依赖与并行性

- **前置**：P0-4（LLM key 底座）——仅 AI 转换部分依赖；PQL 手写部分无依赖可先行。**可并行**：parser/编译器（后端核心）与前端组件并行。
- **被依赖**：P1-2（仪表盘 PQL 筛选 tab）；P1-13（Webhook v2 filters 内嵌 Basic/PQL——62 号 D-04 判定依赖 PQL）；自动化条件高级模式（二期）；P2-9 AI 平台（PQL 是其查询底座，20 号关键路径 P0-4+P1-7→P2-9）。

## 7. 估算

| 项       | 量                                                                               | 依据                                                                      |
| -------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| 文件数   | 后端 ~8（parser/compiler/转换服务/端点接入/迁移）、前端 ~10（组件三处接入+类型） | 18 号域 13 方案级拆解                                                     |
| model 数 | 0 新表（IssueView +1 字段）                                                      |                                                                           |
| 迁移数   | 1（view 表加 pql_filters）                                                       |                                                                           |
| 后端人天 | 14                                                                               | parser+compiler 8（语法全集 30+ 元素）+转换服务 3+执行点接入 2+安全校验 1 |
| 前端人天 | 7                                                                                | PQL 编辑组件+AI 输入框+三处接入                                           |
| **合计** | **21 人天**                                                                      | L 段位（20 号 P1-7 判 L）                                                 |

## 8. 上游冲突面（风险：中）

- `app/views/issue.py`（列表端点加 pql 参数）与 `api/views/issue.py`（:393 放行）均为**安全修复高密度既有文件**（17 号：guest/权限域绑定遍布 issue views）。**隔离策略**：pql 参数解析放独立 helper（`utils/pql_compiler.py`），view 层仅 +3 行调用；外部 API 放行处保持权限装饰器不动。
- 前端筛选组件是共用核心组件（propel 高危区交叉）——AI 入口做独立按钮/弹层注入，不改 filter 组件主体。
- 官方先做掉风险：无（17 号 AN/AU 域无提交；PQL 属云端 EE 能力）。

## 9. 风险与未知

1. **服务端 PQL 引擎与 MCP 参考实现的差异未证**（18 号域 13 可信度标注：MCP 为客户端预编译提示，服务端原生执行面未知）——以 18 号语法表为规格自研，行为差异可接受（追赶口径）。
2. PQL 错误消息/预览交互云端细节未实测（41 号仅录到转换生效）。
3. `cf[]` 自定义属性函数域：CE 无自定义属性（17 号对象 1：考古未找到），一期明确不支持并在文档标注，待 P2-13。
4. CJK/连字符边界（65 号 D-14：「调研」单查 0 结果的分词问题）与 PQL 的 `~` 模糊运算符相关——PQL 走 Postgres ilike 需验证 CJK 行为。
5. 性能：复杂函数（blockedBy 等关系谓词）在 Postgres 上可能产生重子查询——一期限制函数集，重关系函数缓行。

## 10. 验收用例

| #   | Given                                                             | When                             | Then                                                                  |
| --- | ----------------------------------------------------------------- | -------------------------------- | --------------------------------------------------------------------- |
| 1   | 视图创建弹窗                                                      | 切 PQL tab                       | 输入框出现；Basic tab 状态保留                                        |
| 2   | PQL 输入 `priority = "high" AND assignee = currentUser()`         | 应用                             | 列表只显高优+分配给我的（与 Basic 筛选同结果）                        |
| 3   | PQL 输入 `stateGroup IN openStates() AND updatedAt < daysAgo(30)` | 应用                             | 结果正确且≤5 条件内                                                   |
| 4   | LLM key 已配                                                      | AI 描述框输入 "priority is high" | 自动转 `priority = "high"` 并展示可编辑预览→应用生效（41 号实测形态） |
| 5   | 未配 LLM key                                                      | 打开筛选                         | AI 入口隐藏，PQL 手写仍可用（U7 降级语义）                            |
| 6   | PQL 含 `blockedBy("WEB-4")`                                       | 应用                             | 被阻塞项过滤正确（WEB-7←WEB-4 样本）                                  |
| 7   | 外部 API `GET /api/v1/.../issues/?pql=...`                        | —                                | 返回过滤结果而非「not supported」（api/views/issue.py:393 放行）      |
| 8   | PQL 含 6 个条件                                                   | 应用                             | 400+限制提示                                                          |
| 9   | PQL 含非法字段/SQL 片段                                           | 应用                             | 400+字段白名单错误，无注入生效                                        |
| 10  | 视图保存 PQL                                                      | 重开视图                         | pql_filters 持久化并自动应用                                          |
