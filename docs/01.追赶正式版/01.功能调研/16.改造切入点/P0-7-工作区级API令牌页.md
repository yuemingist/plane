# P0-7 工作区级 API 令牌页（Implementation Brief）

> 基线：main HEAD `41af2176d7`｜F-ID：**AP-01**｜难度段位：S
> 证据源：54 号模块对比（D-01-API）、62 号（1.5/1.6、D-09-集成导入）、20 号路线图 P0-7

## 1. 目标与云端形态

在工作区设置 Developer 分组补「API 令牌」管理页（云端 `/settings/access-tokens`，54 号 `cloud-api-tokens-2026-11-14.png`：说明文案「创建令牌，用于验证来自外部系统的 API 请求。」+ 添加访问令牌 + 列表），管理员可统一查看/创建/吊销工作区成员的访问令牌。**云端实测结论（54 号待验证闭环）：云端该页创建的仍是同形态 personal token，无服务端 API key/OAuth apps 分级**——CE 只需"多一个工作区级管理入口"，不涉及新令牌体系。

## 2. CE 现状（已实证）

**已有（组件同源，账号级完整可用）**

- 组件：`apps/web/components/settings/profile/content/pages/api-tokens.tsx:17-20`（`APITokenService` + `CreateApiTokenModal` + `ApiTokensTable`）——个人访问令牌页签完整。
- service：`packages/services/src/developer/api-token.service.ts:22/36/50/64`（`/api/users/api-tokens/` CRUD）。
- 后端：`apps/api/plane/app/urls/api.py:11-18`（`users/api-tokens/`、`users/api-tokens/<uuid:pk>/` → `ApiTokenEndpoint`）；模型 `apps/api/plane/db/models/api.py:23` `class APIToken`。
- 个人设置侧边栏：`apps/web/components/settings/profile/sidebar/item-categories.tsx:32`（"api-tokens" 图标注册）。

**缺失**

- 工作区设置侧边栏无「API 令牌」项：`packages/constants/src/settings/workspace.ts:58-65` `WORKSPACE_SETTINGS` 仅 webhooks（DEVELOPER 分组只有 webhooks，`:79-89` GROUPED 定义）；`apps/web/components/settings/workspace/sidebar/item-icon.tsx` 无 token 图标映射。
- 后端无"工作区全体成员令牌列表"端点（现有端点是 `users/...` 自查口径；APIToken 模型无 workspace FK 的管理视角——需确认 APIToken 归属字段，见风险 1）。
- 路由：`settings/(workspace)/` 下无 access-tokens 目录（仅 exports/integrations/members/webhooks/billing 五目录，rg 实证）。

**考古**：17 号 12 对象未单列 API 令牌（无考古价值——组件同源，纯补页面）；0070 迁移曾顺带给 APIToken 加字段（17 号对象 11a），无功能含义。

## 3. 后端改动面

| 项                 | 文件                                                                            | 说明                                                                                                                                                                                                                           |
| ------------------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 工作区令牌列表端点 | `apps/api/plane/app/views/api.py`（或新文件）+ `apps/api/plane/app/urls/api.py` | `GET workspaces/<slug>/workspace-api-tokens/`（Admin only）：联表 `APIToken → User → WorkspaceMember` 过滤当前工作区成员；返回 token 元数据（label/description/expired_at/created_at/last_used？——last_used 若模型无则不显示） |
| 权限               | `@allow_permission([ROLE.ADMIN], level="WORKSPACE")`                            | 仅 Admin（对齐云端工作区级入口定位）                                                                                                                                                                                           |
| 吊销               | 复用现有 DELETE `users/api-tokens/<pk>/`                                        | 工作区页删除=同端点（Admin 可删成员令牌需在 view 权限上放宽或在 workspace 端点提供 DELETE）                                                                                                                                    |

迁移：**0 个**（若 APIToken 需加 workspace 冗余列则 1 个——见风险 1，倾向不加，用联表）。

## 4. 前端改动面

- 路由：新建 `apps/web/app/(all)/[workspaceSlug]/(settings)/settings/(workspace)/access-tokens/page.tsx`（+header.tsx）。
- 常量注册：`packages/constants/src/settings/workspace.ts` 增 `access-tokens` 项（DEVELOPER 分组）+ i18n 键（`workspace-settings.json` 或对应命名空间，22 locale）。
- 图标：`apps/web/components/settings/workspace/sidebar/item-icon.tsx` 增映射。
- 页面内容：复用 `components/api-token/` 的 Table/Modal（`apps/web/components/api-token/tokens-table.tsx`、`modal/create-token-modal.tsx`），数据源换工作区端点；标题/文案对齐云端。
- 权限：非 Admin 显示 NotAuthorizedView（参考 integrations page 模式）。

## 5. 测试面

- API：Admin 列出工作区成员全部令牌；Member/Guest 403；删除成员令牌成功且令牌立即失效（用令牌调 API 401）；跨工作区令牌不串列。
- 造数：两个用户各建 1 令牌。
- E2E：工作区设置→开发者→API 令牌页显示 2 条；创建（过期时间+永不过期开关，云端弹窗仅过期日期一档——对齐 CE 现有组件即可）；删除后失效。

## 6. 依赖与可并行性

无前置依赖，可并行；与 P0-9（集成目录页）同在 Developer/连接设置区，可同批交付但代码无耦合。

## 7. 估算

| 维度              | 值                                                                                              | 依据                               |
| ----------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------- |
| 新增/修改文件     | 后端 2-3（workspace 列表端点+urls）；前端 5-6（路由 2、常量 1、图标 1、页面 1、i18n 22 locale） | 改动面清单                         |
| 新增 model / 迁移 | 0 / 0（联表方案）                                                                               |                                    |
| 后端人天          | 1                                                                                               | 一个只读列表端点+权限              |
| 前端人天          | 1.5-2                                                                                           | 组件复用为主，工作在路由/常量/文案 |
| **合计**          | **2.5-3 人天（S）**                                                                             | 与 20 号 S 段位一致                |

## 8. 上游冲突面（风险：低）

- `packages/constants/src/settings/workspace.ts` 是官方 propel/设置导航同步触碰点（62 号：云端设置导航分组还在扩张）——追加一项，冲突面一行级。
- `components/api-token/` 复用不改；新页面文件全新——高隔离。

## 9. 风险与未知项

1. **APIToken 与工作区的归属关系**：模型（`db/models/api.py:23`）可能无 workspace 直接 FK——方案用 `user → workspace_member` 联表过滤；若用户属于多工作区，令牌本身是账户级的，工作区页展示"属于本工作区成员的令牌"（语义与云端一致——云端该页创建的也是 personal token，54 号 D-02 结论"无实质差异"）。开发时先读模型确认字段。
2. 云端工作区级创建的令牌是否有 workspace 绑定语义未实测（创建弹窗仅过期日期，54 号 1.5）——按"仅管理视角"实现，不引入新语义。
3. 令牌 last_used 时间戳 CE 模型若无，列表少一列——不做迁移补列（P2 再议）。

## 10. 验收用例（对照 54 号 D-01-API / 62 号 1.5）

1. Given Admin，When 打开 `/demo-workspace/settings/access-tokens/`，Then 显示说明文案+「添加访问令牌」+成员令牌列表（对齐 `cloud-api-tokens` 空态/有数据态）。
2. Given 工作区设置侧边栏 Developer 分组，Then 出现「API 令牌」项（与 Webhooks 并列）。
3. Given Admin，When 在工作区页创建令牌（默认永不过期），Then 生成成功且个人令牌页同步可见（同一令牌池）。
4. Given Member，When 访问该页，Then 未授权视图。
5. Given Admin 删除成员令牌，When 该成员用旧令牌调 API，Then 401（立即失效）。
6. Given 账号级个人访问令牌页（现有），When 操作，Then 行为不变（零回归）。
