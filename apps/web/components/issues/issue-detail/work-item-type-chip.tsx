/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { SwitchHorizontalOutline } from "@makeplane/propel/icons";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import { ConfirmDialog } from "@plane/blocks/dialog";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { IIssueType } from "@plane/types";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useProject } from "@/hooks/store/use-project";
// local imports
import { TypeIcon } from "@/components/settings/projects/work-item-types/type-icon";

type TWorkItemTypeChipProps = {
  issueId: string;
  disabled?: boolean;
  onChangeType: (typeId: string) => Promise<void>;
};

/**
 * Work item type chip next to the work item title (1b-1): shows the icon + type name;
 * the hover/click menu offers "Switch work item type", and picking a type opens the
 * change-confirmation dialog before PATCHing `type_id`. Custom property value migration
 * is not rendered (no property system in this step, 产品方案 §4.1).
 */
export const WorkItemTypeChip = observer(function WorkItemTypeChip(props: TWorkItemTypeChipProps) {
  const { issueId, disabled = false, onChangeType } = props;
  // states
  const [pendingTypeId, setPendingTypeId] = useState<string | undefined>(undefined);
  const [isChanging, setIsChanging] = useState(false);
  // hooks
  const { t } = useTranslation();
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const { getActiveTypes, getTypeById } = useIssueType();
  const { getProjectById } = useProject();
  // derived values
  const issue = getIssueById(issueId);
  const projectId = issue?.project_id;
  const projectDetails = projectId ? getProjectById(projectId) : undefined;
  const isIssueTypeEnabled = projectDetails?.is_issue_type_enabled === true;
  const selectedType = getTypeById(issue?.type_id);
  const activeTypes = getActiveTypes(projectId) ?? [];
  const switchTargets = activeTypes.filter((type) => type.id !== selectedType?.id);

  if (!issue || !isIssueTypeEnabled || !selectedType || switchTargets.length === 0) return null;

  const handleConfirmChange = async () => {
    if (!pendingTypeId) return;
    setIsChanging(true);
    try {
      await onChangeType(pendingTypeId);
      setPendingTypeId(undefined);
    } catch (errorData) {
      const errorStatus = errorData as { status?: number; error?: string };
      setToast({
        type: "error",
        title: t("error"),
        message: errorStatus?.error ?? t("common.something_went_wrong"),
      });
    } finally {
      setIsChanging(false);
    }
  };

  return (
    <>
      <Menu>
        <MenuTrigger
          render={
            <button
              type="button"
              className="group flex max-w-52 items-center gap-1.5 rounded-md px-1.5 py-0.5 text-caption-md-medium text-secondary hover:bg-layer-transparent-hover"
              aria-label={t("work_item_types.switch_entry")}
              disabled={disabled}
            >
              <TypeIcon issueType={selectedType} size={14} />
              <span className="truncate">{selectedType.name}</span>
              <span className="hidden items-center gap-1 text-caption-md-medium text-accent-primary group-hover:flex">
                <SwitchHorizontalOutline className="size-3" />
                {t("work_item_types.switch_entry")}
              </span>
            </button>
          }
        />
        <MenuContent side="bottom" align="start">
          {switchTargets.map((type: IIssueType) => (
            <MenuItem
              key={type.id}
              icon={<TypeIcon issueType={type} size={14} />}
              label={type.name}
              onClick={() => setPendingTypeId(type.id)}
            />
          ))}
        </MenuContent>
      </Menu>

      {/* change confirmation — copy is verbatim from the cloud dialog (产品方案 §6 #6) */}
      <ConfirmDialog
        handleClose={() => setPendingTypeId(undefined)}
        handleSubmit={handleConfirmChange}
        isSubmitting={isChanging}
        isOpen={!!pendingTypeId}
        title={t("work_item_types.change_confirmation.title")}
        content={t("work_item_types.change_confirmation.description")}
        primaryButtonText={{
          default: t("work_item_types.change_confirmation.button.default"),
          loading: t("work_item_types.change_confirmation.button.loading"),
        }}
        variant="danger"
      />
    </>
  );
});
