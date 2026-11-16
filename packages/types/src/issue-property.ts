/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * 自定义属性域类型（Step02 段 2 追赶 FE）。
 * 形状对齐 app API issue-property viewset（段 2 技术方案 §2）。
 */

export type TIssuePropertyType = "text" | "decimal" | "option" | "boolean" | "date" | "member" | "rich_text" | "url";

export type TIssuePropertyOption = {
  id: string;
  name: string;
  is_default: boolean;
};

export type TIssuePropertySettings = {
  /** text: single-line | multi-line | readonly */
  display_format?: string;
  /** decimal: standard | percent | currency */
  format?: string;
  decimal_places?: number;
  thousands_separator?: boolean;
  /** option / member: 多选开关 */
  is_multi?: boolean;
  /** option: 选项集（值引用 option.id） */
  options?: TIssuePropertyOption[];
};

export type TIssuePropertyBindingSummary = {
  issue_type_id: string;
  issue_type_name: string;
};

export interface IIssueProperty {
  id: string;
  name: string;
  description: string;
  property_type: TIssuePropertyType;
  settings: TIssuePropertySettings;
  is_required: boolean;
  is_active: boolean;
  default_value: unknown;
  sort_order: number;
  /** 「使用中的工作项类型」列（57 号 §1.2 Tab2） */
  issue_type_bindings_count: number;
  issue_type_bindings: TIssuePropertyBindingSummary[];
  project: string;
  workspace: string;
  created_at: string;
  updated_at: string;
}

export interface IIssueTypeIssueProperty {
  id: string;
  issue_type: string;
  issue_property: string;
  issue_property_detail: IIssueProperty | null;
  created_at: string;
}

/** 值列表/写后回读行：定义 + 已存值（无值时 value=null） */
export interface IIssuePropertyValueRow {
  property: IIssueProperty;
  value: unknown;
}

/** 批量写值载荷：{property_id: value}，空值清空 */
export type TIssuePropertyValuesPayload = Record<string, unknown>;
