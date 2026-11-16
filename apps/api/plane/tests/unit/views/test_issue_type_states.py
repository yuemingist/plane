# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
按类型区分状态 单元测试（Step02 段 5 追赶 BE）。

用例锚点：段 5 产品方案 §6（GWT 1-14）、技术方案 §4。
覆盖：桥 states 读写端点（PUT 全量替换/空数组=继承全量）、非法 state 400（跨项目/软删）、
权限矩阵（GUEST/非成员/未登录）、state_ids 注入、新建校验（放行/拒绝/未显式选 state 不校验）、
改状态校验（放行/拒绝/继承全量）、与段 3 流转规则叠加语义（串联顺序 + 错误码区分）、
类型切换校验（放行/拒绝/组合改 state）、软删状态陈旧引用、跨项目隔离、零回归基线。
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.urls import reverse

from plane.db.models import (
    Issue,
    IssueActivity,
    IssueType,
    Project,
    ProjectMember,
    ProjectIssueType,
    State,
    User,
    Workflow,
)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def make_user(email: str) -> User:
    user = User.objects.create(email=email, username=email, first_name="Test")
    user.set_password("test@123")
    user.save()
    return user


def make_project(workspace, name: str, *, types_enabled: bool = True) -> Project:
    return Project.objects.create(
        name=name,
        workspace=workspace,
        identifier=f"TPS{uuid.uuid4().hex[:6].upper()}",
        is_issue_type_enabled=types_enabled,
    )


def add_member(project, user, role: int = 20) -> ProjectMember:
    return ProjectMember.objects.create(project=project, member=user, role=role)


def make_state(project, name: str, group: str = "unstarted") -> State:
    return State.objects.create(project=project, name=name, color="#60646C", group=group)


def make_type(workspace, name: str) -> IssueType:
    return IssueType.objects.create(workspace=workspace, name=name, is_active=True)


def bind_bridge(project, issue_type) -> ProjectIssueType:
    return ProjectIssueType.objects.create(project=project, issue_type=issue_type)


def states_url(project, issue_type) -> str:
    return reverse(
        "project-work-item-type-states",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(issue_type.id)},
    )


def issue_detail_url(project, issue) -> str:
    return reverse(
        "project-issue",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(issue.id)},
    )


def issue_create_url(project) -> str:
    return f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/issues/"


def types_url(project) -> str:
    return reverse("project-work-item-types", kwargs={"slug": project.workspace.slug, "project_id": str(project.id)})


def put_states(client, project, issue_type, state_ids) -> object:
    return client.put(states_url(project, issue_type), {"state_ids": state_ids}, format="json")


@pytest.fixture
def project(workspace, create_user):
    """已启用类型开关的干净项目，owner 为 create_user（ADMIN）"""
    project = make_project(workspace, "Type States Project")
    add_member(project, create_user, role=20)
    return project


@pytest.fixture
def states(project):
    """项目状态池：Todo(unstarted) / In Progress(started) / Done(completed)"""
    return {
        "todo": make_state(project, "Todo"),
        "in_progress": make_state(project, "In Progress", group="started"),
        "done": make_state(project, "Done", group="completed"),
    }


@pytest.fixture
def task_type(workspace):
    return make_type(workspace, "Task")


@pytest.fixture
def epic_type(workspace):
    return make_type(workspace, "Epic")


class TestTypeStatesCRUD:
    """桥 states 读写端点（产品方案 GWT-2，技术方案 §2.2）"""

    def test_put_sets_and_get_returns_states(self, session_client, project, task_type, states):
        """PUT 配置可用状态 → 200，GET 可读，M2M 落库，inherits_all=False"""
        bind_bridge(project, task_type)
        response = put_states(session_client, project, task_type, [str(states["todo"].id), str(states["done"].id)])
        assert response.status_code == status.HTTP_200_OK
        assert response.data["inherits_all"] is False
        assert set(response.data["state_ids"]) == {str(states["todo"].id), str(states["done"].id)}

        bridge = ProjectIssueType.objects.get(project=project, issue_type=task_type, deleted_at__isnull=True)
        assert set(bridge.states.values_list("id", flat=True)) == {states["todo"].id, states["done"].id}

        get_response = session_client.get(states_url(project, task_type))
        assert get_response.status_code == status.HTTP_200_OK
        assert set(get_response.data["state_ids"]) == {str(states["todo"].id), str(states["done"].id)}

    def test_put_empty_restores_inherit_all(self, session_client, project, task_type, states):
        """空数组 = 清空 = 恢复继承全量（产品方案 A2）"""
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id)])
        response = put_states(session_client, project, task_type, [])
        assert response.status_code == status.HTTP_200_OK
        assert response.data["state_ids"] == []
        assert response.data["inherits_all"] is True

    def test_get_unconfigured_type_inherits_all(self, session_client, project, task_type):
        """桥已绑定但从未配置 GET → 空数组 + inherits_all=True（兼容性，现网数据零影响）"""
        bind_bridge(project, task_type)
        response = session_client.get(states_url(project, task_type))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"state_ids": [], "inherits_all": True}

    def test_put_rejects_cross_project_state(self, session_client, workspace, project, task_type):
        """跨项目 state → 400（隔离）"""
        bind_bridge(project, task_type)
        other_project = make_project(workspace, "Type States Project B", types_enabled=False)
        other_state = make_state(other_project, "Other State")
        response = put_states(session_client, project, task_type, [str(other_state.id)])
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_put_rejects_soft_deleted_state(self, session_client, project, task_type, states):
        """软删 state → 400，不落库"""
        bind_bridge(project, task_type)
        states["done"].delete()  # SoftDeleteModel.delete → 置 deleted_at
        response = put_states(session_client, project, task_type, [str(states["done"].id)])
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        bridge = ProjectIssueType.objects.get(project=project, issue_type=task_type, deleted_at__isnull=True)
        assert bridge.states.count() == 0

    def test_type_list_includes_state_ids(self, session_client, project, task_type, states):
        """类型列表透出 state_ids 注入（技术方案 §2.1）；未配置 → []"""
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id)])
        response = session_client.get(types_url(project))
        assert response.status_code == status.HTTP_200_OK
        row = next(item for item in response.data if str(item["id"]) == str(task_type.id))
        assert row["state_ids"] == [str(states["todo"].id)]


class TestTypeStatesPermissions:
    """权限矩阵（产品方案 §5，A8）"""

    def test_guest_can_read_cannot_write(self, project, task_type, states, create_user):
        """GUEST GET 200 / PUT 403"""
        guest = make_user("guest-type-states@plane.so")
        add_member(project, guest, role=5)
        guest_client = APIClient()
        guest_client.force_authenticate(user=guest)

        bind_bridge(project, task_type)
        assert guest_client.get(states_url(project, task_type)).status_code == status.HTTP_200_OK
        response = put_states(guest_client, project, task_type, [str(states["todo"].id)])
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_member_cannot_access(self, workspace, session_client, project, task_type, states):
        """非项目成员 403"""
        outsider = make_user("outsider-type-states@plane.so")
        outsider_client = APIClient()
        outsider_client.force_authenticate(user=outsider)

        bind_bridge(project, task_type)
        assert outsider_client.get(states_url(project, task_type)).status_code == status.HTTP_403_FORBIDDEN
        response = put_states(outsider_client, project, task_type, [str(states["todo"].id)])
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self, project, task_type, states):
        """未登录 401"""
        client = APIClient()
        bind_bridge(project, task_type)
        assert client.get(states_url(project, task_type)).status_code == status.HTTP_401_UNAUTHORIZED
        response = put_states(client, project, task_type, [str(states["todo"].id)])
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestIssueCreateValidation:
    """新建校验（产品方案 GWT-1/4，A6）"""

    def test_create_with_allowed_state_succeeds(self, session_client, project, task_type, states, mock_celery):
        """GWT-1（正路径）：空集合继承全量，显式选 Done → 201"""
        bind_bridge(project, task_type)
        response = session_client.post(
            issue_create_url(project),
            {"name": "New Task", "type_id": str(task_type.id), "state_id": str(states["done"].id)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_with_state_outside_set_rejected(self, session_client, project, task_type, states, mock_celery):
        """GWT-4（拒路径）：集合外 state → 400 code=issue_type_state_not_allowed，工作项未落库"""
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id), str(states["in_progress"].id)])

        response = session_client.post(
            issue_create_url(project),
            {"name": "New Task", "type_id": str(task_type.id), "state_id": str(states["done"].id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "issue_type_state_not_allowed"
        assert Issue.objects.filter(project=project).count() == 0

    def test_create_without_explicit_state_not_validated(self, session_client, project, task_type, states, mock_celery):
        """A6：未显式选 state（落项目默认状态）→ 不校验集合，201"""
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["in_progress"].id)])

        response = session_client.post(
            issue_create_url(project),
            {"name": "New Task", "type_id": str(task_type.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED


class TestIssuePatchStateValidation:
    """改状态校验（产品方案 GWT-5/6，A2/A3）"""

    def _make_issue(self, project, state, issue_type=None) -> Issue:
        kwargs = {"project": project, "name": "Type States Issue", "state": state}
        if issue_type is not None:
            kwargs["type"] = issue_type
        return Issue.objects.create(**kwargs)

    def test_patch_to_allowed_state_succeeds(self, session_client, project, task_type, states, mock_celery):
        """GWT-6（正路径）：集合内目标状态 → 204"""
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id), str(states["done"].id)])
        issue = self._make_issue(project, states["todo"], task_type)

        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        issue.refresh_from_db()
        assert issue.state_id == states["done"].id

    def test_patch_to_disallowed_state_rejected(self, session_client, project, task_type, states, mock_celery):
        """GWT-5（拒路径）：集合外目标状态 → 400 + code + state 不变 + 不写活动留痕"""
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id)])
        issue = self._make_issue(project, states["todo"], task_type)

        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "issue_type_state_not_allowed"
        assert response.data["type_name"] == "Task"
        assert response.data["state_name"] == "Done"
        issue.refresh_from_db()
        assert issue.state_id == states["todo"].id
        # 拒绝发生在 serializer.save 之前：不产生 state 变更活动留痕（段 3 同口径）
        assert IssueActivity.objects.filter(issue=issue, field="state").count() == 0

    def test_patch_with_empty_set_inherits_all(self, session_client, project, task_type, states, mock_celery):
        """兼容性：集合为空（继承全量）→ 204，行为与 main 一致"""
        bind_bridge(project, task_type)
        issue = self._make_issue(project, states["todo"], task_type)

        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        issue.refresh_from_db()
        assert issue.state_id == states["done"].id

    def test_patch_without_type_ignores_validation(self, session_client, project, task_type, states, mock_celery):
        """无类型工作项（type 为空）→ 放行（A2 集合语义只作用于绑定类型的类型）"""
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id)])
        issue = self._make_issue(project, states["todo"])

        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestStackingWithTransitionRules:
    """与段 3 流转规则叠加语义（产品方案 GWT-9/10/11，A3 串联）"""

    def _make_issue(self, project, state, issue_type) -> Issue:
        return Issue.objects.create(project=project, name="Stacking Issue", state=state, type=issue_type)

    def _put_todo_rule(self, client, project, workflow, states):
        return client.put(
            reverse(
                "project-workflow-transitions",
                kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(workflow.id)},
            ),
            {"transitions": [{"from_state": str(states["todo"].id), "to_states": [str(states["in_progress"].id)]}]},
            format="json",
        )

    def test_type_set_passes_transition_rules_pass(self, session_client, project, task_type, states, mock_celery):
        """GWT-10：集合含 In Progress 且规则 Todo→In Progress → 204（两环都过）"""
        workflow = Workflow.objects.create(project=project, name="Default Workflow", is_active=True)
        self._put_todo_rule(session_client, project, workflow, states)
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["in_progress"].id), str(states["done"].id)])
        issue = self._make_issue(project, states["todo"], task_type)

        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["in_progress"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_set_passes_but_transition_rule_rejects(self, session_client, project, task_type, states, mock_celery):
        """GWT-11：集合含 Done 但流转规则只允许 In Progress → 400 workflow_transition_not_allowed"""
        workflow = Workflow.objects.create(project=project, name="Default Workflow", is_active=True)
        self._put_todo_rule(session_client, project, workflow, states)
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["in_progress"].id), str(states["done"].id)])
        issue = self._make_issue(project, states["todo"], task_type)

        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "workflow_transition_not_allowed"

    def test_set_checked_before_transition_rules(self, session_client, project, task_type, states, mock_celery):
        """A3 顺序：集合拒（Done 不在集合）在流转规则校验之前生效 → issue_type_state_not_allowed"""
        workflow = Workflow.objects.create(project=project, name="Default Workflow", is_active=True)
        self._put_todo_rule(session_client, project, workflow, states)
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id), str(states["in_progress"].id)])
        issue = self._make_issue(project, states["todo"], task_type)

        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "issue_type_state_not_allowed"

    def test_transition_rules_without_type_set_unaffected(
        self, session_client, project, task_type, states, mock_celery
    ):
        """零回归：未配置集合时段 3 规则行为不变（规则命中 → 拒绝；规则未命中 → 放行）"""
        workflow = Workflow.objects.create(project=project, name="Default Workflow", is_active=True)
        self._put_todo_rule(session_client, project, workflow, states)
        issue = self._make_issue(project, states["todo"], task_type)

        # 规则未命中目标状态 → 拒绝
        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "workflow_transition_not_allowed"
        # 规则命中目标状态 → 放行
        ok = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["in_progress"].id)}, format="json"
        )
        assert ok.status_code == status.HTTP_204_NO_CONTENT


class TestTypeSwitchValidation:
    """切换类型校验（产品方案 GWT-7/8，A4 拒绝式）"""

    def _make_issue(self, project, state, issue_type) -> Issue:
        return Issue.objects.create(project=project, name="Switch Issue", state=state, type=issue_type)

    def test_switch_to_compatible_type_succeeds(
        self, session_client, project, epic_type, task_type, states, mock_celery
    ):
        """GWT-7（正路径）：新类型集合含当前状态 → 204"""
        bind_bridge(project, epic_type)
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id), str(states["done"].id)])
        issue = self._make_issue(project, states["done"], epic_type)

        response = session_client.patch(issue_detail_url(project, issue), {"type_id": str(task_type.id)}, format="json")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        issue.refresh_from_db()
        assert issue.type_id == task_type.id

    def test_switch_to_incompatible_type_rejected(
        self, session_client, project, epic_type, task_type, states, mock_celery
    ):
        """GWT-8（拒路径）：新类型集合不含当前状态 → 400 + type 未变"""
        bind_bridge(project, epic_type)
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id), str(states["in_progress"].id)])
        issue = self._make_issue(project, states["done"], epic_type)

        response = session_client.patch(issue_detail_url(project, issue), {"type_id": str(task_type.id)}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "issue_type_state_not_allowed"
        assert response.data["type_name"] == "Task"
        issue.refresh_from_db()
        assert issue.type_id == epic_type.id

    def test_switch_with_state_change_combo(self, session_client, project, epic_type, task_type, states, mock_celery):
        """切类型 + 同时改 state：按新类型 + 新 state 校验 → 204"""
        bind_bridge(project, epic_type)
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id), str(states["in_progress"].id)])
        issue = self._make_issue(project, states["done"], epic_type)

        response = session_client.patch(
            issue_detail_url(project, issue),
            {"type_id": str(task_type.id), "state_id": str(states["in_progress"].id)},
            format="json",
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        issue.refresh_from_db()
        assert issue.type_id == task_type.id
        assert issue.state_id == states["in_progress"].id

    def test_switch_combo_state_outside_set_rejected(
        self, session_client, project, epic_type, task_type, states, mock_celery
    ):
        """切类型 + 同时改 state：新 state 在新类型集合外 → 400"""
        bind_bridge(project, epic_type)
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id)])
        issue = self._make_issue(project, states["done"], epic_type)

        response = session_client.patch(
            issue_detail_url(project, issue),
            {"type_id": str(task_type.id), "state_id": str(states["in_progress"].id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "issue_type_state_not_allowed"
        issue.refresh_from_db()
        assert issue.type_id == epic_type.id
        assert issue.state_id == states["done"].id


class TestSoftDeleteAndIsolation:
    """软删陈旧引用与跨项目隔离（产品方案 A9、GWT-13/14）"""

    def test_soft_deleted_state_filtered_from_set(self, session_client, project, task_type, states):
        """A9：集合含状态被软删后，GET/校验按剔除后的集合生效"""
        bind_bridge(project, task_type)
        put_states(session_client, project, task_type, [str(states["todo"].id), str(states["done"].id)])
        states["done"].delete()

        response = session_client.get(states_url(project, task_type))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["state_ids"] == [str(states["todo"].id)]
        assert response.data["inherits_all"] is False

    def test_cross_project_type_access_isolated(self, workspace, session_client, project, task_type, create_user):
        """GWT-14：项目 B 语境取项目 A 的类型 states → 404"""
        project_b = make_project(workspace, "Type States Project C")
        add_member(project_b, create_user, role=20)
        bind_bridge(project, task_type)

        response = session_client.get(states_url(project_b, task_type))
        assert response.status_code == status.HTTP_404_NOT_FOUND
