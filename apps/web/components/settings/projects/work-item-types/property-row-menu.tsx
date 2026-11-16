/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogHeading,
  DialogMain,
  DialogTitle,
} from "@makeplane/propel/components/dialog";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from "@makeplane/propel/components/menu";
import { EditOutline, MoreHorizontalOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import type { IIssueProperty } from "@plane/types";

type TPropertyRowMenuProps = {
  property: IIssueProperty;
  onEdit: () => void;
  onDelete: () => void;
  onToggleActive: (nextActive: boolean) => void;
};

/**
 * 属性池行菜单（57 号 §3.3 步骤 5：编辑/删除；CE 补启停项，
 * 删除走确认弹窗 + 使用中约束由服务端兜底）。
 */
export const PropertyRowMenu = observer(function PropertyRowMenu(props: TPropertyRowMenuProps) {
  const { property, onEdit, onDelete, onToggleActive } = props;
  // states
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  // hooks
  const { t } = useTranslation();

  return (
    <>
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
          <MenuItem icon={<Icon icon={EditOutline} />} label={t("common.actions.edit")} onClick={onEdit} />
          <MenuItem
            label={
              property.is_active
                ? t("common.actions.disable")
                : t("work_item_types.settings.properties.enable_disable.label")
            }
            onClick={() => onToggleActive(!property.is_active)}
          />
          <MenuSeparator />
          <MenuItem variant="danger" label={t("common.actions.delete")} onClick={() => setIsDeleteDialogOpen(true)} />
        </MenuContent>
      </Menu>

      {/* delete confirmation（57 号 §3.3 删除确认语义） */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={(open) => !open && setIsDeleteDialogOpen(false)}>
        <DialogContent size="sm">
          <DialogMain>
            <DialogHeader>
              <DialogHeading>
                <DialogTitle>{t("work_item_types.settings.properties.delete_confirmation.title")}</DialogTitle>
              </DialogHeading>
            </DialogHeader>
            <DialogBody render={<div className="flex flex-col gap-4" />}>
              <p className="text-body-sm-regular text-secondary">
                {t("work_item_types.settings.properties.delete_confirmation.description", { name: property.name })}
              </p>
            </DialogBody>
          </DialogMain>
          <DialogActions>
            <Button
              type="button"
              variant="secondary"
              size="md"
              stretch="auto"
              label={t("common.cancel")}
              onClick={() => setIsDeleteDialogOpen(false)}
            />
            <Button
              type="button"
              variant="danger"
              size="md"
              stretch="auto"
              label={t("common.actions.delete")}
              onClick={() => {
                setIsDeleteDialogOpen(false);
                onDelete();
              }}
            />
          </DialogActions>
        </DialogContent>
      </Dialog>
    </>
  );
});
