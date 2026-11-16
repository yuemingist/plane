/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
import { observer } from "mobx-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { EWorkflowChangeAction, IWorkflow, IWorkflowChangeLog } from "@plane/types";
import { cn } from "@plane/utils";
import { Avatar } from "@makeplane/propel/components/avatar";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { SortAscendingOutline, CloseOutline } from "@makeplane/propel/icons";
import { calculateTimeAgo } from "@plane/utils";
import { WorkflowService } from "@/services/workflow.service";

type TWorkflowChangeHistoryPanelProps = {
  workspaceSlug: string;
  projectId: string;
  workflow: IWorkflow;
  handleClose: () => void;
};

/**
 * Right slide-out "Change history" panel (cloud parity, 58号 screenshot 4).
 * The cloud Business tier shows an empty panel (rule-level changes are
 * Enterprise-only); the CE shell records lifecycle events (enable/disable/
 * re-enable) so the feature has readable data — segment product plan §2.5.
 */
export const WorkflowChangeHistoryPanel = observer(function WorkflowChangeHistoryPanel(
  props: TWorkflowChangeHistoryPanelProps
) {
  const { workspaceSlug, projectId, workflow, handleClose } = props;
  // hooks
  const { t } = useTranslation();
  const workflowService = new WorkflowService();

  const { data: changeLogs } = useSWR(
    workspaceSlug && projectId && workflow?.id ? `WORKFLOW_CHANGE_HISTORY_${workflow.id}` : null,
    async () => {
      const response = await workflowService.getWorkflowChangeHistory(workspaceSlug, projectId, workflow.id);
      return response ?? [];
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  const renderActionLabel = (action: EWorkflowChangeAction) => {
    switch (action) {
      case "enabled":
        return t("workflows.settings.history.action.enabled");
      case "disabled":
        return t("workflows.settings.history.action.disabled");
      case "re_enabled":
        return t("workflows.settings.history.action.re_enabled");
      default:
        return action;
    }
  };

  return (
    <>
      {/* backdrop */}
      {/* oxlint-disable-next-line jsx_a11y/click-events-have-key-events jsx_a11y/no-static-element-interactions */}
      <div className="fixed inset-0 z-20 bg-black/30" onClick={handleClose} />
      {/* panel */}
      <div className="shadow-xl fixed inset-y-0 right-0 z-30 flex w-full max-w-[420px] flex-col border-l border-subtle bg-layer-1">
        {/* header: title + sort glyph (cloud shows it; interaction not observed — rendered inert) + close */}
        <div className="flex items-center justify-between gap-2 border-b border-subtle px-4 py-3">
          <h4 className="text-body-md-medium text-primary">{t("common.change_history")}</h4>
          <div className="flex items-center gap-1">
            <IconButton
              type="button"
              variant="ghost"
              size="xs"
              aria-label={t("common.sort.label")}
              icon={<Icon icon={SortAscendingOutline} />}
              disabled
            />
            <IconButton
              type="button"
              variant="ghost"
              size="xs"
              aria-label={t("close")}
              icon={<Icon icon={CloseOutline} />}
              onClick={handleClose}
            />
          </div>
        </div>
        {/* entries */}
        <div className="vertical-scrollbar scrollbar-sm flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-4">
          {(changeLogs ?? []).length === 0 && (
            <p className="text-body-sm-regular text-tertiary">{t("workflows.settings.history.empty")}</p>
          )}
          {(changeLogs ?? []).map((log: IWorkflowChangeLog) => (
            <div key={log.id} className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                {log.actor_detail ? (
                  <Avatar
                    src={log.actor_detail.avatar || undefined}
                    fallback={log.actor_detail.display_name || log.actor_detail.first_name || "?"}
                    size="sm"
                  />
                ) : null}
                <span className="text-body-sm-medium text-primary">{renderActionLabel(log.action)}</span>
              </div>
              <div className={cn("flex items-center gap-2 text-caption-md-regular text-tertiary")}>
                {log.actor_detail && <span>{log.actor_detail.display_name || log.actor_detail.first_name}</span>}
                <span>·</span>
                <span>{calculateTimeAgo(log.created_at)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
});
