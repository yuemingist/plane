/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set } from "lodash-es";
import { action, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// plane imports
import type { IIssueType } from "@plane/types";
// plane web
import { IssueTypeService } from "@/services/issue/issue-type.service";
import type { RootStore } from "@/store/root.store";

export interface IIssueTypeStore {
  // observables
  fetchedMap: Record<string, boolean>;
  typeMap: Record<string, IIssueType>;
  projectTypeIdsMap: Record<string, string[]>;
  // computed actions
  getTypesByProjectId: (projectId: string | null | undefined) => IIssueType[] | undefined;
  getTypeById: (typeId: string | null | undefined) => IIssueType | undefined;
  getDefaultType: (projectId: string | null | undefined) => IIssueType | undefined;
  getActiveTypes: (projectId: string | null | undefined) => IIssueType[] | undefined;
  getProjectIssueTypeIds: (projectId: string | null | undefined) => string[] | undefined;
  hasEpicType: (projectId: string | null | undefined) => boolean;
  areTypesFetched: (projectId: string | null | undefined) => boolean;
  // fetch actions
  fetchProjectWorkItemTypes: (workspaceSlug: string, projectId: string) => Promise<IIssueType[]>;
  // crud actions
  createWorkItemType: (workspaceSlug: string, projectId: string, data: Partial<IIssueType>) => Promise<IIssueType>;
  updateWorkItemType: (
    workspaceSlug: string,
    projectId: string,
    issueTypeId: string,
    data: Partial<IIssueType>
  ) => Promise<IIssueType>;
  deleteWorkItemType: (workspaceSlug: string, projectId: string, issueTypeId: string) => Promise<void>;
  markWorkItemTypeAsDefault: (workspaceSlug: string, projectId: string, issueTypeId: string) => Promise<void>;
  enableWorkItemTypes: (workspaceSlug: string, projectId: string) => Promise<void>;
}

export class IssueTypeStore implements IIssueTypeStore {
  fetchedMap: Record<string, boolean> = {};
  typeMap: Record<string, IIssueType> = {};
  projectTypeIdsMap: Record<string, string[]> = {};
  rootStore: RootStore;
  issueTypeService: IssueTypeService;

  constructor(_rootStore: RootStore) {
    makeObservable(this, {
      // observables
      fetchedMap: observable,
      typeMap: observable,
      projectTypeIdsMap: observable,
      // fetch actions
      fetchProjectWorkItemTypes: action,
      // crud actions
      createWorkItemType: action,
      updateWorkItemType: action,
      deleteWorkItemType: action,
      markWorkItemTypeAsDefault: action,
      enableWorkItemTypes: action,
    });
    this.issueTypeService = new IssueTypeService();
    this.rootStore = _rootStore;
  }

  /**
   * Returns the work item types of a project
   */
  getTypesByProjectId = computedFn((projectId: string | null | undefined) => {
    if (!projectId || !this.fetchedMap[projectId]) return;
    const typeIds = this.projectTypeIdsMap[projectId] ?? [];
    return typeIds.map((typeId) => this.typeMap[typeId]).filter((type): type is IIssueType => !!type);
  });

  /**
   * Returns a work item type by its id
   */
  getTypeById = computedFn((typeId: string | null | undefined) => {
    if (!this.typeMap || !typeId) return;
    return this.typeMap[typeId] ?? undefined;
  });

  /**
   * Returns the project's default work item type
   */
  getDefaultType = computedFn((projectId: string | null | undefined) => {
    const projectTypes = this.getTypesByProjectId(projectId);
    return projectTypes?.find((type) => type.is_default);
  });

  /**
   * Returns the project's active work item types
   */
  getActiveTypes = computedFn((projectId: string | null | undefined) => {
    const projectTypes = this.getTypesByProjectId(projectId);
    return projectTypes?.filter((type) => type.is_active);
  });

  /**
   * Returns the issue type ids of a project
   */
  getProjectIssueTypeIds = computedFn((projectId: string | null | undefined) => {
    if (!projectId || !this.fetchedMap[projectId]) return;
    return this.projectTypeIdsMap[projectId] ?? [];
  });

  /**
   * Whether the project has an active type with `is_epic` set (Epic layout entry point gate)
   */
  hasEpicType = computedFn((projectId: string | null | undefined) => {
    const projectTypes = this.getTypesByProjectId(projectId);
    return !!projectTypes?.some((type) => type.is_epic && type.is_active);
  });

  /**
   * Whether the project's work item types have been fetched
   */
  areTypesFetched = computedFn((projectId: string | null | undefined) => {
    if (!projectId) return false;
    return !!this.fetchedMap[projectId];
  });

  /**
   * Fetches the work item types of a project
   */
  fetchProjectWorkItemTypes = async (workspaceSlug: string, projectId: string) => {
    const typesResponse = await this.issueTypeService.getWorkItemTypes(workspaceSlug, projectId);
    runInAction(() => {
      typesResponse.forEach((type) => {
        set(this.typeMap, [type.id], type);
      });
      set(
        this.projectTypeIdsMap,
        [projectId],
        typesResponse.map((type) => type.id)
      );
      set(this.fetchedMap, projectId, true);
    });
    return typesResponse;
  };

  /**
   * Creates a new work item type for the project (created as inactive by the backend)
   */
  createWorkItemType = async (workspaceSlug: string, projectId: string, data: Partial<IIssueType>) =>
    await this.issueTypeService.createWorkItemType(workspaceSlug, projectId, data).then((response) => {
      runInAction(() => {
        set(this.typeMap, [response?.id], response);
        set(this.projectTypeIdsMap, [projectId], [...(this.projectTypeIdsMap[projectId] ?? []), response.id]);
      });
      return response;
    });

  /**
   * Updates a work item type; on failure the previous snapshot is restored
   */
  updateWorkItemType = async (
    workspaceSlug: string,
    projectId: string,
    issueTypeId: string,
    data: Partial<IIssueType>
  ) => {
    const originalType = this.typeMap[issueTypeId];
    try {
      runInAction(() => {
        set(this.typeMap, [issueTypeId], { ...this.typeMap?.[issueTypeId], ...data });
      });
      const response = await this.issueTypeService.updateWorkItemType(workspaceSlug, projectId, issueTypeId, data);
      runInAction(() => {
        set(this.typeMap, [issueTypeId], response);
      });
      return response;
    } catch (error) {
      runInAction(() => {
        this.typeMap = {
          ...this.typeMap,
          [issueTypeId]: originalType,
        };
      });
      throw error;
    }
  };

  /**
   * Deletes a work item type from the store after the API call succeeds
   */
  deleteWorkItemType = async (workspaceSlug: string, projectId: string, issueTypeId: string) => {
    await this.issueTypeService.deleteWorkItemType(workspaceSlug, projectId, issueTypeId);
    runInAction(() => {
      delete this.typeMap[issueTypeId];
      set(
        this.projectTypeIdsMap,
        [projectId],
        (this.projectTypeIdsMap[projectId] ?? []).filter((id) => id !== issueTypeId)
      );
    });
  };

  /**
   * Marks a work item type as the project default (single default: the previous default loses its badge)
   */
  markWorkItemTypeAsDefault = async (workspaceSlug: string, projectId: string, issueTypeId: string) => {
    const originalTypes = this.typeMap;
    const currentDefaultType = Object.values(this.typeMap).find((type) => type.is_default);
    try {
      runInAction(() => {
        if (currentDefaultType) set(this.typeMap, [currentDefaultType.id, "is_default"], false);
        set(this.typeMap, [issueTypeId, "is_default"], true);
      });
      await this.issueTypeService.markDefaultWorkItemType(workspaceSlug, projectId, issueTypeId);
    } catch (error) {
      runInAction(() => {
        this.typeMap = originalTypes;
      });
      throw error;
    }
  };

  /**
   * Enables work item types for the project (one-way switch) and refreshes the project flag and type list
   */
  enableWorkItemTypes = async (workspaceSlug: string, projectId: string) => {
    await this.issueTypeService.enableWorkItemTypes(workspaceSlug, projectId);
    // refresh project flag (`is_issue_type_enabled`) and seed the type list
    await this.rootStore.projectRoot.project.fetchProjectDetails(workspaceSlug, projectId);
    await this.fetchProjectWorkItemTypes(workspaceSlug, projectId);
  };
}
