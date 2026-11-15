/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@makeplane/propel/components/button";
import { EpicOutline } from "@makeplane/propel/icons";
import { EIssuesStoreType } from "@plane/types";
import { Breadcrumbs } from "@plane/blocks/breadcrumb";
import { Header } from "@plane/blocks/layout";
// components
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { CountChip } from "@/components/common/count-chip";
import { HeaderFilters } from "@/components/issues/filters";
import { CreateUpdateIssueModal } from "@/components/issues/issue-modal/modal";
// hooks
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useIssues } from "@/hooks/store/use-issues";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// plane web imports
import { CommonProjectBreadcrumbs } from "@/components/breadcrumbs/common";
import { useProjectCrumbProps } from "@/components/breadcrumbs/use-project-crumb-props";

/**
 * Epic page header: project breadcrumbs + Epics crumb, count chip, list/gantt layout
 * switcher, filters and a "New Epic" button that opens the generic create modal with
 * the project's Epic type preselected (the old epic-modal shell is not used).
 */
export const EpicsHeader = observer(function EpicsHeader() {
  // router
  const { workspaceSlug, projectId } = useParams();
  const projectCrumb = useProjectCrumbProps(workspaceSlug?.toString(), projectId?.toString());
  // states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  // store hooks
  const {
    issues: { getGroupIssueCount },
  } = useIssues(EIssuesStoreType.EPIC);
  const { currentProjectDetails, loader } = useProject();
  const { getTypesByProjectId } = useIssueType();
  const { allowPermissions } = useUserPermissions();
  // i18n
  const { t } = useTranslation();
  // derived values
  const issuesCount = getGroupIssueCount(undefined, undefined, false);
  const canUserCreateIssue = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug?.toString(),
    projectId?.toString()
  );
  const epicType = (getTypesByProjectId(projectId?.toString()) ?? []).find((type) => type.is_epic);

  return (
    <Header>
      <Header.LeftItem>
        <div className="flex items-center gap-2.5">
          <Breadcrumbs isLoading={loader === "init-loader"} className="flex-grow-0">
            <CommonProjectBreadcrumbs
              workspaceSlug={workspaceSlug?.toString()}
              projectId={projectId?.toString()}
              {...projectCrumb}
            />
            <Breadcrumbs.Item
              component={
                <BreadcrumbLink
                  label={t("epic.label", { count: 2 })}
                  icon={<EpicOutline className="h-4 w-4 text-tertiary" />}
                  isLast
                />
              }
              isLast
            />
          </Breadcrumbs>
          {issuesCount && issuesCount > 0 ? <CountChip count={issuesCount} /> : null}
        </div>
      </Header.LeftItem>
      <Header.RightItem>
        <div className="hidden gap-2 md:flex">
          <HeaderFilters
            projectId={projectId?.toString()}
            currentProjectDetails={currentProjectDetails}
            workspaceSlug={workspaceSlug?.toString()}
            canUserCreateIssue={canUserCreateIssue}
            storeType={EIssuesStoreType.EPIC}
          />
        </div>
        {canUserCreateIssue && (
          <Button
            variant="primary"
            size="md"
            stretch="auto"
            type="button"
            label={t("epic.new")}
            onClick={() => setIsCreateModalOpen(true)}
          />
        )}
      </Header.RightItem>

      {/* generic create modal with the Epic type preselected */}
      {projectId && (
        <CreateUpdateIssueModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          data={{
            project_id: projectId.toString(),
            type_id: epicType?.id,
          }}
          withDraftIssueWrapper={false}
          primaryButtonText={{
            default: t("epic.new"),
            loading: t("creating"),
          }}
        />
      )}
    </Header>
  );
});
