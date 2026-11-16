# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third Party imports
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from plane.db.models import Workflow, WorkflowChangeLog, WorkflowTransition


class WorkflowSerializer(BaseSerializer):
    """工作流壳序列化器（app 端，项目语境）。

    本段无改名入口：`name` 只读透出（默认 "Default Workflow"，云端中文界面
    也不翻译，58 号截图 2 实拍）；启停走专用端点而非 PATCH。
    """

    class Meta:
        model = Workflow
        fields = [
            "id",
            "name",
            "is_active",
            "project",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "name",
            "is_active",
            "project",
            "workspace",
            "created_at",
            "updated_at",
        ]


class WorkflowChangeLogSerializer(BaseSerializer):
    """工作流更改历史序列化器：动作/操作人/时间/备注。"""

    actor_detail = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowChangeLog
        fields = [
            "id",
            "action",
            "note",
            "actor",
            "actor_detail",
            "created_at",
        ]
        read_only_fields = ["id", "action", "note", "actor", "actor_detail", "created_at"]

    def get_actor_detail(self, instance) -> dict | None:
        actor = instance.actor
        if actor is None:
            return None
        return {
            "id": str(actor.id),
            "first_name": actor.first_name or "",
            "display_name": actor.display_name,
            "avatar": actor.avatar or "",
        }


class WorkflowTransitionSerializer(BaseSerializer):
    """流转规则行序列化器（段 3，只读透出；写入走视图层全量替换 PUT）。"""

    class Meta:
        model = WorkflowTransition
        fields = ["id", "workflow", "from_state", "to_state", "created_at", "updated_at"]
        read_only_fields = ["id", "workflow", "from_state", "to_state", "created_at", "updated_at"]
