/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useRouter } from "next/navigation";
import { ArrowNarrowLeftOutline, DefaultTabOutline } from "@makeplane/propel/icons";
import { Button } from "@makeplane/propel/components/button";
import { Switch } from "@makeplane/propel/components/switch";
import { useTranslation } from "@plane/i18n";
import { setToast } from "@plane/blocks/toast";
// helpers
import { cn } from "@plane/utils";
// hooks
import { useIssueType } from "@/hooks/store/use-issue-type";
// local imports
import { CreateTypeModal } from "./create-type-modal";
import { PropertiesTab } from "./properties-tab";
import { TypeIcon } from "./type-icon";

type TTypeDetailRootProps = {
  workspaceSlug: string;
  projectId: string;
  issueTypeId: string;
};

/**
 * Type detail page: header (icon + name + enable/disable toggle) and the properties
 * empty state. The toggle mirrors the row menu's enable/disable action.
 */
export const TypeDetailRoot = observer(function TypeDetailRoot(props: TTypeDetailRootProps) {
  const { workspaceSlug, projectId, issueTypeId } = props;
  // states
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  // hooks
  const { t } = useTranslation();
  const router = useRouter();
  const { getTypeById, updateWorkItemType, markWorkItemTypeAsDefault } = useIssueType();
  // derived values
  const issueType = getTypeById(issueTypeId);

  if (!issueType) {
    return (
      <div className={cn("flex flex-col items-start gap-3")}>
        <Button
          variant="ghost"
          size="sm"
          stretch="auto"
          label={t("common.back")}
          icon={<ArrowNarrowLeftOutline className="size-3.5" />}
          onClick={() => router.push(`/${workspaceSlug}/settings/projects/${projectId}/work-item-types/`)}
        />
        <p className="text-body-sm-regular text-tertiary">{t("common.search.no_results.title")}</p>
      </div>
    );
  }

  const handleToggleActive = async (checked: boolean) => {
    setIsToggling(true);
    try {
      await updateWorkItemType(workspaceSlug, projectId, issueType.id, { is_active: checked });
      setToast({
        type: "success",
        title: t("work_item_types.enable_disable.toast.success.title"),
        message: t("work_item_types.enable_disable.toast.success.message", {
          action: checked ? t("common.actions.enable").toLowerCase() : t("common.actions.disable").toLowerCase(),
          name: issueType.name,
        }),
      });
    } catch {
      setToast({
        type: "error",
        title: t("error"),
        message: t("common.something_went_wrong"),
      });
    } finally {
      setIsToggling(false);
    }
  };

  const handleMarkDefault = async () => {
    setIsToggling(true);
    try {
      await markWorkItemTypeAsDefault(workspaceSlug, projectId, issueType.id);
    } catch {
      setToast({
        type: "error",
        title: t("error"),
        message: t("common.something_went_wrong"),
      });
    } finally {
      setIsToggling(false);
    }
  };

  // set-as-default entry (BUG-03 裁决口径): active non-default types only; Epic keeps "disable only"
  const canMarkDefault = issueType.is_active && !issueType.is_default && !issueType.is_epic;

  return (
    <div className="flex flex-col gap-6">
      {/* detail header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            stretch="auto"
            label={t("common.back")}
            icon={<ArrowNarrowLeftOutline className="size-3.5" />}
            onClick={() => router.push(`/${workspaceSlug}/settings/projects/${projectId}/work-item-types/`)}
          />
          <TypeIcon issueType={issueType} size={20} />
          <span className="truncate text-h5-medium text-primary">{issueType.name}</span>
          {issueType.is_default && (
            <span className="rounded-full border border-accent-strong/40 bg-accent-primary/10 px-2 py-0.5 text-caption-md-medium text-accent-primary">
              {t("common.default")}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {canMarkDefault && (
            <Button
              variant="secondary"
              size="sm"
              stretch="auto"
              label={t("work_item_types.settings.set_as_default")}
              icon={<DefaultTabOutline className="size-3.5" />}
              disabled={isToggling}
              onClick={() => void handleMarkDefault()}
            />
          )}
          {issueType.is_active ? (
            <span className="text-caption-md-regular text-tertiary">
              {t("work_item_types.settings.properties.enable_disable.label")}
            </span>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              stretch="auto"
              label={t("common.actions.edit")}
              onClick={() => setIsEditModalOpen(true)}
            />
          )}
          <Switch
            size="sm"
            checked={issueType.is_active}
            disabled={isToggling || issueType.is_default}
            onCheckedChange={(checked) => void handleToggleActive(checked)}
            aria-label={t("work_item_types.enable_disable.tooltip", {
              action: issueType.is_active
                ? t("common.actions.disable").toLowerCase()
                : t("common.actions.enable").toLowerCase(),
            })}
          />
        </div>
      </div>

      {/* properties empty state (detail variant, no tab title) */}
      <PropertiesTab variant="detail" />

      {isEditModalOpen && (
        <CreateTypeModal
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          issueType={issueType}
        />
      )}
    </div>
  );
});
