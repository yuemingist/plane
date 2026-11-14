---
name: plane-wrapup
description: Plane 项目收工写回。一轮工作结束、调研批次验收完、或明哥在对话里拍板之后使用：把决策/状态/台账写回对的位置，提交推送本仓库，并（统筹）同步 ThinkYM STATUS 与 Linear。
---

# plane-wrapup：收工写回

规则全文见 `docs/项目管理/08.工作约定.md`；本技能是执行清单。

## 步骤

1. **范围**：`git status -sb`，列出本次改动路径；别人的未提交改动不碰。
2. **写回仓库内的唯一来源**（只写变化，不复制正文）：
   - 明哥拍板/重要结论 → `docs/项目管理/02.会议与决策记录.md` 追加一节（接 D 序号）；影响架构/范围/许可/同步策略/迁库的另写 `docs/项目管理/决策/ADR-NNN-标题.md`（≤30 行：状态、背景、决定、备选、后果、依据）。
   - `docs/项目管理/07.项目记忆.md`：决策索引加一行、待确认项增删（保持 ≤150 行）。
   - 调研批次交付 → `01.项目计划与进度.md` 台账：批次、交付物、验收结论、遗留。
   - 测试账号变化 → 仅 `docs/运维/测试账号.md`。
3. **自检**（提交前）：`git diff --cached --stat`，并 `git diff --cached | grep -iE 'api[_-]?key|secret|token|sk-[A-Za-z0-9]{20}'`——命中真实生产凭据即停。测试口令只允许出现在 `测试账号.md`。
4. **提交推送**：
   - 中文 `类型(范围): 摘要`；`git -c user.name='姜子牙团队' -c user.email='yueming1985+thinkym-agents@gmail.com' commit`；只 `git add <本次路径>`；不 `--no-verify`、不 force push。
   - **调研阶段**：在 `main` 提交并 `git push origin main`。
   - **开发阶段**：只提交推送任务分支；**合并回 `main` 前必须问明哥并得到点头**，未点头不合并。
   - `preview` 不改；上游同步按 `08` §1，需明哥决定。
5. **ThinkYM 同步（统筹执行）**：
   ```bash
   cd /workspace/ThinkYM && flock /tmp/thinkym.lock -c '
     git pull --rebase --autostash &&
     # 更新 项目/plane/STATUS.md：现状、下一步、待明哥拍板；刷新 frontmatter 的 updated
     git add 项目/plane/STATUS.md &&
     git -c user.name="姜子牙团队" -c user.email="yueming1985+thinkym-agents@gmail.com" commit -m "项目/plane：<摘要>" -m "助理: Plane助理" &&
     git push'
   ```
   ThinkYM 里不放凭据、不复制仓内正文，只放进度和链接；冲突即停。
6. **Linear（统筹）**：更新相关 issue 状态/评论，写 commit hash；仓库文档里只引用编号。
7. **回报**：commit hash、push 结果、文件清单、冲突/未决事项、需明哥拍板的问题（编号 + 字母选项）。执行者无 ThinkYM/Linear 权限时，把「需同步事项」列在回报末尾交统筹。
