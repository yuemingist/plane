# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
自定义属性贯穿单元测试（Step02 段 4 追赶 BE）。

用例锚点：段 4 产品方案 §6 GWT（G2/G6-G9/G11）、技术方案 §7 pytest 计划。
覆盖：列表响应属性值批量聚合（含 assertNumQueries 恒定，无 N+1）、
customproperty 筛选（下拉单值/多值 contains、成员、日期、布尔、非法/跨项目
属性 id 空匹配、非法键 400）、导出动态属性列（含禁用属性不出列与对齐防御）。
"""

import json
import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    Issue,
    IssueProperty,
    IssuePropertyValue,
    IssueType,
    Project,
    ProjectIssueType,
    ProjectMember,
    State,
    User,
    Workspace,
)
from plane.utils.property_values import attach_issue_property_export_columns

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


# ---------- 造数 helpers（与段 2 测试同构） ----------


def make_user(email: str) -> User:
    user = User.objects.create(email=email, username=email, first_name="Test")
    user.set_password("test@123")
    user.save()
    return user


def add_member(project: Project, user: User, role: int = 20) -> ProjectMember:
    return ProjectMember.objects.create(project=project, member=user, role=role)


def make_project(workspace: Workspace, name: str) -> Project:
    return Project.objects.create(
        name=name,
        workspace=workspace,
        identifier=f"PRP{uuid.uuid4().hex[:6].upper()}",
    )


def make_type(workspace: Workspace, project: Project, name: str) -> IssueType:
    issue_type = IssueType.objects.create(workspace=workspace, name=name, is_active=True, level=0)
    ProjectIssueType.objects.create(project=project, issue_type=issue_type, level=0)
    return issue_type


def make_property(
    project: Project,
    name: str,
    property_type: str,
    settings: dict | None = None,
    is_active: bool = True,
) -> IssueProperty:
    return IssueProperty.objects.create(
        project=project,
        workspace=project.workspace,
        name=name,
        property_type=property_type,
        settings=settings or {},
        is_active=is_active,
    )


def bind_property(issue_type: IssueType, issue_property: IssueProperty) -> None:
    from plane.db.models import IssueTypeIssueProperty

    IssueTypeIssueProperty.objects.create(issue_type=issue_type, issue_property=issue_property)


def make_issue(project: Project, name: str, type_obj=None) -> Issue:
    state, _ = State.objects.get_or_create(
        project=project,
        name="Backlog",
        defaults={"group": "backlog", "color": "#000000"},
    )
    return Issue.objects.create(project=project, name=name, state=state, type=type_obj)


def set_value(issue: Issue, issue_property: IssueProperty, value) -> IssuePropertyValue:
    return IssuePropertyValue.objects.create(issue=issue, issue_property=issue_property, value=value)


# ---------- 端点 helpers ----------


def issues_list_url(project: Project) -> str:
    from django.urls import reverse

    return reverse("project-issue", kwargs={"slug": project.workspace.slug, "project_id": str(project.id)})


def filters_payload(**conditions) -> str:
    """rich filters JSON：leaf 条件 AND 组合（与前端 TWorkItemFilterExpression 同构）"""
    return json.dumps({"and": [dict([condition]) for condition in conditions.items()]})


# ---------- fixtures ----------


@pytest.fixture
def enabled_project(workspace, create_user):
    project = make_project(workspace, "Penetration Project")
    add_member(project, create_user, role=20)
    project.is_issue_type_enabled = True
    project.save(update_fields=["is_issue_type_enabled"])
    return project


@pytest.fixture
def issue_type(enabled_project):
    return make_type(enabled_project.workspace, enabled_project, "Bug")


@pytest.fixture
def dropdown_property(enabled_project):
    return make_property(
        enabled_project,
        "调研-下拉属性",
        "option",
        settings={
            "is_multi": True,
            "options": [
                {"id": str(uuid.uuid4()), "name": "选项A", "is_default": False},
                {"id": str(uuid.uuid4()), "name": "选项B", "is_default": False},
            ],
        },
    )


@pytest.fixture
def text_property(enabled_project):
    return make_property(enabled_project, "调研-文本属性", "text")


@pytest.fixture
def member_property(enabled_project):
    return make_property(enabled_project, "调研-成员属性", "member", settings={"is_multi": False})


@pytest.fixture
def date_property(enabled_project):
    return make_property(enabled_project, "调研-日期属性", "date")


@pytest.fixture
def boolean_property(enabled_project):
    return make_property(enabled_project, "调研-布尔属性", "boolean")


# ---------- 列表聚合 ----------


class TestListPropertyValues:
    """列表响应属性值批量聚合（技术方案 §7 列表聚合组）"""

    def test_list_includes_property_values(
        self, session_client, enabled_project, issue_type, dropdown_property, mock_celery
    ):
        """值随行返回：{property_id: rawJSON}，多选下拉为数组"""
        bind_property(issue_type, dropdown_property)
        issue = make_issue(enabled_project, "带值工作项", type_obj=issue_type)
        option_id = dropdown_property.settings["options"][0]["id"]
        set_value(issue, dropdown_property, [option_id])
        empty_issue = make_issue(enabled_project, "无值工作项", type_obj=issue_type)

        response = session_client.get(issues_list_url(enabled_project), format="json")
        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        values_by_name = {row["name"]: row["issue_property_values"] for row in results}
        assert values_by_name["带值工作项"] == {str(dropdown_property.id): [option_id]}
        # 无值行为空 dict（G3）
        assert values_by_name["无值工作项"] == {}

    def test_list_excludes_disabled_property_values(
        self, session_client, enabled_project, issue_type, dropdown_property, mock_celery
    ):
        """禁用属性（双门控第二门关闭）的值不出现在列表响应（G11 对齐）"""
        bind_property(issue_type, dropdown_property)
        issue = make_issue(enabled_project, "禁用属性工作项", type_obj=issue_type)
        option_id = dropdown_property.settings["options"][0]["id"]
        set_value(issue, dropdown_property, [option_id])
        dropdown_property.is_active = False
        dropdown_property.save(update_fields=["is_active"])

        response = session_client.get(issues_list_url(enabled_project), format="json")
        assert response.status_code == status.HTTP_200_OK
        for row in response.data["results"]:
            assert row["issue_property_values"] == {}

    def test_list_batch_queries_constant(
        self, session_client, enabled_project, issue_type, text_property, mock_celery
    ):
        """性能红线：补值恒定 +1 查询，与值行数/属性数无关（无 N+1）"""
        bind_property(issue_type, text_property)
        for index in range(5):
            issue = make_issue(enabled_project, f"工作项{index}", type_obj=issue_type)
            set_value(issue, text_property, f"值{index}")

        url = issues_list_url(enabled_project)

        def run_list():
            with CaptureQueriesContext(connection) as context:
                response = session_client.get(url, format="json")
                assert response.status_code == status.HTTP_200_OK
            return len(context.captured_queries)

        count_without_values = run_list()
        # 再加 3 个工作项 3 条值：查询数应保持不变（分页批量补值恒 +1）
        for index in range(3):
            issue = make_issue(enabled_project, f"追加工作项{index}", type_obj=issue_type)
            set_value(issue, text_property, "追加值")
        count_with_more_values = run_list()
        assert count_with_more_values == count_without_values


# ---------- customproperty 筛选 ----------


class TestCustomPropertyFilters:
    """customproperty_<id> 筛选（技术方案 §7 筛选组）"""

    def test_filter_option_single_in(
        self, session_client, enabled_project, issue_type, dropdown_property, mock_celery
    ):
        """下拉单选属性：__in 选项 id，命中含该选项的工作项（G7）"""
        dropdown_property.settings["is_multi"] = False
        dropdown_property.save(update_fields=["settings"])
        bind_property(issue_type, dropdown_property)
        option_a, option_b = [option["id"] for option in dropdown_property.settings["options"]]
        hit = make_issue(enabled_project, "命中A", type_obj=issue_type)
        set_value(hit, dropdown_property, option_a)
        other = make_issue(enabled_project, "命中B", type_obj=issue_type)
        set_value(other, dropdown_property, option_b)
        make_issue(enabled_project, "无值", type_obj=issue_type)

        response = session_client.get(
            issues_list_url(enabled_project),
            {"filters": filters_payload(**{f"customproperty_{dropdown_property.id}__in": [option_a]})},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        names = {row["name"] for row in response.data["results"]}
        assert names == {"命中A"}

    def test_filter_option_multi_contains(
        self, session_client, enabled_project, issue_type, dropdown_property, mock_celery
    ):
        """多选下拉属性：任一选项命中（value__contains OR，G7 多选面）"""
        bind_property(issue_type, dropdown_property)
        option_a, option_b = [option["id"] for option in dropdown_property.settings["options"]]
        hit = make_issue(enabled_project, "多选含A", type_obj=issue_type)
        set_value(hit, dropdown_property, [option_a, option_b])
        make_issue(enabled_project, "多选含B", type_obj=issue_type)
        other = make_issue(enabled_project, "含B", type_obj=issue_type)
        set_value(other, dropdown_property, [option_b])

        response = session_client.get(
            issues_list_url(enabled_project),
            {"filters": filters_payload(**{f"customproperty_{dropdown_property.id}__in": [option_a]})},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        names = {row["name"] for row in response.data["results"]}
        assert names == {"多选含A"}

    def test_filter_member_exact(
        self, session_client, enabled_project, issue_type, member_property, create_user, mock_celery
    ):
        """成员属性：exact 成员 id（G8）"""
        bind_property(issue_type, member_property)
        hit = make_issue(enabled_project, "成员命中", type_obj=issue_type)
        set_value(hit, member_property, str(create_user.id))
        make_issue(enabled_project, "成员未填", type_obj=issue_type)

        response = session_client.get(
            issues_list_url(enabled_project),
            {"filters": filters_payload(**{f"customproperty_{member_property.id}__exact": str(create_user.id)})},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        names = {row["name"] for row in response.data["results"]}
        assert names == {"成员命中"}

    def test_filter_date_exact(
        self, session_client, enabled_project, issue_type, date_property, mock_celery
    ):
        """日期属性：exact ISO 日期字符串（G9）"""
        bind_property(issue_type, date_property)
        hit = make_issue(enabled_project, "日期命中", type_obj=issue_type)
        set_value(hit, date_property, "2026-11-17")
        make_issue(enabled_project, "日期未填", type_obj=issue_type)

        response = session_client.get(
            issues_list_url(enabled_project),
            {"filters": filters_payload(**{f"customproperty_{date_property.id}__exact": "2026-11-17"})},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        names = {row["name"] for row in response.data["results"]}
        assert names == {"日期命中"}

    def test_filter_boolean_exact(
        self, session_client, enabled_project, issue_type, boolean_property, mock_celery
    ):
        """布尔属性：exact true/false 字符串规整为布尔匹配（G9）"""
        bind_property(issue_type, boolean_property)
        hit = make_issue(enabled_project, "布尔真", type_obj=issue_type)
        set_value(hit, boolean_property, True)
        other = make_issue(enabled_project, "布尔假", type_obj=issue_type)
        set_value(other, boolean_property, False)

        response = session_client.get(
            issues_list_url(enabled_project),
            {"filters": filters_payload(**{f"customproperty_{boolean_property.id}__exact": "true"})},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        names = {row["name"] for row in response.data["results"]}
        assert names == {"布尔真"}

    def test_filter_unknown_property_id_empty(self, session_client, enabled_project, mock_celery):
        """非法属性 id（不存在）：空匹配，不报错不泄露行"""
        make_issue(enabled_project, "普通工作项")
        bogus_id = str(uuid.uuid4())
        response = session_client.get(
            issues_list_url(enabled_project),
            {"filters": filters_payload(**{f"customproperty_{bogus_id}__exact": "任意值"})},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []

    def test_filter_cross_project_property_empty(
        self, session_client, workspace, enabled_project, issue_type, mock_celery
    ):
        """跨项目属性 id：空匹配（项目隔离）"""
        other_project = make_project(workspace, "其他项目")
        other_property = make_property(other_project, "他项目属性", "text")
        make_issue(enabled_project, "普通工作项", type_obj=issue_type)

        response = session_client.get(
            issues_list_url(enabled_project),
            {"filters": filters_payload(**{f"customproperty_{other_property.id}__exact": "任意值"})},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []

    def test_filter_invalid_property_key_rejected(self, session_client, enabled_project, mock_celery):
        """非法属性键（空属性 id）：400 invalid_filter_field"""
        response = session_client.get(
            issues_list_url(enabled_project),
            {"filters": filters_payload(**{"customproperty___exact": "任意值"})},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_legacy_filters_still_work(self, session_client, enabled_project, mock_celery):
        """回归面：既有 state_id 筛选在 IssueComplexFilterBackend 下照常工作"""
        make_issue(enabled_project, "普通工作项")
        response = session_client.get(
            issues_list_url(enabled_project),
            {"filters": json.dumps({"state_id__in": [str(uuid.uuid4())]})},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []


# ---------- 导出动态列 ----------


class TestExportPropertyColumns:
    """导出动态属性列（技术方案 §7 导出组）"""

    def test_export_columns_appended_and_formatted(
        self, enabled_project, issue_type, dropdown_property, member_property, create_user
    ):
        """属性名列追加、多值 | 连接、成员名格式化（G10）"""
        bind_property(issue_type, dropdown_property)
        bind_property(issue_type, member_property)
        issue = make_issue(enabled_project, "导出工作项", type_obj=issue_type)
        option_a, option_b = [option["id"] for option in dropdown_property.settings["options"]]
        set_value(issue, dropdown_property, [option_a, option_b])
        set_value(issue, member_property, str(create_user.id))
        other = make_issue(enabled_project, "无值工作项", type_obj=issue_type)

        queryset = Issue.objects.filter(project=enabled_project).order_by("created_at")
        rows = [{"name": "导出工作项"}, {"name": "无值工作项"}]
        attach_issue_property_export_columns(rows, queryset)

        option_names = {option["id"]: option["name"] for option in dropdown_property.settings["options"]}
        assert rows[0][dropdown_property.name] == f"{option_names[option_a]}|{option_names[option_b]}"
        assert rows[0][member_property.name] == create_user.full_name
        # 无值行不产生该属性列
        assert dropdown_property.name not in rows[1]

    def test_export_disabled_property_excluded(self, enabled_project, issue_type, text_property):
        """禁用属性不出导出列（G11）"""
        bind_property(issue_type, text_property)
        issue = make_issue(enabled_project, "禁用导出", type_obj=issue_type)
        set_value(issue, text_property, "某值")
        text_property.is_active = False
        text_property.save(update_fields=["is_active"])

        rows = [{"name": "禁用导出"}]
        attach_issue_property_export_columns(rows, Issue.objects.filter(id=issue.id))
        assert text_property.name not in rows[0]

    def test_export_misaligned_rows_defense(self, enabled_project):
        """行数与 queryset 不一致：防御性跳过，不产坏文件"""
        make_issue(enabled_project, "工作项1")
        rows = [{"name": "不匹配行1"}, {"name": "不匹配行2"}]
        attach_issue_property_export_columns(rows, Issue.objects.filter(project=enabled_project))
        assert rows == [{"name": "不匹配行1"}, {"name": "不匹配行2"}]
