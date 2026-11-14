# P1-3 集成管道一期（GitHub + Slack）· 改造切入点 Implementation Brief

> 批次 3 · 任务 A（R5）· P1 组 ｜ 基线 main `41af2176d7` ｜ 编号按本批次指令（对应 20 号路线图 5.2 节「P1-5 集成管道一期」；F-ID：IG-02/IG-04/IG-09）
> 模块依据：62.集成导入深测/对比.md（三通道安装+安装即建 webhook）；50.集成生态/对比.md；18 号域文档 06（DeployBoard 复用面）/50 模块 P0-9 边界；**17 号考古对象 3（被删直连实现）**

## 1. 目标与云端形态

一期补齐两个高频集成的完整管道（62 号实测）：

- **GitHub**：`/settings/integrations/github/` 详情页（连接组织+连接按钮）；点击「连接」→ 本 tab Plane 自有 OAuth 身份握手（`/oauth/?request=…`）→ 新标签 github.com GitHub App（slug=makeplane）安装流；**安装尝试即自动注册活动 webhook**（`silo.plane.so/api/github/plane-webhook`，62 号 D-02）；安装后 work items↔GitHub issues 双向同步+状态回写（13 号 IG-02 口径）。
- **Slack**：`/settings/integrations/slack/`；安装 → slack.com/workspace-signin；Slack 内建单+评论同步（IG-04）；安装自动注册 `/api/slack/plane/events` webhook。
- **自建范围界定（本 brief 核心结论）**：云端执行体在**独立 silo 服务**（17 号考古：2024-03 `a852e3cc52` 把应用内集成后端整体裁剪 -1891 行，生产走 silo；silo 服务 CE 没有、闭源）。追赶=**在 CE API 内自建轻量「集成执行体」**（OAuth 回调+webhook receiver+同步 worker），不做独立微服务（先单体内聚，量大再拆）；三通道中一期只做**外部 OAuth**通道，GHES/GLE 自托管凭据弹窗与 Draw.io/Cursor/Claude 反向 OAuth 排二期（62 号 D-01）。
- 深测文档：`docs/01.追赶正式版/01.功能调研/62.集成导入深测/对比.md`（62 号 §3.4 安装流步骤表）；规格草案：无独立域（集成模型考古见 17 号对象 3）。

## 2. CE 现状（已验证）

- **模型俱在（可直接用）**：`apps/api/plane/db/models/integration/github.py:14` `GithubRepository`、`:32` `GithubRepositorySync`、`:54` `GithubIssueSync`、`:73` `GithubCommentSync`（GitHub 四表）；`apps/api/plane/db/models/integration/slack.py:14` `SlackProjectSync`（access_token/scopes/bot_user_id/webhook_url/team_id，unique(team_id, project)）；`Integration`/`WorkspaceIntegration` 基础表同目录。
- **API 层零路由**：`apps/api/plane/app/urls/` grep `integrations` 零命中（17 号：`app/urls/integration.py` 150 行完整路由随 `a852e3cc52` 删除）；前端 `apps/web/services/integrations/integration.service.ts:19,27,43` 调 `/api/integrations/`、`/workspace-integrations/`、`/importers/` 全部 404。
- **前端页面 404**：集成设置页不存在（50 号 U8 实拍 404）；`github.service.ts` 同为死代码。
- **考古引用（17 号对象 3，★★）**：被删直连实现 `app/views/integration/{base,github,slack}.py`（181+202+96 行，直接 `import requests` 调 GitHub/Slack REST，非 silo 代理）、`utils/integrations/{github,slack}.py` 可 `git show a852e3cc52^:<path>` 取块作架构参考；但 2024 后 serializer 权限/bgtasks 约定变化大，**管道需重写，模型层直接用**。silo 回归开源=无迹象。
- P0-9（集成设置目录页最小恢复）是前置：本条在其目录页/详情路由之上装真管道。

## 3. 后端改动面

1. **OAuth 安装状态机（自建 silo 对应物·单体）**：`Integration`/`WorkspaceIntegration` 上的安装生命周期（initiated→authorized→connected→error/disconnected）；Plane 自有 OAuth 身份握手端点（`/oauth/?request=` 简化版：工作区选择+授权确认页，scope=工作区资源读写+用户配置文件，对齐 62 号 4.3 scope 文案）；每集成 provider 配置（client_id/secret/回调 URL，god-mode 实例配置或 env）。
2. **GitHub App 安装流**：manifest 流或手动 App 配置（自托管不能写死 makeplane App——需支持自建 GitHub App：App ID/私钥/Webhook secret 配置项，字段面参照 62 号 4.1 GHES 弹窗）；安装回调→创建 WorkspaceIntegration+自动注册项目 webhook（对齐 D-02「安装即建 webhook」语义， webhook 记录走 P1-13 的 Webhook 表体系或 silo 等价内部通道）。
3. **webhook receiver**：`/api/integrations/github/webhook/`、`/api/integrations/slack/events/` 匿名端点（signature 校验）接收 GitHub/Slack 事件→Celery 任务。
4. **同步引擎**：GitHub issue→work item 创建/更新（状态映射表）、work item→GitHub issue 回写（创建/评论/关闭）、双向评论同步（四表 GithubRepositorySync/GithubIssueSync/GithubCommentSync 落映射）；Celery 任务+重试+幂等键。Slack 一期先做**通知推送**（工作项事件推频道，消费 SlackProjectSync.webhook_url），建单/评论同步二期。
5. **路由**：新增 `app/urls/integration.py` 独立模块（恢复被删路由的精简版：integrations 列表/详情、workspace-integrations、github install/callback、slack install/callback）；外部 API 层不动。

## 4. 前端改动面

1. 集成目录页/详情页（P0-9 交付的静态目录上）接真数据：GitHub/Slack 卡片+详情页（logo+描述+连接/安装按钮）+安装状态徽标。
2. 安装流前端：跳转第三方授权页（新标签）+回调落地页+错误态（62 号 3.4 步骤 1-2 形态）；Plane 自有 OAuth 授权页（工作区下拉+权限文案+接受/取消）。
3. 安装后配置视图：GitHub 连接组织/仓库列表+状态映射（一期可简化为默认映射）；Slack 频道选择+通知开关。
4. store/service：`integration.service.ts` 死端点改指向新 API；新增安装状态轮询。
5. i18n：新增集成文案键（不重排既有键）。

## 5. 测试面

- 后端：OAuth 回调 CSRF/state 校验（上游 2026-10 安全波次有 OAuth state 修复 #10069，必须对齐）；webhook signature 校验+SSRF 防护；同步幂等（重复事件不重复建工作项）；状态映射正确；断连清理（WorkspaceIntegration 级联+webhook 注销）。
- 前端：安装流状态机、错误回显。
- 集成（人工）：真实 GitHub App（测试仓库）双向同步跑通；Slack 通知到达；取消授权后停止同步。

## 6. 依赖与并行性

- **前置**：**P0-9**（集成目录页最小恢复）——本条在其上装管道；**P1-13**（Webhook V2 观测）软相关——集成安装产生的 webhook 可被观测 UI 展示。
- **可并行**：GitHub 与 Slack 两管道并行（两套 OAuth+receiver+worker）；OAuth 授权页组件可与 P2-1 OIDC 共享设计。
- **被依赖**：D29（工作项 Development 面板：branch/PR 关联展示）由 GitHub 同步解锁（20 号路线图关键路径）；MCP 连接器（IG-08）架构上复用本条 OAuth/凭据体系。

## 7. 估算

| 项               | 量                                                                  | 依据                                                                                                         |
| ---------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| 文件数           | 后端 ~22（oauth 状态机+2 receiver+同步 worker+urls+迁移）、前端 ~15 | 17 号被删直连 479 行视图作参考+62 号三通道流程                                                               |
| model 数         | 0-1（复用四表；可能加 InstallationState 轻表或 JSON 字段）          | 模型俱在                                                                                                     |
| 迁移数           | 0-1                                                                 | 仅 provider 配置字段（可走 instance config 免迁移）                                                          |
| 后端人天         | 20                                                                  | OAuth 状态机 4+GitHub App 流与自动 webhook 4+同步引擎 8+Slack 通知 2+receiver 安全 2；被删代码参考省 ~4 人天 |
| 前端人天         | 9                                                                   | 目录/详情/授权页/配置视图（P0-9 已有壳）                                                                     |
| **合计（一期）** | **29 人天**                                                         | XL 段位（首集成 L≈16-18，逐个叠加）；GitLab/Sentry/Bitbucket 各 +8-12 人天二期                               |

## 8. 上游冲突面（风险：低）

- 新增 urls/views 文件=低；唯一交叉点是「安装即建 webhook」要写 Webhook 表（P1-13 会扩事件枚举，模型不动，冲突小）。
- instance_config_variables 追加 provider 配置键=低（35 键尾部追加）。
- 前端集成页是 P0-9 新建页面=低。
- 官方先做掉风险：17 号判定 silo 未回归开源，无交叠。

## 9. 风险与未知

1. **自托管 GitHub App 前置条件**：自托管用户须自建 GitHub App（Manifest 流可降低门槛）——云端用官方 makeplane App，CE 必须支持任意 App 配置，这是与云端形态的必然差异（需在文档/设置页明示）。
2. silo 对应物的边界：一期单体内聚，若同步吞吐大（大组织）需拆 worker——架构预留（Celery 队列独立 routing key）。
3. 云端 OAuth 握手 `/oauth/?request=` 内部协议未知（62 号仅记录到起点）——追赶自定协议，接受页文案对齐 4.3。
4. GitHub 同步的状态/优先级映射规则官方未公开——一期提供可配置映射 UI 兜底。
5. 62 号待验证：重复安装幂等、Build your own 表单——均排二期。
6. Slack 建单与评论同步（IG-04 完整口径）一期未含，需在验收时明确「一期=通知推送」。

## 10. 验收用例（对照 62 号 §3.4）

| #   | Given                     | When        | Then                                                           |
| --- | ------------------------- | ----------- | -------------------------------------------------------------- |
| 1   | CE 工作区设置             | 打开集成页  | 目录页可见（P0-9），GitHub/Slack 卡片有「连接/安装」           |
| 2   | GitHub 详情页             | 点「连接」  | 跳 GitHub App 安装起点；不完成授权安全退出无残留               |
| 3   | 完成 GitHub App 安装      | 回到 CE     | WorkspaceIntegration 创建；webhook 自动注册且状态=活动（D-02） |
| 4   | 已连接项目建 GitHub issue | —           | CE 生成对应工作项（状态映射生效），同步留痕表有记录            |
| 5   | CE 工作项关联仓库后关闭   | —           | GitHub issue 状态回写关闭                                      |
| 6   | GitHub issue 新评论       | —           | 工作项评论同步；CE 评论 → GitHub 亦同步                        |
| 7   | Slack 详情页              | 安装授权    | SlackProjectSync 创建（team_id+项目）；频道收到工作项事件通知  |
| 8   | 断开集成                  | 行操作断连  | 双向同步停止、webhook 注销、token 清理                         |
| 9   | 伪造 webhook 请求         | 无签名 POST | 401/签名校验拒绝                                               |
| 10  | 重复点击安装              | 二次授权    | 幂等：不产生重复 WorkspaceIntegration                          |
