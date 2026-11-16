/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
// components
import { IssuePropertyControl } from "@/components/issues/issue-property-controls";
import { IssueDetailSidebarGroup } from "@/components/issues/issue-detail/sidebar-group";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useIssueProperty } from "@/hooks/store/use-issue-property";
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useProject } from "@/hooks/store/use-project";

type TCustomPropertiesSectionProps = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled: boolean;
};

/**
 * 详情侧栏「自定义属性」分区（57 号 D-11 / §3.4 步骤 8）：按工作项类型显示
 * 绑定且已启用的属性（双门控），逐类控件，变更即批量落库（单属性 upsert）。
 */
export const CustomPropertiesSection = observer(function CustomPropertiesSection(props: TCustomPropertiesSectionProps) {
  const { workspaceSlug, projectId, issueId, disabled } = props;
  // states
  const [localValues, setLocalValues] = useState<Record<string, unknown>>({});
  // hooks
  const { t } = useTranslation();
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const { getTypeById } = useIssueType();
  const { getProjectById } = useProject();
  const {
    fetchTypeProperties,
    getActiveBoundPropertiesByTypeId,
    fetchIssuePropertyValues,
    getValuesByIssueId,
    saveIssuePropertyValues,
  } = useIssueProperty();
  // derived values
  const issue = getIssueById(issueId);
  const issueType = getTypeById(issue?.type_id);
  const projectDetails = getProjectById(projectId);
  const isIssueTypeEnabled = projectDetails?.is_issue_type_enabled === true;
  const boundProperties = issueType ? getActiveBoundPropertiesByTypeId(issueType.id) : [];
  const storedValues = getValuesByIssueId(issueId);

  // fetch bindings for the issue's type and stored values (idempotent via store maps)
  useSWR(
    issueType ? `TYPE_PROPERTIES_${workspaceSlug}_${projectId}_${issueType.id}` : null,
    async () => {
      if (workspaceSlug && projectId && issueType) {
        await fetchTypeProperties(workspaceSlug, projectId, issueType.id);
      }
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );
  useSWR(
    isIssueTypeEnabled && issueId ? `ISSUE_PROPERTY_VALUES_${workspaceSlug}_${projectId}_${issueId}` : null,
    async () => {
      if (workspaceSlug && projectId && issueId && isIssueTypeEnabled) {
        await fetchIssuePropertyValues(workspaceSlug, projectId, issueId);
      }
    },
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  // 值从 store 读 + 本地编辑态合并（失焦保存后由写后回读刷新）
  useEffect(() => {
    setLocalValues({});
  }, [issueId]);

  const valueOf = useMemo(
    () => (propertyId: string) => {
      if (propertyId in localValues) return localValues[propertyId];
      const row = (storedValues ?? []).find((candidate) => candidate.property.id === propertyId);
      return row?.value ?? null;
    },
    [localValues, storedValues]
  );

  if (!isIssueTypeEnabled || boundProperties.length === 0) return null;

  const handleSave = async (propertyId: string, value: unknown) => {
    try {
      await saveIssuePropertyValues(workspaceSlug, projectId, issueId, { [propertyId]: value });
    } catch (errorData) {
      const errorResponse = errorData as { error?: string };
      setToast({ type: "error", title: t("error"), message: errorResponse?.error ?? t("common.something_went_wrong") });
    }
  };

  return (
    <IssueDetailSidebarGroup label={t("work_item_types.settings.linked_properties.title")}>
      <div className="flex w-full flex-col gap-3">
        {boundProperties.map((property) => {
          const currentValue = valueOf(property.id);
          return (
            <div key={property.id} className="flex flex-col gap-1">
              <span className="text-caption-md-medium text-tertiary">
                {property.name}
                {property.is_required && " *"}
              </span>
              <IssuePropertyControl
                property={property}
                value={currentValue}
                projectId={projectId}
                disabled={disabled}
                onChange={(value) => {
                  setLocalValues((previous) => ({ ...previous, [property.id]: value }));
                  void handleSave(property.id, value);
                }}
              />
            </div>
          );
        })}
      </div>
    </IssueDetailSidebarGroup>
  );
});
