/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR from "swr";
import { observer } from "mobx-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel, SETTINGS_DOCS_URLS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { IWorkflow } from "@plane/types";
import { Switch } from "@makeplane/propel/components/switch";
import { ConfirmDialog } from "@plane/blocks/dialog";
import { setToast } from "@plane/blocks/toast";
import { SettingsBoxedControlItem } from "@/components/settings/boxed-control-item";
// hooks
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import { WorkflowChangeHistoryPanel } from "./change-history-panel";
import { WorkflowTable } from "./workflow-table";
import { WorkflowService } from "@/services/workflow.service";

type TProjectWorkflowsRootProps = {
  workspaceSlug: string;
  projectId: string;
};

/**
 * Settings page root for the project workflow shell (Step02 segment 1).
 * Cloud parity (58号 D-10): the "Enable workflows" toggle card is always rendered;
 * when a workflow is active the Default Workflow table shows below it. Disabling
 * (toggle off or row menu) asks for confirmation first, per segment product plan §2.4.
 */
export const ProjectWorkflowsRoot = observer(function ProjectWorkflowsRoot(props: TProjectWorkflowsRootProps) {
  const { workspaceSlug, projectId } = props;
  // states
  const [isDisableConfirmOpen, setIsDisableConfirmOpen] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  // hooks
  const { t } = useTranslation();
  const { allowPermissions } = useUserPermissions();
  const workflowService = new WorkflowService();
  // derived values
  const canPerformActions = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );

  // fetch the project's workflows (empty array = gate/off state)
  const { data: workflows, mutate } = useSWR(
    workspaceSlug && projectId ? `PROJECT_WORKFLOWS_${workspaceSlug}_${projectId}` : null,
    async () => {
      const response = await workflowService.getWorkflows(workspaceSlug, projectId);
      return response ?? [];
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  const workflow: IWorkflow | undefined = workflows?.find((item) => item.is_active) ?? workflows?.[0];
  const isEnabled = workflow?.is_active === true;

  const handleToggle = (checked: boolean) => {
    if (!canPerformActions || isToggling) return;
    if (checked) {
      void handleEnable();
    } else {
      // disable asks for confirmation (segment product plan §2.4)
      setIsDisableConfirmOpen(true);
    }
  };

  const handleEnable = async () => {
    if (isToggling) return;
    setIsToggling(true);
    try {
      await workflowService.enableWorkflow(workspaceSlug, projectId);
      await mutate();
      setToast({
        type: "success",
        title: t("workflows.settings.enable.success_toast.title"),
        message: t("workflows.settings.enable.success_toast.message"),
      });
    } catch (errorData) {
      const errorStatus = errorData as { error?: string };
      setToast({
        type: "error",
        title: t("error"),
        message: errorStatus?.error ?? t("common.something_went_wrong"),
      });
    } finally {
      setIsToggling(false);
    }
  };

  const handleDisable = async () => {
    if (!workflow || isToggling) return;
    setIsToggling(true);
    try {
      await workflowService.disableWorkflow(workspaceSlug, projectId, workflow.id);
      await mutate();
      setToast({
        type: "success",
        title: t("workflows.settings.disable.success_toast.title"),
        message: t("workflows.settings.disable.success_toast.message"),
      });
      setIsDisableConfirmOpen(false);
    } catch (errorData) {
      const errorStatus = errorData as { error?: string };
      setToast({
        type: "error",
        title: t("error"),
        message: errorStatus?.error ?? t("common.something_went_wrong"),
      });
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <>
      <SettingsBoxedControlItem
        title={t("workflows.settings.enable.title")}
        description={t("workflows.settings.enable.description")}
        docHref={SETTINGS_DOCS_URLS.workflows}
        control={
          <Switch
            size="md"
            checked={isEnabled}
            onCheckedChange={handleToggle}
            disabled={!canPerformActions || isToggling || workflows === undefined}
            aria-label={t("workflows.settings.enable.title")}
          />
        }
      />

      {isEnabled && workflow && (
        <div className="mt-8">
          <WorkflowTable
            workspaceSlug={workspaceSlug}
            workflow={workflow}
            canPerformActions={canPerformActions}
            onRequestDisable={() => setIsDisableConfirmOpen(true)}
            onRequestHistory={() => setIsHistoryOpen(true)}
          />
        </div>
      )}

      <ConfirmDialog
        handleClose={() => setIsDisableConfirmOpen(false)}
        handleSubmit={handleDisable}
        isSubmitting={isToggling}
        isOpen={isDisableConfirmOpen}
        title={t("workflows.settings.disable.confirmation.title")}
        content={t("workflows.settings.disable.confirmation.description")}
        primaryButtonText={{
          default: t("workflows.settings.row_menu.disable"),
          loading: t("workflows.settings.row_menu.disable"),
        }}
        variant="danger"
      />

      {isHistoryOpen && workflow && (
        <WorkflowChangeHistoryPanel
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          workflow={workflow}
          handleClose={() => setIsHistoryOpen(false)}
        />
      )}
    </>
  );
});
