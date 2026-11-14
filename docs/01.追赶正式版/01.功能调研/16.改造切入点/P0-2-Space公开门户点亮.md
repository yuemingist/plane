# P0-2 Space 公开门户点亮（Implementation Brief）

> 基线：main HEAD `41af2176d7`｜F-ID：**SP-01、PG-09、IN-02、SP-04**｜难度段位：M（P1-8/P1-9 的前置）
> 证据源：17 号考古对象 5、53 号模块对比、55 号 U6 全流程、18 号草案 05/06、13 号映射表

## 1. 目标与云端形态

补齐 CE 公开提交/公开访问链路的三处断裂，让 Space（:3002）成为可用的对外门户：
① 公开页面发布（云端形态：53 号 `cloud-page-publish-modal/-published-modal/-public-page-site` ——编辑器头部「发布」一键生成 sites.plane.so/pages/{anchor} 只读页，免费无付费墙）；
② 公开 Intake 表单（55 号 U6 步骤 9：sites.plane.so/intake/{anchor}，Name/Email/Title/Description 四字段 + 品牌横条）；
③ 修复项目发布链接崩溃（55 号 U6 步骤 3：`/spaces/issues/{anchor}` 渲染「Yikes! That doesn't look good.」，后端公开 API 实测正常——纯 space 前端 bug）。
不含（归 P1）：视图发布公开站点（P1-8）、space 首页站点目录与主题打磨（P1-9）。

## 2. CE 现状（已实证）

**模型层（7 实体全支持）**

- `apps/api/plane/db/models/deploy_board.py:20-29`：`TYPE_CHOICES` 枚举 `project/issue/module/cycle/page/view/intake` 七实体 + anchor（uuid4().hex）+ 评论/表情/投票三开关；迁移 0 个需要。
- 发布管理端点已在：`apps/api/plane/app/urls/project.py:113-120`（`project-deploy-boards/` CRUD）。
- `apps/api/plane/db/models/project.py:350/370`（ProjectDeployBoard、ProjectPublicMember，18-06 号）。

**后端公开 API**

- space 挂载点：`apps/api/plane/urls.py:20` `path("api/public/", include("plane.space.urls"))`。
- `apps/api/plane/space/urls/__init__.py:7-10`：**仅注册 intake/issue/project/asset 四组**——`space/views/{cycle,module,state,label,meta}.py` 五个视图文件齐全但**从未接线**（17 号考古：08d9e95a86 2024-07 重构预留，公开路由从未存在，非被裁剪）。
- 公开 Intake 路由在（`space/urls/intake.py:16-28`），但 401 根因已定位：`apps/api/plane/space/views/base.py:65/151` `permission_classes = [IsAuthenticated]`——匿名提交被拒（55 号 U6 步骤 5 实测 401）。
- 页面公开读取：space 侧无 page 公开路由（需按 anchor 新挂只读投影）。

**space 前端（React Router，仅 3 条路由）**

- `apps/space/app/routes.ts:8-13`：index（占位页「Nice! Just one more step.」）、`:workspaceSlug/:projectId`（跳转板）、`issues/:anchor`（崩溃点）——无 intake/pages/boards 公开表单与页面路由。
- 项目发布跳转板 `apps/space/app/[workspaceSlug]/[projectId]/page.tsx:24-43`：取 settings 后 `redirect(/issues/{anchor})`，崩溃发生在 `issues/[anchor]/page.tsx` 渲染链（55 号 U6 步骤 3 实测）。

**web 前端（发布入口缺失）**

- 页面行菜单：`apps/web/components/pages/dropdowns/actions.tsx:46-52` 仅 toggle-lock/copy-markdown/open-in-new-tab/copy-link/make-a-copy/archive-restore——**无发布项**（53 号 D-01-Space：行菜单 6 项无发布）。
- 视图发布 stub（`apps/web/components/views/publish/use-view-publish.tsx:7-13` publishContextMenu=undefined）属 P1-8，本条不动。

**考古结论引用**（17 号对象 5）：公开 cycle/module 路由"从未存在"；死视图文件是"干净预留件"，挂路由即可；公开 pages 发布路由同样从未存在（`--all` 检索零命中）。

## 3. 后端改动面

| 项                         | 文件                                                          | 说明                                                                                                                                                                                        |
| -------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 公开匿名权限               | `apps/api/plane/space/views/base.py`                          | 新增 `IsAnonymousAllowed`/`AllowAnyForPublished` 权限类或把 intake 公开 viewset 的 permission 改为按 anchor+DeployBoard 发布态校验（**最小侵入：只改 intake 公开 viewset，不动全局 base**） |
| 挂载公开 cycle/module 路由 | `apps/api/plane/space/urls/__init__.py` + 新 `urls/boards.py` | include 现成 `space/views/cycle.py`、`module.py`（序列化器泄露面审查：17 号提示）                                                                                                           |
| 页面公开投影               | 新文件 `apps/api/plane/space/views/page.py` + `urls/page.py`  | `GET anchor/<anchor>/pages/`（按 DeployBoard entity_name=page 取 Page 只读字段；复用 app/serializers/page.py 的只读投影）                                                                   |
| 发布入口 API               | 无新文件                                                      | 复用 `project-deploy-boards/`（POST entity_name="page"）；仅 serializer 确认 page 分支放行                                                                                                  |
| 权限/安全                  | space serializers                                             | 公开面字段白名单（防 workspace 泄露），加节流（Throttle）防刷                                                                                                                               |
| Celery/feature             | 无                                                            | 无新任务、无新开关（is_comments/reactions/votes 开关已在 DeployBoard）                                                                                                                      |

迁移：**0 个**。

## 4. 前端改动面

**space（apps/space）**

- 修崩溃：`apps/space/app/issues/[anchor]/page.tsx` 渲染链排错（SSR loader→组件；重点排查 anchor 数据缺失分支与 Provider 装配），55 号已给出复现路径。
- 新路由：`routes.ts` 增 `issues/:anchor/intake`（公开表单页，四字段 Name/Email/Title/Description——对应后端 intake-issues POST，extra 承载 Email）与 `pages/:anchor`（只读文档渲染，复用 editor 只读 renderer）。
- 表单页组件（新目录 `apps/space/app/intake/`）、页面只读渲染（新 `apps/space/app/pages/[anchor]/`）。
- i18n：space 文案键补进对应 locale。

**web（apps/web）**

- 页面发布入口：`apps/web/components/pages/dropdowns/actions.tsx` 增"发布页面"项 + 新弹层组件（复用项目发布弹窗形态：URL 展示/复制/取消发布——参照 `components/publish` 现有项目发布 Modal 模式）。
- service：新增 page publish 调用（POST project-deploy-boards）。
- 类型：`packages/types/src/` 补发布响应类型。

## 5. 测试面

- API：匿名 POST intake-issues 成功落库 source=IN_APP→（放宽为 FORM）→ 分诊端可见；未发布 anchor 的匿名访问 404；评论/表情/投票开关关闭时公开互动被拒；公开序列化器不泄露 workspace 敏感字段。
- 造数：沿用 WEB 项目已发布 board（U6 遗留）；需新建一条测试 Page 发布态。
- E2E：① 发布项目→无痕窗口打开链接→列表可浏览（崩溃修复）；② 发布页面→打开公开 URL→只读渲染；③ Intake 表单匿名提交→登录态分诊接受→成为正式工作项（对应 55 号 U6 步骤 1-8 全链路）。

## 6. 依赖与可并行性

- 无前置依赖，可并行；是 **P1-8（视图发布）/P1-9（站点体验打磨）的硬前置**（20 号关键路径）。
- 修复崩溃 bug 与挂路由两项可拆分并行（不同 app：space vs api）。

## 7. 估算

| 维度              | 值                                                                                                                                                           | 依据                                                                 |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| 新增/修改文件     | 后端 6-8（权限类、2 个新公开视图+urls、space serializer 白名单核对）、space 前端 6-8（routes、修复、2 个新页面+表单）、web 3-4（入口、弹层、service、types） | 改动面清单                                                           |
| 新增 model / 迁移 | 0 / 0                                                                                                                                                        | DeployBoard 7 实体已支持                                             |
| 后端人天          | 3-4                                                                                                                                                          | 视图文件现成，主要工作量在权限放宽的安全设计与泄露面审计             |
| 前端人天          | 6-8                                                                                                                                                          | space 崩溃排修（未知 bug 工作量波动）+ 两个新公开页面 + web 发布弹层 |
| **合计**          | **9-12 人天（M）**                                                                                                                                           | 与 20 号 M 段位一致                                                  |

## 8. 上游冲突面（风险：中）

- `apps/api/plane/space/` 近 90 天上游几乎未触碰（17 号：死文件 2024-07 至今未动）——挂路由冲突面小。
- `apps/space/app` 在官方 propel 同步范围内（#10038 "sync web, Space and Admin UI with the Propel design system"）——**新页面放新目录**、修改 `issues/[anchor]/page.tsx` 时尽量小 diff。
- `space/views/base.py` 是公开安全面：不要全局放开 permission_classes；用独立权限类包裹（17 号同步策略：新端点新文件）。
- web `pages/dropdowns/actions.tsx` 属官方菜单重构热点（propel 迁移），发布入口用"新增菜单项"而非改既有项。

## 9. 风险与未知项

1. space 崩溃根因未在代码层定位（实测仅现象）——排修时间有 ±2 天波动，是本条最大不确定项。
2. 公开匿名写接口（intake POST）放开后的滥用风险：需加节流与 DeployBoard 发布态强校验；Email 字段云端有但 CE IntakeIssue 无列——放 `extra` JSON（18-05 号 §5.4 建议）。
3. 公开 cycle/module 序列化器的字段泄露面未逐一审计（17 号遗留），上线前需安全过一遍。
4. 云端公开站点为独立域 sites.plane.so；CE 保持 :3002 单域——架构差异已判定可接受（53 号 D-02-Space）。

## 10. 验收用例（对照 55 号 U6 步骤表 / 53 号流程）

1. Given 已发布项目，When 无痕窗口访问 `/spaces/issues/{anchor}`，Then 页面正常渲染工作项列表（不崩溃）。
2. Given WEB 项目，When 页面行菜单点「发布页面」→确认，Then 弹窗展示公开 URL 并可复制。
3. Given 已发布页面，When 无痕访问公开 URL，Then 只读渲染正文，头部显示已发布态；取消发布后访问 404。
4. Given 未发布页面，When 访问其 anchor URL，Then 404（不泄露存在性）。
5. Given Intake 已发布项目，When 无痕访问公开表单页，Then 显示 Name/Email/Title/Description 四字段与项目卡。
6. Given 公开表单，When 匿名提交一条请求，Then 返回成功，登录态 Intake「未处理」列表 +1（source 可识别）。
7. Given 分诊端，When 接受该匿名请求，Then 成为正式工作项且活动流留痕 "accepted this work item from intake"（55 号 U6 步骤 7-8）。
8. Given DeployBoard is_comments_enabled=false，When 公开页尝试评论，Then 无评论入口/API 403。
