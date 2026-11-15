# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.urls import path

from plane.app.views import EpicSubIssuesEndpoint, EpicViewSet, IssueLinkViewSet

urlpatterns = [
    # Epic 列表/创建（EpicViewSet 强制 type__is_epic=True 过滤 + 项目开关门控）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epics/",
        EpicViewSet.as_view({"get": "list", "post": "create"}),
        name="project-epics",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epics/<uuid:pk>/",
        EpicViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="project-epic",
    ),
    # Epic 子工作项（层级规则：子项类型不得为 Epic）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epics/<uuid:issue_id>/issues/",
        EpicSubIssuesEndpoint.as_view(),
        name="project-epic-sub-issues",
    ),
    # Epic 链接：复用 IssueLinkViewSet（按 issue_id 泛化，无需新视图）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epics/<uuid:issue_id>/links/",
        IssueLinkViewSet.as_view({"get": "list", "post": "create"}),
        name="project-epic-links",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epics/<uuid:issue_id>/links/<uuid:pk>/",
        IssueLinkViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="project-epic-links",
    ),
]
