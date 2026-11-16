/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { IState, IWorkflowTransition, IWorkflowTransitionGroup } from "@plane/types";
import { Button } from "@makeplane/propel/components/button";
import { setToast } from "@plane/blocks/toast";
// hooks
import { useProjectState } from "@/hooks/store/use-project-state";
// local imports
import { WorkflowService } from "@/services/workflow.service";

type TWorkflowTransitionsPanelProps = {
  workspaceSlug: string;
  projectId: string;
  workflowId: string;
};

/**
 * 流转规则配置面板（Step02 段 3，CE 设计最简形态——云端 Business 档无规则
 * 配置界面可对照，58 号 §1.3 边界行）：「状态 × 允许移动到」chip 矩阵，
 * 点 chip 即勾选/取消，显式保存（全量替换 PUT）。
 * 语义（段 3 产品方案 A2）：某源状态未勾选任何目标 = 该源状态不受限（默认全部允许）。
 */
export const WorkflowTransitionsPanel = observer(function WorkflowTransitionsPanel(
  props: TWorkflowTransitionsPanelProps
) {
  const { workspaceSlug, projectId, workflowId } = props;
  // states: 本地勾选矩阵 / 用户是否改动过（保存按钮门控）
  const [allowedMap, setAllowedMap] = useState<Record<string, string[]> | undefined>(undefined);
  const [hasEdits, setHasEdits] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // hooks
  const { t } = useTranslation();
  const { getProjectStates, fetchProjectStates } = useProjectState();
  const workflowService = new WorkflowService();
  // derived values
  const states: IState[] = getProjectStates(projectId) ?? [];

  // 面板直开时项目状态可能尚未拉取：兜底拉取（幂等，store 门控）
  useSWR(
    workspaceSlug && projectId ? `WORKFLOW_TRANSITIONS_STATES_${workspaceSlug}_${projectId}` : null,
    async () => {
      if (workspaceSlug && projectId && getProjectStates(projectId) === undefined) {
        await fetchProjectStates(workspaceSlug, projectId);
      }
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  // 拉取既有规则（按源状态分组）
  useSWR(
    workspaceSlug && projectId && workflowId
      ? `WORKFLOW_TRANSITIONS_${workspaceSlug}_${projectId}_${workflowId}`
      : null,
    async () => {
      const rows: IWorkflowTransition[] = await workflowService.getWorkflowTransitions(
        workspaceSlug,
        projectId,
        workflowId
      );
      const grouped: Record<string, string[]> = {};
      rows.forEach((row) => {
        grouped[row.from_state] = [...(grouped[row.from_state] ?? []), row.to_state];
      });
      setAllowedMap(grouped);
      setHasEdits(false);
      return rows;
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  const handleToggle = (fromStateId: string, toStateId: string) => {
    if (fromStateId === toStateId) return;
    setHasEdits(true);
    setAllowedMap((previous) => {
      const current = previous?.[fromStateId] ?? [];
      const next = current.includes(toStateId) ? current.filter((id) => id !== toStateId) : [...current, toStateId];
      return { ...previous, [fromStateId]: next };
    });
  };

  const handleSave = async () => {
    if (isSubmitting || allowedMap === undefined) return;
    setIsSubmitting(true);
    try {
      const groups: IWorkflowTransitionGroup[] = states
        .filter((state) => (allowedMap[state.id] ?? []).length > 0)
        .map((state) => ({ from_state: state.id, to_states: allowedMap[state.id] }));
      const rows = await workflowService.updateWorkflowTransitions(workspaceSlug, projectId, workflowId, groups);
      const grouped: Record<string, string[]> = {};
      rows.forEach((row) => {
        grouped[row.from_state] = [...(grouped[row.from_state] ?? []), row.to_state];
      });
      setAllowedMap(grouped);
      setHasEdits(false);
      setToast({
        type: "success",
        title: t("workflows.settings.transitions.toasts.success.title"),
        message: t("workflows.settings.transitions.toasts.success.message"),
      });
    } catch {
      setToast({
        type: "error",
        title: t("workflows.settings.transitions.toasts.error.title"),
        message: t("workflows.settings.transitions.toasts.error.message"),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (allowedMap === undefined) {
    return <p className="px-1 py-2 text-caption-md-regular text-tertiary">{t("common.loading")}</p>;
  }

  return (
    <div className="flex flex-col gap-3 px-1 pb-1">
      <p className="text-caption-md-regular text-tertiary">{t("workflows.settings.transitions.description")}</p>
      {/* chip 矩阵：每行 = 源状态 + 允许移动到的目标状态 chips（点选即切换） */}
      <div className="flex flex-col gap-2">
        {states.map((state) => (
          <div key={state.id} className="flex flex-wrap items-center gap-1.5">
            <span className="inline-flex min-w-32 items-center gap-1.5 text-body-sm-medium text-primary">
              <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: state.color }} />
              {state.name}
            </span>
            <span className="text-caption-md-regular text-tertiary">{t("workflows.settings.transitions.move_to")}</span>
            {states
              .filter((candidate) => candidate.id !== state.id)
              .map((candidate) => {
                const isEnabled = (allowedMap[state.id] ?? []).includes(candidate.id);
                return (
                  <button
                    key={candidate.id}
                    type="button"
                    onClick={() => handleToggle(state.id, candidate.id)}
                    className={
                      isEnabled
                        ? "inline-flex items-center gap-1 rounded-full bg-accent-primary/10 px-2 py-0.5 text-caption-md-medium text-accent-primary"
                        : "inline-flex items-center gap-1 rounded-full bg-layer-2 px-2 py-0.5 text-caption-md-medium text-tertiary"
                    }
                  >
                    <span
                      className="size-1.5 shrink-0 rounded-full"
                      style={isEnabled ? { backgroundColor: candidate.color } : undefined}
                    />
                    {candidate.name}
                  </button>
                );
              })}
            {(allowedMap[state.id] ?? []).length === 0 && (
              <span className="text-caption-md-regular text-tertiary">
                {t("workflows.settings.transitions.unrestricted")}
              </span>
            )}
          </div>
        ))}
      </div>
      <div>
        <Button
          type="button"
          variant="primary"
          size="sm"
          stretch="auto"
          loading={isSubmitting}
          disabled={!hasEdits}
          label={t("common.save")}
          onClick={() => void handleSave()}
        />
      </div>
    </div>
  );
});
