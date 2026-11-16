/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
// plane types
import type { IIssueProperty, IIssueType } from "@plane/types";
// plane web
import { useIssueProperty } from "@/hooks/store/use-issue-property";
import { useIssueType } from "@/hooks/store/use-issue-type";
import { useProject } from "@/hooks/store/use-project";

/**
 * 列表上下文的自定义属性取数（段 4 属性贯穿）：
 * - 拉项目属性池（一次）与项目各类型的属性绑定（类型数小，逐类型一次并缓存）；
 * - 仅当项目启用工作项类型时生效；
 * - 返回项目属性池清单（行渲染与菜单按类型绑定/显示开关二次过滤）。
 */
export const useProjectCustomProperties = (
  workspaceSlug: string | undefined,
  projectId: string | undefined
): {
  properties: IIssueProperty[];
  projectTypes: IIssueType[];
  arePropertiesReady: boolean;
} => {
  const { getProjectById } = useProject();
  const { getTypesByProjectId } = useIssueType();
  const {
    fetchProjectProperties,
    fetchTypeProperties,
    arePropertiesFetched,
    areTypeBindingsFetched,
    getPropertiesByProjectId,
  } = useIssueProperty();

  const project = projectId ? getProjectById(projectId) : undefined;
  const isTypeEnabled = !!project?.is_issue_type_enabled;
  const projectTypes: IIssueType[] = (projectId && isTypeEnabled ? getTypesByProjectId(projectId) : undefined) ?? [];
  const properties = (projectId ? getPropertiesByProjectId(projectId) : undefined) ?? [];
  const arePropertiesReady = !!projectId && arePropertiesFetched(projectId);

  useEffect(() => {
    if (!workspaceSlug || !projectId || !isTypeEnabled) return;
    // 属性池（一次）
    if (!arePropertiesFetched(projectId)) {
      fetchProjectProperties(workspaceSlug, projectId).catch((error) => console.error(error));
    }
    // 逐类型绑定（store 按 typeId 缓存；getTypesByProjectId 为 computedFn，引用稳定）
    const types = getTypesByProjectId(projectId) ?? [];
    types.forEach((issueType) => {
      if (!areTypeBindingsFetched(issueType.id)) {
        fetchTypeProperties(workspaceSlug, projectId, issueType.id).catch((error) => console.error(error));
      }
    });
  }, [
    workspaceSlug,
    projectId,
    isTypeEnabled,
    getTypesByProjectId,
    arePropertiesFetched,
    areTypeBindingsFetched,
    fetchProjectProperties,
    fetchTypeProperties,
  ]);

  return { properties, projectTypes, arePropertiesReady };
};
