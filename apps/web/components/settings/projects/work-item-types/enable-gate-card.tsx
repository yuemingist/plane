/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@makeplane/propel/components/button";
import { useTranslation } from "@plane/i18n";
import { ConfirmDialog } from "@plane/blocks/dialog";
import { setToast } from "@plane/blocks/toast";
// hooks
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useUserPermissions } from "@/hooks/store/user";

type TWorkItemTypesGateProps = {
  workspaceSlug: string;
  projectId: string;
};

/**
 * Gate card shown when the project has `is_issue_type_enabled === false`.
 * Enabling is one-way: the backend seeds the Epic + Task types on confirm.
 */
export const WorkItemTypesGate = observer(function WorkItemTypesGate(props: TWorkItemTypesGateProps) {
  const { workspaceSlug, projectId } = props;
  // states
  const [isEnableConfirmOpen, setIsEnableConfirmOpen] = useState(false);
  const [isEnabling, setIsEnabling] = useState(false);
  // store hooks
  const { t } = useTranslation();
  const { enableWorkItemTypes } = useIssueType();
  const { allowPermissions } = useUserPermissions();
  // derived values
  const canEnable = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT, workspaceSlug, projectId);

  const handleEnable = async () => {
    setIsEnabling(true);
    try {
      await enableWorkItemTypes(workspaceSlug, projectId);
      setToast({
        type: "success",
        title: t("work_item_types.settings.enable_success_toast.title"),
        message: t("work_item_types.settings.enable_success_toast.message"),
      });
    } catch {
      setToast({
        type: "error",
        title: t("error"),
        message: t("common.something_went_wrong"),
      });
    } finally {
      setIsEnabling(false);
      setIsEnableConfirmOpen(false);
    }
  };

  return (
    <div className="flex w-full flex-col items-center justify-center gap-5 py-10">
      <p className="max-w-2xl text-center text-body-md-regular text-secondary">
        {t("work_item_types.empty_state.enable.description")}
      </p>
      {canEnable && (
        <Button
          variant="primary"
          size="md"
          stretch="auto"
          label={t("work_item_types.empty_state.enable.primary_button.text")}
          onClick={() => setIsEnableConfirmOpen(true)}
        />
      )}
      <ConfirmDialog
        handleClose={() => setIsEnableConfirmOpen(false)}
        handleSubmit={handleEnable}
        isSubmitting={isEnabling}
        isOpen={isEnableConfirmOpen}
        title={t("work_item_types.empty_state.enable.confirmation.title")}
        content={t("work_item_types.empty_state.enable.confirmation.description")}
        primaryButtonText={{
          default: t("work_item_types.empty_state.enable.confirmation.button.default"),
          loading: t("work_item_types.empty_state.enable.confirmation.button.loading"),
        }}
        variant="primary"
      />
    </div>
  );
});

export type { TWorkItemTypesGateProps };
