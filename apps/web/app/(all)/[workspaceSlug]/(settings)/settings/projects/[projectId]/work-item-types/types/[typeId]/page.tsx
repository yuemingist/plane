/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
import { EUserPermissions, EUserPermissionsLevel, SETTINGS_DOCS_URLS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
import { TypeDetailRoot } from "@/components/settings/projects/work-item-types/type-detail-root";
// hooks
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import type { Route } from "./+types/page";
import { WorkItemTypesProjectSettingsHeader } from "../../header";

function WorkItemTypeDetailPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId, typeId } = params;
  // store
  const { currentProjectDetails } = useProject();
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { t } = useTranslation();
  const { getTypeById, areTypesFetched, fetchProjectWorkItemTypes } = useIssueType();

  // make sure the project's types are loaded before resolving the detail view
  useSWR(
    workspaceSlug && projectId ? `PROJECT_WORK_ITEM_TYPES_${workspaceSlug}_${projectId}` : null,
    async () => {
      if (workspaceSlug && projectId && !areTypesFetched(projectId)) {
        await fetchProjectWorkItemTypes(workspaceSlug, projectId);
      }
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  // derived values
  const pageTitle = currentProjectDetails?.name ? `${currentProjectDetails?.name} - Work item type` : undefined;
  const canPerformProjectMemberActions = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT
  );
  const issueType = areTypesFetched(projectId) ? getTypeById(typeId) : undefined;

  if (workspaceUserInfo && !canPerformProjectMemberActions) {
    return <NotAuthorizedView section="settings" isProjectView className="h-auto" />;
  }

  return (
    <SettingsContentWrapper header={<WorkItemTypesProjectSettingsHeader />}>
      <PageHead title={pageTitle} />
      <div className="w-full">
        <SettingsHeading
          title={issueType?.name ?? t("work_item_types.label")}
          description={t("work_item_types.settings.subtitle")}
          docHref={SETTINGS_DOCS_URLS.work_item_types}
        />
        <div className="mt-6">
          <TypeDetailRoot workspaceSlug={workspaceSlug} projectId={projectId} issueTypeId={typeId} />
        </div>
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(WorkItemTypeDetailPage);
