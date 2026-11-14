# P1-10 Recurring 重复工作项 · 改造切入点 Implementation Brief

> 批次 3 · 任务 A（R5）· P1 组 ｜ 基线 main `41af2176d7` ｜ 编号按本批次指令（对应 20 号路线图 5.2 节「P1-10 重复工作项 Recurring」；F-ID：AU-04）
> 模块依据：58.自动化与工作流深测/对比.md（D-09+§3.5 全字段实测）；18 号域文档 03 §1.5/§6

## 1. 目标与云端形态

项目设置 → 自动化分组 →「重复工作项」（`/settings/projects/{id}/recurring-work-items`，58 号 D-09/§3.5 实测）：

- **列表页**：说明文案「按重复计划自动创建工作项——适用于站会、报告或任何常规事项。」+创建按钮；行=图标+规则名+频率短语（repeats every day，英文）+…菜单（**编辑/删除，无暂停/启停开关**）；**列表不显示下一次生成时间**。
- **创建/编辑整页表单**（全字段，58 号 4.6）：工作项类型 chip（默认 Task 可换）+标题\*+描述+属性 chips（状态默认 Backlog/优先级/负责人/标签）+计划区（开始日期\***必填红框校验**/结束日期选填/repeats 下拉）。
- **repeats 频率 5 项**：Daily / Weekly / Monthly / Yearly / Custom（英文未翻译；Custom 子配置未展开）。
- **生成语义（关键实测）**：**开始日期当天立即生成首个工作项**；编辑页「活动」区记录生成历史（「successfully created a recurring work item SURVEY-4.」链接到生成的工作项）；生成的工作项按预置属性（状态/优先级/负责人/标签）创建。
- 深测文档：`docs/01.追赶正式版/01.功能调研/58.自动化与工作流深测/对比.md`（§1.4/§3.5/§4.6+截图 6 张）；规格草案：`18.数据模型与API规格草案/03.重复工作项与自动化.md` §1.5（**SDK 无 recurrence 模型**——UI 独有，追赶按独立实体设计）。

## 2. CE 现状（已验证）

- **全仓库零命中**：grep `recurring|recurrence` 于 apps/api+apps/web 仅命中 `apps/api/plane/celery.py:47` 的注释「Intra day recurring jobs」（与功能无关）——无模型/路由/组件/文案（58 号 §6.4 结论维持）。
- **可复用基建**：Celery beat（`apps/api/plane/celery.py:46` beat_schedule+`:124` DatabaseScheduler——支持运行时增删任务条目，重复项调度可走 DB scheduler 或每日全量扫描两种方案）；工作项创建服务（属性 chips 对应的 issue create 管道）；活动流（`bgtasks/issue_activities_task.py` 模式可复用于生成日志）。
- **文案资产**：`packages/i18n/src/locales/en/automation.json` 的 schedule 区（frequency_daily/weekly/monthly+时区+cron 表达式校验/预览文案）可直接复用于 repeats 频率与 Custom cron 子配置——**官方自动化 schedule 组件的文案结构证明 Custom 频率=cron 表达式**（`schedule_mode_fixed`/`schedule_mode_cron`/`cron_expression_placeholder: "0 9 * * 1-5"`），18 号 §6 的疑问（Custom 是否 cron）由此解。
- **考古引用**：17 号对象表无 recurring 条目（对象 11b 同为「不适用，从零建」类）；13 号 AU-04「无任何 recurrence 代码」核实成立。

## 3. 后端改动面

1. **模型（2 新表，1 迁移）**：`RecurringWorkItem`（name/description_html/project FK/work_item_type FK/预置属性 state/priority/assignees M2M/labels M2M/start_date **必填**/end_date 可空/recurrence_type enum DAILY|WEEKLY|MONTHLY|YEARLY|CUSTOM/recurrence_config JSON（weekly 星期几、monthly 几号、custom cron 表达式）/is_active/last_generated_at/next_run_at）；`RecurringWorkItemLog`（recurring FK/generated_work_item FK/生成时间/状态——对应云端活动区生成历史）。
2. **调度方案（建议）**：**每日全量扫描 beat 任务**（不逐规则动态注册 beat——DatabaseScheduler 动态任务运维复杂；扫描 `next_run_at <= today` 的 active 规则）→ 生成工作项（当天立即生成首个=创建规则时 start_date=今天即跑一次或创建事务内同步生成首个）→ 计算 next_run_at（rrule/自写：daily+1d、weekly 按 config 星期、monthly 按几号、yearly+1y、custom cron 解析）→ 写 Log+活动流（actor=创建者或系统，文案对齐「successfully created a recurring work item」）。
3. **API**：项目级 CRUD `/api/workspaces/{slug}/projects/{id}/recurring-work-items/{id}/`+logs 子列表（`.../{id}/logs/`）；校验：start_date 必填（表单红框对应 400 校验）、end_date>start_date、custom cron 合法性校验。
4. 生成的工作项标题默认=规则名（云端实测 SURVEY-4 生成项未展开属性，按规则名+预置属性实现）。

## 4. 前端改动面（apps/web）

1. 设置侧边栏自动化分组追加「重复工作项」项（导航组件加项）+`/settings/projects/{id}/recurring-work-items/` 列表页（空态文案+行+菜单 编辑/删除）。
2. 创建/编辑**整页**表单（路由 `/recurring-work-items/create/` 与 `/…/{id}/edit/`）：类型 chip+标题+描述+属性 chips（复用工作项属性选择组件）+计划区（日期日历组件已有：58 号 3.5 步 5 描述年/月下拉+翻月）+repeats 下拉（5 项；Weekly/Monthly/Custom 子配置：星期几/几号/cron 输入+校验+预览——文案全在 automation.json schedule 区）。
3. 编辑页下方**活动区**：生成历史列表（时间+指向生成工作项的链接，58 号 3.5 步 8 形态）。
4. store/service：新建 recurring.store/service；i18n：recurring 命名空间键（频率名可中文化——云端英文未翻译，CE 补译优于云端）。

## 5. 测试面

- 后端 pytest：频率计算（daily/weekly 多选星期/monthly 月末边界/yearly 闰年/custom cron 解析+非法 cron 400）、当天立即生成（start_date=today 创建→首项存在）、end_date 停止、去重（重复执行同日不双生成——last_generated_at 幂等）、预置属性正确落库、时区（跨时区项目的「当天」语义）。
- 前端：必填校验（缺 start_date 红框不提交——58 号 3.5 步 4）、cron 校验预览。
- 集成：建规则→人工调任务→工作项生成+活动区记录+活动流留痕。

## 6. 依赖与并行性

- **前置**：无硬依赖（beat/创建服务全在）；与 P1-1 共享 beat 与活动流基建（建议同批设计调度模块）。
- **可并行**：模型/调度（后端）与表单（前端）并行。
- **被依赖**：无；P2-14 工作流/审批不依赖本条；SDK v2 无该资源（18 号 §3 端点表标注「追赶自建 CRUD」）。

## 7. 估算

| 项       | 量                                                                                                    | 依据                                                                     |
| -------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| 文件数   | 后端 ~10（2 models+serializers+views+urls+迁移+task）、前端 ~12（列表+整页表单+活动区+store/service） | 58 号表单 7 字段+频率 5 项                                               |
| model 数 | 2                                                                                                     | 18 号 §1.5（结构中可信度，字段面照 UI 实测）                             |
| 迁移数   | 1                                                                                                     |                                                                          |
| 后端人天 | 9                                                                                                     | 调度/频率计算 4（月末/闰年/cron 边界多）+API 2+生成管道与活动流 2+校验 1 |
| 前端人天 | 6                                                                                                     | 整页表单+属性 chips+活动区                                               |
| **合计** | **15 人天**                                                                                           | L 段位（58 号 D-09 判 L）                                                |

## 8. 上游冲突面（风险：低）

- 全新模型/urls/组件=低；唯一既有文件触碰=设置侧边栏导航数组追加+celery.py beat_schedule 尾部加一条=低。
- 官方先做掉风险：无（17 号 AU 域零提交）。

## 9. 风险与未知

1. **Weekly/Monthly/Yearly/Custom 子配置未逐个展开**（58 号待验证 2）——按 automation.json schedule 文案结构（星期几/几号/时区+cron）设计，云端复核修正。
2. **生成时刻**（当天几点）未实测（58 号待验证 5）——按项目时区早晨（如 08:00）或跟随服务器时区配置；列表不显示下次生成时间（云端行为），CE 亦不显示。
3. **与 Automation 模型的关系未定**（18 号 §1.5：推断可由调度型触发器承载，SDK 无独立资源）——**按独立实体设计**（追赶自定），表结构与 Automation 分离，避免引擎耦合。
4. 生成的工作项与规则的关联（生成项是否记录来源规则元数据）未实测——Log 表保留关联，工作项端可后续加徽标（不实测对齐，增强项）。
5. 暂停/启停：云端无开关（仅编辑/删除）——CE 对齐；is_active 字段保留作内部语义（软停用）。

## 10. 验收用例（对照 58 号 §3.5）

| #   | Given                            | When               | Then                                                                                                     |
| --- | -------------------------------- | ------------------ | -------------------------------------------------------------------------------------------------------- |
| 1   | 项目设置自动化分组               | 打开               | 「重复工作项」入口出现；空态「暂无循环工作项」+创建按钮                                                  |
| 2   | 创建表单                         | 不填开始日期点创建 | 开始日期 chip 变红、不提交（58 号步 4）                                                                  |
| 3   | 填齐+开始日期=今天+repeats=Daily | 点创建             | 跳回列表（行=repeats every day）+toast；**当天已生成首个工作项**                                         |
| 4   | 编辑该规则                       | 查看活动区         | 「successfully created a recurring work item <序列号>」+链接到生成项+「created the recurring work item」 |
| 5   | repeats=Weekly 勾周一/周三       | 保存               | 每周一/周三生成（cron/星期计算正确）                                                                     |
| 6   | repeats=Custom 填非法 cron       | 保存               | 400 校验拒绝+预览不渲染                                                                                  |
| 7   | 设置 end_date=下周               | 到期后             | 停止生成                                                                                                 |
| 8   | 重复执行扫描任务同日             | —                  | 不重复生成（幂等）                                                                                       |
| 9   | 行菜单                           | 查看               | 仅 编辑/删除（无暂停开关，对齐云端）                                                                     |
| 10  | 生成项属性                       | 打开生成的工作项   | 状态=Backlog、负责人/标签/优先级按规则预置；描述一致                                                     |
