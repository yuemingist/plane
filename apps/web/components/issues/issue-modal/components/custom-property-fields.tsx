/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
// components
import { IssuePropertyControl } from "@/components/issues/issue-property-controls";
// hooks
import { useIssueProperty } from "@/hooks/store/use-issue-property";
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useProject } from "@/hooks/store/use-project";

type TCustomPropertyFieldsProps = {
  workspaceSlug: string;
  projectId: string | null;
  typeId: string | null | undefined;
  disabled?: boolean;
};

/**
 * 新建/更新弹窗的自定义属性字段区（57 号 §3.4 步骤 7/12）：按所选类型渲染
 * 绑定且已启用的属性；值暂存到 issue-property store 的 draftValues，
 * 由 modal provider 的 handleCreateUpdatePropertyValues 在工作项创建/更新成功后落库。
 */
export const CustomPropertyFields = observer(function CustomPropertyFields(props: TCustomPropertyFieldsProps) {
  const { workspaceSlug, projectId, typeId, disabled = false } = props;
  // hooks
  const { t } = useTranslation();
  const { getActiveBoundPropertiesByTypeId, fetchTypeProperties, areTypeBindingsFetched, setDraftValue } =
    useIssueProperty();
  const { getTypeById } = useIssueType();
  const { getProjectById } = useProject();
  // derived values
  const projectDetails = projectId ? getProjectById(projectId) : undefined;
  const isIssueTypeEnabled = projectDetails?.is_issue_type_enabled === true;
  const issueType = getTypeById(typeId);
  const boundProperties = issueType ? getActiveBoundPropertiesByTypeId(issueType.id) : [];

  // ensure the selected type's bindings are loaded
  useEffect(() => {
    if (workspaceSlug && projectId && issueType && !areTypeBindingsFetched(issueType.id)) {
      void fetchTypeProperties(workspaceSlug, projectId, issueType.id);
    }
  }, [workspaceSlug, projectId, issueType, areTypeBindingsFetched, fetchTypeProperties]);

  if (!isIssueTypeEnabled || !issueType || boundProperties.length === 0) return null;

  return (
    <div className="flex w-full flex-col gap-3 border-t border-subtle pt-3">
      <span className="text-caption-md-medium text-tertiary">
        {t("work_item_types.settings.linked_properties.title")}
      </span>
      <div className="grid grid-cols-2 gap-3">
        {boundProperties.map((property) => (
          <div key={property.id} className="flex flex-col gap-1">
            <span className="text-caption-md-medium text-tertiary">
              {property.name}
              {property.is_required && " *"}
            </span>
            <IssuePropertyControl
              property={property}
              value={null}
              projectId={projectId ?? ""}
              disabled={disabled}
              onChange={(value) => setDraftValue(property.id, value)}
            />
          </div>
        ))}
      </div>
    </div>
  );
});
