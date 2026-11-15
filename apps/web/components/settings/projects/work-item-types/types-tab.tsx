/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import { useRouter } from "next/navigation";
import { EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { FilterOutline, SearchOutline, SortAscendingOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import type { IIssueType } from "@plane/types";
import { EUserProjectRoles } from "@plane/types";
// helpers
import { cn } from "@plane/utils";
// hooks
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import { CreateTypeModal } from "./create-type-modal";
import { TypeIcon } from "./type-icon";
import { TypeRowMenu } from "./type-row-menu";

type TTypesTabProps = {
  workspaceSlug: string;
  projectId: string;
};

/**
 * Types tab: "Types N" count + search + (locked) filter/sort controls + add button,
 * with the type table (icon + name + default badge | status badge | reference count | row menu).
 */
export const TypesTab = observer(function TypesTab(props: TTypesTabProps) {
  const { workspaceSlug, projectId } = props;
  // states
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingType, setEditingType] = useState<IIssueType | undefined>(undefined);
  // hooks
  const { t } = useTranslation();
  const router = useRouter();
  const { getTypesByProjectId, updateWorkItemType, deleteWorkItemType, markWorkItemTypeAsDefault } = useIssueType();
  const { allowPermissions } = useUserPermissions();
  // derived values
  const projectTypes = getTypesByProjectId(projectId);
  const filteredTypes = useMemo(
    () => (projectTypes ?? []).filter((type) => type.name.toLowerCase().includes(searchQuery.trim().toLowerCase())),
    [projectTypes, searchQuery]
  );
  const canPerformActions = allowPermissions(
    [EUserProjectRoles.ADMIN, EUserProjectRoles.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );

  const handleRowClick = (issueType: IIssueType) => {
    router.push(`/${workspaceSlug}/settings/projects/${projectId}/work-item-types/types/${issueType.id}`);
  };

  return (
    <div className="flex flex-col gap-4">
      {/* tab header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="text-body-sm-medium text-secondary">
            {t("work_item_types.settings.types.count_label", { count: projectTypes?.length ?? 0 })}
          </span>
          {isSearchOpen ? (
            <input
              type="text"
              className="w-44 rounded-md border border-subtle bg-layer-1 px-2 py-1 text-caption-md-regular text-primary outline-none focus:border-accent-strong"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onBlur={() => {
                if (!searchQuery) setIsSearchOpen(false);
              }}
              placeholder={t("common.search.placeholder")}
              // eslint-disable-next-line jsx-a11y/no-autofocus -- 展开搜索即聚焦，与正式版一致
              autoFocus
            />
          ) : (
            <IconButton
              variant="ghost"
              size="xs"
              icon={<Icon icon={SearchOutline} />}
              aria-label={t("common.search.label")}
              onClick={() => setIsSearchOpen(true)}
            />
          )}
          {/* filter/sort interactions were not observed on the cloud page (57号 §8-Q6): rendered
              as locked buttons pending cloud evidence, no invented behavior */}
          <IconButton
            variant="ghost"
            size="xs"
            icon={<Icon icon={FilterOutline} />}
            aria-label={t("common.filters")}
            disabled
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            stretch="auto"
            label={t("common.sort.label")}
            icon={<Icon icon={SortAscendingOutline} />}
            disabled
          />
        </div>
        {canPerformActions && (
          <Button
            variant="primary"
            size="md"
            stretch="auto"
            label={t("work_item_types.create.button")}
            onClick={() => setIsCreateModalOpen(true)}
          />
        )}
      </div>

      {/* table */}
      <div className="flex flex-col overflow-hidden rounded-lg border border-subtle bg-layer-1">
        {/* header row */}
        <div className="grid grid-cols-[minmax(0,1fr)_160px_120px_48px] items-center border-b border-subtle bg-layer-2 px-4 py-2 text-caption-md-medium text-tertiary">
          <span>{t("work_item_types.label_lowercase")}</span>
          <span>{t("work_item_types.settings.types.table.status_column")}</span>
          <span>{t("work_item_types.settings.types.table.work_items_count_column")}</span>
          <span />
        </div>
        {/* body */}
        {filteredTypes.map((issueType) => (
          // oxlint-disable-next-line jsx_a11y/click-events-have-key-events jsx_a11y/no-static-element-interactions
          <div
            key={issueType.id}
            className="grid cursor-pointer grid-cols-[minmax(0,1fr)_160px_120px_48px] items-center border-b border-subtle px-4 py-3 text-body-sm-regular text-primary last:border-b-0 hover:bg-layer-transparent-hover"
            onClick={() => handleRowClick(issueType)}
          >
            {/* name */}
            <div className="flex min-w-0 items-center gap-2">
              <TypeIcon issueType={issueType} size={16} />
              <span className="truncate">{issueType.name}</span>
              {issueType.is_default && (
                <span className="shrink-0 rounded-full border border-accent-strong/40 bg-accent-primary/10 px-2 py-0.5 text-caption-md-medium text-accent-primary">
                  {t("common.default")}
                </span>
              )}
            </div>
            {/* status */}
            <div>
              {issueType.is_active ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-success-primary/10 px-2 py-0.5 text-caption-md-medium text-success-primary">
                  <span className="size-1.5 rounded-full bg-success-primary" />
                  {t("work_item_types.settings.properties.enable_disable.label")}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-layer-2 px-2 py-0.5 text-caption-md-medium text-tertiary">
                  {t("common.disabled")}
                </span>
              )}
            </div>
            {/* reference count */}
            <span className="text-secondary">{issueType.issues_count ?? 0}</span>
            {/* row menu */}
            {/* oxlint-disable-next-line jsx_a11y/click-events-have-key-events jsx_a11y/no-static-element-interactions */}
            <div className="flex justify-end" onClick={(e) => e.stopPropagation()}>
              {canPerformActions && (
                <TypeRowMenu
                  issueType={issueType}
                  onEdit={() => setEditingType(issueType)}
                  onUpdate={(data) => updateWorkItemType(workspaceSlug, projectId, issueType.id, data)}
                  onDelete={() => deleteWorkItemType(workspaceSlug, projectId, issueType.id)}
                  onMarkDefault={() => markWorkItemTypeAsDefault(workspaceSlug, projectId, issueType.id)}
                />
              )}
            </div>
          </div>
        ))}
        {filteredTypes.length === 0 && (
          <div className={cn("px-4 py-6 text-center text-body-sm-regular text-tertiary")}>
            {t("common.search.no_results.title")}
          </div>
        )}
      </div>

      {/* create / edit modal */}
      {isCreateModalOpen && (
        <CreateTypeModal
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          isOpen={isCreateModalOpen}
          onClose={() => {
            setIsCreateModalOpen(false);
            setEditingType(undefined);
          }}
          issueType={editingType}
        />
      )}
    </div>
  );
});
