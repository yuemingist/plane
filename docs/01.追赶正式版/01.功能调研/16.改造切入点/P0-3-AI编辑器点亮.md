# P0-3 AI 编辑器点亮（Implementation Brief）

> 基线：main HEAD `41af2176d7`｜F-ID：**AI-01（编辑器基线）+ AD-05（god-mode AI 分区）**｜难度段位：S
> 证据源：30 号模块对比（U7、D-05-页面协同）、41 号、17 号（未涉考古项，LLM 管线为现存代码）、20 号路线图 P0-4

## 1. 目标与云端形态

为自托管实例配置 LLM key 后，编辑器 AI 能力回归可用，达到云端编辑器 AI 基线（30 号 U7 云端全集）：

- 页面编辑器右上 **AI summary** 按钮（生成整页摘要块，可重新生成/删除，30 号 `cloud-page-ai-summary`）；
- slash 菜单 **AI Block**（Advanced 组）；
- 编辑器侧边 **AI 手柄**（选区/块级 AI 菜单，editor 内 `AIFeaturesMenu`）。
  不含（归 P2-9）：全局 AI 工作台/上下文助手/Build 模式/AI filters。god-mode 顺带补齐 provider 下拉（现状仅 OpenAI 单区块，52 号实测）。

## 2. CE 现状（已实证）

**后端：LLM 管线三层贯通，只差 key**

- 端点：`apps/api/plane/app/views/external/base.py:148` `GPTIntegrationEndpoint`（project 级）与 `:184` `WorkspaceGPTIntegrationEndpoint`——`get_llm_config()`（:76）读 `LLM_API_KEY/LLM_PROVIDER/LLM_MODEL` 三个实例配置，未配 key 返回 400 "LLM provider API key and model are required"。
- Provider 抽象已支持三家：`apps/api/plane/app/views/external/base.py:69-73` `SUPPORTED_PROVIDERS = {openai, anthropic, gemini}`。
- 配置注册：`apps/api/plane/utils/instance_config_variables/core.py:216-243` `llm_config_variables`（LLM_API_KEY 加密、LLM_PROVIDER 默认 openai、LLM_MODEL 默认 gpt-4o-mini、GPT_ENGINE 已标 Deprecated）。
- god-mode（admin :3001）AI 分区现状仅 OpenAI 单区块（52 号实测 #15 与代码盘点吻合）。

**前端：AI 扩展整体存在但被开关硬关**

- 开关：`apps/web/hooks/use-editor-flagging.ts:37/41/45` —— document/liteText/richText 三种编辑器 `disabled: ["ai", "collaboration-cursor"]`。
- 扩展链完整：`packages/editor/src/extensions/side-menu.ts:50` `ai: aiEnabled` → `:90` 注入 `#ai-handle`；`packages/editor/src/plugins/ai-handle.ts:99`；AI 菜单组件 `packages/editor/src/components/menus/ai-menu.tsx`（`AIFeaturesMenu`，index.ts:7 导出）；类型 `packages/editor/src/types/ai.ts:12` `TAIHandler`。
- 残端：`apps/web/components/core/modals/gpt-assistant-popover.tsx:46` `GptAssistantPopover`（调 project 级 GPT 端点），仅剩一处消费 `apps/web/components/issues/issue-modal/components/description-editor.tsx:267`——旧「描述 AI 生成」残端，需处置（保留或统一到新 AI 面板）。

**实测基线**（30 号 U7）：CE 未配 key 时 slash 菜单无 AI 项、选区无 AI、无 AI summary——整体隐藏而非置灰；配 key 且开 flag 即亮。

## 3. 后端改动面

- **无模型/无迁移**。LLM key 走实例配置（god-mode 写入 `instanceconfig`），管线现成。
- 小修 1：`get_llm_response`（base.py）对 anthropic/gemini 的响应格式核对（各 provider 调用代码现存，需冒烟验证三 provider 均可返回）。
- 小修 2（可选）：god-mode admin 表单的 AI 分区补 LLM_PROVIDER/LLM_MODEL 下拉——`apps/admin` god-mode 表单按 `instance_config_variables` 生成，AI 分类键已注册（core.py:216 起），预期零改动或仅 UI 分组微调。
- 编辑器 AI 需要的端点核对：`AIFeaturesMenu` 的 TAIHandler 回调由 web 侧注入（section 4），对应调 `GPTIntegrationEndpoint`（external/base.py:148），路径核对 `apps/api/plane/app/urls/external.py:16-21`（已注册）。

## 4. 前端改动面

- `apps/web/hooks/use-editor-flagging.ts`：`"ai"` 从三处 disabled 移除（或改为读实例配置的 `has_llm_key` 派生状态——建议后者，实现"配了 key 才显示"与云端行为对齐；实例配置可经现有 instance info 端点暴露布尔位）。
- AI summary 按钮：`apps/web/components/pages/editor/` 头部操作区补按钮 + 生成摘要块组件（云端形态：正文顶部摘要块，可重新生成/删除，30 号 D-05-页面协同）。生成调用走页面正文→LLM 的封装（新 service 方法调 GPT 端点）。
- AI 手柄菜单动作表：为 `TAIHandler` 注入动作（改写/翻译/总结/继续写等），新组件目录 `apps/web/components/editor/ai/`。
- 残端处置：`gpt-assistant-popover.tsx` 保留在 issue-modal description-editor（功能仍可用）或摘除统一入口——建议保留不动，避免扩散改动面。
- i18n：AI 菜单键补进 locale（editor 命名空间）。
- 类型：无新增实体类型。

## 5. 测试面

- API：未配 key → 400；配 key → 三 provider 冒烟（openai/anthropic/gemini 各一次真实调用）；权限（GUEST 拒绝 GPT 端点）。
- 造数：无需特殊造数；需一份长文测试页（30 号 U7 用 12 节长文可复用）。
- E2E：① god-mode 配 key 后刷新页面，slash 菜单出现 AI Block；② 选中文本出现 AI 手柄，执行"总结"；③ 页面头部 AI summary 生成摘要块并可删除；④ 不配 key 的实例一切 AI UI 不出现（回归）。

## 6. 依赖与可并行性

- 无前置依赖，可并行；是 **P1-7（NL→PQL 转换）与 P2-9（自托管 AI 平台）的底座**（20 号关键路径：P0-4 + P1-7 → P2-9）。
- god-mode provider 下拉可与主链路并行。

## 7. 估算

| 维度              | 值                                                                                                                                    | 依据                                              |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| 新增/修改文件     | 后端 0-2（冒烟修正）；前端 6-8（flagging hook、AI summary 按钮与块、AI 手柄动作组件、service、i18n、instance info 布尔位）；admin 0-1 | 改动面清单                                        |
| 新增 model / 迁移 | 0 / 0                                                                                                                                 | 配置面现成                                        |
| 后端人天          | 0.5-1                                                                                                                                 | 管线现成，仅冒烟与响应格式核对                    |
| 前端人天          | 2-3                                                                                                                                   | flag 翻转极小；工作量在 AI summary 块与手柄动作表 |
| **合计**          | **2.5-4 人天（S）**                                                                                                                   | 与 20 号 S 段位一致                               |

## 8. 上游冲突面（风险：低-中）

- `packages/editor` 官方 09-28 做过 src/core 拆平（17 号高危区）——本条**不改 editor 包内部**（ai-menu/handle 已存在），只改 apps/web 侧注入与开关；editor 包零改动则冲突面近零。
- `use-editor-flagging.ts` 是小文件、上游低频改动——最小侵入。
- `apps/web/components/pages/editor/` 处 propel 迁移热点——AI summary 按钮放新组件文件，头部挂载点一行接入。
- 不要新建任何 `ee` 命名空间目录（17 号附：官方 2026-02 已清除 web/ee）。

## 9. 风险与未知项

1. editor 的 AI 菜单组件与后端 GPT 端点的协议（prompt/响应字段）是否完全咬合未运行验证——`TAIHandler.menu` 回调由 web 注入，理论可控；留 0.5 天联调余量。
2. 实例配置"是否已配 key"的暴露方式需设计（直接暴露布尔位 vs 编辑器调用失败静默）——建议布尔位（`has_llm_configured`），不泄露 key 本身。
3. Anthropic/Gemini 分支代码自 2024 起可能未经上游回归（无测试覆盖），三家冒烟必须做。
4. AI summary 的费用/配额控制 CE 无计费层——自用场景可接受，商业化需并入 P2-18。

## 10. 验收用例（对照 30 号 U7 云端基线）

1. Given 未配置 LLM key 的实例，When 打开页面编辑器，Then slash 菜单/选区/头部均无 AI 项（与现状一致，回归）。
2. Given god-mode 已配置 OpenAI key+model，When 打开页面编辑器输入 `/`，Then Advanced 组出现 AI Block。
3. Given 选中文本，When 点击 AI 手柄，Then 弹出 AI 动作菜单，执行"改写/总结"返回结果并可插入。
4. Given 打开任一页面，When 点头部 AI summary，Then 正文顶部出现"生成中"条并最终渲染摘要块，可重新生成与删除。
5. Given LLM_PROVIDER=anthropic，When 执行同上操作，Then 三 provider 冒烟全部可用。
6. Given GUEST 用户，When 直接 POST GPT 端点，Then 403。
7. Given Issue 创建弹窗描述区，When 点击 AI 残端按钮，Then 功能仍可用（不回归）。
