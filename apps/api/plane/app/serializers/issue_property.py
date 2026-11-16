# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
自定义属性序列化器（Step02 段 2 追赶 BE）。

- IssuePropertySerializer：池 CRUD + settings/逐类子配置校验（段 2 产品方案 §2）。
  property_type 创建后锁定（PATCH 忽略变更——改类型会破坏存量值语义，
  段 2 技术方案 §2.2）。
- IssueTypeIssuePropertySerializer：绑定桥。
- IssuePropertyValueSerializer：值读写校验按 property_type 分派（技术方案 §2.3）。

选项集存 settings.options（[{"id","name","is_default"}]，产品方案 A1）；
值引用选项 id，选项改名不影响存量值。
"""

import re
from datetime import date as date_cls
from uuid import uuid4

# Third Party imports
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from plane.db.models import Issue, IssueProperty, IssuePropertyType, IssueTypeIssueProperty, IssuePropertyValue

NUMBER_FORMATS = {"standard", "percent", "currency"}
TEXT_DISPLAY_FORMATS = {"single-line", "multi-line", "readonly"}
URL_PATTERN = re.compile(
    r"^(https?|ftp)://"  # scheme
    r"((([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,})|"  # domain
    r"((\d{1,3}\.){3}\d{1,3})|"  # ipv4
    r"(\[[0-9a-f:]+\]))"  # ipv6
    r"(:\d{1,5})?"  # port
    r"(/[^\s]*)?$",
    re.IGNORECASE,
)


def _normalize_empty(value):
    """空值统一为 None（清空语义，服务层据此删值行）。"""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    if isinstance(value, (list, tuple)) and len(value) == 0:
        return None
    return value


def _validate_settings_for_type(property_type: str, settings: dict, project_id) -> dict:
    """逐类校验 settings 子配置（段 2 产品方案 §2 逐类清单）。"""
    if settings is None:
        settings = {}
    if not isinstance(settings, dict):
        raise serializers.ValidationError({"settings": ["Settings must be a JSON object"]})

    if property_type == IssuePropertyType.TEXT:
        display_format = settings.get("display_format", "single-line")
        if display_format not in TEXT_DISPLAY_FORMATS:
            raise serializers.ValidationError({"settings": [f"Invalid display_format: {display_format}"]})
        return {"display_format": display_format}

    if property_type == IssuePropertyType.DECIMAL:
        number_format = settings.get("format", "standard")
        if number_format not in NUMBER_FORMATS:
            raise serializers.ValidationError({"settings": [f"Invalid format: {number_format}"]})
        decimal_places = settings.get("decimal_places", 2)
        if not isinstance(decimal_places, int) or not (0 <= decimal_places <= 8):
            raise serializers.ValidationError({"settings": ["decimal_places must be an integer between 0 and 8"]})
        thousands = bool(settings.get("thousands_separator", False))
        return {"format": number_format, "decimal_places": decimal_places, "thousands_separator": thousands}

    if property_type == IssuePropertyType.OPTION:
        is_multi = bool(settings.get("is_multi", False))
        options = settings.get("options", [])
        if not isinstance(options, list) or len(options) == 0:
            # 选项集非空校验（段 2 产品方案 §4）
            raise serializers.ValidationError({"settings": ["Dropdown options cannot be empty"]})
        normalized_options = []
        seen_names = set()
        for option in options:
            if not isinstance(option, dict) or not str(option.get("name", "")).strip():
                raise serializers.ValidationError({"settings": ["Each option requires a non-empty name"]})
            option_name = str(option["name"]).strip()
            if option_name in seen_names:
                raise serializers.ValidationError({"settings": [f"Duplicate option name: {option_name}"]})
            seen_names.add(option_name)
            normalized_options.append(
                {
                    "id": option.get("id") or str(uuid4()),
                    "name": option_name,
                    "is_default": bool(option.get("is_default", False)),
                }
            )
        return {"is_multi": is_multi, "options": normalized_options}

    if property_type == IssuePropertyType.MEMBER:
        return {"is_multi": bool(settings.get("is_multi", False))}

    # boolean / date / rich_text / url：无额外配置
    return {}


def _validate_default_value(property_type: str, settings: dict, default_value, project_id):
    """默认值校验：数字须数值、下拉须在选项集、成员须是项目成员。"""
    default_value = _normalize_empty(default_value)
    if default_value is None:
        return None

    if property_type == IssuePropertyType.DECIMAL:
        if isinstance(default_value, bool) or not isinstance(default_value, (int, float)):
            raise serializers.ValidationError({"default_value": ["Default value must be a number"]})
        return default_value

    if property_type == IssuePropertyType.OPTION:
        option_ids = {option["id"] for option in settings.get("options", [])}
        values = default_value if isinstance(default_value, list) else [default_value]
        for option_id in values:
            if option_id not in option_ids:
                raise serializers.ValidationError({"default_value": ["Default value must be one of the options"]})
        return values if settings.get("is_multi") else values[0]

    if property_type == IssuePropertyType.MEMBER:
        _validate_member_values(default_value, project_id)
        return default_value

    return None


def _validate_member_values(value, project_id) -> None:
    """成员值须是该项目成员的用户 id（单值或数组均收敛到此处）。"""
    from plane.db.models import ProjectMember

    member_ids = value if isinstance(value, list) else [value]
    if not member_ids:
        return
    valid_ids = set(
        ProjectMember.objects.filter(
            project_id=project_id,
            member_id__in=member_ids,
            is_active=True,
        ).values_list("member_id", flat=True)
    )
    for member_id in member_ids:
        if str(member_id) not in {str(valid_id) for valid_id in valid_ids}:
            raise serializers.ValidationError({"value": [f"Member {member_id} is not part of this project"]})


class IssuePropertySerializer(BaseSerializer):
    """项目属性池序列化器。"""

    issue_type_bindings_count = serializers.SerializerMethodField()
    issue_type_bindings = serializers.SerializerMethodField()

    class Meta:
        model = IssueProperty
        fields = [
            "id",
            "name",
            "description",
            "property_type",
            "settings",
            "is_required",
            "is_active",
            "default_value",
            "sort_order",
            "issue_type_bindings_count",
            "issue_type_bindings",
            "project",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "project", "workspace", "created_at", "updated_at"]

    def get_issue_type_bindings_count(self, instance) -> int:
        """「使用中的工作项类型」列（57 号 §1.2 Tab2）。"""
        return instance.issue_type_bindings.count()

    def get_issue_type_bindings(self, instance) -> list:
        return [
            {
                "issue_type_id": str(binding.issue_type_id),
                "issue_type_name": binding.issue_type.name,
            }
            for binding in instance.issue_type_bindings.select_related("issue_type").all()
        ]

    def validate(self, data):
        """创建时逐类校验 settings/default_value；property_type 创建后锁定。"""
        instance = self.instance
        property_type = data.get("property_type", getattr(instance, "property_type", None) if instance else None)
        if not property_type:
            raise serializers.ValidationError({"property_type": ["This field is required"]})
        if instance is not None and "property_type" in data and data["property_type"] != instance.property_type:
            raise serializers.ValidationError({"property_type": ["Property type cannot be changed after creation"]})

        settings = data.get("settings", getattr(instance, "settings", {}) if instance else {})
        data["settings"] = _validate_settings_for_type(property_type, settings, self.context.get("project_id"))

        if "default_value" in data:
            data["default_value"] = _validate_default_value(
                property_type, data["settings"], data["default_value"], self.context.get("project_id")
            )
        elif instance is not None and instance.default_value is not None:
            # 改 settings（如下拉选项集）后重校既有默认值
            data["default_value"] = _validate_default_value(
                property_type, data["settings"], instance.default_value, self.context.get("project_id")
            )
        return data


class IssueTypeIssuePropertySerializer(BaseSerializer):
    """绑定桥序列化器（绑定/解绑经 ViewSet 端点，不走通用 create）。"""

    issue_property_detail = serializers.SerializerMethodField()

    class Meta:
        model = IssueTypeIssueProperty
        fields = [
            "id",
            "issue_type",
            "issue_property",
            "issue_property_detail",
            "created_at",
        ]
        read_only_fields = ["id", "issue_type", "created_at"]

    def get_issue_property_detail(self, instance) -> dict | None:
        detail = IssuePropertySerializer(instance.issue_property, context=self.context)
        return detail.data


class IssuePropertyValueSerializer(BaseSerializer):
    """属性值序列化器：读透出定义+值；写校验在 ViewSet 服务层（批量单事务）。"""

    class Meta:
        model = IssuePropertyValue
        fields = ["id", "issue", "issue_property", "value", "created_at", "updated_at"]
        read_only_fields = ["id", "issue", "issue_property", "created_at", "updated_at"]


def validate_property_value(issue_property: IssueProperty, value, project_id):
    """按 property_type 分派校验（段 2 技术方案 §2.3），返回规范化值。

    抛 serializers.ValidationError；空值统一 None（调用方据此删值行）。
    """
    value = _normalize_empty(value)
    if value is None:
        return None

    property_type = issue_property.property_type
    settings = issue_property.settings or {}

    if property_type == IssuePropertyType.TEXT:
        if not isinstance(value, str):
            raise serializers.ValidationError({"value": ["Text value must be a string"]})
        return value

    if property_type == IssuePropertyType.DECIMAL:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise serializers.ValidationError({"value": ["Number value must be numeric"]})
        return value

    if property_type == IssuePropertyType.OPTION:
        option_ids = {option["id"] for option in settings.get("options", [])}
        if settings.get("is_multi"):
            if not isinstance(value, list):
                raise serializers.ValidationError({"value": ["Multi-select value must be a list of option ids"]})
            for option_id in value:
                if option_id not in option_ids:
                    raise serializers.ValidationError({"value": [f"Unknown option: {option_id}"]})
            return value
        if isinstance(value, list):
            raise serializers.ValidationError({"value": ["Single-select value must be an option id"]})
        if value not in option_ids:
            raise serializers.ValidationError({"value": [f"Unknown option: {value}"]})
        return value

    if property_type == IssuePropertyType.BOOLEAN:
        if not isinstance(value, bool):
            raise serializers.ValidationError({"value": ["Boolean value must be true or false"]})
        return value

    if property_type == IssuePropertyType.DATE:
        if not isinstance(value, str):
            raise serializers.ValidationError({"value": ["Date value must be an ISO date string"]})
        try:
            date_cls.fromisoformat(value[:10])
        except ValueError:
            raise serializers.ValidationError({"value": ["Date value must be a valid ISO date"]}) from None
        return value

    if property_type == IssuePropertyType.MEMBER:
        _validate_member_values(value, project_id)
        return value

    if property_type == IssuePropertyType.RICH_TEXT:
        if not isinstance(value, str):
            raise serializers.ValidationError({"value": ["Rich text value must be a string"]})
        return value

    if property_type == IssuePropertyType.URL:
        if not isinstance(value, str) or not URL_PATTERN.match(value.strip()):
            raise serializers.ValidationError({"value": ["Value must be a valid URL"]})
        return value.strip()

    raise serializers.ValidationError({"value": [f"Unsupported property type: {property_type}"]})


def issue_type_of_issue(issue: Issue) -> Issue | None:
    """工作项当前类型（可为 None：未分配类型的存量工作项）。"""
    return issue.type
