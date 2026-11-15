/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import type { Control } from "react-hook-form";
import { Controller, useFormContext } from "react-hook-form";
import { ChevronDownOutline } from "@makeplane/propel/icons";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import { useTranslation } from "@plane/i18n";
import type { IIssueType, TIssue } from "@plane/types";
// hooks
import { useIssueModal } from "@/hooks/context/use-issue-modal";
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useProject } from "@/hooks/store/use-project";
// local imports
import { TypeIcon } from "@/components/settings/projects/work-item-types/type-icon";

type TIssueTypeSelectProps = {
  control: Control<TIssue>;
  handleFormChange: () => void;
};

const renderTypeOption = (type: IIssueType) => (
  <span className="flex items-center gap-1.5">
    <TypeIcon issueType={type} size={14} />
    <span className="truncate">{type.name}</span>
  </span>
);

/**
 * Work item type chip in the create/update modal breadcrumb. Lists the project's
 * active types; when the selected parent is an Epic work item, Epic types are excluded
 * from the dropdown (hierarchy rule, 产品方案 §5.2) and the project default type is
 * preselected via the modal context.
 */
export const IssueTypeSelect = observer(function IssueTypeSelect(props: TIssueTypeSelectProps) {
  const { control, handleFormChange } = props;
  // hooks
  const { t } = useTranslation();
  const { getProjectById } = useProject();
  const { getActiveTypes, getDefaultType, getTypeById } = useIssueType();
  const { selectedParentIssue } = useIssueModal();
  const { watch } = useFormContext<TIssue>();
  // derived values
  // resolve the project context: prefer the parent issue's project when creating a sub work item,
  // falling back to the form's selected project
  const projectId = selectedParentIssue?.project_id ?? watch("project_id") ?? undefined;
  const projectDetails = projectId ? getProjectById(projectId) : undefined;
  const isIssueTypeEnabled = projectDetails?.is_issue_type_enabled === true;
  const activeTypes = getActiveTypes(projectId) ?? [];
  // hierarchy rule: when the parent is an Epic work item, Epic types are excluded from the dropdown
  const parentType = selectedParentIssue ? getTypeById(selectedParentIssue.type_id) : undefined;
  const availableTypes = parentType?.is_epic ? activeTypes.filter((type) => !type.is_epic) : activeTypes;

  // the chip only renders on projects with the work item types module enabled
  if (!isIssueTypeEnabled || availableTypes.length === 0) return null;

  return (
    <Controller
      control={control}
      name="type_id"
      render={({ field: { value, onChange } }) => {
        const selectedType = getTypeById(value);
        return (
          <Menu>
            <MenuTrigger
              render={
                <button
                  type="button"
                  className="flex max-w-52 items-center gap-1.5 rounded-md px-2 py-1 text-caption-md-medium text-secondary hover:bg-layer-transparent-hover"
                  aria-label={t("work_item_types.label")}
                >
                  {selectedType ? (
                    renderTypeOption(selectedType)
                  ) : (
                    <span className="truncate">
                      {getDefaultType(projectId)?.name ?? t("work_item_types.label_lowercase")}
                    </span>
                  )}
                  <ChevronDownOutline className="size-3 shrink-0" />
                </button>
              }
            />
            <MenuContent side="bottom" align="start">
              {availableTypes.map((type) => (
                <MenuItem
                  key={type.id}
                  icon={<TypeIcon issueType={type} size={14} />}
                  label={type.name}
                  selected={type.id === value}
                  onClick={() => {
                    onChange(type.id);
                    handleFormChange();
                  }}
                />
              ))}
            </MenuContent>
          </Menu>
        );
      }}
    />
  );
});
