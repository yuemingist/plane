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

export type EWorkflowChangeAction = "enabled" | "disabled" | "re_enabled" | "transition_rules_updated";

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

/**
 * Transition rules (Step02 segment 3 — CE-designed minimal form, see
 * docs/01.追赶正式版/04.追赶Step02/产品方案/03.段3-流转规则产品方案.md):
 * whitelist of allowed target states per source state; a source state with
 * no entry is unrestricted (default no-rules = all allowed).
 */
export interface IWorkflowTransition {
  id: string;
  workflow: string;
  from_state: string;
  to_state: string;
  created_at: string;
  updated_at: string;
}

/** Grouped write payload: one entry per source state. */
export interface IWorkflowTransitionGroup {
  from_state: string;
  to_states: string[];
}

/** Error body returned by the issue PATCH transition guard (400). */
export interface IWorkflowTransitionError {
  error?: string;
  code?: string;
  from_state_name?: string;
  to_state_name?: string;
  /** Step02 segment 5: type available-state guard error body. */
  type_name?: string;
  state_name?: string;
}
