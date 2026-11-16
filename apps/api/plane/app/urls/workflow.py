# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.urls import path

from plane.app.views import WorkflowViewSet

urlpatterns = [
    # 列表（未启用 → 空数组，门卡语义）+ 项目级启用（建行或复活动行 + 历史）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/workflows/",
        WorkflowViewSet.as_view({"get": "list", "post": "create"}),
        name="project-workflows",
    ),
    # 详情
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/workflows/<uuid:pk>/",
        WorkflowViewSet.as_view({"get": "retrieve"}),
        name="project-workflow",
    ),
    # 停用（行菜单「禁用」）+ 单行再启用（API 对称保留）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/workflows/<uuid:pk>/disable/",
        WorkflowViewSet.as_view({"post": "disable"}),
        name="project-workflow-disable",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/workflows/<uuid:pk>/enable/",
        WorkflowViewSet.as_view({"post": "enable"}),
        name="project-workflow-enable",
    ),
    # 更改历史（时间倒序游标分页）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/workflows/<uuid:pk>/change-history/",
        WorkflowViewSet.as_view({"get": "change_history"}),
        name="project-workflow-change-history",
    ),
]
