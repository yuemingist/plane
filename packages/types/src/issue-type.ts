/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TLogoProps } from "./common";

export interface IIssueType {
  id: string;
  name: string;
  description: string;
  /** accepts both the canonical TLogoProps shape and the backend seed's `{ in_app_icon }` shape */
  logo_props: TLogoProps | undefined;
  is_epic: boolean;
  is_active: boolean;
  /** project-scoped level (bridge `ProjectIssueType.level`, Epic=1) exposed by the settings type API; the workspace-level column is not consumed (BUG-04) */
  level: number;
  /** project-scoped computed flag: whether this type is the project's default (bridge) */
  is_default: boolean;
  /** project-scoped computed count of work items using this type */
  issues_count: number;
  /**
   * Available state ids for this type within the project (bridge M2M, Step02 segment 5).
   * An empty array means "not configured" — the type inherits the full project state pool.
   */
  state_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface IProjectIssueType {
  id: string;
  project: string;
  issue_type: string;
  level: number;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export type TIssueTypeStatus = "active" | "disabled";

export type TIssueTypeOperationsCallbacks = {
  createType: (data: Partial<IIssueType>) => Promise<IIssueType>;
  updateType: (typeId: string, data: Partial<IIssueType>) => Promise<IIssueType>;
  deleteType: (typeId: string) => Promise<void>;
  markTypeAsDefault: (typeId: string) => Promise<void>;
  enableWorkItemTypes: () => Promise<void>;
};
