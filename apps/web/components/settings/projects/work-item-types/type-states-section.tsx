/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@makeplane/propel/components/button";
import { Checkbox } from "@makeplane/propel/components/checkbox";
import { useTranslation } from "@plane/i18n";
import { setToast } from "@plane/blocks/toast";
import type { IState } from "@plane/types";
import { EUserProjectRoles } from "@plane/types";
// hooks
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useUserPermissions } from "@/hooks/store/user";

type TTypeStatesSectionProps = {
  workspaceSlug: string;
  projectId: string;
  typeId: string;
};

/**
 * 类型详情页「可用状态」配置区（Step02 段 5）：从项目状态池逐项勾选该类型可用的状态。
 * 空集合 = 继承项目全量状态池（产品方案 A2）。CE 自行设计的配置面（云端 Business 无对照，
 * 产品方案 §2.1），文案为 CE 自拟（A7）。
 */
export const TypeStatesSection = observer(function TypeStatesSection(props: TTypeStatesSectionProps) {
  const { workspaceSlug, projectId, typeId } = props;
  // states
  const [selectedStateIds, setSelectedStateIds] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  // hooks
  const { t } = useTranslation();
  const { getTypeById, updateWorkItemTypeStates } = useIssueType();
  const { getProjectStateIds, getStateById, fetchProjectStates } = useProjectState();
  const { allowPermissions } = useUserPermissions();
  // derived values
  const issueType = getTypeById(typeId);
  const projectStateIds = getProjectStateIds(projectId);
  const canPerformActions = allowPermissions(
    [EUserProjectRoles.ADMIN, EUserProjectRoles.MEMBER],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );

  // ensure the project state pool is loaded
  useSWR(
    workspaceSlug && projectId ? `PROJECT_STATES_${workspaceSlug}_${projectId}` : null,
    async () => {
      if (workspaceSlug && projectId && !projectStateIds) {
        await fetchProjectStates(workspaceSlug, projectId);
      }
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  // sync local selection from the store value (and reset dirty flag)
  useEffect(() => {
    setSelectedStateIds(issueType?.state_ids ?? []);
    setIsDirty(false);
  }, [issueType?.id, issueType?.state_ids]);

  const projectStates = useMemo<IState[]>(() => {
    // 非链式原地排序：oxlint fixer 会把链尾 .sort 改写为 .toSorted（ES2022 lib 无该类型，编译失败）
    const states = (projectStateIds ?? [])
      .map((stateId) => getStateById(stateId))
      .filter((state): state is IState => !!state);
    states.sort((a, b) => a.sequence - b.sequence);
    return states;
  }, [projectStateIds, getStateById]);

  const handleToggle = (stateId: string, checked: boolean) => {
    setSelectedStateIds((previous) => (checked ? [...previous, stateId] : previous.filter((id) => id !== stateId)));
    setIsDirty(true);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateWorkItemTypeStates(workspaceSlug, projectId, typeId, selectedStateIds);
      setIsDirty(false);
      setToast({
        type: "success",
        title: t("work_item_types.states.toasts.success.title"),
        message: t("work_item_types.states.toasts.success.message"),
      });
    } catch {
      setToast({
        type: "error",
        title: t("work_item_types.states.toasts.error.title"),
        message: t("work_item_types.states.toasts.error.message"),
      });
    } finally {
      setIsSaving(false);
    }
  };

  if (!issueType) return null;

  return (
    <div className="flex flex-col gap-3">
      {/* section header + save */}
      <div className="flex items-center justify-between gap-4">
        <span className="text-body-sm-medium text-secondary">{t("work_item_types.states.title")}</span>
        {canPerformActions && (
          <Button
            type="button"
            variant="primary"
            size="sm"
            stretch="auto"
            label={t("common.save")}
            loading={isSaving}
            disabled={!isDirty}
            onClick={() => void handleSave()}
          />
        )}
      </div>
      <p className="text-caption-md-regular text-tertiary">{t("work_item_types.states.description")}</p>
      {!canPerformActions && (
        <p className="text-caption-md-regular text-tertiary">{t("work_item_types.states.readonly_hint")}</p>
      )}

      {/* state pool with per-state checkboxes */}
      <div className="flex flex-col overflow-hidden rounded-lg border border-subtle bg-layer-1">
        {projectStates.map((state) => (
          <label
            key={state.id}
            className={
              canPerformActions
                ? "flex cursor-pointer items-center gap-3 border-b border-subtle px-4 py-3 text-body-sm-regular text-primary last:border-b-0 hover:bg-layer-transparent-hover"
                : "flex items-center gap-3 border-b border-subtle px-4 py-3 text-body-sm-regular text-primary last:border-b-0"
            }
          >
            <Checkbox
              checked={selectedStateIds.includes(state.id)}
              disabled={!canPerformActions}
              onCheckedChange={(checked) => handleToggle(state.id, !!checked)}
            />
            <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: state.color }} />
            <span className="min-w-0 flex-1 truncate">{state.name}</span>
          </label>
        ))}
        {projectStates.length === 0 && (
          <div className="px-4 py-6 text-center text-caption-md-regular text-tertiary">
            {t("common.search.no_results.title")}
          </div>
        )}
      </div>

      {/* inherit-all hint (CE 自拟文案，产品方案 A2/A7) */}
      <p className="text-caption-md-regular text-tertiary">
        {selectedStateIds.length === 0
          ? t("work_item_types.states.inherit_hint.active")
          : t("work_item_types.states.inherit_hint.configured")}
      </p>
    </div>
  );
});
