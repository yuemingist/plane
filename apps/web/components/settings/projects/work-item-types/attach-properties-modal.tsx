/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
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
import { Checkbox } from "@makeplane/propel/components/checkbox";
import { useTranslation } from "@plane/i18n";
import { setToast } from "@plane/blocks/toast";
import type { TIssuePropertyType } from "@plane/types";
// hooks
import { useIssueProperty } from "@/hooks/store/use-issue-property";
// local imports
import { propertyTypeLabel } from "./property-type-meta";

type TAttachPropertiesModalProps = {
  workspaceSlug: string;
  projectId: string;
  typeId: string;
  /** already-bound property ids are hidden from the picker */
  boundPropertyIds: string[];
  onClose: () => void;
};

/**
 * 「添加属性」弹窗（57 号 §3.4 步骤 2）：搜索框 + 属性行
 * （复选框 + 状态 badge + 类型 badge）+ 取消/添加（未选时禁用），多选。
 * 候选列表来自项目属性池：本弹窗可能在类型详情页直接打开（属性池未加载过），
 * 打开时兜底拉取，避免误报「所有属性均已关联」（缺陷 #3）。
 */
export const AttachPropertiesModal = observer(function AttachPropertiesModal(props: TAttachPropertiesModalProps) {
  const { workspaceSlug, projectId, typeId, boundPropertyIds, onClose } = props;
  // states
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // hooks
  const { t } = useTranslation();
  const { getPropertiesByProjectId, arePropertiesFetched, fetchProjectProperties, bindProperties } = useIssueProperty();
  // derived values
  // 缺陷 #7 根因：useMemo 依赖里没有 store 的响应式读取结果——直载类型详情时池在弹窗
  // 打开后才加载完成，首次渲染算出的空数组被 memo 缓存，池到位后依赖不变不重算，
  // 空态误报「所有属性均已关联」。改为渲染期先读 store（observer 据此追踪重渲染），
  // 再以读到的数组引用作为 memo 依赖做过滤。
  const projectProperties = getPropertiesByProjectId(projectId);
  const availableProperties = useMemo(
    () =>
      (projectProperties ?? [])
        .filter((property) => !boundPropertyIds.includes(property.id))
        .filter((property) => property.name.toLowerCase().includes(searchQuery.trim().toLowerCase())),
    [projectProperties, boundPropertyIds, searchQuery]
  );

  // 类型详情页直开时属性池可能尚未加载：兜底拉取（fetch 幂等，store fetchedMap 门控）
  useSWR(
    workspaceSlug && projectId ? `ATTACH_PROPERTIES_MODAL_POOL_${workspaceSlug}_${projectId}` : null,
    async () => {
      if (workspaceSlug && projectId && !arePropertiesFetched(projectId)) {
        await fetchProjectProperties(workspaceSlug, projectId);
      }
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  const handleAdd = async () => {
    if (selectedIds.length === 0) return;
    setIsSubmitting(true);
    try {
      await bindProperties(workspaceSlug, projectId, typeId, selectedIds);
      setToast({
        type: "success",
        title: t("success"),
        message: t("work_item_types.settings.linked_properties.add_button"),
      });
      onClose();
    } catch {
      setToast({ type: "error", title: t("error"), message: t("common.something_went_wrong") });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open disablePointerDismissal onOpenChange={() => {}}>
      <DialogContent size="md">
        <DialogMain>
          <DialogHeader>
            <DialogHeading>
              <DialogTitle>{t("work_item_types.settings.linked_properties.modal.title")}</DialogTitle>
            </DialogHeading>
          </DialogHeader>
          <DialogBody render={<div className="flex flex-col gap-3" />}>
            <input
              type="text"
              className="rounded-md border border-subtle bg-layer-1 px-2 py-1.5 text-body-sm-regular text-primary outline-none focus:border-accent-strong"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder={t("work_item_types.settings.linked_properties.modal.search_placeholder")}
            />
            <div className="flex max-h-72 flex-col overflow-y-auto rounded-md border border-subtle">
              {availableProperties.map((property) => (
                <label
                  key={property.id}
                  className="flex cursor-pointer items-center gap-3 border-b border-subtle px-3 py-2 text-body-sm-regular text-primary last:border-b-0 hover:bg-layer-transparent-hover"
                >
                  <Checkbox
                    checked={selectedIds.includes(property.id)}
                    onCheckedChange={(checked) =>
                      setSelectedIds((previous) =>
                        checked ? [...previous, property.id] : previous.filter((id) => id !== property.id)
                      )
                    }
                  />
                  <span className="min-w-0 flex-1 truncate">{property.name}</span>
                  <span
                    className={
                      property.is_active
                        ? "inline-flex items-center rounded-full bg-success-primary/10 px-2 py-0.5 text-caption-md-medium text-success-primary"
                        : "inline-flex items-center rounded-full bg-layer-2 px-2 py-0.5 text-caption-md-medium text-tertiary"
                    }
                  >
                    {property.is_active
                      ? t("work_item_types.settings.properties.enable_disable.label")
                      : t("common.disabled")}
                  </span>
                  <span className="rounded-full border border-subtle px-2 py-0.5 text-caption-md-medium text-tertiary">
                    {propertyTypeLabel(property.property_type as TIssuePropertyType, t)}
                  </span>
                </label>
              ))}
              {availableProperties.length === 0 && (
                <div className="flex flex-col items-center gap-1 px-3 py-6 text-center">
                  {!arePropertiesFetched(projectId) ? (
                    // 属性池加载中：不能显示「所有属性均已关联」误报文案（缺陷 #3）
                    <p className="text-caption-md-regular text-tertiary">{t("common.loading")}</p>
                  ) : (
                    <>
                      <p className="text-body-sm-medium text-secondary">
                        {searchQuery
                          ? t("work_item_types.settings.linked_properties.modal.empty_search")
                          : t("work_item_types.settings.linked_properties.modal.empty.title")}
                      </p>
                      {!searchQuery && (
                        <p className="text-caption-md-regular text-tertiary">
                          {t("work_item_types.settings.linked_properties.modal.empty.description")}
                        </p>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          </DialogBody>
        </DialogMain>
        <DialogActions>
          <Button
            type="button"
            variant="secondary"
            size="md"
            stretch="auto"
            label={t("common.cancel")}
            onClick={onClose}
          />
          <Button
            type="button"
            variant="primary"
            size="md"
            stretch="auto"
            loading={isSubmitting}
            disabled={selectedIds.length === 0}
            label={t("common.add")}
            onClick={() => void handleAdd()}
          />
        </DialogActions>
      </DialogContent>
    </Dialog>
  );
});
