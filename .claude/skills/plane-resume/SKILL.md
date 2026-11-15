---
name: plane-resume
description: Plane 项目开工恢复。每次新会话开始、接手 Plane 任务或不确定当前阶段/规则时使用：核对 git 状态，按固定顺序读项目记忆与约定，5 行汇报现状后再动手。
---

# plane-resume：开工恢复

目标：5 分钟内恢复上下文，不全量阅读，不改任何文件。

## 步骤

1. **git 状态**（仓库 `~/Develop/plane`）：`git status -sb`、`git fetch origin`。
   - 看分支：文档与方案阶段应在 `main`；编码阶段应在 `feat/<YUE-编号>-简述` 或约定的 `feat/<step>-简述` 分支。
   - 落后 origin → `git pull --ff-only`；有冲突或本地有非本次任务的改动 → **停下汇报**，不 reset、不覆盖。
2. **按顺序读**（够用即止）：
   1. `AGENTS.md` 末尾「Plane 项目」小节（上游开发规范在其上方，写代码时再读）
   2. `docs/项目管理/07.项目记忆.md`（稳定事实、决策索引、待确认）
   3. `docs/项目管理/08.工作约定.md`（git、提交、凭据、何时问明哥）
   4. `docs/项目管理/09.角色与分工.md` 中**自己的**角色行
   5. 任务相关资料：任务书指定的文件；当前 Step 先看其 `00.子项目章程.md`。若需回看调研批次，见 `docs/01.追赶正式版/00.调研计划/`
3. **统筹（Plane助理）额外**：`cd /workspace/ThinkYM && git pull --ff-only`，读 `项目/plane/STATUS.md`；查 Linear「Plane」项目（P-YUE-4）进行中的 issue。**执行者（zcode 等）没有 ThinkYM 权限，以任务书为准。**
4. **汇报 5 行**：① 分支与同步状态 ② 当前阶段 ③ 进行中的任务 ④ 阻塞/待明哥拍板 ⑤ 本次打算做什么。

## 注意

- 区分「已确认 / 推断 / 待确认」；`07` 第 6 节的待确认项不得自行固化为规则。
- 测试口令在 `docs/运维/测试账号.md`；正式凭据只在 Vault。
- 工作结束后用 `plane-wrapup` 写回。
