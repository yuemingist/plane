# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Epic 域 API 单元测试（Step01 追赶 BE-2）。

用例锚点：产品方案 §7 A-13/B-9、技术方案 §2.5/§4.1。
覆盖：epics 列表仅含 is_epic 工作项、开关门控、Guest 只读、创建时 Epic 类型
强制注入、子工作项层级规则（Epic 不得作为子项）、Epic 不得改非 Epic 类型、
非 Epic 工作项在 Epic 域 404。
"""

import uuid

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, IssueType, Project, ProjectIssueType, ProjectMember, User

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def make_user(email: str) -> User:
    user = User.objects.create(email=email, username=email, first_name="Test")
    user.set_password("test@123")
    user.save()
    return user


def add_member(project, user, role: int = 20) -> ProjectMember:
    return ProjectMember.objects.create(project=project, member=user, role=role)


@pytest.fixture
def enabled_project(workspace, create_user):
    """已启用工作项类型开关的项目（enable 产线复刻：直接置位 + 复用 enable 端点建类型）"""
    project = Project.objects.create(
        name="Epic Project",
        workspace=workspace,
        identifier=f"EPI{uuid.uuid4().hex[:6].upper()}",
    )
    add_member(project, create_user, role=20)
    project.is_issue_type_enabled = True
    project.save(update_fields=["is_issue_type_enabled"])
    return project


@pytest.fixture
def types(enabled_project):
    """项目内 Epic/Task 两类型 + 项目桥（enable 产线字段复刻）"""
    epic = IssueType.objects.create(
        workspace=enabled_project.workspace,
        name="Epic",
        is_epic=True,
        is_active=True,
        level=1,
    )
    task = IssueType.objects.create(
        workspace=enabled_project.workspace,
        name="Task",
        is_epic=False,
        is_active=True,
        level=0,
    )
    ProjectIssueType.objects.create(project=enabled_project, issue_type=epic, level=1, is_default=False)
    ProjectIssueType.objects.create(project=enabled_project, issue_type=task, level=0, is_default=True)
    return {"epic": epic, "task": task}


def make_issue(project, name: str, type_obj=None, parent=None) -> Issue:
    return Issue.objects.create(project=project, name=name, type=type_obj, parent=parent)


class TestEpicList:
    def test_epic_list_only_contains_is_epic(self, session_client, enabled_project, types, mock_celery):
        """Epic 列表仅返回 type__is_epic=true 的工作项"""
        epic_issue = make_issue(enabled_project, "Epic one", type_obj=types["epic"])
        make_issue(enabled_project, "Task one", type_obj=types["task"])

        url = reverse(
            "project-epics",
            kwargs={"slug": enabled_project.workspace.slug, "project_id": str(enabled_project.id)},
        )
        response = session_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        ids = [item["id"] for item in response.data["results"]]
        assert str(epic_issue.id) in ids
        assert len(ids) == 1
        # 列表响应带 type_id（BE-3 读模型）
        assert response.data["results"][0]["type_id"] == str(types["epic"].id)

    def test_epic_detail_404_for_non_epic_issue(self, session_client, enabled_project, types, mock_celery):
        """非 Epic 工作项在 Epic 域详情 404（retrieve 前置校验）"""
        task_issue = make_issue(enabled_project, "Task two", type_obj=types["task"])

        url = reverse(
            "project-epic",
            kwargs={
                "slug": enabled_project.workspace.slug,
                "project_id": str(enabled_project.id),
                "pk": str(task_issue.id),
            },
        )
        response = session_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_epic_detail_returns_epic(self, session_client, enabled_project, types, mock_celery):
        epic_issue = make_issue(enabled_project, "Epic two", type_obj=types["epic"])

        url = reverse(
            "project-epic",
            kwargs={
                "slug": enabled_project.workspace.slug,
                "project_id": str(enabled_project.id),
                "pk": str(epic_issue.id),
            },
        )
        response = session_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["type_id"] == str(types["epic"].id)


class TestEpicCreate:
    def test_create_injects_epic_type(self, session_client, enabled_project, types, mock_celery):
        """Epic 域创建的工作项自动绑定项目内 is_epic 类型"""
        url = reverse(
            "project-epics",
            kwargs={"slug": enabled_project.workspace.slug, "project_id": str(enabled_project.id)},
        )
        response = session_client.post(url, {"name": "Epic from API"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        issue = Issue.objects.get(pk=response.data["id"])
        assert issue.type_id == types["epic"].id

    def test_create_rejects_non_epic_type(self, session_client, enabled_project, types, mock_celery):
        """Epic 域创建传入非 Epic 类型 → 400"""
        url = reverse(
            "project-epics",
            kwargs={"slug": enabled_project.workspace.slug, "project_id": str(enabled_project.id)},
        )
        response = session_client.post(url, {"name": "Bad epic", "type": str(types["task"].id)}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_guest_is_read_only(self, enabled_project, types, create_user):
        """Guest：GET 200 / POST 403"""
        guest = make_user("guest-epics@plane.so")
        add_member(enabled_project, guest, role=5)
        make_issue(enabled_project, "Epic guest", type_obj=types["epic"])

        client = APIClient()
        client.force_authenticate(user=guest)

        url = reverse(
            "project-epics",
            kwargs={"slug": enabled_project.workspace.slug, "project_id": str(enabled_project.id)},
        )
        assert client.get(url).status_code == status.HTTP_200_OK
        assert client.post(url, {"name": "Guest epic"}, format="json").status_code == status.HTTP_403_FORBIDDEN


class TestEpicUpdateRules:
    def test_cannot_change_epic_to_non_epic_type(self, session_client, enabled_project, types, mock_celery):
        """层级规则：Epic 不得 PATCH 成非 Epic 类型"""
        epic_issue = make_issue(enabled_project, "Epic three", type_obj=types["epic"])

        url = reverse(
            "project-epic",
            kwargs={
                "slug": enabled_project.workspace.slug,
                "project_id": str(enabled_project.id),
                "pk": str(epic_issue.id),
            },
        )
        response = session_client.patch(url, {"type_id": str(types["task"].id)}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        epic_issue.refresh_from_db()
        assert epic_issue.type_id == types["epic"].id

    def test_update_epic_fields_still_works(self, session_client, enabled_project, types, mock_celery):
        epic_issue = make_issue(enabled_project, "Epic four", type_obj=types["epic"])

        url = reverse(
            "project-epic",
            kwargs={
                "slug": enabled_project.workspace.slug,
                "project_id": str(enabled_project.id),
                "pk": str(epic_issue.id),
            },
        )
        response = session_client.patch(url, {"name": "Renamed epic"}, format="json")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        epic_issue.refresh_from_db()
        assert epic_issue.name == "Renamed epic"


class TestEpicSubIssues:
    def test_sub_issue_list_and_attachment(self, session_client, enabled_project, types, mock_celery):
        """…/epics/{id}/issues/：子项列表 + 挂子项（非 Epic 子项正常）"""
        epic_issue = make_issue(enabled_project, "Epic parent", type_obj=types["epic"])
        child = make_issue(enabled_project, "Child task", type_obj=types["task"])

        url = reverse(
            "project-epic-sub-issues",
            kwargs={
                "slug": enabled_project.workspace.slug,
                "project_id": str(enabled_project.id),
                "issue_id": str(epic_issue.id),
            },
        )
        response = session_client.post(url, {"sub_issue_ids": [str(child.id)]}, format="json")
        assert response.status_code == status.HTTP_200_OK

        child.refresh_from_db()
        assert child.parent_id == epic_issue.id

        listing = session_client.get(url)
        assert listing.status_code == status.HTTP_200_OK
        sub_ids = [str(item["id"]) for item in listing.data["sub_issues"]]
        assert str(child.id) in sub_ids

    def test_epic_cannot_be_sub_issue_of_epic(self, session_client, enabled_project, types):
        """B-9/技术方案 §2.5：Epic 不得挂成 Epic 的子项 → 400"""
        parent_epic = make_issue(enabled_project, "Parent epic", type_obj=types["epic"])
        child_epic = make_issue(enabled_project, "Child epic", type_obj=types["epic"])

        url = reverse(
            "project-epic-sub-issues",
            kwargs={
                "slug": enabled_project.workspace.slug,
                "project_id": str(enabled_project.id),
                "issue_id": str(parent_epic.id),
            },
        )
        response = session_client.post(url, {"sub_issue_ids": [str(child_epic.id)]}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        child_epic.refresh_from_db()
        assert child_epic.parent_id is None

    def test_sub_issues_404_for_non_epic_parent(self, session_client, enabled_project, types):
        task_issue = make_issue(enabled_project, "Plain task", type_obj=types["task"])

        url = reverse(
            "project-epic-sub-issues",
            kwargs={
                "slug": enabled_project.workspace.slug,
                "project_id": str(enabled_project.id),
                "issue_id": str(task_issue.id),
            },
        )
        response = session_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestEpicLinks:
    def test_epic_links_routes_reuse_issue_link_viewset(self, session_client, enabled_project, types, mock_celery):
        """…/epics/{id}/links/ 复用 IssueLinkViewSet（前端 issue.service.ts 路径）"""
        epic_issue = make_issue(enabled_project, "Epic with link", type_obj=types["epic"])

        url = reverse(
            "project-epic-links",
            kwargs={
                "slug": enabled_project.workspace.slug,
                "project_id": str(enabled_project.id),
                "issue_id": str(epic_issue.id),
            },
        )
        response = session_client.post(url, {"title": "Docs", "url": "https://plane.so"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["issue"] == str(epic_issue.id)

        listing = session_client.get(url)
        assert listing.status_code == status.HTTP_200_OK
        assert len(listing.data) == 1
