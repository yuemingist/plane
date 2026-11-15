# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Epic 域（Step01 追赶 BE-2）。

独立新文件继承 IssueViewSet（继承而非复制，技术方案 §2.5）——不动
`issue/base.py` 一行（官方安全修复高密度区）。仅 override：

- get_queryset：强制 `type__is_epic=True` 过滤；
- initial：项目工作项类型开关门控（未启用 403）；
- create：Epic 域创建的工作项强制绑定项目内 is_epic 类型；
- retrieve/destroy：父类实现走非过滤管理器，这里先校验目标是 Epic；
- partial_update：禁止把 Epic 改成非 Epic 类型；
- 子工作项端点（…/epics/{id}/issues/）：校验子项类型不得为 Epic（层级规则）。
"""

# Third Party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.views.issue.base import IssueViewSet
from plane.app.views.issue.sub_issue import SubIssuesEndpoint
from plane.app.views.issue_type import WorkItemTypeFeatureGateMixin
from plane.db.models import Issue, IssueType, Project


class EpicViewSet(WorkItemTypeFeatureGateMixin, IssueViewSet):
    """Epic 工作项视图集：Epic 列表 = Issue 查询 + type__is_epic 强制过滤。

    权限沿用 IssueViewSet 各动作上的 allow_permission（Guest 只读、
    写 ADMIN/MEMBER、删 ADMIN），门控由 WorkItemTypeFeatureGateMixin 提供。
    """

    def get_queryset(self):
        # Epic 布局查询面：仅返回绑定 is_epic 类型的工作项
        return super().get_queryset().filter(type__is_epic=True)

    def _project_epic_type(self, project_id):
        # 项目内唯一 is_epic 类型（经项目桥绑定）
        return (
            IssueType.objects.filter(
                project_issue_types__project_id=project_id,
                project_issue_types__deleted_at__isnull=True,
                is_epic=True,
            )
            .distinct()
            .first()
        )

    def create(self, request, slug, project_id):
        epic_type = self._project_epic_type(project_id)
        if epic_type is None:
            return Response(
                {"error": "The epic work item type is not available for this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_type = request.data.get("type") or request.data.get("type_id")
        if requested_type is not None and str(requested_type) != str(epic_type.id):
            # Epic 域创建的工作项必须是 Epic 类型
            return Response(
                {"error": "The work item type must be the epic type of this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            request.data["type"] = str(epic_type.id)
            request.data.pop("type_id", None)
        except (TypeError, AttributeError):
            # 不可变请求体（如 form 编码）：仅在已带正确类型时放行
            if not requested_type:
                return Response(
                    {"error": "The epic work item type is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return super().create(request, slug=slug, project_id=project_id)

    def retrieve(self, request, slug, project_id, pk):
        # 父类 retrieve 用非过滤管理器直查，这里先确认目标确实是 Epic（否则 404）
        is_epic = Issue.objects.filter(
            pk=pk,
            project_id=project_id,
            workspace__slug=slug,
            type__is_epic=True,
        ).exists()
        if not is_epic:
            return Response(
                {"error": "The required object does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return super().retrieve(request, slug=slug, project_id=project_id, pk=pk)

    def partial_update(self, request, slug, project_id, pk):
        requested_type = request.data.get("type") or request.data.get("type_id")
        if requested_type is not None:
            requested_is_epic = IssueType.objects.filter(pk=requested_type, is_epic=True).exists()
            if not requested_is_epic:
                # 层级规则：Epic 不得被改成非 Epic 类型
                return Response(
                    {"error": "The epic work item type cannot be changed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().partial_update(request, slug=slug, project_id=project_id, pk=pk)

    def destroy(self, request, slug, project_id, pk):
        # 父类 destroy 用非过滤管理器直查，这里先确认目标确实是 Epic
        is_epic = Issue.objects.filter(
            pk=pk,
            project_id=project_id,
            workspace__slug=slug,
            type__is_epic=True,
        ).exists()
        if not is_epic:
            return Response(
                {"error": "The required object does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return super().destroy(request, slug=slug, project_id=project_id, pk=pk)


class EpicSubIssuesEndpoint(SubIssuesEndpoint):
    """Epic 子工作项端点（…/epics/{id}/issues/，前端 issue.service.ts 子项路径）。

    层级规则（产品方案 §5.2 / B-9）：子项类型不得为 Epic（不得把子项挂成 Epic）；
    父项必须是 Epic。权限沿用 SubIssuesEndpoint 的 ProjectEntityPermission，
    开关门控在此显式补齐。
    """

    def _gate_and_validate_parent(self, request, slug, project_id, issue_id):
        project = Project.objects.filter(pk=project_id, workspace__slug=slug).first()
        if project is None:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)
        if not project.is_issue_type_enabled:
            return Response(
                {"error": "Work item types are not enabled for this project"},
                status=status.HTTP_403_FORBIDDEN,
            )
        parent_is_epic = Issue.objects.filter(
            pk=issue_id,
            project_id=project_id,
            workspace__slug=slug,
            type__is_epic=True,
        ).exists()
        if not parent_is_epic:
            return Response({"error": "Parent issue not found"}, status=status.HTTP_404_NOT_FOUND)
        return None

    def get(self, request, slug, project_id, issue_id):
        error = self._gate_and_validate_parent(request, slug, project_id, issue_id)
        if error is not None:
            return error
        return super().get(request, slug=slug, project_id=project_id, issue_id=issue_id)

    def post(self, request, slug, project_id, issue_id):
        error = self._gate_and_validate_parent(request, slug, project_id, issue_id)
        if error is not None:
            return error

        # 层级规则：挂到 Epic 下的工作项不得是 Epic 类型（B-9 / 技术方案 §2.5）
        sub_issue_ids = request.data.get("sub_issue_ids", [])
        if (
            sub_issue_ids
            and Issue.issue_objects.filter(
                id__in=sub_issue_ids,
                workspace__slug=slug,
                project_id=project_id,
                type__is_epic=True,
            ).exists()
        ):
            return Response(
                {"error": "The epic work item type cannot be a sub work item of an epic"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().post(request, slug=slug, project_id=project_id, issue_id=issue_id)
