# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
流转规则 API 单元测试（Step02 段 3 追赶 BE）。

用例锚点：段 3 产品方案 §6（GWT 1-12）、技术方案 §4。
覆盖：规则 GET 空态、PUT 全量替换（建/改/清空）、非法 state 400、
规则变更写 WorkflowChangeLog（变化才写）、权限矩阵（GUEST/非成员/未登录）、
流转校验放行三态（无规则/源状态无规则/工作流停用）、拒绝路径（400+state 不变+
不触发 issue_activity）、状态删除级联清理、跨项目隔离。
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, IssueActivity, Project, ProjectMember, State, User, Workflow, WorkflowChangeLog, WorkflowTransition

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
        identifier=f"TRN{uuid.uuid4().hex[:6].upper()}",
    )


def add_member(project, user, role: int = 20) -> ProjectMember:
    return ProjectMember.objects.create(project=project, member=user, role=role)


def make_state(project, name: str, group: str = "unstarted") -> State:
    return State.objects.create(project=project, name=name, color="#60646C", group=group)


def make_workflow(project, is_active: bool = True) -> Workflow:
    return Workflow.objects.create(project=project, name="Default Workflow", is_active=is_active)


def transitions_url(project, workflow) -> str:
    from django.urls import reverse

    return reverse(
        "project-workflow-transitions",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(workflow.id)},
    )


def issue_detail_url(project, issue) -> str:
    from django.urls import reverse

    return reverse(
        "project-issue",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(issue.id)},
    )


def put_transitions(client, project, workflow, groups) -> object:
    return client.put(transitions_url(project, workflow), {"transitions": groups}, format="json")


@pytest.fixture
def project(workspace, create_user):
    """干净项目，owner 为 create_user（ADMIN）"""
    project = make_project(workspace, "Transition Project")
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
def enabled_workflow(project):
    return make_workflow(project)


class TestTransitionRulesCRUD:
    """规则 CRUD（产品方案 GWT-6，技术方案 §2）"""

    def test_get_returns_empty_list_when_no_rules(self, session_client, project, enabled_workflow):
        """空规则 → 200 []（默认无规则 = 全部允许的读取面）"""
        response = session_client.get(transitions_url(project, enabled_workflow))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_put_creates_rules_and_get_returns_rows(self, session_client, project, enabled_workflow, states):
        """PUT 分组形态 → 展开成行落库，GET 可读"""
        response = put_transitions(
            session_client,
            project,
            enabled_workflow,
            [{"from_state": str(states["todo"].id), "to_states": [str(states["in_progress"].id)]}],
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert str(response.data[0]["from_state"]) == str(states["todo"].id)
        assert str(response.data[0]["to_state"]) == str(states["in_progress"].id)

        assert WorkflowTransition.objects.filter(workflow=enabled_workflow).count() == 1

        get_response = session_client.get(transitions_url(project, enabled_workflow))
        assert get_response.status_code == status.HTTP_200_OK
        assert len(get_response.data) == 1

    def test_put_replaces_all_rules(self, session_client, project, enabled_workflow, states):
        """全量替换：旧行不残留"""
        put_transitions(
            session_client,
            project,
            enabled_workflow,
            [{"from_state": str(states["todo"].id), "to_states": [str(states["in_progress"].id)]}],
        )
        response = put_transitions(
            session_client,
            project,
            enabled_workflow,
            [
                {"from_state": str(states["todo"].id), "to_states": [str(states["done"].id)]},
                {"from_state": str(states["in_progress"].id), "to_states": [str(states["done"].id)]},
            ],
        )
        assert response.status_code == status.HTTP_200_OK
        rows = set(WorkflowTransition.objects.filter(workflow=enabled_workflow).values_list("from_state_id", "to_state_id"))
        assert rows == {
            (states["todo"].id, states["done"].id),
            (states["in_progress"].id, states["done"].id),
        }

    def test_put_empty_clears_rules(self, session_client, project, enabled_workflow, states):
        """空数组 = 清空规则（产品方案 A2）"""
        put_transitions(
            session_client,
            project,
            enabled_workflow,
            [{"from_state": str(states["todo"].id), "to_states": [str(states["in_progress"].id)]}],
        )
        response = put_transitions(session_client, project, enabled_workflow, [])
        assert response.status_code == status.HTTP_200_OK
        assert WorkflowTransition.objects.filter(workflow=enabled_workflow).count() == 0

    def test_put_rejects_invalid_states(self, session_client, workspace, project, enabled_workflow, states):
        """from=to / 跨项目 state / 非法 uuid → 400，不落库"""
        other_project = make_project(workspace, "Transition Project B")
        other_state = make_state(other_project, "Other State")

        same = put_transitions(
            session_client,
            project,
            enabled_workflow,
            [{"from_state": str(states["todo"].id), "to_states": [str(states["todo"].id)]}],
        )
        assert same.status_code == status.HTTP_400_BAD_REQUEST

        cross = put_transitions(
            session_client,
            project,
            enabled_workflow,
            [{"from_state": str(states["todo"].id), "to_states": [str(other_state.id)]}],
        )
        assert cross.status_code == status.HTTP_400_BAD_REQUEST

        bad_uuid = put_transitions(
            session_client,
            project,
            enabled_workflow,
            [{"from_state": str(states["todo"].id), "to_states": ["not-a-uuid"]}],
        )
        assert bad_uuid.status_code == status.HTTP_400_BAD_REQUEST

        assert WorkflowTransition.objects.count() == 0


class TestTransitionChangeLog:
    """规则变更写 WorkflowChangeLog（产品方案 A3，GWT-7）"""

    def test_put_writes_change_log_on_change(self, session_client, project, enabled_workflow, states, create_user):
        """规则实际变化 → 新增一条 transition_rules_updated 历史"""
        put_transitions(
            session_client,
            project,
            enabled_workflow,
            [{"from_state": str(states["todo"].id), "to_states": [str(states["in_progress"].id)]}],
        )
        log = WorkflowChangeLog.objects.filter(
            workflow=enabled_workflow, action="transition_rules_updated"
        ).first()
        assert log is not None
        assert log.actor_id == create_user.id
        assert "1" in (log.note or "")

    def test_put_without_change_does_not_write_log(self, session_client, project, enabled_workflow, states):
        """无变化的重复 PUT → 不新增历史（避免噪音，技术方案 §2）"""
        groups = [{"from_state": str(states["todo"].id), "to_states": [str(states["in_progress"].id)]}]
        put_transitions(session_client, project, enabled_workflow, groups)
        count_before = WorkflowChangeLog.objects.filter(
            workflow=enabled_workflow, action="transition_rules_updated"
        ).count()
        put_transitions(session_client, project, enabled_workflow, groups)
        count_after = WorkflowChangeLog.objects.filter(
            workflow=enabled_workflow, action="transition_rules_updated"
        ).count()
        assert count_before == count_after == 1


class TestTransitionPermissions:
    """权限矩阵（产品方案 §5，GWT-8/9/12）"""

    def test_guest_can_read_cannot_write(self, session_client, project, enabled_workflow, states, create_user):
        """GUEST 读 200 / PUT 403"""
        guest = make_user("guest-transitions@plane.so")
        add_member(project, guest, role=5)
        guest_client = APIClient()
        guest_client.force_authenticate(user=guest)

        assert guest_client.get(transitions_url(project, enabled_workflow)).status_code == status.HTTP_200_OK
        response = put_transitions(
            guest_client,
            project,
            enabled_workflow,
            [{"from_state": str(states["todo"].id), "to_states": [str(states["done"].id)]}],
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_member_cannot_access(self, workspace, session_client, project, enabled_workflow):
        """非项目成员 403"""
        outsider = make_user("outsider-transitions@plane.so")
        outsider_client = APIClient()
        outsider_client.force_authenticate(user=outsider)

        assert outsider_client.get(transitions_url(project, enabled_workflow)).status_code == status.HTTP_403_FORBIDDEN
        assert (
            outsider_client.put(transitions_url(project, enabled_workflow), {"transitions": []}, format="json").status_code
            == status.HTTP_403_FORBIDDEN
        )

    def test_unauthenticated_returns_401(self, project, enabled_workflow):
        """未登录 401"""
        client = APIClient()
        assert client.get(transitions_url(project, enabled_workflow)).status_code == status.HTTP_401_UNAUTHORIZED
        assert (
            client.put(transitions_url(project, enabled_workflow), {"transitions": []}, format="json").status_code
            == status.HTTP_401_UNAUTHORIZED
        )

    def test_project_isolation(self, workspace, session_client, project, enabled_workflow, create_user):
        """项目 B 语境下取项目 A 的 workflow → 404（GWT-12）"""
        project_b = make_project(workspace, "Transition Project B")
        add_member(project_b, create_user, role=20)
        response = session_client.get(transitions_url(project_b, enabled_workflow))
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestStateTransitionValidation:
    """issue PATCH 流转校验（产品方案 GWT-1/2/3/4/5/10）"""

    def _make_issue(self, project, state) -> Issue:
        return Issue.objects.create(project=project, name="Transition Issue", state=state)

    def _put_todo_rule(self, client, project, workflow, states):
        return put_transitions(
            client,
            project,
            workflow,
            [{"from_state": str(states["todo"].id), "to_states": [str(states["in_progress"].id)]}],
        )

    def test_patch_allowed_transition_succeeds(self, session_client, project, enabled_workflow, states, mock_celery):
        """GWT-3（正路径）：Todo → In Progress 命中规则 → 204"""
        self._put_todo_rule(session_client, project, enabled_workflow, states)
        issue = self._make_issue(project, states["todo"])

        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["in_progress"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        issue.refresh_from_db()
        assert issue.state_id == states["in_progress"].id

    def test_patch_disallowed_transition_rejected(self, session_client, project, enabled_workflow, states, mock_celery):
        """GWT-2（拒路径）：Todo → Done 不在规则内 → 400 + code + state 不变"""
        self._put_todo_rule(session_client, project, enabled_workflow, states)
        issue = self._make_issue(project, states["todo"])

        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "workflow_transition_not_allowed"
        assert response.data["from_state_name"] == "Todo"
        assert response.data["to_state_name"] == "Done"

        issue.refresh_from_db()
        assert issue.state_id == states["todo"].id

    def test_rejected_transition_does_not_write_activity(
        self, session_client, project, enabled_workflow, states, mock_celery
    ):
        """GWT-10（拒路径）：被拒不触发 issue_activity（无 state 活动留痕）"""
        self._put_todo_rule(session_client, project, enabled_workflow, states)
        issue = self._make_issue(project, states["todo"])

        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert mock_celery.call_count == 0
        assert IssueActivity.objects.filter(issue=issue, field="state").count() == 0

    def test_no_rules_allows_all_transitions(self, session_client, project, enabled_workflow, states, mock_celery):
        """GWT-1（正路径）：无规则 = 全部允许（A2）"""
        issue = self._make_issue(project, states["todo"])
        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_state_without_rule_entry_is_unrestricted(self, session_client, project, enabled_workflow, states, mock_celery):
        """GWT-4：只配了 Todo 规则，In Progress 无规则条目 → 不受限（A2 精确化）"""
        self._put_todo_rule(session_client, project, enabled_workflow, states)
        issue = self._make_issue(project, states["in_progress"])

        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_disabled_workflow_does_not_enforce(self, session_client, project, enabled_workflow, states, mock_celery):
        """GWT-5：工作流停用 → 规则暂停执行（官方「停用暂停执行不丢配置」）"""
        self._put_todo_rule(session_client, project, enabled_workflow, states)
        enabled_workflow.is_active = False
        enabled_workflow.save(update_fields=["is_active"])

        issue = self._make_issue(project, states["todo"])
        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["done"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_same_state_patch_is_noop_allowed(self, session_client, project, enabled_workflow, states, mock_celery):
        """同状态 PATCH（非流转）不触发校验拒绝"""
        self._put_todo_rule(session_client, project, enabled_workflow, states)
        issue = self._make_issue(project, states["todo"])
        response = session_client.patch(
            issue_detail_url(project, issue), {"state_id": str(states["todo"].id)}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestSoftDeletedStates:
    """软删除状态与规则（产品方案 A6，GWT-11：CE State 为软删除，无即时级联）"""

    def test_soft_deleted_state_rejected_and_stale_rules_dropped_on_replace(
        self, session_client, project, enabled_workflow, states, mock_celery
    ):
        """软删除状态不可作为规则端点（400）；全量替换丢弃陈旧行"""
        put_transitions(
            session_client,
            project,
            enabled_workflow,
            [{"from_state": str(states["todo"].id), "to_states": [str(states["in_progress"].id)]}],
        )
        assert WorkflowTransition.objects.filter(workflow=enabled_workflow).count() == 1

        # 软删除 In Progress（SoftDeleteModel：delete() 置 deleted_at）
        states["in_progress"].delete()
        states["in_progress"].refresh_from_db()
        assert states["in_progress"].deleted_at is not None

        # 软删除后的状态不能再作为规则端点
        response = put_transitions(
            session_client,
            project,
            enabled_workflow,
            [{"from_state": str(states["todo"].id), "to_states": [str(states["in_progress"].id)]}],
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # 全量替换（不含已删状态）丢弃陈旧行
        response = put_transitions(
            session_client,
            project,
            enabled_workflow,
            [{"from_state": str(states["todo"].id), "to_states": [str(states["done"].id)]}],
        )
        assert response.status_code == status.HTTP_200_OK
        rows = set(
            WorkflowTransition.objects.filter(workflow=enabled_workflow).values_list("from_state_id", "to_state_id")
        )
        assert rows == {(states["todo"].id, states["done"].id)}
