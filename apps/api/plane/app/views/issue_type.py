# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
工作项类型域（Step01 追赶 BE-1）。

端点形态对照技术方案 §2.1（项目域扁平路由，kebab-case 路径 work-item-types/）：
- CRUD + mark-default + enable（项目启用，自动建 Epic/Task）+ properties 占位（恒空数组）
- project-issue-types/ 桥绑定最小面

约定（防后人误用）：
- 项目内默认类型以 `ProjectIssueType.is_default`（项目桥）为准；
  `IssueType.is_default`（工作区级字段）本步不消费。
- 启用为单向开关：enable 幂等（已启用直接返回现状，不报错、不重复建类型）。
"""

# Django imports
from django.db import transaction
from django.db.models import BooleanField, F, Func, IntegerField, OuterRef, Subquery

# Third Party imports
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

# Module imports
from .base import BaseViewSet
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import IssueTypeSerializer, ProjectIssueTypeSerializer
from plane.db.models import Issue, IssueType, Project, ProjectIssueType


class WorkItemTypeFeatureGateMixin:
    """项目工作项类型开关门控：未启用 `Project.is_issue_type_enabled` 的项目
    一律 403（list/详情/写操作同口径；enable 自身除外）。

    权限装饰器（allow_permission）负责角色校验，本 mixin 负责功能开关校验，
    两者互不替代（章程验收 8）。
    """

    # 不受开关门控的动作（enable 是开开关本身）
    feature_gate_excluded_actions = frozenset({"enable"})

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if getattr(self, "action", None) in self.feature_gate_excluded_actions:
            return
        project = Project.objects.filter(pk=kwargs.get("project_id"), workspace__slug=kwargs.get("slug")).first()
        if project is None:
            # 项目不存在时不在门控层报错，交给后续具体查询兜底（404/ DoesNotExist）
            return
        if not project.is_issue_type_enabled:
            raise PermissionDenied("Work item types are not enabled for this project")


class WorkItemTypeViewSet(WorkItemTypeFeatureGateMixin, BaseViewSet):
    """工作项类型 CRUD + 项目启用 + 设默认 + 属性占位。"""

    serializer_class = IssueTypeSerializer
    model = IssueType

    def get_queryset(self):
        # 类型为工作区级资源，经项目桥收敛到 URL 项目（§2.3 权限域绑定）；
        # 同时要求调用者是该项目成员（Guest 只读由装饰器控制）
        return (
            IssueType.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_issue_types__project_id=self.kwargs.get("project_id"),
                project_issue_types__deleted_at__isnull=True,
            )
            .filter(
                project_issue_types__project__project_projectmember__member=self.request.user,
                project_issue_types__project__project_projectmember__is_active=True,
                project_issue_types__project__archived_at__isnull=True,
            )
            .distinct()
        )

    def _annotated_queryset(self, project_id):
        """附加项目桥默认标记与引用计数（「特性」列数据源，R3：每项目类型数 <=10）。"""
        default_subquery = ProjectIssueType.objects.filter(
            issue_type=OuterRef("pk"),
            project_id=project_id,
            deleted_at__isnull=True,
        ).values("is_default")[:1]

        issues_count_subquery = (
            Issue.issue_objects.filter(type_id=OuterRef("pk"), project_id=project_id)
            .order_by()
            .annotate(count=Func(F("id"), function="Count"))
            .values("count")[:1]
        )

        return (
            IssueType.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_issue_types__project_id=project_id,
                project_issue_types__deleted_at__isnull=True,
            )
            .annotate(project_is_default=Subquery(default_subquery, output_field=BooleanField()))
            .annotate(project_issues_count=Subquery(issues_count_subquery, output_field=IntegerField()))
            .order_by("level", "name")
        )

    def _get_annotated_instance(self, project_id, pk):
        return self._annotated_queryset(project_id).filter(pk=pk).first()

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id):
        serializer = IssueTypeSerializer(self._annotated_queryset(project_id), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def retrieve(self, request, slug, project_id, pk):
        issue_type = self._get_annotated_instance(project_id, pk)
        if issue_type is None:
            return Response({"error": "Work item type not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = IssueTypeSerializer(issue_type)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)

        # 重名 400：工作区内同名类型不允许重复创建（产品方案 §3.3 新建弹窗）
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"error": "Name is required"}, status=status.HTTP_400_BAD_REQUEST)
        if IssueType.objects.filter(workspace_id=project.workspace_id, name=name).exists():
            return Response(
                {"error": "A work item type with this name already exists in the workspace"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = IssueTypeSerializer(data=request.data)
        if serializer.is_valid():
            # 新建默认 is_active=False 已在序列化器 validate 内覆盖（model 默认 True）
            serializer.save(workspace_id=project.workspace_id)
            # 项目语境下创建即绑定项目桥（否则类型不会出现在项目列表中）
            ProjectIssueType.objects.create(
                project=project,
                issue_type_id=serializer.data["id"],
                level=serializer.instance.level,
                is_default=False,
            )
            instance = self._get_annotated_instance(project_id, serializer.data["id"])
            return Response(IssueTypeSerializer(instance).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def partial_update(self, request, slug, project_id, pk):
        issue_type = self.get_queryset().filter(pk=pk).first()
        if issue_type is None:
            return Response({"error": "Work item type not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = IssueTypeSerializer(issue_type, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            instance = self._get_annotated_instance(project_id, pk)
            return Response(IssueTypeSerializer(instance).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def destroy(self, request, slug, project_id, pk):
        issue_type = self.get_queryset().filter(pk=pk).first()
        if issue_type is None:
            return Response({"error": "Work item type not found"}, status=status.HTTP_404_NOT_FOUND)

        # 删除约束矩阵（技术方案 §2.4）
        bridge = ProjectIssueType.objects.filter(
            project_id=project_id,
            issue_type=issue_type,
            deleted_at__isnull=True,
        ).first()
        if bridge is not None and bridge.is_default:
            # A-7：默认类型不可删
            return Response(
                {"error": "This work item type cannot be deleted because it's set as the default for this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if issue_type.is_epic:
            # A-8：内置 Epic 类型不可删（前端只暴露「禁用」，服务端兜底）
            return Response(
                {"error": "The epic work item type cannot be deleted"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Issue.objects.filter(type_id=issue_type.id).exists():
            # A-15：被工作项引用的类型不可删（「特性」列 = 该计数）
            return Response(
                {"error": "The work item type has associated work items and cannot be deleted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            ProjectIssueType.objects.filter(issue_type=issue_type).delete()
            issue_type.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def mark_default(self, request, slug, project_id, pk):
        """设默认：唯一默认约束在事务内先清旧默认再置新默认（A-9）。"""
        issue_type = self.get_queryset().filter(pk=pk).first()
        if issue_type is None:
            return Response({"error": "Work item type not found"}, status=status.HTTP_404_NOT_FOUND)

        # A-6：未激活类型不可设默认
        if not issue_type.is_active:
            return Response(
                {"error": "Activate this type before setting it as default"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # 先清旧默认（桥上 is_default 单例），再置新默认
            ProjectIssueType.objects.filter(project_id=project_id, is_default=True).update(is_default=False)
            bridge, _ = ProjectIssueType.objects.get_or_create(
                project_id=project_id,
                issue_type=issue_type,
                defaults={"level": issue_type.level, "is_default": True},
            )
            if not bridge.is_default:
                bridge.is_default = True
                bridge.save(update_fields=["is_default"])

        instance = self._get_annotated_instance(project_id, pk)
        return Response(IssueTypeSerializer(instance).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def enable(self, request, slug, project_id):
        """项目启用（幂等）：置位开关 + 自动建 Epic/Task 两类型并绑定项目。

        幂等语义（通宵提示词决策 3A）：
        - 已启用 → 直接返回现状（200），不报错、不重复建行；
        - 类型复用：按 (workspace, name, is_epic) 查找工作区已有 IssueType
          （Epic/Task），找到即复用并补桥，找不到才新建。
        """
        Project.objects.get(pk=project_id, workspace__slug=slug)

        with transaction.atomic():
            # 锁行防并发双开
            project = Project.objects.select_for_update().get(pk=project_id)
            if not project.is_issue_type_enabled:
                project.is_issue_type_enabled = True
                project.save(update_fields=["is_issue_type_enabled"])

            workspace_id = project.workspace_id

            # Epic：is_epic=True、活动、level=1、山形图标（57 号 §3.1 步骤 3 复刻）
            epic = IssueType.objects.filter(workspace_id=workspace_id, name="Epic", is_epic=True).first()
            if epic is None:
                epic = IssueType.objects.create(
                    workspace_id=workspace_id,
                    name="Epic",
                    is_epic=True,
                    is_active=True,
                    level=1,
                    logo_props={"in_app_icon": {"color": "#fcbe53", "name": "mountain"}},
                )

            # Task：活动、level=0
            task_type = IssueType.objects.filter(workspace_id=workspace_id, name="Task", is_epic=False).first()
            if task_type is None:
                task_type = IssueType.objects.create(
                    workspace_id=workspace_id,
                    name="Task",
                    is_epic=False,
                    is_active=True,
                    level=0,
                )

            # 桥绑定去重（unique 约束已存在，get_or_create 幂等复用）
            ProjectIssueType.objects.get_or_create(
                project=project,
                issue_type=epic,
                defaults={"level": 1, "is_default": False},
            )
            task_bridge, _ = ProjectIssueType.objects.get_or_create(
                project=project,
                issue_type=task_type,
                defaults={"level": 0, "is_default": True},
            )
            # 幂等兜底：项目尚无任何默认类型时，把 Task 桥补成默认
            if not ProjectIssueType.objects.filter(project=project, is_default=True).exists():
                task_bridge.is_default = True
                task_bridge.save(update_fields=["is_default"])

        serializer = IssueTypeSerializer(self._annotated_queryset(project_id), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def properties(self, request, slug, project_id, pk):
        """类型属性列表占位：本步恒返回空数组（属性体系属 P2-13），
        路由先占位避免前端另造路径。"""
        exists = IssueType.objects.filter(
            pk=pk,
            workspace__slug=slug,
            project_issue_types__project_id=project_id,
            project_issue_types__deleted_at__isnull=True,
        ).exists()
        if not exists:
            return Response({"error": "Work item type not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response([], status=status.HTTP_200_OK)


class ProjectIssueTypeViewSet(WorkItemTypeFeatureGateMixin, BaseViewSet):
    """项目 <-> 类型桥最小绑定面：把工作区已有类型挂进项目（未来导入用）。

    绑定/解绑时维护不变量：level 与类型对齐、is_default 项目内单例、
    项目默认桥不可解绑。
    """

    serializer_class = ProjectIssueTypeSerializer
    model = ProjectIssueType

    def get_queryset(self):
        return (
            ProjectIssueType.objects.filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
                deleted_at__isnull=True,
            )
            .filter(
                project__project_projectmember__member=self.request.user,
                project__project_projectmember__is_active=True,
                project__archived_at__isnull=True,
            )
            .select_related("issue_type")
            .distinct()
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id):
        serializer = ProjectIssueTypeSerializer(self.get_queryset(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def retrieve(self, request, slug, project_id, pk):
        bridge = self.get_queryset().filter(pk=pk).first()
        if bridge is None:
            return Response({"error": "Project issue type not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectIssueTypeSerializer(bridge).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        issue_type_id = request.data.get("issue_type")
        if not issue_type_id:
            return Response({"error": "issue_type is required"}, status=status.HTTP_400_BAD_REQUEST)

        # 类型必须属于同一工作区（防跨工作区越权绑定）
        issue_type = IssueType.objects.filter(pk=issue_type_id, workspace_id=project.workspace_id).first()
        if issue_type is None:
            return Response(
                {"error": "The work item type does not exist in this workspace"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProjectIssueTypeSerializer(
            data={
                "issue_type": str(issue_type.id),
                "level": request.data.get("level", issue_type.level),
                "is_default": request.data.get("is_default", False),
            },
        )
        if serializer.is_valid():
            with transaction.atomic():
                serializer.save(project_id=project_id, issue_type=issue_type, level=issue_type.level)
                # 维护唯一默认：请求显式要默认时清旧默认
                if serializer.instance.is_default:
                    ProjectIssueType.objects.filter(project_id=project_id, is_default=True).exclude(
                        pk=serializer.instance.pk
                    ).update(is_default=False)
            return Response(ProjectIssueTypeSerializer(serializer.instance).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def partial_update(self, request, slug, project_id, pk):
        bridge = self.get_queryset().filter(pk=pk).first()
        if bridge is None:
            return Response({"error": "Project issue type not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProjectIssueTypeSerializer(bridge, data=request.data, partial=True)
        if serializer.is_valid():
            with transaction.atomic():
                serializer.save()
                if serializer.instance.is_default:
                    ProjectIssueType.objects.filter(project_id=project_id, is_default=True).exclude(
                        pk=serializer.instance.pk
                    ).update(is_default=False)
            return Response(ProjectIssueTypeSerializer(serializer.instance).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def destroy(self, request, slug, project_id, pk):
        bridge = self.get_queryset().filter(pk=pk).first()
        if bridge is None:
            return Response({"error": "Project issue type not found"}, status=status.HTTP_404_NOT_FOUND)
        # 不变量：项目默认桥不可解绑（先换默认再解绑）
        if bridge.is_default:
            return Response(
                {"error": "The default work item type cannot be unbound from the project"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bridge.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
