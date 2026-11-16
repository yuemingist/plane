/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel, SETTINGS_DOCS_URLS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
import { ProjectWorkflowsRoot } from "@/components/settings/projects/workflows/root";
// hooks
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import type { Route } from "./+types/page";
import { WorkflowsProjectSettingsHeader } from "./header";

function WorkflowsSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  // store hooks
  const { currentProjectDetails } = useProject();
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { t } = useTranslation();

  // derived values
  const pageTitle = currentProjectDetails?.name ? `${currentProjectDetails?.name} - Workflows` : undefined;
  const canPerformProjectMemberActions = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT
  );

  if (workspaceUserInfo && !canPerformProjectMemberActions) {
    return <NotAuthorizedView section="settings" isProjectView className="h-auto" />;
  }

  return (
    <SettingsContentWrapper header={<WorkflowsProjectSettingsHeader />}>
      <PageHead title={pageTitle} />
      <div className="w-full">
        <SettingsHeading
          title={t("workflows.settings.label")}
          description={t("workflows.settings.description")}
          docHref={SETTINGS_DOCS_URLS.workflows}
        />
        <div className="mt-6">
          <ProjectWorkflowsRoot workspaceSlug={workspaceSlug} projectId={projectId} />
        </div>
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(WorkflowsSettingsPage);
