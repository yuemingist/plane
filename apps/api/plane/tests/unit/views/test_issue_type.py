# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
工作项类型域 API 单元测试（Step01 追赶 BE-1）。

用例锚点：产品方案 §7 A-2/A-3/A-4/A-5/A-6/A-7/A-8/A-9/A-14/A-15、技术方案 §4.1。
覆盖：enable 幂等与自动建类型、CRUD（新建默认禁用/重名 400）、设默认唯一性、
删除约束矩阵（默认/Epic/被引用）、启停、未启用项目 403 门控、Guest 只读、
工作区已有同名类型的幂等复用。
"""

import uuid

import pytest
from django.urls import reverse
from rest_framework import status

from plane.db.models import IssueType, Project, ProjectIssueType, ProjectMember, User

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
        identifier=f"TST{uuid.uuid4().hex[:6].upper()}",
    )


def add_member(project, user, role: int = 20) -> ProjectMember:
    return ProjectMember.objects.create(project=project, member=user, role=role)

def enable_project(client, project) -> None:
    """调用 enable 端点置位开关（同时自动产出 Epic/Task 两类型与项目桥）"""
    url = reverse(
        "project-work-item-types-enable",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id)},
    )
    response = client.post(url, format="json")
    assert response.status_code == status.HTTP_200_OK



@pytest.fixture
def project(workspace, create_user):
    """未启用类型开关的干净项目，owner 为 create_user（ADMIN）"""
    project = make_project(workspace, "Types Project")
    add_member(project, create_user, role=20)
    return project


class TestWorkItemTypeEnable:
    """启用动作：自动建 Epic/Task + 开关置位 + 幂等"""

    def _enable(self, client, project):
        url = reverse(
            "project-work-item-types-enable",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id)},
        )
        return client.post(url, format="json")

    def test_enable_creates_epic_and_task(self, session_client, project, create_user):
        """A-3：启用后出现 Epic（is_epic/活动/level=1）+ Task（活动/默认/level=0），开关置位"""
        assert project.is_issue_type_enabled is False

        response = self._enable(session_client, project)
        assert response.status_code == status.HTTP_200_OK

        project.refresh_from_db()
        assert project.is_issue_type_enabled is True

        epic = IssueType.objects.get(workspace=project.workspace, name="Epic", is_epic=True)
        assert epic.is_active is True
        assert epic.level == 1

        task = IssueType.objects.get(workspace=project.workspace, name="Task", is_epic=False)
        assert task.is_active is True
        assert task.level == 0

        epic_bridge = ProjectIssueType.objects.get(project=project, issue_type=epic)
        assert epic_bridge.is_default is False
        assert epic_bridge.level == 1

        task_bridge = ProjectIssueType.objects.get(project=project, issue_type=task)
        assert task_bridge.is_default is True

        # 唯一默认成立
        assert ProjectIssueType.objects.filter(project=project, is_default=True).count() == 1

    def test_enable_is_idempotent(self, session_client, project):
        """A-4：重复启用不报错、不产生重复行"""
        first = self._enable(session_client, project)
        assert first.status_code == status.HTTP_200_OK

        second = self._enable(session_client, project)
        assert second.status_code == status.HTTP_200_OK

        assert IssueType.objects.filter(workspace=project.workspace, name__in=["Epic", "Task"]).count() == 2
        assert ProjectIssueType.objects.filter(project=project).count() == 2
        assert ProjectIssueType.objects.filter(project=project, is_default=True).count() == 1

    def test_enable_reuses_existing_workspace_types(self, session_client, workspace, project):
        """幂等复用：工作区已有 (name, is_epic) 相同的类型时复用不新建"""
        # 另一个项目先启用，产出 Epic/Task
        other_project = make_project(workspace, "Other Project")
        add_member(other_project, workspace.owner, role=20)
        client = session_client
        url = reverse(
            "project-work-item-types-enable",
            kwargs={"slug": workspace.slug, "project_id": str(other_project.id)},
        )
        assert client.post(url, format="json").status_code == status.HTTP_200_OK

        existing_epic = IssueType.objects.get(workspace=workspace, name="Epic", is_epic=True)
        existing_task = IssueType.objects.get(workspace=workspace, name="Task", is_epic=False)

        response = self._enable(client, project)
        assert response.status_code == status.HTTP_200_OK

        # 复用同一 IssueType 行，不新建
        assert IssueType.objects.filter(workspace=workspace, name="Epic", is_epic=True).count() == 1
        assert IssueType.objects.filter(workspace=workspace, name="Task", is_epic=False).count() == 1
        assert IssueType.objects.get(pk=existing_epic.pk) is not None
        project_epic = ProjectIssueType.objects.get(project=project, issue_type=existing_epic)
        assert project_epic.issue_type_id == existing_epic.id
        assert ProjectIssueType.objects.filter(project=project, issue_type=existing_task).exists()

    def test_enable_requires_admin(self, session_client, project):
        """enable 仅 ADMIN（技术方案 §2.1）；MEMBER 403"""
        member = make_user("member-enable@plane.so")
        add_member(project, member, role=15)

        # session_client 绑定的是 create_user（ADMIN），这里换 MEMBER 身份验证
        from rest_framework.test import APIClient

        member_client = APIClient()
        member_client.force_authenticate(user=member)
        response = self._enable(member_client, project)
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestWorkItemTypeGating:
    """A-14：未启用项目的读写全部被开关门控（403）"""

    def _types_url(self, project):
        return reverse(
            "project-work-item-types",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id)},
        )

    def test_list_gated_when_disabled(self, session_client, project):
        response = session_client.get(self._types_url(project))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_gated_when_disabled(self, session_client, project):
        response = session_client.post(self._types_url(project), {"name": "Bug"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_epics_list_gated_when_disabled(self, session_client, project):
        url = reverse(
            "project-epics",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id)},
        )
        response = session_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_ok_after_enable(self, session_client, project):
        project.is_issue_type_enabled = True
        project.save(update_fields=["is_issue_type_enabled"])
        response = session_client.get(self._types_url(project))
        assert response.status_code == status.HTTP_200_OK


class TestWorkItemTypeCRUD:
    """A-5/A-6：新建默认禁用、启停、重名 400、Guest 只读"""

    def _types_url(self, project):
        return reverse(
            "project-work-item-types",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id)},
        )

    def _enable_project(self, client, project):
        enable_project(client, project)

    def test_create_defaults_to_inactive(self, session_client, project):
        """A-5：新建类型默认「已禁用」（model 默认 True，由序列化层覆盖）"""
        self._enable_project(session_client, project)
        response = session_client.post(self._types_url(project), {"name": "调研-缺陷"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is False
        assert response.data["is_epic"] is False

        issue_type = IssueType.objects.get(name="调研-缺陷", workspace=project.workspace)
        assert issue_type.is_active is False
        # 项目语境创建即绑定项目桥
        assert ProjectIssueType.objects.filter(project=project, issue_type=issue_type).exists()

    def test_create_duplicate_name_returns_400(self, session_client, project):
        self._enable_project(session_client, project)
        first = session_client.post(self._types_url(project), {"name": "Bug"}, format="json")
        assert first.status_code == status.HTTP_200_OK
        response = session_client.post(self._types_url(project), {"name": "Bug"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_missing_name_returns_400(self, session_client, project):
        self._enable_project(session_client, project)
        response = session_client.post(self._types_url(project), {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_partial_update_activates_type(self, session_client, project):
        """A-6：行菜单「启用」→ 地位变活动（PATCH is_active）"""
        self._enable_project(session_client, project)
        issue_type = IssueType.objects.create(workspace=project.workspace, name="Feature", is_active=False)
        ProjectIssueType.objects.create(project=project, issue_type=issue_type)

        url = reverse(
            "project-work-item-type",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(issue_type.id)},
        )
        response = session_client.patch(url, {"is_active": True}, format="json")
        assert response.status_code == status.HTTP_200_OK
        issue_type.refresh_from_db()
        assert issue_type.is_active is True

    def test_partial_update_cannot_flip_is_epic(self, session_client, project):
        """is_epic 为只读字段，防止客户端伪造 Epic 类型"""
        self._enable_project(session_client, project)
        issue_type = IssueType.objects.create(workspace=project.workspace, name="Custom", is_active=True)
        ProjectIssueType.objects.create(project=project, issue_type=issue_type)

        url = reverse(
            "project-work-item-type",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(issue_type.id)},
        )
        response = session_client.patch(url, {"is_epic": True}, format="json")
        assert response.status_code == status.HTTP_200_OK
        issue_type.refresh_from_db()
        assert issue_type.is_epic is False

    def test_guest_is_read_only(self, session_client, project):
        """A-14 后半句：Guest 读 200 / 写 403"""
        self._enable_project(session_client, project)
        guest = make_user("guest-types@plane.so")
        add_member(project, guest, role=5)

        from rest_framework.test import APIClient

        guest_client = APIClient()
        guest_client.force_authenticate(user=guest)

        assert guest_client.get(self._types_url(project)).status_code == status.HTTP_200_OK
        assert (
            guest_client.post(self._types_url(project), {"name": "GuestType"}, format="json").status_code
            == status.HTTP_403_FORBIDDEN
        )

    def test_list_response_shape(self, session_client, project):
        """序列化字段面：id/name/logo_props/is_epic/is_default/is_active/level + issues_count"""
        self._enable_project(session_client, project)
        response = session_client.get(self._types_url(project))
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert len(data) == 2  # enable 自动建的 Epic + Task
        keys = set(data[0].keys())
        assert {
            "id",
            "name",
            "description",
            "logo_props",
            "is_epic",
            "is_active",
            "level",
            "is_default",
            "issues_count",
        }.issubset(keys)

    def test_list_exposes_project_bridge_level(self, session_client, project):
        """BUG-04：列表 `level` 取项目桥 ProjectIssueType.level（Epic=1）而非工作区级
        IssueType.level，工作区级即使被改写也不影响项目语境透出（层级 tab 分组数据源）"""
        self._enable_project(session_client, project)
        epic = IssueType.objects.get(workspace=project.workspace, name="Epic", is_epic=True)
        task = IssueType.objects.get(workspace=project.workspace, name="Task", is_epic=False)
        # 模拟 WEB seed 的偏差形态：工作区级 level 与桥 level 不一致（桥=正确源）
        IssueType.objects.filter(pk=epic.pk).update(level=0)
        IssueType.objects.filter(pk=task.pk).update(level=2)

        response = session_client.get(self._types_url(project))
        assert response.status_code == status.HTTP_200_OK
        by_name = {item["name"]: item for item in response.data}
        assert by_name["Epic"]["level"] == 1  # 桥 level（enable 流写入 Epic=1）
        assert by_name["Task"]["level"] == 0
        # 桥 level 优先排序（层级升序），Epic 排最后（level=1）
        # PK 字段返回 UUID 对象（渲染前数据），统一 str 对比
        assert str(response.data[-1]["id"]) == str(epic.id)


class TestWorkItemTypeMarkDefault:
    """A-6 未激活设默认 400 / A-9 唯一默认"""

    def _mark_default_url(self, project, issue_type):
        return reverse(
            "project-work-item-type-mark-default",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(issue_type.id)},
        )

    def _enable_project(self, client, project):
        enable_project(client, project)

    def test_mark_default_moves_the_badge(self, session_client, project):
        """A-9：设默认后「默认」badge 迁移，唯一默认成立"""
        self._enable_project(session_client, project)
        task = IssueType.objects.get(workspace=project.workspace, name="Task", is_epic=False)
        assert ProjectIssueType.objects.get(project=project, issue_type=task).is_default is True

        new_type = IssueType.objects.create(workspace=project.workspace, name="Story", is_active=True)
        ProjectIssueType.objects.create(project=project, issue_type=new_type)

        response = session_client.post(self._mark_default_url(project, new_type), format="json")
        assert response.status_code == status.HTTP_200_OK

        project.refresh_from_db()
        defaults = ProjectIssueType.objects.filter(project=project, is_default=True)
        assert defaults.count() == 1
        assert defaults.first().issue_type_id == new_type.id

    def test_mark_default_rejected_for_inactive_type(self, session_client, project):
        """A-6：未激活类型设默认 → 400"""
        self._enable_project(session_client, project)
        inactive = IssueType.objects.create(workspace=project.workspace, name="Inactive", is_active=False)
        ProjectIssueType.objects.create(project=project, issue_type=inactive)

        response = session_client.post(self._mark_default_url(project, inactive), format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestWorkItemTypeDeleteConstraints:
    """A-7 默认不可删 / A-8 Epic 不可删 / A-15 被引用不可删"""

    def _type_detail_url(self, project, issue_type):
        return reverse(
            "project-work-item-type",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(issue_type.id)},
        )

    def _enable_project(self, client, project):
        enable_project(client, project)

    def test_default_type_cannot_be_deleted(self, session_client, project):
        """A-7：默认类型删除 → 400"""
        self._enable_project(session_client, project)
        task = IssueType.objects.get(workspace=project.workspace, name="Task", is_epic=False)

        response = session_client.delete(self._type_detail_url(project, task))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert IssueType.objects.filter(pk=task.pk).exists()

    def test_epic_type_cannot_be_deleted(self, session_client, project):
        """A-8：内置 Epic 类型删除 → 400"""
        self._enable_project(session_client, project)
        epic = IssueType.objects.get(workspace=project.workspace, name="Epic", is_epic=True)

        response = session_client.delete(self._type_detail_url(project, epic))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_referenced_type_cannot_be_deleted(self, session_client, project):
        """A-15：被工作项引用的类型删除 → 400"""
        self._enable_project(session_client, project)
        task = IssueType.objects.get(workspace=project.workspace, name="Task", is_epic=False)
        ProjectIssueType.objects.filter(project=project, issue_type=task).update(is_default=False)

        from plane.db.models import Issue

        Issue.objects.create(project=project, name="Referencing issue", type=task)

        response = session_client.delete(self._type_detail_url(project, task))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert IssueType.objects.filter(pk=task.pk).exists()

    def test_unreferenced_type_can_be_deleted(self, session_client, project):
        self._enable_project(session_client, project)
        issue_type = IssueType.objects.create(workspace=project.workspace, name="Disposable", is_active=True)
        ProjectIssueType.objects.create(project=project, issue_type=issue_type)

        response = session_client.delete(self._type_detail_url(project, issue_type))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueType.objects.filter(pk=issue_type.pk).exists()
        assert not ProjectIssueType.objects.filter(issue_type=issue_type).exists()


class TestWorkItemTypePropertiesPlaceholder:
    """属性 tab 空态（决策 1A）：属性端点恒返回空数组"""

    def test_properties_returns_empty_list(self, session_client, project):
        project.is_issue_type_enabled = True
        project.save(update_fields=["is_issue_type_enabled"])
        issue_type = IssueType.objects.create(workspace=project.workspace, name="Typed", is_active=True)
        ProjectIssueType.objects.create(project=project, issue_type=issue_type)

        url = reverse(
            "project-work-item-type-properties",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(issue_type.id)},
        )
        response = session_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_properties_404_for_unbound_type(self, session_client, project):
        project.is_issue_type_enabled = True
        project.save(update_fields=["is_issue_type_enabled"])
        # 工作区内存在但未绑定到该项目
        issue_type = IssueType.objects.create(workspace=project.workspace, name="Ghost", is_active=True)

        url = reverse(
            "project-work-item-type-properties",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(issue_type.id)},
        )
        response = session_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestProjectIssueTypeBinding:
    """project-issue-types 桥最小绑定面"""

    def _bindings_url(self, project):
        return reverse(
            "project-issue-types",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id)},
        )

    def test_bind_and_unbind(self, session_client, project):
        project.is_issue_type_enabled = True
        project.save(update_fields=["is_issue_type_enabled"])
        workspace_type = IssueType.objects.create(workspace=project.workspace, name="Imported", is_active=True)

        response = session_client.post(
            self._bindings_url(project), {"issue_type": str(workspace_type.id)}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        bridge = ProjectIssueType.objects.get(project=project, issue_type=workspace_type)
        assert bridge.level == workspace_type.level

        detail_url = reverse(
            "project-issue-type",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(bridge.id)},
        )
        assert session_client.delete(detail_url).status_code == status.HTTP_204_NO_CONTENT
        assert not ProjectIssueType.objects.filter(pk=bridge.pk).exists()

    def test_cannot_bind_type_from_other_workspace(self, session_client, project, workspace):
        project.is_issue_type_enabled = True
        project.save(update_fields=["is_issue_type_enabled"])
        from plane.db.models import Workspace as WorkspaceModel

        other_workspace = WorkspaceModel.objects.create(
            name="Other Workspace", slug="other-workspace", owner=workspace.owner
        )
        foreign_type = IssueType.objects.create(workspace=other_workspace, name="Foreign", is_active=True)

        response = session_client.post(self._bindings_url(project), {"issue_type": str(foreign_type.id)}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_default_binding_cannot_be_unbound(self, session_client, project):
        enable_project(session_client, project)
        task = IssueType.objects.get(workspace=project.workspace, name="Task", is_epic=False)
        bridge = ProjectIssueType.objects.get(project=project, issue_type=task)
        assert bridge.is_default is True

        detail_url = reverse(
            "project-issue-type",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(bridge.id)},
        )
        assert session_client.delete(detail_url).status_code == status.HTTP_400_BAD_REQUEST
