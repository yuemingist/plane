/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { observer } from "mobx-react";
import { Switch } from "@makeplane/propel/components/switch";
import type { IIssueProperty } from "@plane/types";
// hooks
import { useMember } from "@/hooks/store/use-member";

type TIssuePropertyControlProps = {
  property: IIssueProperty;
  value: unknown;
  projectId: string;
  disabled?: boolean;
  /** 保存由调用方决定：侧栏失焦/变更即存；新建弹窗先暂存 */
  onChange: (value: unknown) => void;
};

/** 文本类输入：本地编辑态，失焦时保存（避免逐键写库） */
function BlurSaveInput(props: {
  value: unknown;
  disabled: boolean;
  className: string;
  placeholder: string;
  inputType?: string;
  toValue: (raw: string) => unknown;
  onChange: (value: unknown) => void;
}) {
  const { value, disabled, className, placeholder, inputType = "text", toValue, onChange } = props;
  const [draft, setDraft] = useState(typeof value === "string" || typeof value === "number" ? String(value) : "");
  useEffect(() => {
    setDraft(typeof value === "string" || typeof value === "number" ? String(value) : "");
  }, [value]);
  return (
    <input
      type={inputType}
      className={className}
      disabled={disabled}
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => onChange(toValue(draft))}
      placeholder={placeholder}
    />
  );
}

/** 多行文本：本地编辑态，失焦时保存 */
function BlurSaveTextArea(props: {
  value: unknown;
  disabled: boolean;
  className: string;
  placeholder: string;
  onChange: (value: unknown) => void;
}) {
  const { value, disabled, className, placeholder, onChange } = props;
  const [draft, setDraft] = useState(typeof value === "string" ? value : "");
  useEffect(() => {
    setDraft(typeof value === "string" ? value : "");
  }, [value]);
  return (
    <textarea
      className={className}
      rows={3}
      disabled={disabled}
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => onChange(draft)}
      placeholder={placeholder}
    />
  );
}

/**
 * 8 类属性的值编辑控件（段 2 产品方案 §5）。
 * 富文本值以多行文本域承载（产品方案 A5 折衷，段 4 换 editor 不动 schema）。
 */
export const IssuePropertyControl = observer(function IssuePropertyControl(props: TIssuePropertyControlProps) {
  const { property, value, projectId, disabled = false, onChange } = props;
  // hooks
  const {
    project: { getProjectMemberIds, getProjectMemberDetails },
  } = useMember();
  // derived values
  const settings = property.settings ?? {};
  const memberIds = useMemo(
    () => (projectId ? (getProjectMemberIds(projectId, false) ?? []) : []),
    [projectId, getProjectMemberIds]
  );
  const optionList = settings.options ?? [];
  const isMulti = settings.is_multi === true;

  const controlClass =
    "w-full rounded-md border border-subtle bg-layer-1 px-2 py-1.5 text-body-sm-regular text-primary outline-none focus:border-accent-strong";

  switch (property.property_type) {
    case "text": {
      const displayFormat = settings.display_format ?? "single-line";
      if (displayFormat === "readonly") {
        return <span className="text-body-sm-regular text-primary">{typeof value === "string" ? value : "—"}</span>;
      }
      if (displayFormat === "multi-line") {
        return (
          <BlurSaveTextArea
            value={value}
            disabled={disabled}
            className={controlClass}
            placeholder={property.name}
            onChange={onChange}
          />
        );
      }
      return (
        <BlurSaveInput
          value={value}
          disabled={disabled}
          className={controlClass}
          placeholder={property.name}
          toValue={(raw) => raw}
          onChange={onChange}
        />
      );
    }

    case "decimal":
      return (
        <BlurSaveInput
          value={value}
          disabled={disabled}
          className={controlClass}
          placeholder={property.name}
          inputType="number"
          toValue={(raw) => (raw === "" ? null : Number(raw))}
          onChange={onChange}
        />
      );

    case "option": {
      if (isMulti) {
        const selectedIds = Array.isArray(value) ? (value as string[]) : [];
        return (
          <div className="flex flex-col gap-1">
            {optionList.map((option) => (
              <label key={option.id} className="flex items-center gap-2 text-body-sm-regular text-primary">
                <input
                  type="checkbox"
                  disabled={disabled}
                  checked={selectedIds.includes(option.id)}
                  onChange={(event) =>
                    onChange(
                      event.target.checked
                        ? [...selectedIds, option.id]
                        : selectedIds.filter((optionId) => optionId !== option.id)
                    )
                  }
                />
                {option.name}
              </label>
            ))}
          </div>
        );
      }
      return (
        <select
          className={controlClass}
          disabled={disabled}
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value || null)}
        >
          <option value="">—</option>
          {optionList.map((option) => (
            <option key={option.id} value={option.id}>
              {option.name}
            </option>
          ))}
        </select>
      );
    }

    case "boolean":
      return (
        <Switch
          size="sm"
          checked={value === true}
          disabled={disabled}
          onCheckedChange={(checked) => onChange(checked)}
        />
      );

    case "date":
      return (
        <input
          type="date"
          className={controlClass}
          disabled={disabled}
          value={typeof value === "string" ? value.slice(0, 10) : ""}
          onChange={(event) => onChange(event.target.value || null)}
        />
      );

    case "member": {
      if (isMulti) {
        const selectedIds = Array.isArray(value) ? (value as string[]) : [];
        return (
          <div className="flex flex-col gap-1">
            {memberIds.map((memberId: string) => (
              <label key={memberId} className="flex items-center gap-2 text-body-sm-regular text-primary">
                <input
                  type="checkbox"
                  disabled={disabled}
                  checked={selectedIds.includes(memberId)}
                  onChange={(event) =>
                    onChange(
                      event.target.checked
                        ? [...selectedIds, memberId]
                        : selectedIds.filter((selectedId) => selectedId !== memberId)
                    )
                  }
                />
                {getProjectMemberDetails(memberId, projectId)?.member.display_name ?? memberId}
              </label>
            ))}
          </div>
        );
      }
      return (
        <select
          className={controlClass}
          disabled={disabled}
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value || null)}
        >
          <option value="">—</option>
          {memberIds.map((memberId: string) => (
            <option key={memberId} value={memberId}>
              {getProjectMemberDetails(memberId, projectId)?.member.display_name ?? memberId}
            </option>
          ))}
        </select>
      );
    }

    case "rich_text":
      return (
        <BlurSaveTextArea
          value={value}
          disabled={disabled}
          className={controlClass}
          placeholder={property.name}
          onChange={onChange}
        />
      );

    case "url":
      return (
        <BlurSaveInput
          value={value}
          disabled={disabled}
          className={controlClass}
          placeholder="https://"
          inputType="url"
          toValue={(raw) => raw}
          onChange={onChange}
        />
      );

    default:
      return null;
  }
});
