/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type {
  IIssueProperty,
  IIssuePropertyValueRow,
  IIssueTypeIssueProperty,
  TIssuePropertyValuesPayload,
} from "@plane/types";
// services
import { APIService } from "@/services/api.service";

/**
 * Service for project custom properties (pool, type bindings, issue values).
 * Endpoints mirror the app API issue-property viewsets (Step02 段 2 技术方案 §2).
 */
export class IssuePropertyService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private poolUrl(workspaceSlug: string, projectId: string) {
    return `/api/workspaces/${workspaceSlug}/projects/${projectId}/issue-properties/`;
  }

  // ---------- 属性池 ----------

  async getProperties(workspaceSlug: string, projectId: string): Promise<IIssueProperty[]> {
    return this.get(this.poolUrl(workspaceSlug, projectId))
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createProperty(
    workspaceSlug: string,
    projectId: string,
    data: Partial<IIssueProperty>
  ): Promise<IIssueProperty> {
    return this.post(this.poolUrl(workspaceSlug, projectId), data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateProperty(
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: Partial<IIssueProperty>
  ): Promise<IIssueProperty> {
    return this.patch(`${this.poolUrl(workspaceSlug, projectId)}${propertyId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteProperty(workspaceSlug: string, projectId: string, propertyId: string): Promise<void> {
    return this.delete(`${this.poolUrl(workspaceSlug, projectId)}${propertyId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  // ---------- 类型绑定 ----------

  async getTypeProperties(
    workspaceSlug: string,
    projectId: string,
    typeId: string
  ): Promise<IIssueTypeIssueProperty[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/${typeId}/properties/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async bindProperties(
    workspaceSlug: string,
    projectId: string,
    typeId: string,
    propertyIds: string[]
  ): Promise<IIssueTypeIssueProperty[]> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/${typeId}/properties/`, {
      property_ids: propertyIds,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async unbindProperty(workspaceSlug: string, projectId: string, typeId: string, propertyId: string): Promise<void> {
    return this.delete(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-item-types/${typeId}/properties/${propertyId}/`
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  // ---------- 工作项属性值 ----------

  async getIssuePropertyValues(
    workspaceSlug: string,
    projectId: string,
    issueId: string
  ): Promise<IIssuePropertyValueRow[]> {
    return this.get(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/issue-property-values/`
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /** 批量 upsert（空值清空）；返回写后回读行（原子刷新面板） */
  async saveIssuePropertyValues(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    values: TIssuePropertyValuesPayload
  ): Promise<IIssuePropertyValueRow[]> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/work-items/${issueId}/issue-property-values/`,
      { values }
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
