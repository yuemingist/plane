/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { IIssueType } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

/**
 * Service for project-scoped work item types management.
 * Endpoints mirror the app API issue-type viewset (see docs/01.追赶正式版/03.追赶Step01 §2.1).
 */
export class IssueTypeService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private resourceUrl(workspaceSlug: string, projectId: string) {
    return `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/`;
  }

  async getWorkItemTypes(workspaceSlug: string, projectId: string): Promise<IIssueType[]> {
    return this.get(this.resourceUrl(workspaceSlug, projectId))
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createWorkItemType(workspaceSlug: string, projectId: string, data: Partial<IIssueType>): Promise<IIssueType> {
    return this.post(this.resourceUrl(workspaceSlug, projectId), data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateWorkItemType(
    workspaceSlug: string,
    projectId: string,
    issueTypeId: string,
    data: Partial<IIssueType>
  ): Promise<IIssueType> {
    return this.patch(`${this.resourceUrl(workspaceSlug, projectId)}${issueTypeId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteWorkItemType(workspaceSlug: string, projectId: string, issueTypeId: string): Promise<void> {
    return this.delete(`${this.resourceUrl(workspaceSlug, projectId)}${issueTypeId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Available state ids for a work item type (Step02 segment 5). Empty list = inherits
   * the full project state pool (`inherits_all` flag mirrors that).
   */
  async getWorkItemTypeStates(
    workspaceSlug: string,
    projectId: string,
    issueTypeId: string
  ): Promise<{ state_ids: string[]; inherits_all: boolean }> {
    return this.get(`${this.resourceUrl(workspaceSlug, projectId)}${issueTypeId}/states/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Full replacement of the available state set (PUT). Empty array clears the
   * configuration, restoring "inherit the full project state pool".
   */
  async updateWorkItemTypeStates(
    workspaceSlug: string,
    projectId: string,
    issueTypeId: string,
    stateIds: string[]
  ): Promise<{ state_ids: string[]; inherits_all: boolean }> {
    return this.put(`${this.resourceUrl(workspaceSlug, projectId)}${issueTypeId}/states/`, {
      state_ids: stateIds,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async markDefaultWorkItemType(workspaceSlug: string, projectId: string, issueTypeId: string): Promise<void> {
    return this.post(`${this.resourceUrl(workspaceSlug, projectId)}${issueTypeId}/mark-default/`, {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * One-way project-level enable: sets `is_issue_type_enabled` and seeds the
   * Epic (level 1) + Task (level 0, default) types. Returns 400 when already enabled.
   */
  async enableWorkItemTypes(workspaceSlug: string, projectId: string): Promise<void> {
    return this.post(`${this.resourceUrl(workspaceSlug, projectId)}enable/`, {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
