/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ComponentType } from "react";
import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import {
  BooleanOutline,
  CalendarOutline,
  FileOutline,
  HashOutline,
  LinkOutline,
  ListOutline,
  SearchOutline,
  TextOutline,
  UserOutline,
} from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import type { IIssueProperty } from "@plane/types";
import { EUserProjectRoles } from "@plane/types";
import { setToast } from "@plane/blocks/toast";
// hooks
import { useIssueProperty } from "@/hooks/store/use-issue-property";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import { CreatePropertyModal } from "./create-property-modal";
import { PropertyRowMenu } from "./property-row-menu";
import { propertyTypeLabel } from "./property-type-meta";

type TPropertiesTabProps = {
  workspaceSlug: string;
  projectId: string;
};

const PROPERTY_TYPE_META: Record<string, { icon: ComponentType<{ className?: string }>; color: string }> = {
  text: { icon: TextOutline, color: "#3f76ff" },
  decimal: { icon: HashOutline, color: "#f5a623" },
  option: { icon: ListOutline, color: "#1fb9a5" },
  boolean: { icon: BooleanOutline, color: "#a855f7" },
  date: { icon: CalendarOutline, color: "#eb5757" },
  member: { icon: UserOutline, color: "#0f9d58" },
  rich_text: { icon: FileOutline, color: "#6b7280" },
  url: { icon: LinkOutline, color: "#3f76ff" },
};

/**
 * Properties tab — the project property pool (57 号 §1.2 Tab2): columns
 * 名称｜状态｜类型｜使用中的工作项类型｜row menu (编辑/删除). The "Coming soon"
 * empty state (Step01 1A) is no longer the main path: this tab now manages the pool.
 */
export const PropertiesTab = observer(function PropertiesTab(props: TPropertiesTabProps) {
  const { workspaceSlug, projectId } = props;
  // states
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingProperty, setEditingProperty] = useState<IIssueProperty | undefined>(undefined);
  // hooks
  const { t } = useTranslation();
  const { getPropertiesByProjectId, fetchProjectProperties, arePropertiesFetched, deleteProperty, updateProperty } =
    useIssueProperty();
  const { allowPermissions } = useUserPermissions();
  // derived values
  const projectProperties = getPropertiesByProjectId(projectId);
  const filteredProperties = useMemo(
    () =>
      (projectProperties ?? []).filter((property) =>
        property.name.toLowerCase().includes(searchQuery.trim().toLowerCase())
      ),
    [projectProperties, searchQuery]
  );
  const canPerformActions = allowPermissions(
    [EUserProjectRoles.ADMIN, EUserProjectRoles.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );

  // load the project property pool (fetch is idempotent via store fetchedMap)
  useSWR(
    workspaceSlug && projectId ? `PROJECT_ISSUE_PROPERTIES_${workspaceSlug}_${projectId}` : null,
    async () => {
      if (workspaceSlug && projectId && !arePropertiesFetched(projectId)) {
        await fetchProjectProperties(workspaceSlug, projectId);
      }
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  const handleDelete = async (property: IIssueProperty) => {
    try {
      await deleteProperty(workspaceSlug, projectId, property.id);
      setToast({
        type: "success",
        title: t("work_item_types.settings.properties.toast.delete.success.title"),
        message: t("work_item_types.settings.properties.toast.delete.success.message", { name: property.name }),
      });
    } catch (errorData) {
      // service 层 throw 的是 response.data（{error: string}，无 status 字段），
      // 需同时兜底后端 detail 文案才能命中 400 使用中约束（缺陷 #4）
      const errorPayload = errorData as { status?: number; error?: string };
      const isBoundError =
        errorPayload?.status === 400 ||
        (typeof errorPayload?.error === "string" && errorPayload.error.includes("still bound"));
      setToast({
        type: "error",
        title: t("work_item_types.settings.properties.toast.delete.error.title"),
        message: isBoundError
          ? t("work_item_types.settings.properties.delete_confirmation.bound_error")
          : t("work_item_types.settings.properties.toast.delete.error.message"),
      });
    }
  };

  const handleToggleActive = async (property: IIssueProperty, nextActive: boolean) => {
    try {
      await updateProperty(workspaceSlug, projectId, property.id, { is_active: nextActive });
      setToast({
        type: "success",
        title: t("work_item_types.settings.properties.toast.enable_disable.success.title"),
        message: t("work_item_types.settings.properties.toast.enable_disable.success.message", {
          name: property.name,
          action: nextActive ? t("common.actions.enable").toLowerCase() : t("common.actions.disable").toLowerCase(),
        }),
      });
    } catch {
      setToast({
        type: "error",
        title: t("work_item_types.settings.properties.toast.enable_disable.error.title"),
        message: t("work_item_types.settings.properties.toast.enable_disable.error.message"),
      });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* tab header */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="text-body-sm-medium text-secondary">
            {t("work_item_types.settings.properties.description")}
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
        </div>
        {canPerformActions && (
          <Button
            variant="primary"
            size="md"
            stretch="auto"
            label={t("work_item_types.settings.properties.add_button")}
            onClick={() => {
              setEditingProperty(undefined);
              setIsCreateModalOpen(true);
            }}
          />
        )}
      </div>

      {/* table */}
      <div className="flex flex-col overflow-hidden rounded-lg border border-subtle bg-layer-1">
        {/* header row */}
        <div className="grid grid-cols-[minmax(0,1fr)_140px_140px_200px_48px] items-center border-b border-subtle bg-layer-2 px-4 py-2 text-caption-md-medium text-tertiary">
          <span>{t("work_item_types.settings.properties.list.name_column")}</span>
          <span>{t("work_item_types.settings.properties.list.status_column")}</span>
          <span>{t("work_item_types.settings.properties.list.type_column")}</span>
          <span>{t("work_item_types.settings.properties.list.linked_types_column")}</span>
          <span />
        </div>
        {/* body */}
        {filteredProperties.map((property) => {
          const typeMeta = PROPERTY_TYPE_META[property.property_type] ?? PROPERTY_TYPE_META.text;
          return (
            <div
              key={property.id}
              className="grid grid-cols-[minmax(0,1fr)_140px_140px_200px_48px] items-center border-b border-subtle px-4 py-3 text-body-sm-regular text-primary last:border-b-0"
            >
              {/* name */}
              <div className="flex min-w-0 flex-col">
                <span className="truncate">{property.name}</span>
                {property.description && (
                  <span className="truncate text-caption-md-regular text-tertiary">{property.description}</span>
                )}
              </div>
              {/* status */}
              <div>
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
              </div>
              {/* type */}
              <div>
                <span
                  className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-caption-md-medium"
                  style={{ backgroundColor: `${typeMeta.color}1a`, color: typeMeta.color }}
                >
                  <typeMeta.icon className="size-3" />
                  {propertyTypeLabel(property.property_type, t)}
                </span>
              </div>
              {/* linked type count */}
              <span className="truncate text-secondary">
                {property.issue_type_bindings_count > 0
                  ? property.issue_type_bindings.map((binding) => binding.issue_type_name).join("、")
                  : "0"}
              </span>
              {/* row menu */}
              <div className="flex justify-end">
                {canPerformActions && (
                  <PropertyRowMenu
                    property={property}
                    onEdit={() => setEditingProperty(property)}
                    onDelete={() => handleDelete(property)}
                    onToggleActive={(next) => handleToggleActive(property, next)}
                  />
                )}
              </div>
            </div>
          );
        })}
        {/* empty state: 57 号空态文案（创建入口不再是占位） */}
        {filteredProperties.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
            <p className="text-body-sm-medium text-secondary">
              {t("work_item_types.settings.properties.empty_state.no_properties_description")}
            </p>
          </div>
        )}
      </div>

      {/* create / edit modal（编辑入口单独打开：editingProperty 即弹窗开关，缺陷 #1） */}
      {(isCreateModalOpen || !!editingProperty) && (
        <CreatePropertyModal
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          isOpen={isCreateModalOpen || !!editingProperty}
          onClose={() => {
            setIsCreateModalOpen(false);
            setEditingProperty(undefined);
          }}
          issueProperty={editingProperty}
        />
      )}
    </div>
  );
});
