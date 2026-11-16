/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { IWorkflow, IWorkflowChangeLog } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

/**
 * Service for the project workflow shell (Step02 segment 1).
 * Endpoints mirror the app API workflow viewset (see
 * docs/01.追赶正式版/04.追赶Step02/技术方案/01.段1-工作流壳技术方案.md §1.3):
 * enable (project toggle), disable/re-enable (row menu), paginated change history.
 */
export class WorkflowService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private resourceUrl(workspaceSlug: string, projectId: string) {
    return `/api/workspaces/${workspaceSlug}/projects/${projectId}/workflows/`;
  }

  async getWorkflows(workspaceSlug: string, projectId: string): Promise<IWorkflow[]> {
    return this.get(this.resourceUrl(workspaceSlug, projectId))
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Project-level enable toggle: creates the Default Workflow when absent,
   * revives the disabled row when present. Returns 400 when already active.
   */
  async enableWorkflow(workspaceSlug: string, projectId: string): Promise<IWorkflow> {
    return this.post(this.resourceUrl(workspaceSlug, projectId), {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async disableWorkflow(workspaceSlug: string, projectId: string, workflowId: string): Promise<IWorkflow> {
    return this.post(`${this.resourceUrl(workspaceSlug, projectId)}${workflowId}/disable/`, {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async reEnableWorkflow(workspaceSlug: string, projectId: string, workflowId: string): Promise<IWorkflow> {
    return this.post(`${this.resourceUrl(workspaceSlug, projectId)}${workflowId}/enable/`, {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getWorkflowChangeHistory(
    workspaceSlug: string,
    projectId: string,
    workflowId: string,
    cursor?: string
  ): Promise<IWorkflowChangeLog[]> {
    const url = `${this.resourceUrl(workspaceSlug, projectId)}${workflowId}/change-history/${
      cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""
    }`;
    return this.get(url)
      .then((response) => response?.data?.results ?? response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
