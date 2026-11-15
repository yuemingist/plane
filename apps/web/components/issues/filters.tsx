/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import { observer } from "mobx-react";
import { useRouter } from "next/navigation";
import { AnalyticsOutline, EpicOutline, PreferencesOutline } from "@makeplane/propel/icons";
// plane imports
import { EIssueFilterType, ISSUE_STORE_TO_FILTERS_MAP } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import type { IIssueDisplayFilterOptions, IIssueDisplayProperties } from "@plane/types";
import { EIssueLayoutTypes, EIssuesStoreType } from "@plane/types";
// hooks
import { useIssues } from "@/hooks/store/use-issues";
import { useIssueType } from "@/hooks/store/use-issue-type";
// plane web imports
import type { TProject } from "@plane/types";
// local imports
import { WorkItemsModal } from "../analytics/work-items/modal";
import { WorkItemFiltersToggle } from "../work-item-filters/filters-toggle";
import {
  DisplayFiltersSelection,
  FiltersDropdown,
  LayoutSelection,
  MobileLayoutSelection,
} from "./issue-layouts/filters";

type Props = {
  currentProjectDetails: TProject | undefined;
  projectId: string;
  workspaceSlug: string;
  canUserCreateIssue: boolean | undefined;
  storeType?: EIssuesStoreType.PROJECT | EIssuesStoreType.EPIC;
};
const PROJECT_LAYOUTS = [
  EIssueLayoutTypes.LIST,
  EIssueLayoutTypes.KANBAN,
  EIssueLayoutTypes.CALENDAR,
  EIssueLayoutTypes.SPREADSHEET,
  EIssueLayoutTypes.GANTT,
];
// the Epic layout ships with list + gantt only (the layouts verified against the cloud Epic view)
const EPIC_LAYOUTS = [EIssueLayoutTypes.LIST, EIssueLayoutTypes.GANTT];

export const HeaderFilters = observer(function HeaderFilters(props: Props) {
  const {
    currentProjectDetails,
    projectId,
    workspaceSlug,
    canUserCreateIssue,
    storeType = EIssuesStoreType.PROJECT,
  } = props;
  // derived values
  const LAYOUTS = storeType === EIssuesStoreType.EPIC ? EPIC_LAYOUTS : PROJECT_LAYOUTS;
  // i18n
  const { t } = useTranslation();
  // router
  const router = useRouter();
  // states
  const [analyticsModal, setAnalyticsModal] = useState(false);
  // store hooks
  const {
    issuesFilter: { issueFilters, updateFilters },
  } = useIssues(storeType);
  const { hasEpicType, areTypesFetched } = useIssueType();
  // derived values
  const activeLayout = issueFilters?.displayFilters?.layout;
  const layoutDisplayFiltersOptions = ISSUE_STORE_TO_FILTERS_MAP[storeType]?.layoutOptions[activeLayout];
  // Epic layout entry (BUG-05 ①): on the work items page, the switcher gains an Epic entry when
  // the project has work item types enabled and an active is_epic type exists (or the type list
  // is still loading); the entry routes to the Epics page
  const showEpicLayoutEntry =
    storeType === EIssuesStoreType.PROJECT &&
    currentProjectDetails?.is_issue_type_enabled === true &&
    (!areTypesFetched(projectId) || hasEpicType(projectId));

  const handleLayoutChange = useCallback(
    (layout: EIssueLayoutTypes) => {
      if (!workspaceSlug || !projectId) return;
      updateFilters(workspaceSlug, projectId, EIssueFilterType.DISPLAY_FILTERS, { layout: layout });
    },
    [workspaceSlug, projectId, updateFilters]
  );

  const handleDisplayFilters = useCallback(
    (updatedDisplayFilter: Partial<IIssueDisplayFilterOptions>) => {
      if (!workspaceSlug || !projectId) return;
      updateFilters(workspaceSlug, projectId, EIssueFilterType.DISPLAY_FILTERS, updatedDisplayFilter);
    },
    [workspaceSlug, projectId, updateFilters]
  );

  const handleDisplayProperties = useCallback(
    (property: Partial<IIssueDisplayProperties>) => {
      if (!workspaceSlug || !projectId) return;
      updateFilters(workspaceSlug, projectId, EIssueFilterType.DISPLAY_PROPERTIES, property);
    },
    [workspaceSlug, projectId, updateFilters]
  );

  return (
    <>
      <WorkItemsModal
        isOpen={analyticsModal}
        onClose={() => setAnalyticsModal(false)}
        projectDetails={currentProjectDetails ?? undefined}
        isEpic={storeType === EIssuesStoreType.EPIC}
      />
      <div className="hidden @4xl:flex">
        <LayoutSelection
          layouts={LAYOUTS}
          onChange={(layout) => handleLayoutChange(layout)}
          selectedLayout={activeLayout}
        />
        {showEpicLayoutEntry && (
          <Tooltip label={t("epic.label", { count: 2 })} side="bottom">
            <button
              type="button"
              className="grid size-7 place-items-center rounded-md text-tertiary transition-colors hover:bg-layer-transparent-hover hover:text-primary"
              aria-label={t("sidebar.epics")}
              onClick={() => router.push(`/${workspaceSlug}/projects/${projectId}/epics`)}
            >
              <EpicOutline className="size-4" />
            </button>
          </Tooltip>
        )}
      </div>
      <div className="flex @4xl:hidden">
        <MobileLayoutSelection
          layouts={LAYOUTS}
          onChange={(layout) => handleLayoutChange(layout)}
          activeLayout={activeLayout}
        />
      </div>
      <WorkItemFiltersToggle entityType={storeType} entityId={projectId} />
      <FiltersDropdown
        miniIcon={<PreferencesOutline className="size-3.5" />}
        title={t("common.display")}
        placement="bottom-end"
      >
        <DisplayFiltersSelection
          layoutDisplayFiltersOptions={layoutDisplayFiltersOptions}
          displayFilters={issueFilters?.displayFilters ?? {}}
          handleDisplayFiltersUpdate={handleDisplayFilters}
          displayProperties={issueFilters?.displayProperties ?? {}}
          handleDisplayPropertiesUpdate={handleDisplayProperties}
          cycleViewDisabled={!currentProjectDetails?.cycle_view}
          moduleViewDisabled={!currentProjectDetails?.module_view}
          isEpic={storeType === EIssuesStoreType.EPIC}
        />
      </FiltersDropdown>
      {canUserCreateIssue ? (
        <>
          {/* icon-only below the header's @4xl container breakpoint, labelled at and above it */}
          <div className="hidden md:flex @4xl:hidden">
            <IconButton
              variant="secondary"
              size="md"
              icon={<Icon icon={AnalyticsOutline} />}
              aria-label={t("common.analytics")}
              onClick={() => setAnalyticsModal(true)}
            />
          </div>
          <div className="hidden @4xl:flex">
            <Button
              variant="secondary"
              size="md"
              stretch="auto"
              label={t("common.analytics")}
              onClick={() => setAnalyticsModal(true)}
            />
          </div>
        </>
      ) : (
        <></>
      )}
    </>
  );
});
