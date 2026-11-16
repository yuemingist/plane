# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third Party imports
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from plane.db.models import IssueType, ProjectIssueType


class IssueTypeSerializer(BaseSerializer):
    """工作项类型序列化器（app 端，项目语境）。

    注意：
    - `is_default` 与 `level` 语义以 `ProjectIssueType`（项目桥）为准；
      `IssueType.is_default` / `IssueType.level`（工作区级字段）本步不消费。
    - `is_default`、`level` 与 `issues_count` 由 ViewSet 通过 annotate 注入实例属性
      （项目桥子查询 / 引用计数），非模型列，因此用 method 字段读取。
    """

    is_default = serializers.SerializerMethodField()
    issues_count = serializers.SerializerMethodField()
    level = serializers.SerializerMethodField()
    # 段 5：可用状态集合（项目桥 M2M），只读透出；写走 PUT {pk}/states/ 全量替换端点
    state_ids = serializers.SerializerMethodField()

    class Meta:
        model = IssueType
        fields = [
            "id",
            "name",
            "description",
            "logo_props",
            "is_epic",
            "is_active",
            "level",
            "is_default",
            "issues_count",
            "state_ids",
            "external_source",
            "external_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_epic",
            "is_default",
            "issues_count",
            "state_ids",
            "level",
            "external_source",
            "external_id",
            "created_at",
            "updated_at",
        ]

    def get_is_default(self, instance) -> bool:
        # 读取 ViewSet annotate 注入的项目桥默认标记；无 annotate（或桥缺失）时视为非默认
        return bool(getattr(instance, "project_is_default", False))

    def get_level(self, instance) -> int:
        # BUG-04：读取 ViewSet annotate 注入的项目桥层级（enable 流写入 Epic=1）；
        # 无 annotate（或桥缺失，如嵌套 issue_type_detail）时回落工作区级 level
        project_level = getattr(instance, "project_level", None)
        if project_level is None:
            return int(instance.level or 0)
        return int(project_level)

    def get_issues_count(self, instance) -> int:
        # 引用计数（「特性」列数据源），由 ViewSet annotate 注入；缺省 0
        return int(getattr(instance, "project_issues_count", 0) or 0)

    def get_state_ids(self, instance) -> list:
        # 段 5：类型可用状态集合（项目桥 M2M，ViewSet annotate 注入）；
        # 空数组 = 未配置 = 继承项目全量状态池（产品方案 A2）
        return [str(state_id) for state_id in (getattr(instance, "state_ids", None) or []) if state_id is not None]

    def validate(self, attrs):
        # 新建类型默认「已禁用」：model 默认 True，这里在序列化层覆盖（产品方案 §3.3）
        if self.instance is None and "is_active" not in attrs:
            attrs["is_active"] = False
        return attrs


class ProjectIssueTypeSerializer(BaseSerializer):
    """项目 <-> 类型桥的最小绑定面（本步不做属性绑定）。"""

    issue_type_detail = IssueTypeSerializer(source="issue_type", read_only=True)

    class Meta:
        model = ProjectIssueType
        fields = [
            "id",
            "issue_type",
            "issue_type_detail",
            "level",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "issue_type_detail", "created_at", "updated_at"]
