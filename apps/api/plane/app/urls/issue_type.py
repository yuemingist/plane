# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.urls import path

from plane.app.views import ProjectIssueTypeViewSet, WorkItemTypeViewSet

urlpatterns = [
    # 项目启用（幂等）：置位开关 + 自动建 Epic/Task
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/enable/",
        WorkItemTypeViewSet.as_view({"post": "enable"}),
        name="project-work-item-types-enable",
    ),
    # 类型 CRUD（项目语境，经项目桥收敛）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/",
        WorkItemTypeViewSet.as_view({"get": "list", "post": "create"}),
        name="project-work-item-types",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:pk>/",
        WorkItemTypeViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="project-work-item-type",
    ),
    # 设默认（项目内唯一默认，事务内清旧置新）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:pk>/mark-default/",
        WorkItemTypeViewSet.as_view({"post": "mark_default"}),
        name="project-work-item-type-mark-default",
    ),
    # 属性列表占位：本步恒返回空数组（属性体系属 P2-13）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:pk>/properties/",
        WorkItemTypeViewSet.as_view({"get": "properties"}),
        name="project-work-item-type-properties",
    ),
    # 项目 <-> 类型桥最小绑定面
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/project-issue-types/",
        ProjectIssueTypeViewSet.as_view({"get": "list", "post": "create"}),
        name="project-issue-types",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/project-issue-types/<uuid:pk>/",
        ProjectIssueTypeViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="project-issue-type",
    ),
]
