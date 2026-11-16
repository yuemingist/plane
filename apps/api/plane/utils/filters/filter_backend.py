# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json

# Django imports
from django.db.models import Q
from django.http import QueryDict

# Third party imports
from django_filters.utils import translate_validation
from rest_framework import filters
from rest_framework.exceptions import ValidationError as DRFValidationError

from plane.utils.exception_logger import log_exception

# 自定义属性筛选键前缀（段 4 属性贯穿）：`customproperty_<属性id>__<op>`。
# 前端 rich filters 侧 shared-state adapter 已放行该前缀。
CUSTOM_PROPERTY_FILTER_PREFIX = "customproperty_"


class ComplexFilterBackend(filters.BaseFilterBackend):
    """
    Filter backend that supports complex JSON filtering.

    For full, up-to-date examples and usage, see the package README
    at `plane/utils/filters/README.md`.
    """

    filter_param = "filters"
    default_max_depth = 5

    def filter_queryset(self, request, queryset, view, filter_data=None):
        """Normalize filter input and apply JSON-based filtering.

        Accepts explicit `filter_data` (dict or JSON string) or reads the
        `filter` query parameter. Enforces JSON-only filtering.
        """
        try:
            if filter_data is not None:
                normalized = self._normalize_filter_data(filter_data, "filter_data")
                return self._apply_json_filter(queryset, normalized, view)

            filter_string = request.query_params.get(self.filter_param, None)
            if not filter_string:
                return queryset

            normalized = self._normalize_filter_data(filter_string, "filter")
            return self._apply_json_filter(queryset, normalized, view)
        except DRFValidationError:
            # Propagate validation errors unchanged
            raise
        except Exception as e:
            log_exception(e)
            raise

    def _normalize_filter_data(self, raw_filter, source_label):
        """Return a dict from raw filter input or raise a ValidationError.

        - raw_filter may be a dict or a JSON string
        - source_label is used in error messages (e.g., 'filter_data' or 'filter')
        """
        try:
            if isinstance(raw_filter, str):
                return json.loads(raw_filter)
            if isinstance(raw_filter, dict):
                return raw_filter
            raise DRFValidationError(
                {
                    "message": f"'{source_label}' must be a dict or a JSON string.",
                    "code": "invalid_filter_type",
                }
            )
        except json.JSONDecodeError:
            raise DRFValidationError(
                {
                    "message": (f"Invalid JSON for '{source_label}'. Expected a valid JSON object."),
                    "code": "invalid_json",
                }
            )

    def _apply_json_filter(self, queryset, filter_data, view):
        """Process a JSON filter structure using Q object composition."""
        if not filter_data:
            return queryset

        # Validate structure and depth before field allowlist checks
        max_depth = self._get_max_depth(view)
        self._validate_structure(filter_data, max_depth=max_depth, current_depth=1)

        # Validate against the view's FilterSet (only declared filters are allowed)
        self._validate_fields(filter_data, view)

        # Build combined Q object from the filter tree
        combined_q = self._evaluate_node(filter_data, view, queryset)
        if combined_q is None:
            return queryset

        # Apply the combined Q object to the queryset once
        return queryset.filter(combined_q)

    def _validate_fields(self, filter_data, view):
        """Validate that filtered fields are defined in the view's FilterSet."""
        filterset_class = getattr(view, "filterset_class", None)
        allowed_fields = set(filterset_class.base_filters.keys()) if filterset_class else None
        if not allowed_fields:
            # If no FilterSet is configured, reject filtering to avoid unintended exposure # noqa: E501
            raise DRFValidationError(
                {
                    "message": ("Filtering is not enabled for this endpoint (missing filterset_class)"),
                    "code": "filtering_not_enabled",
                }
            )

        # Extract field names from the filter data
        fields = self._extract_field_names(filter_data)

        # Check if all fields are allowed
        for field in fields:
            # Field keys must match FilterSet filter names (including any lookups)
            # Example: 'sequence_id__gte' should be declared in base_filters
            # Special-case __range: require the '<base>__range' filter itself
            if field not in allowed_fields:
                raise DRFValidationError(
                    {
                        "message": f"Filtering on field '{field}' is not allowed",
                        "code": "invalid_filter_field",
                    }
                )

    def _transform_field_name_for_validation(self, field_name):
        """Hook: Transform a field name before validation.

        Override this in subclasses to handle special field naming conventions.

        Args:
            field_name: The original field name from the filter data

        Returns:
            The transformed field name to validate against the FilterSet
        """
        return field_name

    def _extract_field_names(self, filter_data):
        """Extract all field names from a nested filter structure"""
        if isinstance(filter_data, dict):
            fields = []
            for key, value in filter_data.items():
                if key.lower() in ("or", "and", "not"):
                    # This is a logical operator, process its children
                    if key.lower() == "not":
                        # 'not' has a dict as its value, not a list
                        if isinstance(value, dict):
                            fields.extend(self._extract_field_names(value))
                    else:
                        # 'or' and 'and' have lists as their values
                        for item in value:
                            fields.extend(self._extract_field_names(item))
                else:
                    # This is a field name - apply transformation hook
                    transformed_field = self._transform_field_name_for_validation(key)
                    fields.append(transformed_field)
            return fields
        return []

    def _evaluate_node(self, node, view, queryset):
        """
        Recursively evaluate a JSON node into a combined Q object.

        Rules:
        - leaf dict → evaluated through FilterSet to produce a Q object
        - {"or": [...]} → Q() | Q() | ... (OR of children)
        - {"and": [...]} → Q() & Q() & ... (AND of children)
        - {"not": {...}} → ~Q() (negation of child)

        Returns a Q object that can be applied to a queryset.
        """
        if not isinstance(node, dict):
            return None

        # 'or' combination - OR of child Q objects
        if "or" in node:
            children = node["or"]
            if not isinstance(children, list) or not children:
                return None
            combined_q = Q()
            for child in children:
                child_q = self._evaluate_node(child, view, queryset)
                if child_q is None:
                    continue
                combined_q |= child_q
            return combined_q

        # 'and' combination - AND of child Q objects
        if "and" in node:
            children = node["and"]
            if not isinstance(children, list) or not children:
                return None
            combined_q = Q()
            for child in children:
                child_q = self._evaluate_node(child, view, queryset)
                if child_q is None:
                    continue
                combined_q &= child_q
            return combined_q

        # 'not' negation - negate the child Q object
        if "not" in node:
            child = node["not"]
            if not isinstance(child, dict):
                return None
            child_q = self._evaluate_node(child, view, queryset)
            if child_q is None:
                return None
            return ~child_q

        # Leaf dict: evaluate via FilterSet to get a Q object
        return self._build_leaf_q(node, view, queryset)

    def _preprocess_leaf_conditions(self, leaf_conditions, view, queryset):
        """Hook: Preprocess leaf conditions before building Q object.

        Override this in subclasses to transform filter keys/values.
        For example, custom property filters might need to be transformed
        from 'customproperty_<id>__<lookup>' to 'customproperty_value__<lookup>'.

        Args:
            leaf_conditions: Dict of field filters
            view: The view instance
            queryset: The queryset being filtered

        Returns:
            Dict of transformed field filters
        """
        return leaf_conditions

    def _build_leaf_q(self, leaf_conditions, view, queryset):
        """Build a Q object from leaf filter conditions using the view's FilterSet.

        We serialize the leaf dict into a QueryDict and let the view's
        filterset_class perform validation and build a combined Q object
        from all the field filters.

        Returns a Q object representing all the field conditions in the leaf.
        """
        if not leaf_conditions:
            return Q()

        # Get the filterset class from the view
        filterset_class = getattr(view, "filterset_class", None)
        if not filterset_class:
            raise DRFValidationError(
                {
                    "message": ("Filtering requires a filterset_class to be defined on the view"),
                    "code": "filterset_missing",
                }
            )

        # Apply preprocessing hook
        processed_conditions = self._preprocess_leaf_conditions(leaf_conditions, view, queryset)

        # Build a QueryDict from the leaf conditions
        qd = QueryDict(mutable=True)
        for key, value in processed_conditions.items():
            # Default serialization to string; QueryDict expects strings
            if isinstance(value, list):
                # Repeat key for list values (e.g., __in)
                qd.setlist(key, [str(v) for v in value])
            else:
                qd[key] = "" if value is None else str(value)

        qd = qd.copy()
        qd._mutable = False

        # Instantiate the filterset with the actual queryset
        # Custom filter methods may need access to the queryset for filtering
        fs = filterset_class(data=qd, queryset=queryset)

        if not fs.is_valid():
            ve = translate_validation(fs.errors)
            raise DRFValidationError(
                {
                    "message": "Invalid filter parameters",
                    "code": "invalid_filterset",
                    "errors": ve.detail,
                }
            )

        # Build and return the combined Q object
        if not hasattr(fs, "build_combined_q"):
            raise DRFValidationError(
                {
                    "message": ("FilterSet must have build_combined_q method for complex filtering"),
                    "code": "missing_build_combined_q",
                }
            )

        return fs.build_combined_q()

    def _get_max_depth(self, view):
        """Return the maximum allowed nesting depth for complex filters.

        Falls back to class default if the view does not specify it or has
        an invalid value.
        """
        value = getattr(view, "complex_filter_max_depth", self.default_max_depth)
        try:
            value_int = int(value)
            if value_int <= 0:
                return self.default_max_depth
            return value_int
        except Exception:
            return self.default_max_depth

    def _validate_structure(self, node, max_depth, current_depth):
        """Validate JSON structure and enforce nesting depth.

        Rules:
        - Each object may contain only one logical operator:
          or/and/not (case-insensitive)
        - Logical operator objects cannot contain field keys alongside the
          operator
        - or/and values must be non-empty lists of dicts
        - not value must be a dict
        - Leaf objects must only contain field keys and acceptable values
        - Depth must not exceed max_depth
        """
        if current_depth > max_depth:
            raise DRFValidationError(
                {
                    "message": (f"Filter nesting is too deep (max {max_depth}); found depth {current_depth}"),
                    "code": "max_depth_exceeded",
                }
            )

        if not isinstance(node, dict):
            raise DRFValidationError(
                {
                    "message": "Each filter node must be a JSON object",
                    "code": "invalid_filter_node",
                }
            )

        if not node:
            raise DRFValidationError(
                {
                    "message": "Filter objects must not be empty",
                    "code": "empty_filter_object",
                }
            )

        logical_keys = [k for k in node.keys() if isinstance(k, str) and k.lower() in ("or", "and", "not")]

        if len(logical_keys) > 1:
            raise DRFValidationError(
                {
                    "message": ("A filter object cannot contain multiple logical operators at the same level"),
                    "code": "multiple_logical_operators",
                }
            )

        if len(logical_keys) == 1:
            op_key = logical_keys[0]
            # must not mix operator with other keys
            if len(node) != 1:
                raise DRFValidationError(
                    {
                        "message": (f"Cannot mix logical operator '{op_key}' with field keys at the same level"),
                        "code": "mixed_operator_and_fields",
                    }
                )

            op = op_key.lower()
            value = node[op_key]

            if op in ("or", "and"):
                if not isinstance(value, list) or len(value) == 0:
                    raise DRFValidationError(
                        {
                            "message": f"'{op}' must be a non-empty list of filter objects",
                            "code": "invalid_operator_children",
                        }
                    )
                for child in value:
                    if not isinstance(child, dict):
                        raise DRFValidationError(
                            {
                                "message": f"All children of '{op}' must be JSON objects",
                                "code": "invalid_operator_child_type",
                            }
                        )
                    self._validate_structure(
                        child,
                        max_depth=max_depth,
                        current_depth=current_depth + 1,
                    )
                return

            if op == "not":
                if not isinstance(value, dict):
                    raise DRFValidationError(
                        {
                            "message": "'not' must be a single JSON object",
                            "code": "invalid_not_child",
                        }
                    )
                self._validate_structure(value, max_depth=max_depth, current_depth=current_depth + 1)
                return

        # Leaf node: validate fields and values
        self._validate_leaf(node)

    def _validate_leaf(self, leaf):
        """Validate a leaf dict containing field lookups and values."""
        if not isinstance(leaf, dict) or not leaf:
            raise DRFValidationError(
                {
                    "message": "Leaf filter must be a non-empty JSON object",
                    "code": "invalid_leaf",
                }
            )

        for key, value in leaf.items():
            if isinstance(key, str) and key.lower() in ("or", "and", "not"):
                raise DRFValidationError(
                    {
                        "message": "Logical operators cannot appear in a leaf filter object",
                        "code": "operator_in_leaf",
                    }
                )

            # Lists/Tuples must contain only scalar values
            if isinstance(value, (list, tuple)):
                if len(value) == 0:
                    raise DRFValidationError(
                        {
                            "message": f"List value for '{key}' must not be empty",
                            "code": "empty_list_value",
                        }
                    )
                for item in value:
                    if not self._is_scalar(item):
                        raise DRFValidationError(
                            {
                                "message": f"List value for '{key}' must contain only scalar items",
                                "code": "non_scalar_list_item",
                            }
                        )
                continue

            # Scalars and None are allowed
            if not self._is_scalar(value):
                raise DRFValidationError(
                    {
                        "message": (f"Value for '{key}' must be a scalar, null, or list/tuple of scalars"),
                        "code": "invalid_value_type",
                    }
                )

    def _is_scalar(self, value):
        return value is None or isinstance(value, (str, int, float, bool))


class IssueComplexFilterBackend(ComplexFilterBackend):
    """IssueViewSet / IssueListEndpoint 专用：在既有 ComplexFilterBackend 上放行
    自定义属性筛选键（`customproperty_<id>__<op>`），其余行为与父类完全一致。

    管线：_validate_fields 放行前缀键 → _preprocess_leaf_conditions 把属性键重写为
    IssueFilterSet 的合成 method 过滤器（exact→custom_property_values、in→
    custom_property_values__in），值编码 `<属性id>:<原值>`。
    """

    def _is_custom_property_key(self, key: str) -> bool:
        return isinstance(key, str) and key.startswith(CUSTOM_PROPERTY_FILTER_PREFIX) and "__" in key

    def _validate_fields(self, filter_data, view):
        """父类校验之外，放行 customproperty_ 前缀键（合成键仍要求在 filterset 声明）。"""
        filterset_class = getattr(view, "filterset_class", None)
        allowed_fields = set(filterset_class.base_filters.keys()) if filterset_class else None
        if not allowed_fields:
            raise DRFValidationError(
                {
                    "message": ("Filtering is not enabled for this endpoint (missing filterset_class)"),
                    "code": "filtering_not_enabled",
                }
            )

        for field in self._extract_field_names(filter_data):
            if self._is_custom_property_key(field):
                # 属性键的结构校验：前缀内是非空属性 id，操作符非空
                property_part, _, operator = field.rpartition("__")
                if not property_part or property_part == CUSTOM_PROPERTY_FILTER_PREFIX or not operator:
                    raise DRFValidationError(
                        {
                            "message": f"Invalid custom property filter key '{field}'",
                            "code": "invalid_filter_field",
                        }
                    )
                continue
            if field not in allowed_fields:
                raise DRFValidationError(
                    {
                        "message": f"Filtering on field '{field}' is not allowed",
                        "code": "invalid_filter_field",
                    }
                )

    def _preprocess_leaf_conditions(self, leaf_conditions, view, queryset):
        """把 `customproperty_<id>__<op>` 重写为合成键，值编码 `<属性id>:<原值>`。

        - `customproperty_<id>__exact`（或其它单值操作符）→ `custom_property_values` 列表追加
        - `customproperty_<id>__in` → `custom_property_values__in` 列表追加（每项一条编码值）
        多个属性条件在同一 leaf 内由 filterset 的 method 过滤器按「组间 AND」合并。
        """
        exact_values: list[str] = []
        in_values: list[str] = []
        passthrough: dict = {}

        for key, value in leaf_conditions.items():
            if not self._is_custom_property_key(key):
                passthrough[key] = value
                continue

            property_part, _, operator = key.rpartition("__")
            property_id = property_part[len(CUSTOM_PROPERTY_FILTER_PREFIX) :]
            if operator == "in":
                raw_values = value if isinstance(value, list) else [value]
                in_values.extend(f"{property_id}:{item}" for item in raw_values)
            else:
                exact_values.append(f"{property_id}:{value}")

        if exact_values:
            passthrough["custom_property_values"] = exact_values
        if in_values:
            passthrough["custom_property_values__in"] = in_values
        return passthrough
