# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
自定义属性域视图（Step02 段 2 追赶 BE，P2-13）。

端点形态对照段 2 技术方案 §2（项目域扁平路由，kebab-case）：
- issue-properties/：属性池 CRUD（8 类校验 + 使用中计数 annotate）
- work-item-types/{type_id}/properties/：绑定列表/批量绑定/解绑
  （替代 Step01 的恒空数组占位路由）
- work-items/{issue_id}/issue-property-values/：值列表 + 批量 upsert

权限：读 ADMIN/MEMBER/GUEST，写 ADMIN/MEMBER（对齐 Step01 §2.3）；
全部受 WorkItemTypeFeatureGateMixin 门控（未启用项目 403）。
双门控在服务端兜底：写值要求属性 is_active=True 且绑定到该工作项类型。
"""

# Django imports
from django.db import transaction
from django.db.models import Count

# Third Party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from .base import BaseViewSet
from .issue_type import WorkItemTypeFeatureGateMixin
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import (
    IssuePropertySerializer,
    IssuePropertyValueSerializer,
    IssueTypeIssuePropertySerializer,
    validate_property_value,
)
from plane.db.models import Issue, IssueProperty, IssueTypeIssueProperty, IssuePropertyValue


class IssuePropertyViewSet(WorkItemTypeFeatureGateMixin, BaseViewSet):
    """项目属性池 CRUD（属性 tab 主路径，57 号 §1.2 Tab2）。"""

    serializer_class = IssuePropertySerializer
    model = IssueProperty

    def get_queryset(self):
        return (
            IssueProperty.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
                deleted_at__isnull=True,
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
                project__archived_at__isnull=True,
            )
            .annotate(issue_type_bindings_count=Count("issue_type_bindings", distinct=True))
            .prefetch_related("issue_type_bindings__issue_type")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["project_id"] = self.kwargs.get("project_id")
        return context

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id):
        serializer = IssuePropertySerializer(self.get_queryset(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id):
        serializer = IssuePropertySerializer(
            data=request.data,
            context={"project_id": project_id},
        )
        if serializer.is_valid():
            serializer.save(project_id=project_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def retrieve(self, request, slug, project_id, pk):
        issue_property = self.get_queryset().filter(pk=pk).first()
        if issue_property is None:
            return Response({"error": "Issue property not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = IssuePropertySerializer(issue_property)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def partial_update(self, request, slug, project_id, pk):
        issue_property = self.get_queryset().filter(pk=pk).first()
        if issue_property is None:
            return Response({"error": "Issue property not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = IssuePropertySerializer(
            issue_property,
            data=request.data,
            partial=True,
            context={"project_id": project_id},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def destroy(self, request, slug, project_id, pk):
        """删除约束：被绑定 → 400（先在类型详情移除绑定）；未绑定 → 级联删值。"""
        issue_property = self.get_queryset().filter(pk=pk).first()
        if issue_property is None:
            return Response({"error": "Issue property not found"}, status=status.HTTP_404_NOT_FOUND)

        bound_count = IssueTypeIssueProperty.objects.filter(
            issue_property=issue_property, deleted_at__isnull=True
        ).count()
        if bound_count > 0:
            return Response(
                {
                    "error": "Cannot delete a property that is still bound to work item types."
                    " Remove the bindings first."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            IssuePropertyValue.objects.filter(issue_property=issue_property).delete()
            issue_property.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssueTypePropertyViewSet(WorkItemTypeFeatureGateMixin, BaseViewSet):
    """类型↔属性绑定：类型详情页「添加属性」流（57 号 §3.4 步骤 2/3）。

    替代 Step01 在 WorkItemTypeViewSet 的恒空数组占位 properties action。
    """

    serializer_class = IssueTypeIssuePropertySerializer
    model = IssueTypeIssueProperty

    def _member_scoped_bindings(self, slug, project_id, type_id):
        return IssueTypeIssueProperty.objects.filter(
            issue_type_id=type_id,
            deleted_at__isnull=True,
            issue_property__workspace__slug=slug,
            issue_property__project_id=project_id,
            issue_property__deleted_at__isnull=True,
        ).filter(
            issue_property__project__project_projectmember__member=self.request.user,
            issue_property__project__project_projectmember__is_active=True,
            issue_property__project__archived_at__isnull=True,
        )

    def _get_scoped_type(self, slug, project_id, type_id):
        from plane.db.models import IssueType

        return (
            IssueType.objects.filter(
                pk=type_id,
                workspace__slug=slug,
                project_issue_types__project_id=project_id,
                project_issue_types__deleted_at__isnull=True,
            )
            .distinct()
            .first()
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id, type_id):
        issue_type = self._get_scoped_type(slug, project_id, type_id)
        if issue_type is None:
            return Response({"error": "Work item type not found"}, status=status.HTTP_404_NOT_FOUND)
        bindings = self._member_scoped_bindings(slug, project_id, type_id).select_related(
            "issue_property", "issue_property__project"
        )
        serializer = IssueTypeIssuePropertySerializer(bindings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id, type_id):
        """批量绑定现有属性：{property_ids: [uuid]}；幂等（已绑定跳过）。"""
        issue_type = self._get_scoped_type(slug, project_id, type_id)
        if issue_type is None:
            return Response({"error": "Work item type not found"}, status=status.HTTP_404_NOT_FOUND)

        property_ids = request.data.get("property_ids")
        if not isinstance(property_ids, list) or len(property_ids) == 0:
            return Response({"error": "property_ids must be a non-empty list"}, status=status.HTTP_400_BAD_REQUEST)

        properties = IssueProperty.objects.filter(
            pk__in=property_ids,
            project_id=project_id,
            workspace__slug=slug,
            deleted_at__isnull=True,
        )
        found_ids = {str(property_.id) for property_ in properties}
        missing = [property_id for property_id in property_ids if str(property_id) not in found_ids]
        if missing:
            return Response(
                {"error": f"Issue properties not found in this project: {missing}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        with transaction.atomic():
            existing_ids = {
                str(existing_id)
                for existing_id in IssueTypeIssueProperty.objects.filter(
                    issue_type=issue_type,
                    issue_property_id__in=found_ids,
                    deleted_at__isnull=True,
                ).values_list("issue_property_id", flat=True)
            }
            for property_ in properties:
                property_id = str(property_.id)
                if property_id in existing_ids:
                    continue
                created.append(
                    IssueTypeIssueProperty.objects.create(issue_type=issue_type, issue_property_id=property_.id)
                )

        bindings = self._member_scoped_bindings(slug, project_id, type_id).filter(
            issue_property_id__in=found_ids
        ).select_related("issue_property")
        serializer = IssueTypeIssuePropertySerializer(bindings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def destroy(self, request, slug, project_id, type_id, property_id):
        """解绑：只删桥，属性池与已存值保留（段 2 产品方案 A2）。"""
        issue_type = self._get_scoped_type(slug, project_id, type_id)
        if issue_type is None:
            return Response({"error": "Work item type not found"}, status=status.HTTP_404_NOT_FOUND)
        binding = (
            self._member_scoped_bindings(slug, project_id, type_id)
            .filter(issue_property_id=property_id)
            .first()
        )
        if binding is None:
            return Response({"error": "Property is not bound to this type"}, status=status.HTTP_404_NOT_FOUND)
        binding.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssuePropertyValueViewSet(WorkItemTypeFeatureGateMixin, BaseViewSet):
    """工作项属性值：详情/新建读写（57 号 §3.4 步骤 7/8）。"""

    serializer_class = IssuePropertyValueSerializer
    model = IssuePropertyValue

    def _member_scoped_issue(self, slug, project_id, issue_id):
        return (
            Issue.issue_objects.filter(
                workspace__slug=slug,
                project_id=project_id,
                pk=issue_id,
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
                project__archived_at__isnull=True,
            )
            .select_related("type")
            .first()
        )

    def _bound_active_properties(self, type_id):
        """绑定到工作项类型且已启用的属性（双门控：绑定 + 池级 is_active）。"""
        if type_id is None:
            return IssueProperty.objects.none()
        return (
            IssueProperty.objects.filter(
                issue_type_bindings__issue_type_id=type_id,
                issue_type_bindings__deleted_at__isnull=True,
                is_active=True,
                deleted_at__isnull=True,
            )
            .order_by("sort_order", "created_at")
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id, issue_id):
        """出参：绑定且已启用属性的定义 + 已存值（无值时 value=null）。"""
        issue = self._member_scoped_issue(slug, project_id, issue_id)
        if issue is None:
            return Response({"error": "Work item not found"}, status=status.HTTP_404_NOT_FOUND)

        properties = self._bound_active_properties(issue.type_id)
        values = {
            value.issue_property_id: value.value
            for value in IssuePropertyValue.objects.filter(
                issue=issue, issue_property__in=properties, deleted_at__isnull=True
            )
        }
        property_serializer = IssuePropertySerializer(properties, many=True)
        return Response(
            [
                {"property": property_data, "value": values.get(property_data["id"])}
                for property_data in property_serializer.data
            ],
            status=status.HTTP_200_OK,
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id, issue_id):
        """批量 upsert：{values: {property_id: value}}，单事务，任一失败整体 400。

        空值（null/""/[]）→ 删除该值行（清空语义，技术方案 §2.3-3）。
        """
        issue = self._member_scoped_issue(slug, project_id, issue_id)
        if issue is None:
            return Response({"error": "Work item not found"}, status=status.HTTP_404_NOT_FOUND)

        values = request.data.get("values")
        if not isinstance(values, dict) or len(values) == 0:
            return Response({"error": "values must be a non-empty object"}, status=status.HTTP_400_BAD_REQUEST)

        properties = {
            str(property_.id): property_
            for property_ in IssueProperty.objects.filter(
                pk__in=values.keys(),
                project_id=project_id,
                workspace__slug=slug,
                deleted_at__isnull=True,
            )
        }
        missing = [property_id for property_id in values if property_id not in properties]
        if missing:
            return Response(
                {"error": f"Issue properties not found in this project: {missing}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 双门控服务端兜底：属性须绑定到该工作项类型且已启用
        bound_active_ids = set(
            str(property_.id) for property_ in self._bound_active_properties(issue.type_id)
        )
        for property_id, value in values.items():
            property_ = properties[property_id]
            if property_id not in bound_active_ids:
                return Response(
                    {"error": f"Property {property_id} is not enabled for this work item's type"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                values[property_id] = validate_property_value(property_, value, project_id)
            except Exception as exc:
                return Response(
                    {"error": f"Invalid value for property '{property_.name}': {getattr(exc, 'detail', str(exc))}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            # 行锁串行化同一工作项的并发 upsert：否则 filter-then-create 在并发下
            # 同时通过存在性检查，撞 (issue, issue_property) 唯一约束 → IntegrityError（缺陷 #6）
            Issue.objects.select_for_update().get(pk=issue.pk)
            for property_id, normalized_value in values.items():
                property_ = properties[property_id]
                if normalized_value is None:
                    IssuePropertyValue.objects.filter(issue=issue, issue_property=property_).delete()
                    continue
                existing = IssuePropertyValue.objects.filter(
                    issue=issue, issue_property=property_, deleted_at__isnull=True
                ).first()
                if existing is None:
                    IssuePropertyValue.objects.create(issue=issue, issue_property=property_, value=normalized_value)
                else:
                    existing.value = normalized_value
                    existing.save(update_fields=["value", "updated_at"])

        # 写后回读（原子刷新面板，57 号 §5-2 时序怪癖规避）
        refreshed_properties = self._bound_active_properties(issue.type_id)
        refreshed_values = {
            value.issue_property_id: value.value
            for value in IssuePropertyValue.objects.filter(
                issue=issue,
                issue_property__in=refreshed_properties,
                deleted_at__isnull=True,
            )
        }
        property_serializer = IssuePropertySerializer(refreshed_properties, many=True)
        return Response(
            [
                {"property": property_data, "value": refreshed_values.get(property_data["id"])}
                for property_data in property_serializer.data
            ],
            status=status.HTTP_200_OK,
        )
