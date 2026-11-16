/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TIssuePropertyType } from "@plane/types";

/** i18n 翻译函数的最小形状（避免直接依赖 i18next 类型） */
type TranslateFn = (key: string, values?: Record<string, unknown>) => string;

/** 8 类属性 → i18n 键（property_type.*.label，57 号 §4.2 类型面） */
export const PROPERTY_TYPE_I18N_KEYS: Record<TIssuePropertyType, string> = {
  text: "work_item_types.settings.properties.property_type.text.label",
  decimal: "work_item_types.settings.properties.property_type.number.label",
  option: "work_item_types.settings.properties.property_type.dropdown.label",
  boolean: "work_item_types.settings.properties.property_type.boolean.label",
  date: "work_item_types.settings.properties.property_type.date.label",
  member: "work_item_types.settings.properties.property_type.member_picker.label",
  rich_text: "work_item_types.settings.properties.property_type.rich_text.label",
  url: "work_item_types.settings.properties.property_type.url.label",
};

export const PROPERTY_TYPE_KEYS = Object.keys(PROPERTY_TYPE_I18N_KEYS) as TIssuePropertyType[];

export const propertyTypeLabel = (propertyType: TIssuePropertyType, t: TranslateFn) =>
  t(PROPERTY_TYPE_I18N_KEYS[propertyType] ?? PROPERTY_TYPE_I18N_KEYS.text);
