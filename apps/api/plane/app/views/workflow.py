# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
工作流域视图（Step02 段 1 追赶 BE）。

端点形态对照段 1 技术方案 §1.3（项目域扁平路由，kebab-case 路径 workflows/）：
- GET 列表/详情（读三角色，门卡语义：未启用返回空数组而非 403）
- POST enable/（项目级启用：建行或复活动行 + 历史）
- POST {id}/disable/、{id}/enable/（停用/再启用 + 历史）
- GET {id}/change-history/（分页倒序）

对标：58 号对比 D-10（Business 档壳）——单一 Default Workflow、无规则配置。
状态机（段 1 产品方案 §3）：禁用不删行、再启用复用同一行；每次启停留痕。
"""

# Django imports
from django.db import transaction

# Third Party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from .base import BaseViewSet
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import WorkflowChangeLogSerializer, WorkflowSerializer
from plane.db.models import Project, Workflow, WorkflowChangeAction, WorkflowChangeLog


class WorkflowViewSet(BaseViewSet):
    """项目工作流壳：启用/停用/再启用 + 更改历史。"""

    serializer_class = WorkflowSerializer
    model = Workflow

    def _member_scoped_workflows(self, slug, project_id):
        """项目成员作用域的工作流查询（Step01 §2.3 权限域绑定模式）。"""
        return Workflow.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            deleted_at__isnull=True,
        ).filter(
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
            project__archived_at__isnull=True,
        )

    def _get_scoped_instance(self, slug, project_id, pk):
        return self._member_scoped_workflows(slug, project_id).filter(pk=pk).first()

    def _log_action(self, workflow, actor, action: str, note: str = "") -> None:
        WorkflowChangeLog.objects.create(workflow=workflow, actor=actor, action=action, note=note)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id):
        """未启用项目返回空数组（门卡语义：前端据此渲染启用开关卡片）。"""
        workflows = self._member_scoped_workflows(slug, project_id)
        serializer = WorkflowSerializer(workflows, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id):
        """项目级启用（前端开关总入口）：
        - 无行 → 建 Default Workflow（is_active=True）+ 历史 enabled；
        - 有禁用行 → 复用原行置回 True + 历史 re_enabled；
        - 已有活动行 → 400（不产生第二行、不重复写历史）。
        """
        Project.objects.get(pk=project_id, workspace__slug=slug)

        with transaction.atomic():
            # 锁项目行串行化启停竞态；workflow 行在事务内按项目取
            Project.objects.select_for_update().get(pk=project_id)
            workflow = self._member_scoped_workflows(slug, project_id).first()
            if workflow is not None:
                if workflow.is_active:
                    return Response(
                        {"error": "Workflow is already enabled for this project"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                workflow.is_active = True
                workflow.save(update_fields=["is_active"])
                self._log_action(workflow, request.user, WorkflowChangeAction.RE_ENABLED)
            else:
                workflow = Workflow.objects.create(project_id=project_id, name="Default Workflow", is_active=True)
                self._log_action(workflow, request.user, WorkflowChangeAction.ENABLED)

        return Response(WorkflowSerializer(workflow).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def retrieve(self, request, slug, project_id, pk):
        workflow = self._get_scoped_instance(slug, project_id, pk)
        if workflow is None:
            return Response({"error": "Workflow not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(WorkflowSerializer(workflow).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def disable(self, request, slug, project_id, pk):
        workflow = self._get_scoped_instance(slug, project_id, pk)
        if workflow is None:
            return Response({"error": "Workflow not found"}, status=status.HTTP_404_NOT_FOUND)
        if not workflow.is_active:
            return Response(
                {"error": "Workflow is already disabled for this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        workflow.is_active = False
        workflow.save(update_fields=["is_active"])
        self._log_action(workflow, request.user, WorkflowChangeAction.DISABLED)
        return Response(WorkflowSerializer(workflow).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def enable(self, request, slug, project_id, pk):
        """单行再启用（API 对称保留；UI 启停走项目级 create 入口）。"""
        workflow = self._get_scoped_instance(slug, project_id, pk)
        if workflow is None:
            return Response({"error": "Workflow not found"}, status=status.HTTP_404_NOT_FOUND)
        if workflow.is_active:
            return Response(
                {"error": "Workflow is already enabled for this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        workflow.is_active = True
        workflow.save(update_fields=["is_active"])
        self._log_action(workflow, request.user, WorkflowChangeAction.RE_ENABLED)
        return Response(WorkflowSerializer(workflow).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def change_history(self, request, slug, project_id, pk):
        """更改历史：按时间倒序游标分页（时间/操作人/动作/备注）。"""
        workflow = self._get_scoped_instance(slug, project_id, pk)
        if workflow is None:
            return Response({"error": "Workflow not found"}, status=status.HTTP_404_NOT_FOUND)

        change_logs = (
            WorkflowChangeLog.objects.filter(workflow=workflow, deleted_at__isnull=True)
            .select_related("actor")
            .order_by("-created_at")
        )
        return self.paginate(
            request=request,
            queryset=change_logs,
            on_results=lambda rows: WorkflowChangeLogSerializer(rows, many=True).data,
        )
