# P1-6 导入器框架（CSV 先行）· 改造切入点 Implementation Brief

> 批次 3 · 任务 A（R5）· P1 组 ｜ 基线 main `41af2176d7` ｜ 编号按本批次指令（对应 20 号路线图 5.2 节「P1-6 导入器框架」；F-ID：IG-10/IG-11）
> 模块依据：62.集成导入深测/对比.md（9 importer+CSV/Jira/Notion 第 1-2 步实测）；50.集成生态/对比.md；17 号考古对象 3（importer 管道被删）

## 1. 目标与云端形态

工作区设置 → 连接组 → **导入**（`/settings/imports/`）页面与导入器框架（62 号实测）：

- **9 种 importer 卡片**：Jira / Jira Server DC / Linear / Asana / ClickUp / Notion / Confluence / Flatfile / CSV；Free 档不设墙（20 号实测修正 #13：导入器是获客关键路径）。
- **CSV（本条一期目标）**：作业列表页（「未找到任务/您尚未导入任何 CSV Importer 项目」）→ 两步向导：①选择项目（下拉）②上传 CSV（拖放区，仅 .csv；官方规则=列名直接匹配名称/描述/优先级/日期/状态组，**无映射页**）→ 文件卡（名/大小/Ready 徽标/移除）→ Import CSV。
- **Jira（二期）**：第 1 步 PAT+邮箱+域名三字段（假凭据实测 401「无效的个人访问令牌」内联错误条，62 号 3.1）；第 2 步起 选项目→选站点+JQL→用户导入→状态映射→优先级映射→预览（官方步骤链见 14 号摘要 11.导入导出.md）。
- **Notion（二期）**：目标类型（Wiki/Project/Teamspace）+ZIP 文件/公开 URL 双通道，非 OAuth。
- 深测文档：`docs/01.追赶正式版/01.功能调研/62.集成导入深测/对比.md`（§1.4/§3.1/§3.2/§3.3）；50 号 U9（CE 无导入入口、404 实拍）。

## 2. CE 现状（已验证）

- **页面 404**：`/settings/imports/` 直连 404（50 号 U9 实拍 ce-settings-imports-20261114.png）；设置侧边栏无「导入」入口。
- **前端死壳**：`apps/web/services/integrations/jira.service.ts:18,28` 调 `/api/workspaces/{slug}/importers/jira`、`/api/workspaces/{slug}/projects/importers/jira/`（后端无路由，死代码）。
- **模型遗留**：`apps/api/plane/db/models/importer.py:13` `Importer`（service choices 仅 `github/jira`、status 枚举 queued/processing/completed/failed、initiated_by/metadata/config/data JSON/token FK APIToken/imported_data JSON）——模型在但**无路由无视图**（grep `importer` 于 `app/urls/` 零命中；仅 `plane/api/urls/external.py:17,22` 两条外部 API 遗留）。
- **考古引用（17 号对象 3，★★）**：`a852e3cc52`（2024-03）删除 `app/views/importer.py`（558 行 Jira importer）、`utils/importers/jira.py`、`bgtasks/importer_task.py`（201 行）——`git show a852e3cc52^:<path>` 可取块参考（Jira 映射/批量创建逻辑）；CSV importer 从未存在（全新）。前端导入页 2024-03-25 `8205961d2a` 删除（-250 行）。
- 云端执行体在 silo（62 号：Jira PAT 校验请求发往 `silo.plane.so/api/jira/auth/pat`）——CE 自建=API 内实现，无 silo。

## 3. 后端改动面（一期=框架+CSV 完整；Jira 二期）

1. **Importer 模型扩展（1 迁移）**：service choices 追加 `csv`（保留 github/jira）；status/config/data 结构沿用；新增文件存储引用（CSV 上传复用 FileAsset 通道或临时存储路径字段）。
2. **框架层**：通用导入管道（抽象基类）：上传→解析→校验→批量创建工作项（复用 issue 创建服务，含状态/优先级/日期列映射规则）→进度更新（status+imported_data 统计）→失败行记录。Celery 任务执行（`bgtasks/importer_task.py` 恢复命名新建）。
3. **CSV adapter**：列名匹配规则对齐官方（名称/描述/优先级/日期/状态组——62 号 §1.4 文案逐字）；无映射页=服务端按官方规则直配；错误报告（失败行原因）。
4. **API**：`/api/workspaces/{slug}/importers/`（列表）+ `/importers/csv/`（建作业）+ 上传端点 + `/importers/{id}/status/`（轮询进度）+取消/删除（jira.service.ts:67 已引用 delete 形态）。挂独立 urls 模块。
5. **Jira 二期预留**：PAT 校验端点（`/importers/jira/auth/`，对应 silo `/api/jira/auth/pat` 语义）+项目/JQL 拉取+映射端点；adapter 骨架可先落（参考 17 号被删 558 行实现）。

## 4. 前端改动面

1. 设置侧边栏「连接」分组补「导入」入口+`/settings/imports/` 页（9 卡片：CSV 可用，其余「即将支持」态——对齐 P0-9 集成目录页最小恢复的相同策略）。
2. CSV 两步向导：作业列表页空态+向导（选择项目下拉→上传拖放区→文件卡 Ready→Import CSV）+进度/结果视图（成功 N 失败 M+失败明细）。
3. store/service：jira.service.ts 扩为 importer.service.ts（或新建 csv-importer service），死端点改新 API。
4. i18n：imports 命名空间新增键。

## 5. 测试面

- 后端 pytest：CSV 解析（编码/BOM/空行/列缺失）、批量创建事务边界（部分失败不整批回滚，失败行记录）、进度状态机（queued→processing→completed/failed）、权限（非 admin 不可建作业）、大文件分块。
- 前端：向导状态机、文件校验（非 .csv 拒绝）、进度轮询。
- 集成：导出既有 CSV→再导入的往返一致性（CE 导出 33 列结构见 65 号 1.5，导入按官方 5 列规则，往返用子集验证）。

## 6. 依赖与并行性

- **前置**：无硬依赖（模型在）；工作项批量创建服务复用 P0-1 bulk 端点底层经验（软协同）。
- **可并行**：框架+CSV（后端）与导入页/向导（前端）并行。
- **被依赖**：Jira/Notion/Linear 等 8 源二期直接落框架；IG-11 成员 CSV 导入可复用框架。
- 与 P1-3 无耦合（导入器无 OAuth 依赖——CSV 纯文件、Jira 纯 PAT）。

## 7. 估算

| 项                   | 量                                                         | 依据                                                                                                                  |
| -------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 文件数               | 后端 ~10、前端 ~12                                         | 框架 3 层+CSV adapter+页面/向导                                                                                       |
| model 数             | 0 新表（Importer 扩 choices）                              | importer.py:13 已在                                                                                                   |
| 迁移数               | 0-1（choices 变更无需 DB 迁移，仅字段引用+可能的文件字段） | CharField choices 属应用层                                                                                            |
| 后端人天             | 10                                                         | 框架 4+CSV adapter 与规则匹配 3+API/进度 2+Jira 骨架 1；17 号 558 行被删实现可参考省 ~2                               |
| 前端人天             | 6                                                          | 导入页+两步向导+进度视图                                                                                              |
| **合计（一期 CSV）** | **16 人天**                                                | L 段位（20 号 P1-6 判 L=2-6 周，CSV 先行取下限）；Jira 完整版二期另 +10-12 人天，全部 9 源另计（20 号 XL 判定的原因） |

## 8. 上游冲突面（风险：低）

- 后端新增 urls/views/任务文件=低；Importer 模型 choices 追加=低（模型文件长期未动）。
- 前端 `/settings/imports/` 新页面+设置侧栏加项=低（同 P0-9 模式）。
- 官方先做掉风险：无（17 号：silo 体系未回归开源；导入器 UI 官方也在 silo 侧）。

## 9. 风险与未知

1. **CSV 列匹配规则细节未完全实测**（62 号止步于 Import 前未执行导入；官方规则文案「名称、描述、优先级、日期和状态组的列」）——日期/优先级的具体格式（ISO？枚举名？）需以官方文档 14 号摘要+试错验证。
2. 作业列表/进度页形态未实测（云端作业列表只有空态被记录）；按队列页（同导出「以前的导出」模式 65 号 1.4）设计。
3. 上传文件的存储通道（S3/本地）需对齐 CE FileAsset 体系与实例配置。
4. Flatfile（官方 Beta，交互式映射）结构最丰富，属二期+；不纳入一期估算。
5. Jira 映射 UI（状态映射/优先级映射/用户导入）未实测（需真实凭据）——二期以 17 号被删 importer.py 558 行+官方文档步骤链为蓝本。

## 10. 验收用例（对照 62 号 §3.2）

| #   | Given         | When                    | Then                                                                                              |
| --- | ------------- | ----------------------- | ------------------------------------------------------------------------------------------------- |
| 1   | CE 工作区设置 | 打开 /settings/imports/ | 页面不再 404；9 卡片，CSV 可用、其余即将支持                                                      |
| 2   | CSV 卡        | 点导入                  | 作业列表空态「您尚未导入任何 CSV Importer 项目」（62 号 3.2 步 1）                                |
| 3   | 点导入按钮    | 向导第 1 步             | 选择项目下拉（带项目图标）                                                                        |
| 4   | 选项目→下一步 | 第 2 步                 | 上传说明文案（名称/描述/优先级/日期/状态组列）+拖放区                                             |
| 5   | 上传 .xlsx    | —                       | 拒绝（Only .csv files are supported）                                                             |
| 6   | 上传合法 CSV  | 文件卡                  | 文件名/大小/Ready 徽标/移除 X                                                                     |
| 7   | 点 Import CSV | 执行                    | 作业状态 queued→processing→completed；工作项按列规则创建（状态组→项目状态、优先级枚举、日期解析） |
| 8   | CSV 含坏行    | 执行                    | 好行创建、坏行记录原因不整批失败                                                                  |
| 9   | 作业列表      | 查看                    | 历史作业（时间/状态/导入统计）可查                                                                |
| 10  | 非 admin      | 调导入 API              | 403                                                                                               |
