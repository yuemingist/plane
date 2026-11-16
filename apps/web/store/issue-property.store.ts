/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set } from "lodash-es";
import { action, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// plane imports
import type {
  IIssueProperty,
  IIssuePropertyValueRow,
  IIssueTypeIssueProperty,
  TIssuePropertyValuesPayload,
} from "@plane/types";
// plane web
import { IssuePropertyService } from "@/services/issue/issue-property.service";
import type { RootStore } from "@/store/root.store";

export interface IIssuePropertyStore {
  // observables
  fetchedMap: Record<string, boolean>;
  propertyMap: Record<string, IIssueProperty>;
  projectPropertyIdsMap: Record<string, string[]>;
  typeBindingsMap: Record<string, IIssueTypeIssueProperty[]>;
  typeBindingsFetchedMap: Record<string, boolean>;
  issueValuesMap: Record<string, IIssuePropertyValueRow[]>;
  /** 新建/更新弹窗暂存的待写值（provider 在 create/update 成功后落库并清空） */
  draftValues: TIssuePropertyValuesPayload | null;
  // computed actions
  getPropertiesByProjectId: (projectId: string | null | undefined) => IIssueProperty[] | undefined;
  getPropertyById: (propertyId: string | null | undefined) => IIssueProperty | undefined;
  arePropertiesFetched: (projectId: string | null | undefined) => boolean;
  getBindingsByTypeId: (typeId: string | null | undefined) => IIssueTypeIssueProperty[] | undefined;
  areTypeBindingsFetched: (typeId: string | null | undefined) => boolean;
  getActiveBoundPropertiesByTypeId: (typeId: string | null | undefined) => IIssueProperty[];
  getValuesByIssueId: (issueId: string | null | undefined) => IIssuePropertyValueRow[] | undefined;
  // fetch actions
  fetchProjectProperties: (workspaceSlug: string, projectId: string) => Promise<IIssueProperty[]>;
  fetchTypeProperties: (workspaceSlug: string, projectId: string, typeId: string) => Promise<IIssueTypeIssueProperty[]>;
  fetchIssuePropertyValues: (
    workspaceSlug: string,
    projectId: string,
    issueId: string
  ) => Promise<IIssuePropertyValueRow[]>;
  // crud actions
  createProperty: (workspaceSlug: string, projectId: string, data: Partial<IIssueProperty>) => Promise<IIssueProperty>;
  updateProperty: (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: Partial<IIssueProperty>
  ) => Promise<IIssueProperty>;
  deleteProperty: (workspaceSlug: string, projectId: string, propertyId: string) => Promise<void>;
  bindProperties: (
    workspaceSlug: string,
    projectId: string,
    typeId: string,
    propertyIds: string[]
  ) => Promise<IIssueTypeIssueProperty[]>;
  unbindProperty: (workspaceSlug: string, projectId: string, typeId: string, propertyId: string) => Promise<void>;
  saveIssuePropertyValues: (
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    values: TIssuePropertyValuesPayload
  ) => Promise<IIssuePropertyValueRow[]>;
  // draft values (create/update modal)
  setDraftValue: (propertyId: string, value: unknown) => void;
  clearDraftValues: () => void;
}

export class IssuePropertyStore implements IIssuePropertyStore {
  fetchedMap: Record<string, boolean> = {};
  propertyMap: Record<string, IIssueProperty> = {};
  projectPropertyIdsMap: Record<string, string[]> = {};
  typeBindingsMap: Record<string, IIssueTypeIssueProperty[]> = {};
  typeBindingsFetchedMap: Record<string, boolean> = {};
  issueValuesMap: Record<string, IIssuePropertyValueRow[]> = {};
  draftValues: TIssuePropertyValuesPayload | null = null;
  rootStore: RootStore;
  issuePropertyService: IssuePropertyService;

  constructor(_rootStore: RootStore) {
    makeObservable(this, {
      // observables
      fetchedMap: observable,
      propertyMap: observable,
      projectPropertyIdsMap: observable,
      typeBindingsMap: observable,
      typeBindingsFetchedMap: observable,
      issueValuesMap: observable,
      draftValues: observable,
      // fetch actions
      fetchProjectProperties: action,
      fetchTypeProperties: action,
      fetchIssuePropertyValues: action,
      // crud actions
      createProperty: action,
      updateProperty: action,
      deleteProperty: action,
      bindProperties: action,
      unbindProperty: action,
      saveIssuePropertyValues: action,
      // draft values
      setDraftValue: action,
      clearDraftValues: action,
    });
    this.issuePropertyService = new IssuePropertyService();
    this.rootStore = _rootStore;
  }

  // ---------- computed ----------

  getPropertiesByProjectId = computedFn((projectId: string | null | undefined) => {
    if (!projectId || !this.fetchedMap[projectId]) return;
    const propertyIds = this.projectPropertyIdsMap[projectId] ?? [];
    return propertyIds
      .map((propertyId) => this.propertyMap[propertyId])
      .filter((property): property is IIssueProperty => !!property);
  });

  getPropertyById = computedFn((propertyId: string | null | undefined) => {
    if (!propertyId) return;
    return this.propertyMap[propertyId] ?? undefined;
  });

  arePropertiesFetched = computedFn((projectId: string | null | undefined) => {
    if (!projectId) return false;
    return !!this.fetchedMap[projectId];
  });

  getBindingsByTypeId = computedFn((typeId: string | null | undefined) => {
    if (!typeId || !this.typeBindingsFetchedMap[typeId]) return;
    return this.typeBindingsMap[typeId] ?? [];
  });

  areTypeBindingsFetched = computedFn((typeId: string | null | undefined) => {
    if (!typeId) return false;
    return !!this.typeBindingsFetchedMap[typeId];
  });

  /** 绑定到类型且已启用的属性（双门控：绑定 + 池级 is_active） */
  getActiveBoundPropertiesByTypeId = computedFn((typeId: string | null | undefined): IIssueProperty[] => {
    const bindings = this.getBindingsByTypeId(typeId);
    if (!bindings) return [];
    return bindings
      .map((binding) => binding.issue_property_detail)
      .filter((property): property is IIssueProperty => !!property?.is_active);
  });

  getValuesByIssueId = computedFn((issueId: string | null | undefined) => {
    if (!issueId) return;
    return this.issueValuesMap[issueId];
  });

  // ---------- fetch ----------

  fetchProjectProperties = async (workspaceSlug: string, projectId: string) => {
    const propertiesResponse = await this.issuePropertyService.getProperties(workspaceSlug, projectId);
    runInAction(() => {
      propertiesResponse.forEach((property) => {
        set(this.propertyMap, [property.id], property);
      });
      set(
        this.projectPropertyIdsMap,
        [projectId],
        propertiesResponse.map((property) => property.id)
      );
      set(this.fetchedMap, projectId, true);
    });
    return propertiesResponse;
  };

  fetchTypeProperties = async (workspaceSlug: string, projectId: string, typeId: string) => {
    const bindingsResponse = await this.issuePropertyService.getTypeProperties(workspaceSlug, projectId, typeId);
    runInAction(() => {
      bindingsResponse.forEach((binding) => {
        if (binding.issue_property_detail) {
          set(this.propertyMap, [binding.issue_property_detail.id], binding.issue_property_detail);
        }
      });
      set(this.typeBindingsMap, [typeId], bindingsResponse);
      set(this.typeBindingsFetchedMap, [typeId], true);
    });
    return bindingsResponse;
  };

  fetchIssuePropertyValues = async (workspaceSlug: string, projectId: string, issueId: string) => {
    const valuesResponse = await this.issuePropertyService.getIssuePropertyValues(workspaceSlug, projectId, issueId);
    runInAction(() => {
      valuesResponse.forEach((row) => {
        set(this.propertyMap, [row.property.id], row.property);
      });
      set(this.issueValuesMap, [issueId], valuesResponse);
    });
    return valuesResponse;
  };

  // ---------- 池 CRUD ----------

  createProperty = async (workspaceSlug: string, projectId: string, data: Partial<IIssueProperty>) =>
    await this.issuePropertyService.createProperty(workspaceSlug, projectId, data).then((response) => {
      runInAction(() => {
        set(this.propertyMap, [response.id], response);
        set(this.projectPropertyIdsMap, [projectId], [...(this.projectPropertyIdsMap[projectId] ?? []), response.id]);
      });
      return response;
    });

  updateProperty = async (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: Partial<IIssueProperty>
  ) => {
    const response = await this.issuePropertyService.updateProperty(workspaceSlug, projectId, propertyId, data);
    runInAction(() => {
      set(this.propertyMap, [propertyId], response);
      // 属性启用/停用影响所有绑定类型的可见性：绑定清单里的 detail 同步刷新
      Object.keys(this.typeBindingsMap).forEach((typeId) => {
        const bindings = this.typeBindingsMap[typeId] ?? [];
        bindings.forEach((binding) => {
          if (binding.issue_property === propertyId) {
            binding.issue_property_detail = response;
          }
        });
        set(this.typeBindingsMap, [typeId], [...bindings]);
      });
    });
    return response;
  };

  deleteProperty = async (workspaceSlug: string, projectId: string, propertyId: string) => {
    await this.issuePropertyService.deleteProperty(workspaceSlug, projectId, propertyId);
    runInAction(() => {
      delete this.propertyMap[propertyId];
      set(
        this.projectPropertyIdsMap,
        [projectId],
        (this.projectPropertyIdsMap[projectId] ?? []).filter((id) => id !== propertyId)
      );
      Object.keys(this.typeBindingsMap).forEach((typeId) => {
        set(
          this.typeBindingsMap,
          [typeId],
          (this.typeBindingsMap[typeId] ?? []).filter((binding) => binding.issue_property !== propertyId)
        );
      });
    });
  };

  // ---------- 绑定 ----------

  bindProperties = async (workspaceSlug: string, projectId: string, typeId: string, propertyIds: string[]) => {
    const bindingsResponse = await this.issuePropertyService.bindProperties(
      workspaceSlug,
      projectId,
      typeId,
      propertyIds
    );
    runInAction(() => {
      bindingsResponse.forEach((binding) => {
        if (binding.issue_property_detail) {
          set(this.propertyMap, [binding.issue_property_detail.id], binding.issue_property_detail);
        }
      });
      set(this.typeBindingsMap, [typeId], bindingsResponse);
      set(this.typeBindingsFetchedMap, [typeId], true);
      // 绑定影响属性池「使用中」计数：刷新属性池
    });
    await this.fetchProjectProperties(workspaceSlug, projectId);
    return bindingsResponse;
  };

  unbindProperty = async (workspaceSlug: string, projectId: string, typeId: string, propertyId: string) => {
    await this.issuePropertyService.unbindProperty(workspaceSlug, projectId, typeId, propertyId);
    runInAction(() => {
      set(
        this.typeBindingsMap,
        [typeId],
        (this.typeBindingsMap[typeId] ?? []).filter((binding) => binding.issue_property !== propertyId)
      );
    });
    await this.fetchProjectProperties(workspaceSlug, projectId);
  };

  // ---------- 属性值 ----------

  saveIssuePropertyValues = async (
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    values: TIssuePropertyValuesPayload
  ) => {
    const valuesResponse = await this.issuePropertyService.saveIssuePropertyValues(
      workspaceSlug,
      projectId,
      issueId,
      values
    );
    runInAction(() => {
      valuesResponse.forEach((row) => {
        set(this.propertyMap, [row.property.id], row.property);
      });
      set(this.issueValuesMap, [issueId], valuesResponse);
    });
    return valuesResponse;
  };

  // ---------- 弹窗暂存值 ----------

  setDraftValue = (propertyId: string, value: unknown) => {
    this.draftValues = { ...this.draftValues, [propertyId]: value };
  };

  clearDraftValues = () => {
    this.draftValues = null;
  };
}
