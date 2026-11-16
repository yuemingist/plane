# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
自定义属性 API 单元测试（Step02 段 2 追赶 BE，P2-13）。

用例锚点：段 2 产品方案 §7 GWT 1-20、技术方案 §5 pytest 计划。
覆盖：池 CRUD 8 类校验（下拉空选项/数字格式/重名/默认值）、绑定幂等与
跨项目拒绝、解绑不影响其他类型、删除约束（被绑定 400/未绑定级联删值）、
值读写逐类分派校验（含非法 URL/未知选项/禁用属性/跨类型属性）、
双门控服务端兜底、权限（Guest 只读/未登录 401/非成员 403）、
未启用项目 403 门控、项目隔离。
"""

import uuid

import pytest
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
    User,
    Workspace,
)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def make_user(email: str) -> User:
    user = User.objects.create(email=email, username=email, first_name="Test")
    user.set_password("test@123")
    user.save()
    return user


def add_member(project, user, role: int = 20) -> ProjectMember:
    return ProjectMember.objects.create(project=project, member=user, role=role)


def make_project(workspace: Workspace, name: str) -> Project:
    project = Project.objects.create(
        name=name,
        workspace=workspace,
        identifier=f"PRP{uuid.uuid4().hex[:6].upper()}",
    )
    return project


def properties_url(project: Project) -> str:
    from django.urls import reverse

    return reverse(
        "project-issue-properties",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id)},
    )


def property_detail_url(project: Project, issue_property) -> str:
    from django.urls import reverse

    return reverse(
        "project-issue-property",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "pk": str(issue_property.id)},
    )


def type_properties_url(project: Project, issue_type) -> str:
    from django.urls import reverse

    return reverse(
        "project-work-item-type-properties",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "type_id": str(issue_type.id)},
    )


def unbind_url(project: Project, issue_type, issue_property) -> str:
    from django.urls import reverse

    return reverse(
        "project-work-item-type-property-unbind",
        kwargs={
            "slug": project.workspace.slug,
            "project_id": str(project.id),
            "type_id": str(issue_type.id),
            "property_id": str(issue_property.id),
        },
    )


def values_url(project: Project, issue: Issue) -> str:
    from django.urls import reverse

    return reverse(
        "project-issue-property-values",
        kwargs={"slug": project.workspace.slug, "project_id": str(project.id), "issue_id": str(issue.id)},
    )


def make_type(workspace: Workspace, project: Project, name: str, is_default: bool = False) -> IssueType:
    issue_type = IssueType.objects.create(workspace=workspace, name=name, is_active=True, level=0)
    ProjectIssueType.objects.create(project=project, issue_type=issue_type, level=0, is_default=is_default)
    return issue_type


def make_property(
    project: Project, name: str, property_type: str, settings: dict | None = None, **kwargs
) -> IssueProperty:
    return IssueProperty.objects.create(
        project=project,
        workspace=project.workspace,
        name=name,
        property_type=property_type,
        settings=settings or {},
        **kwargs,
    )


def make_issue(project: Project, name: str, type_obj=None) -> Issue:
    return Issue.objects.create(project=project, name=name, type=type_obj)


@pytest.fixture
def enabled_project(workspace, create_user):
    """已启用工作项类型开关的项目，owner 为 ADMIN"""
    project = make_project(workspace, "Property Project")
    add_member(project, create_user, role=20)
    project.is_issue_type_enabled = True
    project.save(update_fields=["is_issue_type_enabled"])
    return project


@pytest.fixture
def types(enabled_project):
    """Epic（默认）/Task 两类型 + 项目桥"""
    epic = make_type(enabled_project.workspace, enabled_project, "Epic", is_default=True)
    task = make_type(enabled_project.workspace, enabled_project, "Task")
    return {"epic": epic, "task": task}


@pytest.fixture
def dropdown_property(enabled_project):
    """带 2 个选项的下拉属性（已启用）"""
    return make_property(
        enabled_project,
        "下拉属性",
        "option",
        settings={
            "is_multi": False,
            "options": [
                {"id": str(uuid.uuid4()), "name": "选项A", "is_default": False},
                {"id": str(uuid.uuid4()), "name": "选项B", "is_default": False},
            ],
        },
        is_active=True,
    )


class TestPropertyPoolCRUD:
    """池 CRUD：8 类创建、子配置校验、重名、删除约束（GWT 2-5/12/13/16/17）"""

    def test_create_text_property_defaults_disabled(self, session_client, enabled_project):
        """GWT-2：创建文本属性默认已禁用（双门控第一门）"""
        response = session_client.post(
            properties_url(enabled_project),
            {"name": "文本属性", "property_type": "text", "settings": {"display_format": "single-line"}},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_active"] is False
        assert response.data["settings"]["display_format"] == "single-line"
        assert response.data["issue_type_bindings_count"] == 0

    def test_create_all_eight_property_types(self, session_client, enabled_project):
        """8 类逐一创建成功（57 号 §4.2 类型面）"""
        payloads = [
            {"name": "P1", "property_type": "text", "settings": {"display_format": "multi-line"}},
            {
                "name": "P2",
                "property_type": "decimal",
                "settings": {"format": "currency", "decimal_places": 0, "thousands_separator": True},
            },
            {
                "name": "P3",
                "property_type": "option",
                "settings": {"is_multi": True, "options": [{"name": "A"}, {"name": "B"}]},
            },
            {"name": "P4", "property_type": "boolean", "settings": {}},
            {"name": "P5", "property_type": "date", "settings": {}},
            {"name": "P6", "property_type": "member", "settings": {"is_multi": True}},
            {"name": "P7", "property_type": "rich_text", "settings": {}},
            {"name": "P8", "property_type": "url", "settings": {}},
        ]
        for payload in payloads:
            response = session_client.post(properties_url(enabled_project), payload, format="json")
            assert response.status_code == status.HTTP_201_CREATED, payload

    def test_create_dropdown_requires_non_empty_options(self, session_client, enabled_project):
        """GWT-4 拒绝：下拉选项集为空 400"""
        payload = {"name": "空下拉", "property_type": "option", "settings": {"options": []}}
        response = session_client.post(properties_url(enabled_project), payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_number_invalid_format_rejected(self, session_client, enabled_project):
        """数字格式枚举校验：非法 format 400"""
        response = session_client.post(
            properties_url(enabled_project),
            {"name": "坏数字", "property_type": "decimal", "settings": {"format": "scientific"}},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_duplicate_name_rejected(self, session_client, enabled_project):
        """项目池内重名 400（删除约束矩阵）"""
        first_payload = {"name": "重复", "property_type": "date"}
        session_client.post(properties_url(enabled_project), first_payload, format="json")
        response = session_client.post(properties_url(enabled_project), first_payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_dropdown_default_value_must_be_in_options(self, session_client, enabled_project):
        """下拉默认值必须属于选项集"""
        response = session_client.post(
            properties_url(enabled_project),
            {
                "name": "默认值下拉",
                "property_type": "option",
                "settings": {"options": [{"name": "A"}, {"name": "B"}]},
                "default_value": "not-an-option",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_property_type_locked_after_creation(self, session_client, enabled_project):
        """property_type 创建后锁定（PATCH 忽略拒绝）"""
        issue_property = make_property(enabled_project, "锁定类型", "text")
        response = session_client.patch(
            property_detail_url(enabled_project, issue_property),
            {"property_type": "date"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_unbound_property_cascades_values(self, session_client, enabled_project, types):
        """GWT-12：未绑定属性删除成功且级联删值"""
        issue_property = make_property(enabled_project, "可删", "date", is_active=True)
        issue = make_issue(enabled_project, "I1", type_obj=types["epic"])
        IssuePropertyValue.objects.create(issue=issue, issue_property=issue_property, value="2026-01-01")

        response = session_client.delete(property_detail_url(enabled_project, issue_property))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert IssuePropertyValue.objects.filter(issue_property=issue_property).count() == 0

    def test_delete_bound_property_rejected(self, session_client, enabled_project, types):
        """GWT-13 拒绝：被绑定属性删除 400"""
        issue_property = make_property(enabled_project, "使用中", "date")
        session_client.post(
            type_properties_url(enabled_project, types["epic"]),
            {"property_ids": [str(issue_property.id)]},
            format="json",
        )
        response = session_client.delete(property_detail_url(enabled_project, issue_property))
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestPropertyBinding:
    """绑定流：批量绑定幂等、解绑隔离、跨项目拒绝（GWT 6/19/20）"""

    def test_bind_properties_and_count_annotated(self, session_client, enabled_project, types):
        """GWT-6：批量绑定成功且「使用中」计数 +1"""
        p1 = make_property(enabled_project, "P1", "text")
        p2 = make_property(enabled_project, "P2", "date")
        response = session_client.post(
            type_properties_url(enabled_project, types["epic"]),
            {"property_ids": [str(p1.id), str(p2.id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

        detail = session_client.get(property_detail_url(enabled_project, p1))
        assert detail.data["issue_type_bindings_count"] == 1
        assert detail.data["issue_type_bindings"][0]["issue_type_name"] == "Epic"

    def test_bind_is_idempotent(self, session_client, enabled_project, types):
        """重复绑定不产生第二行"""
        p1 = make_property(enabled_project, "幂等", "text")
        payload = {"property_ids": [str(p1.id)]}
        first_bind = session_client.post(type_properties_url(enabled_project, types["epic"]), payload, format="json")
        assert first_bind.status_code == status.HTTP_200_OK
        response = session_client.post(type_properties_url(enabled_project, types["epic"]), payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_unbind_keeps_other_type_and_values(self, session_client, enabled_project, types, dropdown_property):
        """GWT-19：解绑 A 不影响 B 的绑定与已存值"""
        session_client.post(
            type_properties_url(enabled_project, types["epic"]),
            {"property_ids": [str(dropdown_property.id)]},
            format="json",
        )
        session_client.post(
            type_properties_url(enabled_project, types["task"]),
            {"property_ids": [str(dropdown_property.id)]},
            format="json",
        )
        option_id = dropdown_property.settings["options"][0]["id"]
        issue = make_issue(enabled_project, "I1", type_obj=types["task"])
        session_client.post(
            values_url(enabled_project, issue), {"values": {str(dropdown_property.id): option_id}}, format="json"
        )

        response = session_client.delete(unbind_url(enabled_project, types["epic"], dropdown_property))
        assert response.status_code == status.HTTP_204_NO_CONTENT

        bindings = session_client.get(type_properties_url(enabled_project, types["task"]))
        assert len(bindings.data) == 1
        assert IssuePropertyValue.objects.filter(issue=issue, issue_property=dropdown_property).count() == 1

    def test_bind_property_from_other_project_rejected(self, session_client, workspace, enabled_project, types):
        """跨项目属性绑定 400（项目隔离）"""
        other_project = make_project(workspace, "Other Project")
        foreign_property = make_property(other_project, "外来属性", "date")
        response = session_client.post(
            type_properties_url(enabled_project, types["epic"]),
            {"property_ids": [str(foreign_property.id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bind_requires_non_empty_list(self, session_client, enabled_project, types):
        """property_ids 非列表/空 400"""
        response = session_client.post(
            type_properties_url(enabled_project, types["epic"]), {"property_ids": []}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestPropertyValues:
    """值读写：逐类分派校验、双门控兜底、清空删行（GWT 8/9/10/16/17/18）"""

    def _bind_and_activate(self, session_client, project, issue_type, issue_property):
        session_client.post(
            type_properties_url(project, issue_type),
            {"property_ids": [str(issue_property.id)]},
            format="json",
        )
        if not issue_property.is_active:
            session_client.patch(
                property_detail_url(project, issue_property), {"is_active": True}, format="json"
            )

    def test_value_roundtrip_text_decimal_boolean_date_url(self, session_client, enabled_project, types):
        """GWT-8：text/decimal/boolean/date/url 合法值写入读回"""
        issue = make_issue(enabled_project, "I1", type_obj=types["epic"])
        cases = [
            ("文本", "text", {}, "hello world"),
            ("数字", "decimal", {"format": "standard", "decimal_places": 2}, 1234.5),
            ("布尔", "boolean", {}, True),
            ("日期", "date", {}, "2026-11-16"),
            ("链接", "url", {}, "https://example.com/docs"),
        ]
        for name, property_type, settings, value in cases:
            issue_property = make_property(enabled_project, name, property_type, settings=settings)
            self._bind_and_activate(session_client, enabled_project, types["epic"], issue_property)
            response = session_client.post(
                values_url(enabled_project, issue), {"values": {str(issue_property.id): value}}, format="json"
            )
            assert response.status_code == status.HTTP_200_OK, (name, response.data)
            row = next(row for row in response.data if str(row["property"]["id"]) == str(issue_property.id))
            assert row["value"] == value

    def test_dropdown_single_and_multi_values(self, session_client, enabled_project, types, dropdown_property):
        """GWT-9/10：下拉单选/多选值语义"""
        option_a, option_b = dropdown_property.settings["options"]
        issue = make_issue(enabled_project, "I1", type_obj=types["epic"])
        self._bind_and_activate(session_client, enabled_project, types["epic"], dropdown_property)

        response = session_client.post(
            values_url(enabled_project, issue), {"values": {str(dropdown_property.id): option_a["id"]}}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

        # 改成多选属性再写多值
        multi_property = make_property(
            enabled_project,
            "多选下拉",
            "option",
            settings={
                "is_multi": True,
                "options": [
                    {"id": str(uuid.uuid4()), "name": "X", "is_default": False},
                    {"id": str(uuid.uuid4()), "name": "Y", "is_default": False},
                ],
            },
            is_active=True,
        )
        self._bind_and_activate(session_client, enabled_project, types["epic"], multi_property)
        multi_option_ids = [option["id"] for option in multi_property.settings["options"]]
        response = session_client.post(
            values_url(enabled_project, issue), {"values": {str(multi_property.id): multi_option_ids}}, format="json"
        )
        row = next(row for row in response.data if str(row["property"]["id"]) == str(multi_property.id))
        assert sorted(row["value"]) == sorted(multi_option_ids)

    def test_dropdown_value_outside_options_rejected(self, session_client, enabled_project, types, dropdown_property):
        """GWT-16 拒绝：不属于选项集的值 400"""
        issue = make_issue(enabled_project, "I1", type_obj=types["epic"])
        self._bind_and_activate(session_client, enabled_project, types["epic"], dropdown_property)
        response = session_client.post(
            values_url(enabled_project, issue),
            {"values": {str(dropdown_property.id): "unknown-option-id"}},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_url_value_rejected(self, session_client, enabled_project, types):
        """GWT-17 拒绝：非法 URL 400"""
        url_property = make_property(enabled_project, "URL", "url")
        issue = make_issue(enabled_project, "I1", type_obj=types["epic"])
        self._bind_and_activate(session_client, enabled_project, types["epic"], url_property)
        response = session_client.post(
            values_url(enabled_project, issue), {"values": {str(url_property.id): "not a url"}}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_inactive_property_value_rejected(self, session_client, enabled_project, types):
        """GWT-18 拒绝：已绑定但未启用的属性写值 400（双门控服务端兜底）"""
        issue_property = make_property(enabled_project, "禁用属性", "text", is_active=False)
        session_client.post(
            type_properties_url(enabled_project, types["epic"]),
            {"property_ids": [str(issue_property.id)]},
            format="json",
        )
        issue = make_issue(enabled_project, "I1", type_obj=types["epic"])
        response = session_client.post(
            values_url(enabled_project, issue), {"values": {str(issue_property.id): "x"}}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unbound_property_value_rejected(self, session_client, enabled_project, types, dropdown_property):
        """拒绝：未绑定到该工作项类型的属性写值 400"""
        issue = make_issue(enabled_project, "I1", type_obj=types["epic"])
        response = session_client.post(
            values_url(enabled_project, issue), {"values": {str(dropdown_property.id): "whatever"}}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_empty_value_deletes_row(self, session_client, enabled_project, types):
        """清空语义：空值 upsert 删除值行"""
        issue_property = make_property(enabled_project, "可清空", "text", is_active=True)
        self._bind_and_activate(session_client, enabled_project, types["epic"], issue_property)
        issue = make_issue(enabled_project, "I1", type_obj=types["epic"])
        values_payload = {"values": {str(issue_property.id): "first"}}
        session_client.post(values_url(enabled_project, issue), values_payload, format="json")
        assert IssuePropertyValue.objects.filter(issue=issue, issue_property=issue_property).count() == 1

        response = session_client.post(
            values_url(enabled_project, issue), {"values": {str(issue_property.id): ""}}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert IssuePropertyValue.objects.filter(issue=issue, issue_property=issue_property).count() == 0

    def test_value_list_only_active_bound_properties(self, session_client, enabled_project, types, dropdown_property):
        """GWT-18：值列表只含绑定且已启用属性；未启用不出现"""
        inactive = make_property(enabled_project, "未启用", "text", is_active=False)
        session_client.post(
            type_properties_url(enabled_project, types["epic"]),
            {"property_ids": [str(dropdown_property.id), str(inactive.id)]},
            format="json",
        )
        issue = make_issue(enabled_project, "I1", type_obj=types["epic"])
        response = session_client.get(values_url(enabled_project, issue))
        assert response.status_code == status.HTTP_200_OK
        property_ids = [str(row["property"]["id"]) for row in response.data]
        assert str(dropdown_property.id) in property_ids
        assert str(inactive.id) not in property_ids


class TestPermissionsAndGating:
    """权限/门控/隔离（GWT 14/15/20）"""

    def test_disabled_project_forbidden(self, session_client, workspace, create_user):
        """GWT-14 拒绝：未启用项目属性 API 403"""
        project = make_project(workspace, "未启用项目")
        add_member(project, create_user, role=20)
        response = session_client.get(properties_url(project))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_guest_read_ok_write_forbidden(self, session_client, workspace, create_user, enabled_project, types):
        """GWT-15：Guest 读 200 写 403"""
        guest = make_user("guest@property.test")
        add_member(enabled_project, guest, role=5)
        guest_client = APIClient()
        guest_client.force_authenticate(user=guest)

        assert session_client.post(
            properties_url(enabled_project), {"name": "G", "property_type": "date"}, format="json"
        ).status_code == status.HTTP_201_CREATED

        assert guest_client.get(properties_url(enabled_project)).status_code == status.HTTP_200_OK
        assert (
            guest_client.post(
                properties_url(enabled_project), {"name": "G2", "property_type": "date"}, format="json"
            ).status_code
            == status.HTTP_403_FORBIDDEN
        )

    def test_non_member_forbidden(self, enabled_project):
        """非项目成员 403"""
        outsider = make_user("outsider@property.test")
        client = APIClient()
        client.force_authenticate(user=outsider)
        assert client.get(properties_url(enabled_project)).status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_unauthorized(self, enabled_project):
        """未登录 401"""
        client = APIClient()
        assert client.get(properties_url(enabled_project)).status_code == status.HTTP_401_UNAUTHORIZED

    def test_project_isolation_on_values(self, session_client, workspace, create_user, enabled_project, types):
        """GWT-20：项目 B 上下文读项目 A 属性值 404"""
        other = make_project(workspace, "Project B")
        add_member(other, create_user, role=20)
        other.is_issue_type_enabled = True
        other.save(update_fields=["is_issue_type_enabled"])

        issue_a = make_issue(enabled_project, "A issue", type_obj=types["epic"])
        response = session_client.get(values_url(other, issue_a))
        assert response.status_code == status.HTTP_404_NOT_FOUND
