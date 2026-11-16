# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
工作流域视图（Step02 段 1 追赶 BE）。

端点形态对照段 1 技术方案 §1.3（项目域扁平路由，kebab-case 路径 workflows/）：
- GET 列表/详情（读三角色，门卡语义：未启用返回空数组而非 403）
- POST enable/（项目级启用：建行或复活动行 + 历史）
- POST {id}/disable/、{id}/enable/（停用/再启用 + 历史）
- GET {id}/change-history/（分页倒序）

对标：58 号对比 D-10（Business 档壳）——单一 Default Workflow、无规则配置。
状态机（段 1 产品方案 §3）：禁用不删行、再启用复用同一行；每次启停留痕。
"""

# Django imports
from django.db import transaction

# Third Party imports
from rest_framework import status
from rest_framework.response import Response

# Python imports
from uuid import UUID

# Module imports
from .base import BaseViewSet
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import (
    WorkflowChangeLogSerializer,
    WorkflowSerializer,
    WorkflowTransitionSerializer,
)
from plane.db.models import (
    IssueType,
    Project,
    ProjectIssueType,
    State,
    Workflow,
    WorkflowChangeAction,
    WorkflowChangeLog,
    WorkflowTransition,
)


def validate_state_transition(project_id, from_state_id, to_state_id) -> dict | None:
    """流转校验挂载点（Step02 段 3，技术方案 §2.1）。

    语义（段 3 产品方案 A2）：工作流启用且配置了 from_state 的规则行时，
    to_state 必须在允许集合内；无工作流 / 工作流停用 / 该源状态无规则行 → 放行。

    返回 None=放行；返回 dict=拒绝（错误体含 code 与源/目标状态名，供前端
    i18n toast 使用）。只读查询，不写任何留痕（留痕仍由既有 issue_activity 负责）。
    """
    if not from_state_id or not to_state_id or from_state_id == to_state_id:
        return None

    workflow = Workflow.objects.filter(
        project_id=project_id, is_active=True, deleted_at__isnull=True
    ).first()
    if workflow is None:
        return None

    # 该源状态没有规则行 = 不受限（白名单按源状态生效）
    if not WorkflowTransition.objects.filter(
        workflow=workflow, from_state_id=from_state_id, deleted_at__isnull=True
    ).exists():
        return None

    if WorkflowTransition.objects.filter(
        workflow=workflow, from_state_id=from_state_id, to_state_id=to_state_id, deleted_at__isnull=True
    ).exists():
        return None

    from_state_name = State.objects.filter(pk=from_state_id).values_list("name", flat=True).first()
    to_state_name = State.objects.filter(pk=to_state_id).values_list("name", flat=True).first()
    return {
        "error": "This state transition is not allowed by the project workflow.",
        "code": "workflow_transition_not_allowed",
        "from_state_name": from_state_name,
        "to_state_name": to_state_name,
    }


def validate_state_allowed_for_type(project_id, type_id, state_id) -> dict | None:
    """类型可用状态校验（Step02 段 5，技术方案 §2.3）。

    语义（段 5 产品方案 A2/A9）：工作项类型配置了可用状态集合时，目标状态必须
    在集合内；类型为空 / 桥不存在 / 集合为空（继承项目全量状态池）→ 放行。
    软删状态的陈旧引用在集合读取时被过滤（A9）。

    返回 None=放行；返回 dict=拒绝（错误体含 code 与类型/状态名，供前端 i18n toast）。
    只读查询，不写任何留痕。与段 3 validate_state_transition 串联：
    先可用集合（本函数）后流转规则，错误码区分（产品方案 A3）。
    """
    if not type_id or not state_id:
        return None

    try:
        state_uuid = UUID(str(state_id))
    except ValueError:
        # 非法 UUID 交给序列化器既有校验兜底
        return None

    bridge = ProjectIssueType.objects.filter(
        project_id=project_id, issue_type_id=type_id, deleted_at__isnull=True
    ).first()
    if bridge is None:
        return None

    allowed_state_ids = set(bridge.states.filter(deleted_at__isnull=True).values_list("id", flat=True))
    # 空集合 = 继承项目全量状态池（白名单语义，产品方案 A2）
    if not allowed_state_ids:
        return None

    if state_uuid in allowed_state_ids:
        return None

    type_name = IssueType.objects.filter(pk=type_id).values_list("name", flat=True).first()
    state_name = State.objects.filter(pk=state_uuid).values_list("name", flat=True).first()
    return {
        "error": "This state is not available for this work item type.",
        "code": "issue_type_state_not_allowed",
        "type_name": type_name,
        "state_name": state_name,
    }


class WorkflowViewSet(BaseViewSet):
    """项目工作流壳：启用/停用/再启用 + 更改历史。"""

    serializer_class = WorkflowSerializer
    model = Workflow

    def _member_scoped_workflows(self, slug, project_id):
        """项目成员作用域的工作流查询（Step01 §2.3 权限域绑定模式）。"""
        return Workflow.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            deleted_at__isnull=True,
        ).filter(
            project__project_projectmember__member=self.request.user,
            project__project_projectmember__is_active=True,
            project__archived_at__isnull=True,
        )

    def _get_scoped_instance(self, slug, project_id, pk):
        return self._member_scoped_workflows(slug, project_id).filter(pk=pk).first()

    def _log_action(self, workflow, actor, action: str, note: str = "") -> None:
        WorkflowChangeLog.objects.create(workflow=workflow, actor=actor, action=action, note=note)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id):
        """未启用项目返回空数组（门卡语义：前端据此渲染启用开关卡片）。"""
        workflows = self._member_scoped_workflows(slug, project_id)
        serializer = WorkflowSerializer(workflows, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id):
        """项目级启用（前端开关总入口）：
        - 无行 → 建 Default Workflow（is_active=True）+ 历史 enabled；
        - 有禁用行 → 复用原行置回 True + 历史 re_enabled；
        - 已有活动行 → 400（不产生第二行、不重复写历史）。
        """
        Project.objects.get(pk=project_id, workspace__slug=slug)

        with transaction.atomic():
            # 锁项目行串行化启停竞态；workflow 行在事务内按项目取
            Project.objects.select_for_update().get(pk=project_id)
            workflow = self._member_scoped_workflows(slug, project_id).first()
            if workflow is not None:
                if workflow.is_active:
                    return Response(
                        {"error": "Workflow is already enabled for this project"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                workflow.is_active = True
                workflow.save(update_fields=["is_active"])
                self._log_action(workflow, request.user, WorkflowChangeAction.RE_ENABLED)
            else:
                workflow = Workflow.objects.create(project_id=project_id, name="Default Workflow", is_active=True)
                self._log_action(workflow, request.user, WorkflowChangeAction.ENABLED)

        return Response(WorkflowSerializer(workflow).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def retrieve(self, request, slug, project_id, pk):
        workflow = self._get_scoped_instance(slug, project_id, pk)
        if workflow is None:
            return Response({"error": "Workflow not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(WorkflowSerializer(workflow).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def disable(self, request, slug, project_id, pk):
        workflow = self._get_scoped_instance(slug, project_id, pk)
        if workflow is None:
            return Response({"error": "Workflow not found"}, status=status.HTTP_404_NOT_FOUND)
        if not workflow.is_active:
            return Response(
                {"error": "Workflow is already disabled for this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        workflow.is_active = False
        workflow.save(update_fields=["is_active"])
        self._log_action(workflow, request.user, WorkflowChangeAction.DISABLED)
        return Response(WorkflowSerializer(workflow).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def enable(self, request, slug, project_id, pk):
        """单行再启用（API 对称保留；UI 启停走项目级 create 入口）。"""
        workflow = self._get_scoped_instance(slug, project_id, pk)
        if workflow is None:
            return Response({"error": "Workflow not found"}, status=status.HTTP_404_NOT_FOUND)
        if workflow.is_active:
            return Response(
                {"error": "Workflow is already enabled for this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        workflow.is_active = True
        workflow.save(update_fields=["is_active"])
        self._log_action(workflow, request.user, WorkflowChangeAction.RE_ENABLED)
        return Response(WorkflowSerializer(workflow).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def change_history(self, request, slug, project_id, pk):
        """更改历史：按时间倒序游标分页（时间/操作人/动作/备注）。"""
        workflow = self._get_scoped_instance(slug, project_id, pk)
        if workflow is None:
            return Response({"error": "Workflow not found"}, status=status.HTTP_404_NOT_FOUND)

        change_logs = (
            WorkflowChangeLog.objects.filter(workflow=workflow, deleted_at__isnull=True)
            .select_related("actor")
            .order_by("-created_at")
        )
        return self.paginate(
            request=request,
            queryset=change_logs,
            on_results=lambda rows: WorkflowChangeLogSerializer(rows, many=True).data,
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def transitions(self, request, slug, project_id, pk):
        """流转规则行列表（段 3）：ADMIN/MEMBER/GUEST 可读（产品方案 §5）。"""
        workflow = self._get_scoped_instance(slug, project_id, pk)
        if workflow is None:
            return Response({"error": "Workflow not found"}, status=status.HTTP_404_NOT_FOUND)

        transitions = WorkflowTransition.objects.filter(
            workflow=workflow, deleted_at__isnull=True
        ).order_by("from_state_id", "to_state_id")
        serializer = WorkflowTransitionSerializer(transitions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def replace_transitions(self, request, slug, project_id, pk):
        """全量替换流转规则（段 3，技术方案 §2）。

        body: {"transitions": [{"from_state": id, "to_states": [ids...]}]}
        - from/to state 必须属于本项目、from != to，否则 400；
        - 事务内全删全插；仅当规则集合实际变化时写一条
          WorkflowChangeLog(action="transition_rules_updated")（不变更不写历史）；
        - 空数组 = 清空规则（默认无规则 = 全部允许，产品方案 A2）。
        """
        workflow = self._get_scoped_instance(slug, project_id, pk)
        if workflow is None:
            return Response({"error": "Workflow not found"}, status=status.HTTP_404_NOT_FOUND)

        payload = request.data.get("transitions") if isinstance(request.data, dict) else None
        if not isinstance(payload, list):
            return Response(
                {"error": "transitions must be a list of {from_state, to_states} groups"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project_state_ids = set(
            # 软删除状态不可作为规则端点（产品方案 A6：陈旧引用靠全量替换丢弃）
            State.all_state_objects.filter(project_id=project_id, deleted_at__isnull=True).values_list(
                "id", flat=True
            )
        )

        desired_rows: set[tuple[UUID, UUID]] = set()
        for group in payload:
            if not isinstance(group, dict):
                return Response({"error": "Each transition group must be an object"}, status=status.HTTP_400_BAD_REQUEST)
            from_state_id = group.get("from_state")
            to_state_ids = group.get("to_states")
            if not isinstance(from_state_id, str) or not isinstance(to_state_ids, list):
                return Response(
                    {"error": "from_state must be a state id and to_states a list of state ids"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                from_uuid = UUID(from_state_id)
            except ValueError:
                return Response({"error": "Invalid from_state id"}, status=status.HTTP_400_BAD_REQUEST)
            if from_uuid not in project_state_ids:
                return Response(
                    {"error": "from_state is not a state of this project"}, status=status.HTTP_400_BAD_REQUEST
                )
            for to_state_id in to_state_ids:
                if not isinstance(to_state_id, str):
                    return Response({"error": "to_states must contain state ids"}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    to_uuid = UUID(to_state_id)
                except ValueError:
                    return Response({"error": "Invalid to_state id"}, status=status.HTTP_400_BAD_REQUEST)
                if to_uuid not in project_state_ids:
                    return Response(
                        {"error": "to_state is not a state of this project"}, status=status.HTTP_400_BAD_REQUEST
                    )
                if to_uuid == from_uuid:
                    return Response(
                        {"error": "from_state and to_state cannot be the same state"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                desired_rows.add((from_uuid, to_uuid))

        with transaction.atomic():
            # 锁既有规则行串行化并发 PUT（list() 触发求值以真正加锁）
            list(
                WorkflowTransition.objects.select_for_update().filter(
                    workflow=workflow, deleted_at__isnull=True
                )
            )
            current_rows = set(
                WorkflowTransition.objects.filter(workflow=workflow, deleted_at__isnull=True).values_list(
                    "from_state_id", "to_state_id"
                )
            )
            if current_rows != desired_rows:
                WorkflowTransition.objects.filter(workflow=workflow, deleted_at__isnull=True).delete()
                WorkflowTransition.objects.bulk_create(
                    [
                        WorkflowTransition(
                            workflow=workflow,
                            project_id=project_id,
                            workspace_id=workflow.workspace_id,
                            from_state_id=from_state_id,
                            to_state_id=to_state_id,
                        )
                        for from_state_id, to_state_id in sorted(desired_rows)
                    ]
                )
                WorkflowChangeLog.objects.create(
                    workflow=workflow,
                    actor=request.user,
                    action=WorkflowChangeAction.TRANSITION_RULES_UPDATED,
                    note=f"{len(desired_rows)} transition rules",
                )

        transitions = WorkflowTransition.objects.filter(
            workflow=workflow, deleted_at__isnull=True
        ).order_by("from_state_id", "to_state_id")
        return Response(WorkflowTransitionSerializer(transitions, many=True).data, status=status.HTTP_200_OK)
