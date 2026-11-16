/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@makeplane/propel/components/button";
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
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import { PlusCircleOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import { setToast } from "@plane/blocks/toast";
import type { IIssueProperty, IIssueTypeIssueProperty, TIssuePropertyType } from "@plane/types";
import { EUserProjectRoles } from "@plane/types";
// hooks
import { useIssueProperty } from "@/hooks/store/use-issue-property";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import { AttachPropertiesModal } from "./attach-properties-modal";
import { CreatePropertyModal } from "./create-property-modal";
import { propertyTypeLabel } from "./property-type-meta";

type TTypePropertiesSectionProps = {
  workspaceSlug: string;
  projectId: string;
  typeId: string;
};

/**
 * 类型详情页属性区（57 号 §3.4 步骤 1-4）：绑定属性列表 + 「+ 添加属性」
 * 菜单（创建新属性 / 添加现有属性）+ 行菜单（启用属性确认 / 禁用 / 移除）。
 */
export const TypePropertiesSection = observer(function TypePropertiesSection(props: TTypePropertiesSectionProps) {
  const { workspaceSlug, projectId, typeId } = props;
  // states
  const [isAttachModalOpen, setIsAttachModalOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [confirmToggleProperty, setConfirmToggleProperty] = useState<IIssueProperty | undefined>(undefined);
  const [confirmRemoveBinding, setConfirmRemoveBinding] = useState<IIssueTypeIssueProperty | undefined>(undefined);
  const [isConfirmLoading, setIsConfirmLoading] = useState(false);
  // hooks
  const { t } = useTranslation();
  const { getBindingsByTypeId, fetchTypeProperties, areTypeBindingsFetched, updateProperty, unbindProperty } =
    useIssueProperty();
  const { allowPermissions } = useUserPermissions();
  // derived values
  const bindings = getBindingsByTypeId(typeId);
  const boundPropertyIds = useMemo(() => (bindings ?? []).map((binding) => binding.issue_property), [bindings]);
  const canPerformActions = allowPermissions(
    [EUserProjectRoles.ADMIN, EUserProjectRoles.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );

  useSWR(
    workspaceSlug && projectId && typeId ? `TYPE_ISSUE_PROPERTIES_${workspaceSlug}_${projectId}_${typeId}` : null,
    async () => {
      if (workspaceSlug && projectId && typeId && !areTypeBindingsFetched(typeId)) {
        await fetchTypeProperties(workspaceSlug, projectId, typeId);
      }
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  /** 启用走二次确认弹窗（57 号双门控第二门）；确认弹窗内完成启停 */
  const handleConfirmToggle = async () => {
    if (!confirmToggleProperty) return;
    const nextActive = !confirmToggleProperty.is_active;
    setIsConfirmLoading(true);
    try {
      await updateProperty(workspaceSlug, projectId, confirmToggleProperty.id, { is_active: nextActive });
      setToast({
        type: "success",
        title: t("work_item_types.settings.properties.toast.enable_disable.success.title"),
        message: t("work_item_types.settings.properties.toast.enable_disable.success.message", {
          name: confirmToggleProperty.name,
          action: nextActive ? "enabled" : "disabled",
        }),
      });
      setConfirmToggleProperty(undefined);
    } catch {
      setToast({
        type: "error",
        title: t("work_item_types.settings.properties.toast.enable_disable.error.title"),
        message: t("work_item_types.settings.properties.toast.enable_disable.error.message"),
      });
    } finally {
      setIsConfirmLoading(false);
    }
  };

  const handleConfirmRemove = async () => {
    if (!confirmRemoveBinding) return;
    setIsConfirmLoading(true);
    try {
      await unbindProperty(workspaceSlug, projectId, typeId, confirmRemoveBinding.issue_property);
      setToast({ type: "success", title: t("success"), message: t("common.success") });
      setConfirmRemoveBinding(undefined);
    } catch {
      setToast({ type: "error", title: t("error"), message: t("common.something_went_wrong") });
    } finally {
      setIsConfirmLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {/* section header + add menu */}
      <div className="flex items-center justify-between gap-4">
        <span className="text-body-sm-medium text-secondary">
          {t("work_item_types.settings.linked_properties.title")}
        </span>
        {canPerformActions && (
          <Menu>
            <MenuTrigger
              render={
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  stretch="auto"
                  label={t("work_item_types.settings.linked_properties.add_button")}
                  icon={<PlusCircleOutline className="size-3.5" />}
                  iconPosition="start"
                />
              }
            />
            <MenuContent side="bottom" align="end">
              <MenuItem
                label={t("work_item_types.settings.properties.add_button")}
                onClick={() => setIsCreateModalOpen(true)}
              />
              <MenuItem
                label={t("work_item_types.settings.linked_properties.modal.title")}
                onClick={() => setIsAttachModalOpen(true)}
              />
            </MenuContent>
          </Menu>
        )}
      </div>

      {/* bound property rows */}
      <div className="flex flex-col overflow-hidden rounded-lg border border-subtle bg-layer-1">
        {(bindings ?? []).map((binding) => {
          const property = binding.issue_property_detail;
          if (!property) return null;
          return (
            <div
              key={binding.id}
              className="flex items-center gap-3 border-b border-subtle px-4 py-3 text-body-sm-regular text-primary last:border-b-0"
            >
              <span className="min-w-0 flex-1 truncate">{property.name}</span>
              {property.is_active ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-success-primary/10 px-2 py-0.5 text-caption-md-medium text-success-primary">
                  <span className="size-1.5 rounded-full bg-success-primary" />
                  {t("work_item_types.settings.properties.enable_disable.label")}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-layer-2 px-2 py-0.5 text-caption-md-medium text-tertiary">
                  {t("common.disabled")}
                </span>
              )}
              <span className="rounded-full border border-subtle px-2 py-0.5 text-caption-md-medium text-tertiary">
                {propertyTypeLabel(property.property_type as TIssuePropertyType, t)}
              </span>
              {canPerformActions && (
                <Menu>
                  <MenuTrigger
                    render={
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        stretch="auto"
                        label="…"
                        aria-label={t("common.more")}
                      />
                    }
                  />
                  <MenuContent side="bottom" align="end">
                    <MenuItem
                      label={property.is_active ? t("common.actions.disable") : t("common.actions.enable")}
                      description={
                        property.is_active
                          ? undefined
                          : t("work_item_types.settings.properties.enable_confirmation.title")
                      }
                      onClick={() => setConfirmToggleProperty(property)}
                    />
                    <MenuItem
                      variant="danger"
                      label={t("work_item_types.settings.linked_properties.remove.title")}
                      onClick={() => setConfirmRemoveBinding(binding)}
                    />
                  </MenuContent>
                </Menu>
              )}
            </div>
          );
        })}
        {(bindings ?? []).length === 0 && (
          <div className="flex flex-col items-center justify-center gap-1 px-4 py-8 text-center">
            <p className="text-body-sm-medium text-secondary">
              {t("work_item_types.settings.properties.empty_state.title")}
            </p>
            <p className="text-caption-md-regular text-tertiary">
              {t("work_item_types.settings.properties.empty_state.no_properties_description")}
            </p>
          </div>
        )}
      </div>

      {/* modals */}
      {isAttachModalOpen && (
        <AttachPropertiesModal
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          typeId={typeId}
          boundPropertyIds={boundPropertyIds}
          onClose={() => setIsAttachModalOpen(false)}
        />
      )}
      {isCreateModalOpen && (
        <CreatePropertyModal
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
        />
      )}

      {/* enable/disable confirmation（启用正文为 57 号 §3.4 步骤 4 实录文案） */}
      <Dialog open={!!confirmToggleProperty} onOpenChange={(open) => !open && setConfirmToggleProperty(undefined)}>
        <DialogContent size="sm">
          <DialogMain>
            <DialogHeader>
              <DialogHeading>
                <DialogTitle>
                  {confirmToggleProperty?.is_active
                    ? t("work_item_types.settings.properties.enable_disable.label")
                    : t("work_item_types.settings.properties.enable_confirmation.title")}
                </DialogTitle>
              </DialogHeading>
            </DialogHeader>
            <DialogBody render={<div className="flex flex-col gap-4" />}>
              <p className="text-body-sm-regular text-secondary">
                {confirmToggleProperty?.is_active
                  ? t("work_item_types.settings.linked_properties.remove.description")
                  : t("work_item_types.settings.properties.enable_confirmation.content")}
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
              onClick={() => setConfirmToggleProperty(undefined)}
            />
            <Button
              type="button"
              variant="primary"
              size="md"
              stretch="auto"
              loading={isConfirmLoading}
              label={confirmToggleProperty?.is_active ? t("common.actions.disable") : t("common.actions.enable")}
              onClick={() => void handleConfirmToggle()}
            />
          </DialogActions>
        </DialogContent>
      </Dialog>

      {/* remove binding confirmation（CE 语义：解绑保留属性与已存值，产品方案 A2） */}
      <Dialog open={!!confirmRemoveBinding} onOpenChange={(open) => !open && setConfirmRemoveBinding(undefined)}>
        <DialogContent size="sm">
          <DialogMain>
            <DialogHeader>
              <DialogHeading>
                <DialogTitle>{t("work_item_types.settings.linked_properties.remove.title")}</DialogTitle>
              </DialogHeading>
            </DialogHeader>
            <DialogBody render={<div className="flex flex-col gap-4" />}>
              <p className="text-body-sm-regular text-secondary">
                {t("work_item_types.settings.linked_properties.remove.description")}
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
              onClick={() => setConfirmRemoveBinding(undefined)}
            />
            <Button
              type="button"
              variant="danger"
              size="md"
              stretch="auto"
              loading={isConfirmLoading}
              label={t("work_item_types.settings.linked_properties.remove.title")}
              onClick={() => void handleConfirmRemove()}
            />
          </DialogActions>
        </DialogContent>
      </Dialog>
    </div>
  );
});
