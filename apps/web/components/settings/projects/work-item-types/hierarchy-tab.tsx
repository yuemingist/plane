/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { groupBy } from "lodash-es";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
// hooks
import { useIssueType } from "@/hooks/store/use-issue-type";
// local imports
import { TypeIcon } from "./type-icon";

type THierarchyTabProps = {
  workspaceSlug: string;
  projectId: string;
};

/**
 * Hierarchy tab — read-only visualization ("Level 1: Epic → Level 0: Task / custom types").
 * Level editing is intentionally not implemented in this step; the chips are static
 * (no edit controls on hover/click), pending the official editable-hierarchy design.
 */
export const HierarchyTab = observer(function HierarchyTab(props: THierarchyTabProps) {
  const { projectId } = props;
  // hooks
  const { t } = useTranslation();
  const { getTypesByProjectId } = useIssueType();
  // derived values
  const projectTypes = getTypesByProjectId(projectId) ?? [];
  // sort so that the highest level appears first
  const typesByLevel = groupBy(
    // oxlint-disable-next-line unicorn/no-array-sort
    [...projectTypes].sort((a, b) => b.level - a.level),
    "level"
  );
  const levels = Object.keys(typesByLevel)
    .map(Number)
    // oxlint-disable-next-line unicorn/no-array-sort
    .sort((a, b) => b - a);

  return (
    <div className="flex flex-col gap-6">
      <p className="text-body-xs-regular text-tertiary">
        {t("work_item_type_hierarchy.settings.readonly_description")}
      </p>
      {levels.length === 0 ? (
        <p className="text-body-sm-regular text-tertiary">{t("common.search.no_results.title")}</p>
      ) : (
        <div className="flex flex-col gap-4">
          {levels.map((level, levelIndex) => (
            <div key={level} className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-body-sm-medium text-secondary">
                  {t("work_item_type_hierarchy.settings.level_label", { level })}
                </span>
                {typesByLevel[level].map((issueType) => (
                  <span
                    key={issueType.id}
                    className="flex items-center gap-1.5 rounded-md border border-subtle bg-layer-1 px-2.5 py-1 text-body-sm-regular text-primary"
                  >
                    <TypeIcon issueType={issueType} size={14} />
                    {issueType.name}
                    {issueType.is_default && (
                      <span className="rounded-full bg-accent-primary/10 px-1.5 py-0.5 text-caption-md-medium text-accent-primary">
                        {t("common.default")}
                      </span>
                    )}
                  </span>
                ))}
              </div>
              {levelIndex < levels.length - 1 && (
                <span className="ml-6 text-tertiary" aria-hidden>
                  ↓
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
});
