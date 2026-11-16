# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
工作流壳 API 单元测试（Step02 段 1 追赶 BE）。

用例锚点：段 1 产品方案 §5 W-1~W-12、技术方案 §3.1。
覆盖：未启用空态（门卡语义 200 []）、enable 建 Default Workflow + 历史、
重复 enable 400、disable/再启用与历史动作、历史倒序与字段、
Guest 读 200 写 403、非成员 403、未登录 401、项目隔离、单行不变量。
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Project, ProjectMember, User, Workflow, WorkflowChangeLog

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def make_user(email: str) -> User:
    user = User.objects.create(email=email, username=email, first_name="Test")
    user.set_password("test@123")
    user.save()
    return user


def make_project(workspace, name: str) -> Project:
    return Project.objects.create(
        name=name,
        workspace=workspace,
        identifier=f"WFL{uuid.uuid4().hex[:6].upper()}",
    )


def add_member(project, user, role: int = 20) -> ProjectMember:
    return ProjectMember.objects.create(project=project, member=user, role=role)


def workflows_url(project) -> str:
    from django.urls import reverse

    return reverse(
        "project-workflows",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id)},
    )


def workflow_detail_url(project, workflow) -> str:
    from django.urls import reverse

    return reverse(
        "project-workflow",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(workflow.id)},
    )


def workflow_action_url(project, workflow, action: str) -> str:
    from django.urls import reverse

    return reverse(
        f"project-workflow-{action}",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(workflow.id)},
    )


def workflow_history_url(project, workflow) -> str:
    from django.urls import reverse

    return reverse(
        "project-workflow-change-history",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(workflow.id)},
    )


def enable_workflow(client, project):
    """项目级启用（POST workflows/ 即 create 动作）"""
    return client.post(workflows_url(project), format="json")


@pytest.fixture
def project(workspace, create_user):
    """干净项目（未启用工作流），owner 为 create_user（ADMIN）"""
    project = make_project(workspace, "Workflow Project")
    add_member(project, create_user, role=20)
    return project


class TestWorkflowEnable:
    """启用：建行 + 历史 + 重复启用拒绝（W-2/W-3）"""

    def test_enable_creates_default_workflow_and_log(self, session_client, project, create_user):
        """W-2：启用建 Default Workflow（is_active=True）+ 1 条 enabled 历史"""
        assert Workflow.objects.filter(project=project).count() == 0

        response = enable_workflow(session_client, project)
        assert response.status_code == status.HTTP_200_OK

        workflow = Workflow.objects.get(project=project)
        assert workflow.name == "Default Workflow"
        assert workflow.is_active is True

        log = WorkflowChangeLog.objects.get(workflow=workflow)
        assert log.action == "enabled"
        assert log.actor_id == create_user.id

    def test_enable_twice_returns_400(self, session_client, project):
        """W-3：重复 enable 400，不产生第二行、不重复写历史"""
        assert enable_workflow(session_client, project).status_code == status.HTTP_200_OK

        response = enable_workflow(session_client, project)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Workflow.objects.filter(project=project).count() == 1
        assert WorkflowChangeLog.objects.count() == 1


class TestWorkflowList:
    """列表/详情：门卡空态与启用态（W-1/W-4）"""

    def test_list_returns_empty_when_not_enabled(self, session_client, project):
        """W-1：未启用 → 200 且空数组（门卡语义，不 403）"""
        response = session_client.get(workflows_url(project))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_list_returns_single_row_when_enabled(self, session_client, project):
        """W-4：启用后恰 1 行，name/is_active 齐全"""
        enable_workflow(session_client, project)

        response = session_client.get(workflows_url(project))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        row = response.data[0]
        assert row["name"] == "Default Workflow"
        assert row["is_active"] is True

    def test_retrieve_detail(self, session_client, project):
        """详情端点返回启用后的工作流"""
        enable_workflow(session_client, project)
        workflow = Workflow.objects.get(project=project)

        response = session_client.get(workflow_detail_url(project, workflow))
        assert response.status_code == status.HTTP_200_OK
        assert str(response.data["id"]) == str(workflow.id)
        assert response.data["name"] == "Default Workflow"


class TestWorkflowDisableAndReEnable:
    """停用/再启用：状态机与历史（W-5/W-6/W-7/单行不变量）"""

    def _enabled_workflow(self, session_client, project) -> Workflow:
        enable_workflow(session_client, project)
        return Workflow.objects.get(project=project)

    def test_disable_sets_inactive_and_logs(self, session_client, project):
        """W-5：禁用 → is_active=False + disabled 历史"""
        workflow = self._enabled_workflow(session_client, project)

        response = session_client.post(workflow_action_url(project, workflow, "disable"), format="json")
        assert response.status_code == status.HTTP_200_OK

        workflow.refresh_from_db()
        assert workflow.is_active is False
        assert list(
            WorkflowChangeLog.objects.filter(workflow=workflow).order_by("created_at").values_list("action", flat=True)
        ) == ["enabled", "disabled"]

    def test_disable_twice_returns_400(self, session_client, project):
        """W-6：已禁用再禁用 → 400，不重复写历史"""
        workflow = self._enabled_workflow(session_client, project)
        session_client.post(workflow_action_url(project, workflow, "disable"), format="json")

        response = session_client.post(workflow_action_url(project, workflow, "disable"), format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert WorkflowChangeLog.objects.filter(workflow=workflow, action="disabled").count() == 1

    def test_re_enable_reuses_same_row(self, session_client, project):
        """W-7：再启用复用同一行（行总数仍 1）+ re_enabled 历史"""
        workflow = self._enabled_workflow(session_client, project)
        workflow_id = workflow.id
        session_client.post(workflow_action_url(project, workflow, "disable"), format="json")

        # 再启用走项目级开关（UI 行为）
        response = enable_workflow(session_client, project)
        assert response.status_code == status.HTTP_200_OK

        assert Workflow.objects.filter(project=project).count() == 1
        workflow = Workflow.objects.get(pk=workflow_id)
        assert workflow.is_active is True

        actions = list(
            WorkflowChangeLog.objects.filter(workflow=workflow).order_by("created_at").values_list("action", flat=True)
        )
        assert actions == ["enabled", "disabled", "re_enabled"]

    def test_re_enable_via_row_endpoint(self, session_client, project):
        """单行 enable/ 端点（API 对称保留）同样可再启用并留痕"""
        workflow = self._enabled_workflow(session_client, project)
        session_client.post(workflow_action_url(project, workflow, "disable"), format="json")

        response = session_client.post(workflow_action_url(project, workflow, "enable"), format="json")
        assert response.status_code == status.HTTP_200_OK
        assert Workflow.objects.filter(project=project).count() == 1
        assert WorkflowChangeLog.objects.filter(workflow=workflow, action="re_enabled").count() == 1


class TestWorkflowChangeHistory:
    """更改历史端点（W-8）"""

    def test_history_lists_all_actions_newest_first(self, session_client, project, create_user):
        """W-8：启用→禁用→再启用后历史 3 条、倒序、字段齐全"""
        enable_workflow(session_client, project)
        workflow = Workflow.objects.get(project=project)
        session_client.post(workflow_action_url(project, workflow, "disable"), format="json")
        enable_workflow(session_client, project)

        response = session_client.get(workflow_history_url(project, workflow))
        assert response.status_code == status.HTTP_200_OK
        entries = response.data["results"] if isinstance(response.data, dict) else response.data
        assert len(entries) == 3

        # 倒序：最新（re_enabled）在前
        assert [e["action"] for e in entries] == ["re_enabled", "disabled", "enabled"]
        first = entries[0]
        assert set(first.keys()) >= {"id", "action", "note", "created_at", "actor_detail"}
        assert first["actor_detail"] is not None
        assert first["actor_detail"]["id"] == str(create_user.id)


class TestWorkflowPermissions:
    """权限矩阵与项目隔离（W-9/W-10/W-11/W-12）"""

    def test_guest_read_only(self, session_client, project):
        """W-9：Guest 读 200 / 写（enable/disable）403"""
        enable_workflow(session_client, project)
        workflow = Workflow.objects.get(project=project)

        guest = make_user("guest-workflow@plane.so")
        add_member(project, guest, role=5)

        guest_client = APIClient()
        guest_client.force_authenticate(user=guest)

        assert guest_client.get(workflows_url(project)).status_code == status.HTTP_200_OK
        assert guest_client.get(workflow_history_url(project, workflow)).status_code == status.HTTP_200_OK
        assert guest_client.post(workflows_url(project), format="json").status_code == status.HTTP_403_FORBIDDEN
        assert (
            guest_client.post(workflow_action_url(project, workflow, "disable"), format="json").status_code
            == status.HTTP_403_FORBIDDEN
        )

    def test_non_member_cannot_access(self, workspace, session_client, project):
        """W-10：非该项目成员不可读不可写"""
        enable_workflow(session_client, project)
        workflow = Workflow.objects.get(project=project)

        outsider = make_user("outsider-workflow@plane.so")
        # 属于工作区但不属于项目（WorkspaceMember 缺省可省——项目成员过滤已足够）
        outsider_client = APIClient()
        outsider_client.force_authenticate(user=outsider)

        assert outsider_client.get(workflows_url(project)).status_code == status.HTTP_403_FORBIDDEN
        assert outsider_client.post(workflows_url(project), format="json").status_code == status.HTTP_403_FORBIDDEN
        assert (
            outsider_client.get(workflow_detail_url(project, workflow)).status_code == status.HTTP_403_FORBIDDEN
        )

    def test_unauthenticated_returns_401(self, project):
        """W-11：未登录 401"""
        client = APIClient()
        assert client.get(workflows_url(project)).status_code == status.HTTP_401_UNAUTHORIZED
        assert client.post(workflows_url(project), format="json").status_code == status.HTTP_401_UNAUTHORIZED

    def test_project_isolation(self, workspace, session_client, project, create_user):
        """W-12：项目 B 的列表/详情看不到项目 A 的工作流"""
        enable_workflow(session_client, project)
        workflow_a = Workflow.objects.get(project=project)

        project_b = make_project(workspace, "Workflow Project B")
        add_member(project_b, create_user, role=20)

        response = session_client.get(workflows_url(project_b))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

        # 项目 A 的行在项目 B 语境下取不到（404）
        assert (
            session_client.get(workflow_detail_url(project_b, workflow_a)).status_code == status.HTTP_404_NOT_FOUND
        )
