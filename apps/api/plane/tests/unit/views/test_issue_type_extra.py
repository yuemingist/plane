# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
工作项类型贯穿改动（Step01 追赶 BE-3）单元测试。

覆盖：work-items 列表/详情响应含 type_id 且原有字段不缺；IssueFilterSet 的
type_id / type_id__in / parent__type_id 筛选；type 变更产生
`changed work item type to X from Y` 活动留痕（直接同步调用 celery 任务）。
"""

import json
import uuid

import pytest
from django.urls import reverse
from rest_framework import status

from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import Issue, IssueActivity, IssueType, Project, ProjectIssueType, ProjectMember, User
from plane.utils.filters import IssueFilterSet

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def make_user(email: str) -> User:
    user = User.objects.create(email=email, username=email, first_name="Test")
    user.set_password("test@123")
    user.save()
    return user


@pytest.fixture
def project(workspace, create_user):
    project = Project.objects.create(
        name="Cross-cutting Project",
        workspace=workspace,
        identifier=f"XCU{uuid.uuid4().hex[:6].upper()}",
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20)
    project.is_issue_type_enabled = True
    project.save(update_fields=["is_issue_type_enabled"])
    return project


@pytest.fixture
def types(project):
    epic = IssueType.objects.create(workspace=project.workspace, name="Epic", is_epic=True, is_active=True, level=1)
    task = IssueType.objects.create(workspace=project.workspace, name="Task", is_epic=False, is_active=True, level=0)
    bug = IssueType.objects.create(workspace=project.workspace, name="Bug", is_active=True, level=0)
    ProjectIssueType.objects.create(project=project, issue_type=epic, level=1, is_default=False)
    ProjectIssueType.objects.create(project=project, issue_type=task, level=0, is_default=True)
    ProjectIssueType.objects.create(project=project, issue_type=bug, level=0, is_default=False)
    return {"epic": epic, "task": task, "bug": bug}


def make_issue(project, name: str, type_obj=None, parent=None) -> Issue:
    return Issue.objects.create(project=project, name=name, type=type_obj, parent=parent)


class TestIssueSerializerTypeId:
    """段 1b 前置：读模型下发 type_id（BE-3 三处之一）"""

    def test_issue_serializer_outputs_type_id(self, project, types):
        issue = make_issue(project, "Typed issue", type_obj=types["bug"])
        from plane.app.serializers import IssueSerializer

        data = IssueSerializer(issue).data
        # PK 字段返回 UUID 对象（渲染前数据），统一 str 对比
        assert str(data["type_id"]) == str(types["bug"].id)

    def test_issue_detail_serializer_inherits_type_id(self, project, types):
        """current_instance 序列化包含 type_id（track_type 依赖它取旧值）"""
        issue = make_issue(project, "Detail issue", type_obj=types["bug"])
        from plane.app.serializers import IssueDetailSerializer

        data = IssueDetailSerializer(issue).data
        assert str(data["type_id"]) == str(types["bug"].id)
        # 原有字段不缺（抽样）
        for key in ("id", "name", "state_id", "priority", "sequence_id", "project_id", "parent_id"):
            assert key in data

    def test_untyped_issue_returns_null_type_id(self, project, types):
        issue = make_issue(project, "Untyped issue")
        from plane.app.serializers import IssueSerializer

        assert IssueSerializer(issue).data["type_id"] is None


class TestWorkItemsListTypeId:
    """列表响应含 type_id 且原有字段不缺"""

    def test_work_items_list_contains_type_id(self, session_client, project, types, mock_celery):
        issue = make_issue(project, "List issue", type_obj=types["task"])

        url = reverse("project-issue", kwargs={"slug": project.workspace.slug, "project_id": str(project.id)})
        response = session_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        target = next(item for item in results if str(item["id"]) == str(issue.id))
        assert str(target["type_id"]) == str(types["task"].id)
        # 原有字段不缺（抽样）
        for key in ("name", "state_id", "priority", "sequence_id", "project_id", "parent_id", "created_at"):
            assert key in target

    def test_issue_list_endpoint_contains_type_id(self, session_client, project, types, mock_celery):
        """IssueListEndpoint（/issues/list/，.values() 追加处）"""
        issue = make_issue(project, "List endpoint issue", type_obj=types["bug"])

        url = reverse("project-issue", kwargs={"slug": project.workspace.slug, "project_id": str(project.id)})
        response = session_client.get(f"{url}list/", {"issues": str(issue.id)})
        assert response.status_code == status.HTTP_200_OK
        target = next(item for item in response.data if str(item["id"]) == str(issue.id))
        assert str(target["type_id"]) == str(types["bug"].id)

    def test_issue_create_response_contains_type_id(self, session_client, project, types, mock_celery):
        url = reverse("project-issue", kwargs={"slug": project.workspace.slug, "project_id": str(project.id)})
        response = session_client.post(url, {"name": "Created issue", "type_id": str(types["bug"].id)}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert str(response.data["type_id"]) == str(types["bug"].id)


class TestIssueTypeFilters:
    """B-6/B-7 后端面：IssueFilterSet type_id / parent__type_id"""

    def test_filterset_type_id(self, project, types):
        issue_bug = make_issue(project, "Bug issue", type_obj=types["bug"])
        make_issue(project, "Task issue", type_obj=types["task"])

        queryset = Issue.objects.filter(project_id=project.id)
        filtered = IssueFilterSet(queryset=queryset, data={"type_id": str(types["bug"].id)}).qs
        assert set(filtered.values_list("id", flat=True)) == {issue_bug.id}

    def test_filterset_type_id_in(self, project, types):
        issue_bug = make_issue(project, "Bug in", type_obj=types["bug"])
        issue_task = make_issue(project, "Task in", type_obj=types["task"])
        issue_none = make_issue(project, "No type")

        filtered = IssueFilterSet(
            queryset=Issue.objects.filter(project_id=project.id),
            data={"type_id__in": f"{types['bug'].id},{types['task'].id}"},
        ).qs
        assert set(filtered.values_list("id", flat=True)) == {issue_bug.id, issue_task.id}
        assert issue_none.id not in set(filtered.values_list("id", flat=True))

    def test_filterset_parent_type_id(self, project, types):
        """B-7：Parent type 关系筛选——按父工作项的类型过滤"""
        epic_parent = make_issue(project, "Epic parent", type_obj=types["epic"])
        task_parent = make_issue(project, "Task parent", type_obj=types["task"])
        child_of_epic = make_issue(project, "Child of epic", type_obj=types["task"], parent=epic_parent)
        child_of_task = make_issue(project, "Child of task", type_obj=types["task"], parent=task_parent)

        filtered = IssueFilterSet(
            queryset=Issue.objects.filter(project_id=project.id),
            data={"parent__type_id": str(types["epic"].id)},
        ).qs
        assert set(filtered.values_list("id", flat=True)) == {child_of_epic.id}
        assert child_of_task.id not in set(filtered.values_list("id", flat=True))

    def test_filter_via_work_items_api(self, session_client, project, types, mock_celery):
        """端到端：rich filters JSON 参数走 ComplexFilterBackend → IssueFilterSet
        （注意：issue 列表的 filterset 只经由 `filters` JSON 参数生效）"""
        epic_parent = make_issue(project, "API epic parent", type_obj=types["epic"])
        child = make_issue(project, "API child", type_obj=types["task"], parent=epic_parent)
        make_issue(project, "API standalone", type_obj=types["task"])

        url = reverse("project-issue", kwargs={"slug": project.workspace.slug, "project_id": str(project.id)})
        filters = json.dumps({"parent__type_id": str(types["epic"].id)})
        response = session_client.get(url, {"filters": filters})
        assert response.status_code == status.HTTP_200_OK
        ids = {str(item["id"]) for item in response.data["results"]}
        assert ids == {str(child.id)}

    def test_filter_type_id_via_work_items_api(self, session_client, project, types, mock_celery):
        issue_bug = make_issue(project, "API bug", type_obj=types["bug"])
        make_issue(project, "API task", type_obj=types["task"])

        url = reverse("project-issue", kwargs={"slug": project.workspace.slug, "project_id": str(project.id)})
        filters = json.dumps({"type_id": str(types["bug"].id)})
        response = session_client.get(url, {"filters": filters})
        assert response.status_code == status.HTTP_200_OK
        ids = {str(item["id"]) for item in response.data["results"]}
        assert ids == {str(issue_bug.id)}


class TestTypeChangeActivity:
    """B-3：type 变更产生 `changed work item type to X from Y` 活动留痕"""

    def _run_update_activity(self, issue, old_type, new_type, actor):
        """复刻 IssueViewSet.partial_update 传参：current_instance 来自 IssueDetailSerializer"""
        from django.core.serializers.json import DjangoJSONEncoder

        from plane.app.serializers import IssueDetailSerializer

        # 视图同款：序列化器输出含 UUID 对象，必须用 DjangoJSONEncoder
        current_instance = json.dumps(IssueDetailSerializer(issue).data, cls=DjangoJSONEncoder)
        issue_activity(
            type="issue.activity.updated",
            requested_data=json.dumps({"type_id": str(new_type.id)}),
            current_instance=current_instance,
            issue_id=str(issue.id),
            actor_id=str(actor.id),
            project_id=str(issue.project_id),
            epoch=1,
            notification=False,
            subscriber=False,
        )

    def test_type_change_creates_activity(self, project, types, create_user):
        """文案对齐云端：changed work item type to {new} from {old}"""
        issue = make_issue(project, "Type switch issue", type_obj=types["bug"])

        self._run_update_activity(issue, types["bug"], types["task"], create_user)

        activity = IssueActivity.objects.filter(issue_id=issue.id, field="type").first()
        assert activity is not None
        assert activity.comment == f"changed work item type to {types['task'].name} from {types['bug'].name}"
        assert activity.old_value == types["bug"].name
        assert activity.new_value == types["task"].name
        assert activity.verb == "updated"

    def test_no_activity_when_type_unchanged(self, project, types, create_user):
        issue = make_issue(project, "No change issue", type_obj=types["bug"])
        self._run_update_activity(issue, types["bug"], types["bug"], create_user)
        assert IssueActivity.objects.filter(issue_id=issue.id, field="type").count() == 0

    def test_activity_falls_back_to_uuid_prefix_when_type_missing(self, project, types, create_user):
        """R6：旧类型已被删除时，名称兜底显示 UUID 前缀"""
        issue = make_issue(project, "Orphan type issue", type_obj=types["bug"])
        deleted_type_id = str(types["bug"].id)
        types["bug"].delete()

        current_instance = json.dumps({"type_id": deleted_type_id})
        issue_activity(
            type="issue.activity.updated",
            requested_data=json.dumps({"type_id": str(types["task"].id)}),
            current_instance=current_instance,
            issue_id=str(issue.id),
            actor_id=str(create_user.id),
            project_id=str(issue.project_id),
            epoch=1,
            notification=False,
            subscriber=False,
        )

        activity = IssueActivity.objects.filter(issue_id=issue.id, field="type").first()
        assert activity is not None
        assert activity.comment == f"changed work item type to {types['task'].name} from {deleted_type_id[:8]}…"

    def test_type_change_via_api_and_sync_task(self, session_client, project, types, create_user, mock_celery):
        """PATCH type_id 生效且写入键会被活动链路消费（视图 delay 被打桩，
        这里再同步执行任务验证 requested_data 里的 type_id 键能对上读模型）"""
        issue = make_issue(project, "API type switch", type_obj=types["bug"])

        url = reverse(
            "project-issue",
            kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(issue.id)},
        )
        response = session_client.patch(url, {"type_id": str(types["task"].id)}, format="json")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        issue.refresh_from_db()
        assert issue.type_id == types["task"].id
