# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
工作流域（Step02 段 1 追赶 BE）。

对标：58 号对比 §1.3/§3.6（D-10，Business 档工作流壳）——
Business 档只有单一的 Default Workflow：项目级启用/禁用 + 更改历史，
无规则配置、无多套工作流（均为 Enterprise 档，明确不做）。

不变量：
- 每个项目至多一条未删除 Workflow 行（partial unique constraint）。
- 禁用不删行（is_active=False），再启用复用同一行，
  Default Workflow 身份与更改历史得以延续。
- 约定防误用：`name` 默认 "Default Workflow"（云端中文界面也不翻译，
  58 号截图 2 实拍），本段无改名入口，序列化器只读透出。
"""

# Django imports
from django.db import models

# Module imports
from .base import BaseModel
from .project import ProjectBaseModel
from .state import State


class Workflow(ProjectBaseModel):
    """项目工作流壳：Business 档每项目恰好 0 或 1 条（Default Workflow）。"""

    name = models.CharField(max_length=255, default="Default Workflow")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        """Return the workflow name and project."""
        return f"{self.name} <{self.project.name}>"

    class Meta:
        verbose_name = "Workflow"
        verbose_name_plural = "Workflows"
        db_table = "workflows"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["project"],
                condition=models.Q(deleted_at__isnull=True),
                name="workflow_unique_per_project_when_deleted_at_null",
            )
        ]


class WorkflowChangeAction(models.TextChoices):
    ENABLED = "enabled", "enabled"
    DISABLED = "disabled", "disabled"
    RE_ENABLED = "re_enabled", "re-enabled"
    # Step02 段 3：流转规则变更留痕（产品方案 A3）
    TRANSITION_RULES_UPDATED = "transition_rules_updated", "transition rules updated"


class WorkflowChangeLog(BaseModel):
    """工作流生命周期留痕：启用/停用/再启用各写一条。

    云端 Business 档历史面板为空（规则级变更属 Enterprise，58 号 §3.6 步骤 5）；
    CE 记录生命周期事件使 Business 档下历史功能有可读数据（段 1 产品方案 §2.5
    已声明为 CE 设计决策）。
    """

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="change_logs")
    actor = models.ForeignKey(
        "db.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_change_logs",
    )
    action = models.CharField(max_length=30, choices=WorkflowChangeAction.choices)
    note = models.TextField(blank=True)

    def __str__(self):
        """Return the action and workflow."""
        return f"{self.action} <{self.workflow.name}>"

    class Meta:
        verbose_name = "Workflow Change Log"
        verbose_name_plural = "Workflow Change Logs"
        db_table = "workflow_change_logs"
        ordering = ("-created_at",)


class WorkflowTransition(ProjectBaseModel):
    """流转规则行（Step02 段 3 追赶 BE）。

    语义（段 3 产品方案 A1/A2）：规则是按源状态的白名单——
    「从 from_state 只能移动到 to_state 集合」；某源状态没有规则行 = 该源状态
    不受限（默认无规则 = 全部允许，58 号 §3.6 Business 实测依据）。

    不变量：
    - 规则只引用既有项目状态池（不复制状态，章程 §5）；
    - 状态删除级联删除相关规则行（DB 层保证引用有效性，技术方案 §1.1 选型 A）；
    - (workflow, from_state, to_state) 唯一（deleted_at is null 条件约束，同段 1 风格）。
    """

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="transitions")
    from_state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="workflow_transitions_from")
    to_state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="workflow_transitions_to")

    def __str__(self):
        """Return the transition rule endpoints."""
        return f"{self.from_state_id} -> {self.to_state_id} <{self.workflow.name}>"

    class Meta:
        verbose_name = "Workflow Transition"
        verbose_name_plural = "Workflow Transitions"
        db_table = "workflow_transitions"
        ordering = ("from_state_id", "to_state_id")
        constraints = [
            models.UniqueConstraint(
                fields=["workflow", "from_state", "to_state"],
                condition=models.Q(deleted_at__isnull=True),
                name="workflow_transition_unique_when_deleted_at_null",
            )
        ]
