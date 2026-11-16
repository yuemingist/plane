# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
自定义属性值聚合 util（Step02 段 4 属性贯穿 BE）。

对标：段 4 技术方案 §1/§4 —— 列表响应批量补值（每页恒定 +1 查询，无 N+1）
与导出动态属性列（65 号 §1.5 云端 33 列实测含自定义属性动态列）。
"""

# Django imports
from django.db.models import QuerySet
from django.utils.html import strip_tags

# Module imports
from plane.db.models import IssueProperty, IssuePropertyType, IssuePropertyValue, User
from plane.utils.exception_logger import log_exception


def _fetch_active_property_values(issue_ids: list[str]):
    """单次批量查询：页内/导出集合内工作项的已启用属性值（双门控：池级 is_active）。"""
    return IssuePropertyValue.objects.filter(
        issue_id__in=issue_ids,
        issue_property__is_active=True,
        issue_property__deleted_at__isnull=True,
        deleted_at__isnull=True,
    ).select_related("issue_property")


def _format_property_value(property_obj: IssueProperty, value) -> str:
    """属性值 → 导出单元格文本。多值用 `|` 连接（与 11 号导入端自定义属性列解析对齐，可往返）。"""
    if value is None:
        return ""

    property_type = property_obj.property_type
    settings = property_obj.settings or {}

    if property_type == IssuePropertyType.OPTION:
        options_by_id = {str(option.get("id")): str(option.get("name")) for option in settings.get("options", [])}
        raw_ids = value if isinstance(value, list) else [value]
        names = [options_by_id.get(str(option_id), str(option_id)) for option_id in raw_ids]
        return "|".join(names)

    if property_type == IssuePropertyType.MEMBER:
        member_ids = value if isinstance(value, list) else [value]
        members = {
            str(member.id): member.full_name
            for member in User.objects.filter(id__in=[member_id for member_id in member_ids if member_id])
        }
        return "|".join(members.get(str(member_id), str(member_id)) for member_id in member_ids)

    if property_type == IssuePropertyType.BOOLEAN:
        return "true" if value else "false"

    if property_type == IssuePropertyType.RICH_TEXT:
        return strip_tags(str(value))

    # text / url / date / decimal：原文输出（decimal 已是数值）
    return str(value)


def attach_issue_property_values(rows: list[dict], project_id: str) -> list[dict]:
    """列表响应批量补值：每页恒定 +1 查询（段 4 技术方案 §1，pytest assertNumQueries 断言）。

    rows 为分页后的 issue dict 列表（issue_on_results / values(...) 产出），逐行写入
    `issue_property_values: {property_id: rawJSON}`；无值行写 `{}`。
    """
    if not rows or not project_id:
        return rows

    try:
        issue_ids = [row["id"] for row in rows]
        values = (
            _fetch_active_property_values(issue_ids)
            .filter(issue_property__project_id=project_id)
            .values_list("issue_id", "issue_property_id", "value")
        )
        grouped: dict[str, dict[str, object]] = {}
        for issue_id, property_id, value in values:
            grouped.setdefault(str(issue_id), {})[str(property_id)] = value

        for row in rows:
            row["issue_property_values"] = grouped.get(str(row["id"]), {})
    except Exception as e:
        # 补值失败不阻断列表：留空并记日志
        log_exception(e)
        for row in rows:
            row.setdefault("issue_property_values", {})
    return rows


def attach_issue_property_export_columns(rows: list[dict], issue_queryset: QuerySet) -> list[dict]:
    """导出行动态属性列（段 4 产品方案 §4 判定「做」）。

    DRF many=True 保序：rows 与 queryset.values_list("id") 同序 zip；数量不一致时
    防御性跳过追加（不产坏文件）。列名=属性名，值经 _format_property_value 格式化。
    """
    if not rows:
        return rows

    try:
        issue_ids = [str(issue_id) for issue_id in issue_queryset.values_list("id", flat=True)]
        if len(issue_ids) != len(rows):
            return rows

        values = _fetch_active_property_values(issue_ids)
        # 仅保留导出集合内工作项的值
        allowed_ids = set(issue_ids)
        by_issue: dict[str, dict[str, object]] = {}
        properties_by_id: dict[str, IssueProperty] = {}
        for value_row in values:
            if str(value_row.issue_id) not in allowed_ids:
                continue
            by_issue.setdefault(str(value_row.issue_id), {})[str(value_row.issue_property_id)] = value_row.value
            properties_by_id[str(value_row.issue_property_id)] = value_row.issue_property

        for row, issue_id in zip(rows, issue_ids):
            for property_id, value in by_issue.get(issue_id, {}).items():
                property_obj = properties_by_id[property_id]
                row[property_obj.name] = _format_property_value(property_obj, value)
    except Exception as e:
        # 动态列失败不阻断导出：固定列照常产出
        log_exception(e)
    return rows
