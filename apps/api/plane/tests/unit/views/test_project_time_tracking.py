# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
时间跟踪功能开关 单元测试（Step02 段 6 追赶 BE，TM-01）。

用例锚点：段 6 产品方案 §5（GWT 3/4/5/6/8）、技术方案 §4。
覆盖：项目 PATCH `is_time_tracking_enabled` 落库往返（true/false）、GET 回读、
DB 断言、权限矩阵（MEMBER/GUEST/未登录均拒绝，仅 ADMIN 可写）、邻字段零回归
（`is_issue_type_enabled` 同 serializer 行不受影响）。

后端 0 改动：字段与 serializer 官方已在（db/models/project.py:100、
api/serializers/project.py:94），本文件仅做回归验证与落库断言。
"""

import uuid

import pytest
from django.urls import reverse
from rest_framework import status

from plane.db.models import Project, ProjectMember

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def make_user(email: str):
    from plane.db.models import User

    user = User.objects.create(email=email, username=email, first_name="Test")
    user.set_password("test@123")
    user.save()
    return user


def make_project(workspace, name: str) -> Project:
    return Project.objects.create(
        name=name,
        workspace=workspace,
        identifier=f"TTK{uuid.uuid4().hex[:6].upper()}",
    )


def add_member(project, user, role: int) -> ProjectMember:
    return ProjectMember.objects.create(project=project, member=user, role=role)


def project_detail_url(project) -> str:
    return reverse("project", kwargs={"slug": project.workspace.slug, "pk": str(project.id)})


@pytest.fixture
def admin_user(create_user):
    return create_user


@pytest.fixture
def project(workspace, admin_user):
    """干净项目，admin_user 为项目 ADMIN（ROLE.ADMIN=20）"""
    project = make_project(workspace, "Time Tracking Project")
    add_member(project, admin_user, role=20)
    return project


class TestTimeTrackingTogglePersistence:
    """开关 PATCH 落库往返（产品方案 GWT-3/4，技术方案 §4.1/§4.2）"""

    def test_patch_true_persists(self, session_client, project, admin_user):
        """PATCH true → 200，GET 回读 true，DB 落库"""
        assert project.is_time_tracking_enabled is False  # 默认关（产品方案 A2）

        response = session_client.patch(
            project_detail_url(project), {"is_time_tracking_enabled": True}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_time_tracking_enabled"] is True

        project.refresh_from_db()
        assert project.is_time_tracking_enabled is True

        get_response = session_client.get(project_detail_url(project))
        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.data["is_time_tracking_enabled"] is True

    def test_patch_false_roundtrip(self, session_client, project):
        """翻开后再 PATCH false → 200，回读 false（往返关闭）"""
        assert session_client.patch(
            project_detail_url(project), {"is_time_tracking_enabled": True}, format="json"
        ).status_code == status.HTTP_200_OK

        response = session_client.patch(
            project_detail_url(project), {"is_time_tracking_enabled": False}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_time_tracking_enabled"] is False

        project.refresh_from_db()
        assert project.is_time_tracking_enabled is False

    def test_patch_partial_payload_does_not_touch_other_fields(self, session_client, project):
        """仅 PATCH 开关字段，邻字段（cycle_view）不受影响（同屏零回归旁证）"""
        project.cycle_view = True
        project.save()

        response = session_client.patch(
            project_detail_url(project), {"is_time_tracking_enabled": True}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["cycle_view"] is True

        project.refresh_from_db()
        assert project.cycle_view is True


class TestTimeTrackingTogglePermissions:
    """权限矩阵（产品方案 GWT-5，技术方案 §4.3）

    现网语义：项目 PATCH 属性要求项目 ADMIN 或工作区 ADMIN
    （`ProjectViewSet.partial_update` 显式校验，GUEST/MEMBER 均拒绝）。
    """

    def test_member_patch_rejected(self, create_user, session_client, workspace):
        """MEMBER PATCH 项目属性 → 403，开关不变（P0-10 验收 4）"""
        member = make_user("tt-member@plane.so")
        project = make_project(workspace, "TT Member Project")
        ProjectMember.objects.create(project=project, member=member, role=15)
        ProjectMember.objects.create(project=project, member=create_user, role=20)

        client = session_client
        client.force_authenticate(user=member)
        response = client.patch(project_detail_url(project), {"is_time_tracking_enabled": True}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        project.refresh_from_db()
        assert project.is_time_tracking_enabled is False

    def test_guest_patch_rejected(self, create_user, session_client, workspace):
        """GUEST PATCH → 拒绝，开关不变（产品方案 GWT-5）"""
        guest = make_user("tt-guest@plane.so")
        admin = create_user
        project = make_project(workspace, "TT Guest Project")
        ProjectMember.objects.create(project=project, member=guest, role=5)
        ProjectMember.objects.create(project=project, member=admin, role=20)

        client = session_client
        client.force_authenticate(user=guest)
        response = client.patch(project_detail_url(project), {"is_time_tracking_enabled": True}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        project.refresh_from_db()
        assert project.is_time_tracking_enabled is False

    def test_anonymous_patch_rejected(self, api_client, workspace):
        """未登录 PATCH → 401/403"""
        project = make_project(workspace, "TT Anon Project")
        response = api_client.patch(project_detail_url(project), {"is_time_tracking_enabled": True}, format="json")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


class TestNeighborFieldsRegression:
    """邻字段零回归（技术方案 §4.4）：类型开关同 serializer 行不受影响（产品方案 GWT-8）"""

    def test_issue_type_enabled_patch_still_works(self, session_client, project):
        """PATCH is_issue_type_enabled 仍正常，时间跟踪字段不动"""
        response = session_client.patch(
            project_detail_url(project), {"is_issue_type_enabled": True}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_issue_type_enabled"] is True
        assert response.data["is_time_tracking_enabled"] is False

        project.refresh_from_db()
        assert project.is_issue_type_enabled is True
        assert project.is_time_tracking_enabled is False
