/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR from "swr";
import { observer } from "mobx-react";
import { Tab, Tabs, TabsList, TabsPanel } from "@makeplane/propel/components/tabs";
import { useTranslation } from "@plane/i18n";
// hooks
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useProject } from "@/hooks/store/use-project";
// local imports
import { HierarchyTab } from "./hierarchy-tab";
import { PropertiesTab } from "./properties-tab";
import { TypesTab } from "./types-tab";
import { WorkItemTypesGate } from "./enable-gate-card";

type TProjectWorkItemTypesRootProps = {
  workspaceSlug: string;
  projectId: string;
};

/**
 * Settings page root for project work item types:
 * renders the enable gate card when `is_issue_type_enabled` is false, otherwise the
 * three-tab layout (Types / Properties / Hierarchy). Enabling is one-way — the gate
 * branch never renders again once the project flag is true.
 */
export const ProjectWorkItemTypesRoot = observer(function ProjectWorkItemTypesRoot(
  props: TProjectWorkItemTypesRootProps
) {
  const { workspaceSlug, projectId } = props;
  // states
  const [activeTab, setActiveTab] = useState<"types" | "properties" | "hierarchy">("types");
  // store hooks
  const { t } = useTranslation();
  const { fetchProjectWorkItemTypes, areTypesFetched } = useIssueType();
  const { currentProjectDetails } = useProject();
  // derived values
  const isIssueTypeEnabled = currentProjectDetails?.is_issue_type_enabled === true;

  // load the project's work item types once enabled
  useSWR(
    workspaceSlug && projectId && isIssueTypeEnabled ? `PROJECT_WORK_ITEM_TYPES_${workspaceSlug}_${projectId}` : null,
    async () => {
      if (workspaceSlug && projectId && !areTypesFetched(projectId)) {
        await fetchProjectWorkItemTypes(workspaceSlug, projectId);
      }
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  if (!isIssueTypeEnabled) {
    return <WorkItemTypesGate workspaceSlug={workspaceSlug} projectId={projectId} />;
  }

  return (
    <Tabs variant="contained" value={activeTab} onValueChange={(value) => setActiveTab(value as typeof activeTab)}>
      <TabsList aria-label={t("work_item_types.label")}>
        <Tab value="types" label={t("work_item_types.label")} />
        <Tab value="properties" label={t("work_item_types.settings.properties.title")} />
        <Tab value="hierarchy" label={t("work_item_type_hierarchy.settings.tab_label")} />
      </TabsList>
      <TabsPanel value="types">
        <div className="mt-6">
          <TypesTab workspaceSlug={workspaceSlug} projectId={projectId} />
        </div>
      </TabsPanel>
      <TabsPanel value="properties">
        <div className="mt-6">
          <PropertiesTab variant="tab" />
        </div>
      </TabsPanel>
      <TabsPanel value="hierarchy">
        <div className="mt-6">
          <HierarchyTab workspaceSlug={workspaceSlug} projectId={projectId} />
        </div>
      </TabsPanel>
    </Tabs>
  );
});
