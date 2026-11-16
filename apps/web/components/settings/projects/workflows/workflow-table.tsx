/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { IWorkflow } from "@plane/types";
import { ChevronDownOutline, ChevronRightOutline } from "@makeplane/propel/icons";
// local imports
import { WorkflowRowMenu } from "./workflow-row-menu";
import { WorkflowTransitionsPanel } from "./workflow-transitions-panel";

type TWorkflowTableProps = {
  workspaceSlug: string;
  workflow: IWorkflow;
  canPerformActions: boolean;
  onRequestDisable: () => void;
  onRequestHistory: () => void;
};

/**
 * The enabled-state table (cloud parity, 58号 screenshot 2):
 * section title "Workflows" + one Default Workflow row
 * (name verbatim in English / active badge / all states / all work item types).
 * The row body is intentionally not clickable — the cloud page has no rule editor (58号 §3.6 step 3).
 */
export const WorkflowTable = observer(function WorkflowTable(props: TWorkflowTableProps) {
  const { workspaceSlug, workflow, canPerformActions, onRequestDisable, onRequestHistory } = props;
  // states: 行内展开流转规则面板（段 3 CE 设计，云端无对照——产品方案 §2.1）
  const [isTransitionsOpen, setIsTransitionsOpen] = useState(false);
  // hooks
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-3">
      <h5 className="text-body-md-medium text-primary">{t("workflows.settings.table.title")}</h5>
      <div className="flex flex-col overflow-hidden rounded-lg border border-subtle bg-layer-1">
        {/* header row */}
        <div className="grid grid-cols-[minmax(0,1fr)_160px_160px_minmax(0,1fr)_48px] items-center border-b border-subtle bg-layer-2 px-4 py-2 text-caption-md-medium text-tertiary">
          <span>{t("workflows.settings.table.columns.workflow")}</span>
          <span>{t("workflows.settings.table.columns.status")}</span>
          <span>{t("workflows.settings.table.columns.states")}</span>
          <span>{t("workflows.settings.table.columns.work_item_types")}</span>
          <span />
        </div>
        {/* body row: the single Default Workflow */}
        <div className="grid grid-cols-[minmax(0,1fr)_160px_160px_minmax(0,1fr)_48px] items-center border-b border-subtle px-4 py-3 text-body-sm-regular text-primary last:border-b-0">
          {/* name — the cloud page shows the literal "Default Workflow" even in zh UI */}
          <span className="truncate">{workflow.name}</span>
          {/* status badge */}
          {workflow.is_active ? (
            <span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-success-primary/10 px-2 py-0.5 text-caption-md-medium text-success-primary">
                <span className="size-1.5 rounded-full bg-success-primary" />
                {t("common.active")}
              </span>
            </span>
          ) : (
            <span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-layer-2 px-2 py-0.5 text-caption-md-medium text-tertiary">
                {t("common.disabled")}
              </span>
            </span>
          )}
          {/* states coverage */}
          <span className="text-secondary">{t("workflows.settings.table.states.all")}</span>
          {/* work item types coverage */}
          <span className="text-secondary">{t("workflows.settings.table.work_item_types.all")}</span>
          {/* row actions: transition-rules expand toggle (segment 3) + row menu */}
          <div className="flex items-center justify-end gap-1">
            {canPerformActions && (
              <button
                type="button"
                className="flex size-7 items-center justify-center rounded text-tertiary hover:bg-layer-transparent-hover"
                aria-label={t("workflows.settings.transitions.toggle")}
                onClick={() => setIsTransitionsOpen((previous) => !previous)}
              >
                {isTransitionsOpen ? (
                  <ChevronDownOutline className="size-3.5" />
                ) : (
                  <ChevronRightOutline className="size-3.5" />
                )}
              </button>
            )}
            {canPerformActions && (
              <WorkflowRowMenu onRequestDisable={onRequestDisable} onRequestHistory={onRequestHistory} />
            )}
          </div>
        </div>
        {/* transition rules panel (segment 3, CE-designed minimal form) */}
        {isTransitionsOpen && (
          <div className="border-b border-subtle bg-layer-2/50 px-4 py-3 last:border-b-0">
            <p className="mb-2 text-body-sm-medium text-secondary">{t("workflows.settings.transitions.title")}</p>
            <WorkflowTransitionsPanel
              workspaceSlug={workspaceSlug}
              projectId={workflow.project}
              workflowId={workflow.id}
            />
          </div>
        )}
      </div>
    </div>
  );
});
