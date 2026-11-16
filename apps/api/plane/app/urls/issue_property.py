# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.urls import path

from plane.app.views import IssuePropertyViewSet, IssuePropertyValueViewSet, IssueTypePropertyViewSet

urlpatterns = [
    # 项目属性池 CRUD（属性 tab，段 2 技术方案 §2）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-properties/",
        IssuePropertyViewSet.as_view({"get": "list", "post": "create"}),
        name="project-issue-properties",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-properties/<uuid:pk>/",
        IssuePropertyViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="project-issue-property",
    ),
    # 类型↔属性绑定：列表/批量绑定（接管 Step01 占位路由 project-work-item-type-properties）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:type_id>/properties/",
        IssueTypePropertyViewSet.as_view({"get": "list", "post": "create"}),
        name="project-work-item-type-properties",
    ),
    # 解绑（只删桥，值保留）
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:type_id>/properties/<uuid:property_id>/",
        IssueTypePropertyViewSet.as_view({"delete": "destroy"}),
        name="project-work-item-type-property-unbind",
    ),
    # 工作项属性值：列表 + 批量 upsert
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-items/<uuid:issue_id>/issue-property-values/",
        IssuePropertyValueViewSet.as_view({"get": "list", "post": "create"}),
        name="project-issue-property-values",
    ),
]
