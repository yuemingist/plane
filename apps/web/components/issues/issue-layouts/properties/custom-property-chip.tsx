/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import type { IIssueProperty } from "@plane/types";
// plane i18n
import { useTranslation } from "@plane/i18n";
// hooks
import { useMember } from "@/hooks/store/use-member";

/**
 * 自定义属性值的紧凑展示（段 4 属性贯穿，只读）：
 * 文本/URL/数字/富文本=截断文本，下拉/成员=名称 chip，布尔=是/否，日期=文本。
 * 形态对照段 4 产品方案 §2 表。
 */

type TOptionMeta = { id: string; name: string };

const stripHtml = (html: string) =>
  html
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .trim();

const compactChipClass =
  "max-w-32 truncate rounded-sm border border-subtle px-1.5 py-0.5 text-body-xs-regular text-secondary";

type TGetMemberDetails = (userId: string, projectId: string) => { member: { display_name: string } } | null;

const memberName = (memberId: string, projectId: string | undefined, getProjectMemberDetails: TGetMemberDetails) => {
  if (!projectId) return memberId;
  return getProjectMemberDetails(memberId, projectId)?.member.display_name ?? memberId;
};

/** 值 → 纯文本摘要（menuRow preview / measureKey 用） */
export const getCustomPropertyDisplayText = (
  property: IIssueProperty,
  value: unknown,
  projectId: string | undefined,
  getProjectMemberDetails?: TGetMemberDetails
): string => {
  if (value === null || value === undefined || value === "") return "";
  const settings = (property.settings ?? {}) as { options?: TOptionMeta[]; is_multi?: boolean };

  switch (property.property_type) {
    case "option": {
      const optionsById = new Map((settings.options ?? []).map((option) => [option.id, option.name]));
      const ids = Array.isArray(value) ? value : [value];
      return ids.map((id) => optionsById.get(String(id)) ?? String(id)).join(", ");
    }
    case "member": {
      const ids = Array.isArray(value) ? value : [value];
      if (!getProjectMemberDetails) return ids.join(", ");
      return ids.map((id) => memberName(String(id), projectId, getProjectMemberDetails)).join(", ");
    }
    case "boolean":
      return value === true ? "true" : "false";
    case "rich_text":
      return stripHtml(String(value));
    case "decimal":
      return String(value);
    default:
      return String(value);
  }
};

type TCustomPropertyChipProps = {
  property: IIssueProperty;
  value: unknown;
  projectId: string | undefined;
};

export const CustomPropertyChip = observer(function CustomPropertyChip(props: TCustomPropertyChipProps) {
  const { property, value, projectId } = props;
  // i18n
  const { t } = useTranslation();
  // store hooks
  const {
    project: { getProjectMemberDetails },
  } = useMember();

  if (value === null || value === undefined || value === "") return null;

  const settings = (property.settings ?? {}) as { options?: TOptionMeta[] };
  const displayText = getCustomPropertyDisplayText(property, value, projectId, getProjectMemberDetails);

  switch (property.property_type) {
    case "option": {
      const optionsById = new Map((settings.options ?? []).map((option) => [option.id, option.name]));
      const ids = Array.isArray(value) ? value : [value];
      return (
        <span className="flex items-center gap-1">
          {ids.map((id) => (
            <Tooltip key={String(id)} label={optionsById.get(String(id)) ?? String(id)} layout="stacked">
              <span className={compactChipClass}>{optionsById.get(String(id)) ?? String(id)}</span>
            </Tooltip>
          ))}
        </span>
      );
    }
    case "member": {
      const ids = Array.isArray(value) ? value : [value];
      return (
        <span className="flex items-center gap-1">
          {ids.map((id) => {
            const name = memberName(String(id), projectId, getProjectMemberDetails);
            return (
              <Tooltip key={String(id)} label={name} layout="stacked">
                <span className={compactChipClass}>{name}</span>
              </Tooltip>
            );
          })}
        </span>
      );
    }
    case "boolean":
      return <span className={compactChipClass}>{value === true ? t("common.yes") : t("common.no")}</span>;
    default:
      // text / url / decimal / date / rich_text：截断文本 + tooltip 全文
      return (
        <Tooltip label={displayText} layout="stacked">
          <span className="max-w-40 truncate text-body-xs-regular text-secondary">{displayText}</span>
        </Tooltip>
      );
  }
});
