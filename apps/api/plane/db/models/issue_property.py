# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
自定义属性域（Step02 段 2 追赶 BE，P2-13）。

对标：57 号对比 §3.3/§4.2（D-03/D-04）——项目属性池 + 类型绑定 + EAV 值存储。
CE 从未有过云端意义的属性 schema（旧 IssueProperty 0071/0114 迁移改名链是
用户显示偏好 ProjectUserProperty，见 18-01 草案 §4），本域三表从零建：

- IssueProperty：项目属性池（8 类 type 枚举 + settings JSON 子配置 + is_active 双门控）。
- IssueTypeIssueProperty：类型↔属性绑定桥；启用门控由属性池 is_active 承担
  （57 号「启用将在所有已关联的工作项类型中生效」实测语义），桥上无独立开关。
- IssuePropertyValue：issue+属性唯一，value JSON 按类型分派校验（serializer 层）。

升级官方 schema 的收敛预案（段 2 技术方案 §4.3）：表名不可考，若官方 CE 版
发布同名表走 RenameModel + 数据搬迁迁移；value 不写 typed 列便于并轨。
"""

# Django imports
from django.db import models
from django.db.models import Q

# Module imports
from .base import BaseModel
from .issue_type import IssueType
from .project import ProjectBaseModel


class IssuePropertyType(models.TextChoices):
    """属性类型枚举：UI 实测 8 类（57 号 §4.2）。

    SDK 另有 FORMULA/CASCADING/RELATION 等（18-01 §6），UI 无且语义未定，
    不进枚举；官方若补齐在此扩展。
    """

    TEXT = "text", "text"
    DECIMAL = "decimal", "decimal"
    OPTION = "option", "option"
    BOOLEAN = "boolean", "boolean"
    DATE = "date", "date"
    MEMBER = "member", "member"
    RICH_TEXT = "rich_text", "rich_text"
    URL = "url", "url"


class IssueProperty(ProjectBaseModel):
    """项目属性池：创建默认 is_active=False（双门控第一门，57 号 §3.3 步骤 4）。

    settings JSON 结构（段 2 产品方案 §2 逐类）：
    - text: {"display_format": "single-line" | "multi-line" | "readonly"}
    - decimal: {"format": "standard" | "percent" | "currency",
                "decimal_places": int(0..8), "thousands_separator": bool}
    - option: {"is_multi": bool, "options": [{"id", "name", "is_default"}]}
    - member: {"is_multi": bool}
    - boolean/date/rich_text/url: {}
    default_value：数字默认值（数值）/下拉默认选项 id/成员默认 id（数组当 is_multi）。
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    property_type = models.CharField(
        max_length=30,
        choices=IssuePropertyType.choices,
        default=IssuePropertyType.TEXT,
    )
    settings = models.JSONField(default=dict, blank=True)
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    default_value = models.JSONField(null=True, blank=True)
    sort_order = models.FloatField(default=65535)

    def __str__(self):
        """Return the property name and project."""
        return f"{self.name} <{self.project.name}>"

    class Meta:
        verbose_name = "Issue Property"
        verbose_name_plural = "Issue Properties"
        db_table = "issue_properties"
        ordering = ("sort_order", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"],
                condition=Q(deleted_at__isnull=True),
                name="issue_property_unique_name_per_project_when_deleted_at_null",
            )
        ]


class IssueTypeIssueProperty(BaseModel):
    """类型↔属性绑定桥：类型详情页「添加现有属性」建行（57 号 §3.4 步骤 2）。

    无独立 is_active：属性启停是池级开关（产品方案 §4），桥只表达
    「该类型关联了该属性」；解绑只删桥、值保留（产品方案 A2）。
    """

    issue_type = models.ForeignKey(IssueType, related_name="issue_type_properties", on_delete=models.CASCADE)
    issue_property = models.ForeignKey(IssueProperty, related_name="issue_type_bindings", on_delete=models.CASCADE)

    def __str__(self):
        """Return the issue type and property."""
        return f"{self.issue_type.name} - {self.issue_property.name}"

    class Meta:
        verbose_name = "Issue Type Issue Property"
        verbose_name_plural = "Issue Type Issue Properties"
        db_table = "issue_type_issue_properties"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["issue_type", "issue_property"],
                condition=Q(deleted_at__isnull=True),
                name="issue_type_issue_property_unique_when_deleted_at_null",
            )
        ]


class IssuePropertyValue(BaseModel):
    """属性值：issue+属性唯一（软删感知），value JSON 按 property_type 分派校验。

    清空值（null/""/[]）在服务层删除该行而非存 null（段 2 技术方案 §2.3-3）。
    """

    issue = models.ForeignKey("db.Issue", related_name="issue_property_values", on_delete=models.CASCADE)
    issue_property = models.ForeignKey(IssueProperty, related_name="property_values", on_delete=models.CASCADE)
    value = models.JSONField(null=True, blank=True)

    def __str__(self):
        """Return the issue and property."""
        return f"{self.issue_id} - {self.issue_property.name}"

    class Meta:
        verbose_name = "Issue Property Value"
        verbose_name_plural = "Issue Property Values"
        db_table = "issue_property_values"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["issue", "issue_property"],
                condition=Q(deleted_at__isnull=True),
                name="issue_property_value_unique_issue_property_when_deleted_at_null",
            )
        ]
