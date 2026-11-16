/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import type { ISearchIssueResponse, TIssue } from "@plane/types";
// components
import { IssueModalContext } from "@/components/issues/issue-modal/context";
// hooks
import { useIssueProperty } from "@/hooks/store/use-issue-property";
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useUser } from "@/hooks/store/user/user-user";

export type TIssueModalProviderProps = {
  templateId?: string;
  dataForPreload?: Partial<TIssue>;
  allowedProjectIds?: string[];
  children: React.ReactNode;
};

export const IssueModalProvider = observer(function IssueModalProvider(props: TIssueModalProviderProps) {
  const { children, allowedProjectIds } = props;
  // states
  const [selectedParentIssue, setSelectedParentIssue] = useState<ISearchIssueResponse | null>(null);
  // store hooks
  const { projectsWithCreatePermissions } = useUser();
  const { getDefaultType } = useIssueType();
  const issuePropertyStore = useIssueProperty();
  // derived values
  const projectIdsWithCreatePermissions = Object.keys(projectsWithCreatePermissions ?? {});

  return (
    <IssueModalContext.Provider
      // oxlint-disable-next-line react/jsx-no-constructed-context-values
      value={{
        allowedProjectIds: allowedProjectIds ?? projectIdsWithCreatePermissions,
        workItemTemplateId: null,
        setWorkItemTemplateId: () => {},
        isApplyingTemplate: false,
        setIsApplyingTemplate: () => {},
        selectedParentIssue,
        setSelectedParentIssue,
        issuePropertyValues: {},
        setIssuePropertyValues: () => {},
        issuePropertyValueErrors: {},
        setIssuePropertyValueErrors: () => {},
        // default work item type of the project (B-4: the create modal preselects it)
        getIssueTypeIdOnProjectChange: (projectId) => getDefaultType(projectId)?.id ?? null,
        getActiveAdditionalPropertiesLength: () => 0,
        handlePropertyValuesValidation: () => true,
        // Step02 段 2：自定义属性值落库——create/update 成功后把弹窗暂存的
        // draftValues 批量 upsert（空值清空），随后清空暂存区
        handleCreateUpdatePropertyValues: async ({ issueId, projectId, workspaceSlug }) => {
          const draftValues = issuePropertyStore.draftValues;
          if (!draftValues || Object.keys(draftValues).length === 0 || !issueId || !projectId || !workspaceSlug) {
            return;
          }
          await issuePropertyStore.saveIssuePropertyValues(workspaceSlug, projectId, issueId, draftValues);
          issuePropertyStore.clearDraftValues();
        },
        handleProjectEntitiesFetch: () => Promise.resolve(),
        handleTemplateChange: () => Promise.resolve(),
        handleConvert: () => Promise.resolve(),
        handleCreateSubWorkItem: () => Promise.resolve(),
      }}
    >
      {children}
    </IssueModalContext.Provider>
  );
});
