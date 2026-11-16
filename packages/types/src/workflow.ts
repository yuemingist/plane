/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * Project workflow shell (Step02 segment 1, Business-tier parity — single
 * "Default Workflow" per project; rule configuration is an Enterprise concern
 * and is intentionally not modeled here).
 */
export interface IWorkflow {
  id: string;
  name: string;
  is_active: boolean;
  project: string;
  workspace: string;
  created_at: string;
  updated_at: string;
}

export type EWorkflowChangeAction = "enabled" | "disabled" | "re_enabled";

export interface IWorkflowChangeLog {
  id: string;
  action: EWorkflowChangeAction;
  note: string;
  actor: string | null;
  actor_detail: {
    id: string;
    first_name: string;
    display_name: string;
    avatar: string;
  } | null;
  created_at: string;
}
