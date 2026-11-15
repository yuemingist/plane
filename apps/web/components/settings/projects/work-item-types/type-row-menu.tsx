/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from "@makeplane/propel/components/menu";
import { DefaultTabOutline, DeleteOutline, EditOutline, MoreHorizontalOutline } from "@makeplane/propel/icons";
import { ConfirmDialog } from "@plane/blocks/dialog";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { IIssueType } from "@plane/types";

type TTypeRowMenuProps = {
  issueType: IIssueType;
  onEdit: () => void;
  onUpdate: (data: Partial<IIssueType>) => Promise<unknown>;
  onDelete: () => Promise<unknown>;
  onMarkDefault: () => Promise<unknown>;
};

/**
 * The type row's "…" menu, following the cloud state machine:
 * - inactive type: set as default (locked with hint) / edit / enable / delete
 * - active non-default type (Epic included): disable only
 * - default type: edit, delete locked (cannot delete the project default)
 */
export const TypeRowMenu = observer(function TypeRowMenu(props: TTypeRowMenuProps) {
  const { issueType, onEdit, onUpdate, onDelete, onMarkDefault } = props;
  // states
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  // hooks
  const { t } = useTranslation();
  // derived values
  const { is_active: isActive, is_default: isDefault } = issueType;
  const isDeleteDisabled = isDefault;
  const deleteDisabledReason = isDefault ? t("work_item_types.settings.cant_delete_default_message") : undefined;

  const withLoader = async (action: () => Promise<unknown>) => {
    if (isLoading) return;
    setIsLoading(true);
    try {
      await action();
    } catch (errorData) {
      const errorStatus = errorData as { status?: number; error?: string };
      setToast({
        type: "error",
        title: t("error"),
        message: errorStatus?.error ?? t("common.something_went_wrong"),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteType = async () => {
    setIsDeleting(true);
    try {
      await onDelete();
      setIsDeleteModalOpen(false);
    } catch (errorData) {
      const errorStatus = errorData as { status?: number; error?: string };
      setToast({
        type: "error",
        title: t("error"),
        message: errorStatus?.error ?? t("work_item_types.settings.item_delete_confirmation.toast.error.message"),
      });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <ConfirmDialog
        handleClose={() => setIsDeleteModalOpen(false)}
        handleSubmit={handleDeleteType}
        isSubmitting={isDeleting}
        isOpen={isDeleteModalOpen}
        title={t("work_item_types.settings.item_delete_confirmation.title")}
        content={t("work_item_types.settings.item_delete_confirmation.description")}
        primaryButtonText={{
          default: t("work_item_types.settings.item_delete_confirmation.primary_button"),
          loading: t("work_item_types.change_confirmation.button.loading"),
        }}
      />
      <Menu>
        <MenuTrigger
          render={
            <IconButton
              type="button"
              variant="ghost"
              size="xs"
              aria-label={t("aria_labels.common.more_actions")}
              icon={<Icon icon={MoreHorizontalOutline} />}
            />
          }
        />
        <MenuContent side="bottom" align="end">
          {!isActive && (
            <>
              <MenuItem
                icon={<Icon icon={DefaultTabOutline} />}
                label={t("work_item_types.settings.set_as_default")}
                description={t("work_item_types.settings.cant_set_default_inactive_message")}
                disabled
                onClick={() => void withLoader(onMarkDefault)}
              />
              <MenuItem icon={<Icon icon={EditOutline} />} label={t("common.actions.edit")} onClick={onEdit} />
              <MenuItem
                label={t("common.actions.enable")}
                disabled={isLoading}
                onClick={() => void withLoader(() => onUpdate({ is_active: true }))}
              />
              <MenuSeparator />
              <MenuItem
                variant="danger"
                icon={<Icon icon={DeleteOutline} />}
                label={t("common.actions.delete")}
                disabled={isLoading}
                onClick={() => setIsDeleteModalOpen(true)}
              />
            </>
          )}
          {isActive && isDefault && (
            <>
              <MenuItem icon={<Icon icon={EditOutline} />} label={t("common.actions.edit")} onClick={onEdit} />
              <MenuSeparator />
              <MenuItem
                variant="danger"
                icon={<Icon icon={DeleteOutline} />}
                label={t("common.actions.delete")}
                description={deleteDisabledReason}
                disabled={isDeleteDisabled}
                onClick={() => setIsDeleteModalOpen(true)}
              />
            </>
          )}
          {isActive && !isDefault && (
            // active non-default types (built-in Epic included) only offer "Disable"
            <MenuItem
              label={t("common.actions.disable")}
              disabled={isLoading}
              onClick={() => void withLoader(() => onUpdate({ is_active: false }))}
            />
          )}
        </MenuContent>
      </Menu>
    </>
  );
});
