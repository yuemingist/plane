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
import { InputField } from "@makeplane/propel/components/input-field";
import { TextAreaField } from "@makeplane/propel/components/text-area-field";
import { EmojiPicker } from "@plane/blocks/emoji-icon-picker";
import { useTranslation } from "@plane/i18n";
import { setToast } from "@plane/blocks/toast";
import type { IIssueType, TLogoProps } from "@plane/types";
// hooks
import { useIssueType } from "@/hooks/store/use-issue-type";
// local imports
import { TypeIcon } from "./type-icon";

type TCreateTypeModalProps = {
  workspaceSlug: string;
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  /** when provided, the modal edits the existing type instead of creating one */
  issueType?: IIssueType;
};

const DEFAULT_LOGO_PROPS: TLogoProps = {
  in_use: "icon",
  icon: { name: "shapes", color: "#fcbe53" },
};

/**
 * "Create work item type" modal: icon picker + name + description.
 * A newly created type is disabled by default (backend enforces `is_active=false`).
 */
export const CreateTypeModal = observer(function CreateTypeModal(props: TCreateTypeModalProps) {
  const { workspaceSlug, projectId, isOpen, onClose, issueType } = props;
  // states
  const [name, setName] = useState(issueType?.name ?? "");
  const [description, setDescription] = useState(issueType?.description ?? "");
  const [logoProps, setLogoProps] = useState<TLogoProps>(issueType?.logo_props ?? DEFAULT_LOGO_PROPS);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isIconPickerOpen, setIsIconPickerOpen] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  // store hooks
  const { t } = useTranslation();
  const { createWorkItemType, updateWorkItemType } = useIssueType();
  // derived values
  const isEditMode = !!issueType;

  const handleClose = () => {
    setIsSubmitting(false);
    setError(undefined);
    onClose();
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError(t("work_item_types.settings.properties.create_update.errors.name.required"));
      return;
    }
    setIsSubmitting(true);
    try {
      if (isEditMode && issueType) {
        await updateWorkItemType(workspaceSlug, projectId, issueType.id, {
          name: name.trim(),
          description: description.trim(),
          logo_props: logoProps,
        });
        setToast({
          type: "success",
          title: t("work_item_types.update.toast.success.title"),
          message: t("work_item_types.update.toast.success.message", { name: name.trim() }),
        });
      } else {
        await createWorkItemType(workspaceSlug, projectId, {
          name: name.trim(),
          description: description.trim(),
          logo_props: logoProps,
        });
        setToast({
          type: "success",
          title: t("work_item_types.create.toast.success.title"),
          message: t("work_item_types.create.toast.success.message"),
        });
      }
      handleClose();
    } catch (errorData) {
      const errorStatus = errorData as { status?: number; error?: string };
      setToast({
        type: "error",
        title: t("error"),
        message:
          errorStatus?.status === 400
            ? t("work_item_types.create.toast.error.message.conflict", { name: name.trim() })
            : isEditMode
              ? t("work_item_types.update.toast.error.message.default")
              : t("work_item_types.create.toast.error.message.default"),
      });
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} disablePointerDismissal onOpenChange={() => {}}>
      <DialogContent size="md">
        <DialogMain>
          <DialogHeader>
            <DialogHeading>
              <DialogTitle>
                {isEditMode ? t("work_item_types.update.title") : t("work_item_types.create.title")}
              </DialogTitle>
            </DialogHeading>
          </DialogHeader>
          <DialogBody render={<div className="flex flex-col gap-4" />}>
            {/* icon picker */}
            <div className="flex items-center gap-3">
              <EmojiPicker
                isOpen={isIconPickerOpen}
                handleToggle={setIsIconPickerOpen}
                label={
                  <span className="grid size-8 shrink-0 place-items-center rounded-md border border-subtle-1 bg-layer-1">
                    <TypeIcon issueType={{ logo_props: logoProps }} size={16} />
                  </span>
                }
                defaultOpen="icon"
                showEmojiTab={false}
                onChange={(value) => {
                  if (value.type === "icon") {
                    setLogoProps({ in_use: "icon", icon: { name: value.value.name, color: value.value.color } });
                  }
                }}
              />
            </div>
            {/* name */}
            <InputField
              size="lg"
              orientation="vertical"
              id="work-item-type-name"
              type="text"
              name="name"
              aria-label={t("common.name")}
              placeholder={t("work_item_types.create_update.form.name.placeholder")}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setError(undefined);
              }}
              maxLength={100}
              error={error}
              // eslint-disable-next-line jsx-a11y/no-autofocus -- 弹窗打开聚焦名称输入，与正式版一致
              autoFocus
            />
            {/* description */}
            <TextAreaField
              size="lg"
              resize="none"
              autoResize
              maxRows={8}
              id="work-item-type-description"
              name="description"
              aria-label={t("common.description")}
              placeholder={t("work_item_types.create_update.form.description.placeholder")}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </DialogBody>
        </DialogMain>
        <DialogActions>
          <Button
            type="button"
            variant="secondary"
            size="md"
            stretch="auto"
            label={t("common.cancel")}
            onClick={handleClose}
          />
          <Button
            variant="primary"
            size="md"
            stretch="auto"
            loading={isSubmitting}
            disabled={!name.trim()}
            label={isEditMode ? t("common.update") : t("common.add")}
            onClick={() => void handleSubmit()}
          />
        </DialogActions>
      </DialogContent>
    </Dialog>
  );
});
