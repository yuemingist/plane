/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogHeading,
  DialogMain,
  DialogTitle,
} from "@makeplane/propel/components/dialog";
import { Button } from "@makeplane/propel/components/button";
import { InputField } from "@makeplane/propel/components/input-field";
import { TextAreaField } from "@makeplane/propel/components/text-area-field";
import { Checkbox } from "@makeplane/propel/components/checkbox";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import { ChevronDownOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import { setToast } from "@plane/blocks/toast";
import type { IIssueProperty, TIssuePropertyOption, TIssuePropertySettings, TIssuePropertyType } from "@plane/types";
// hooks
import { useIssueProperty } from "@/hooks/store/use-issue-property";
import { useMember } from "@/hooks/store/use-member";
// local imports
import { PROPERTY_TYPE_KEYS, propertyTypeLabel } from "./property-type-meta";

type TCreatePropertyModalProps = {
  workspaceSlug: string;
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  /** when provided, the modal edits the existing property (type locked) */
  issueProperty?: IIssueProperty;
};

const EMPTY_SETTINGS: Record<TIssuePropertyType, TIssuePropertySettings> = {
  text: { display_format: "single-line" },
  decimal: { format: "standard", decimal_places: 2, thousands_separator: false },
  option: { is_multi: false, options: [] },
  boolean: {},
  date: {},
  member: { is_multi: false },
  rich_text: {},
  url: {},
};

/**
 * 「创建新的自定义属性」弹窗（57 号 §4.2 字段清单）：
 * 标题* / 描述 / 属性类型*（8 选 1）/ 逐类子配置 / 活动、必填属性复选框（默认不勾）。
 * 编辑复用同表单；property_type 创建后锁定（后端 400 兜底）。
 */
export const CreatePropertyModal = observer(function CreatePropertyModal(props: TCreatePropertyModalProps) {
  const { workspaceSlug, projectId, isOpen, onClose, issueProperty } = props;
  // states
  const [name, setName] = useState(issueProperty?.name ?? "");
  const [description, setDescription] = useState(issueProperty?.description ?? "");
  const [propertyType, setPropertyType] = useState<TIssuePropertyType>(issueProperty?.property_type ?? "text");
  const [settings, setSettings] = useState<TIssuePropertySettings>(issueProperty?.settings ?? EMPTY_SETTINGS.text);
  const [defaultOptions, setDefaultOptions] = useState<string[]>(
    Array.isArray(issueProperty?.default_value)
      ? (issueProperty.default_value as string[])
      : issueProperty?.default_value
        ? [String(issueProperty.default_value)]
        : []
  );
  const [defaultNumber, setDefaultNumber] = useState<string>(
    propertyType === "decimal" && typeof issueProperty?.default_value === "number"
      ? String(issueProperty.default_value)
      : ""
  );
  const [defaultMemberIds, setDefaultMemberIds] = useState<string[]>(
    Array.isArray(issueProperty?.default_value) && propertyType === "member"
      ? (issueProperty.default_value as string[])
      : typeof issueProperty?.default_value === "string" && propertyType === "member"
        ? [issueProperty.default_value]
        : []
  );
  const [isActive, setIsActive] = useState(issueProperty?.is_active ?? false);
  const [isRequired, setIsRequired] = useState(issueProperty?.is_required ?? false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const [optionDraft, setOptionDraft] = useState("");
  // hooks
  const { t } = useTranslation();
  const { createProperty, updateProperty } = useIssueProperty();
  const {
    project: { getProjectMemberIds, getProjectMemberDetails },
  } = useMember();
  // derived values
  const isEditMode = !!issueProperty;
  const members = useMemo(
    () => (projectId ? (getProjectMemberIds(projectId, false) ?? []) : []),
    [projectId, getProjectMemberIds]
  );
  const memberDetails = useMemo(
    () =>
      new Map(
        members.map((memberId: string) => [
          memberId,
          (projectId ? getProjectMemberDetails(memberId, projectId) : null)?.member.display_name ?? memberId,
        ])
      ),
    [members, projectId, getProjectMemberDetails]
  );

  const handleClose = () => {
    setIsSubmitting(false);
    setError(undefined);
    onClose();
  };

  const handleTypeChange = (nextType: TIssuePropertyType) => {
    setPropertyType(nextType);
    setSettings(EMPTY_SETTINGS[nextType]);
    setDefaultOptions([]);
  };

  const updateSettings = (patch: Partial<TIssuePropertySettings>) => {
    setSettings((previous) => ({ ...previous, ...patch }));
  };

  const handleAddOption = () => {
    const optionName = optionDraft.trim();
    if (!optionName) return;
    const options = settings.options ?? [];
    if (options.some((option) => option.name === optionName)) return;
    updateSettings({ options: [...options, { id: "", name: optionName, is_default: false }] });
    setOptionDraft("");
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError(t("work_item_types.settings.properties.create_update.errors.name.required"));
      return;
    }
    if (propertyType === "option" && (settings.options ?? []).length === 0) {
      setError(t("work_item_types.settings.properties.create_update.errors.options.required"));
      return;
    }
    setIsSubmitting(true);
    try {
      const payload: Partial<IIssueProperty> = {
        name: name.trim(),
        description: description.trim(),
        property_type: propertyType,
        settings,
        is_active: isActive,
        is_required: isRequired,
        default_value:
          propertyType === "decimal" && defaultNumber !== "" && !Number.isNaN(Number(defaultNumber))
            ? Number(defaultNumber)
            : propertyType === "member" && defaultMemberIds.length > 0
              ? settings.is_multi
                ? defaultMemberIds
                : defaultMemberIds[0]
              : defaultOptions.length > 0
                ? settings.is_multi
                  ? defaultOptions
                  : defaultOptions[0]
                : null,
      };
      if (isEditMode && issueProperty) {
        // property_type 锁定：编辑不提交该字段
        const editable: Partial<IIssueProperty> = { ...payload };
        delete editable.property_type;
        await updateProperty(workspaceSlug, projectId, issueProperty.id, editable);
        setToast({
          type: "success",
          title: t("work_item_types.settings.properties.toast.update.success.title"),
          message: t("work_item_types.settings.properties.toast.update.success.message", { name: name.trim() }),
        });
      } else {
        const createdProperty = await createProperty(workspaceSlug, projectId, payload);
        // 新建时下拉默认值以选项名选择：服务端生成选项 id 后回填为 id 引用
        if (propertyType === "option" && defaultOptions.length > 0) {
          const nameToId = new Map(
            (createdProperty.settings.options ?? []).map((option: TIssuePropertyOption) => [option.name, option.id])
          );
          const resolvedDefault = defaultOptions.map((optionName) => nameToId.get(optionName) ?? optionName);
          await updateProperty(workspaceSlug, projectId, createdProperty.id, {
            default_value: settings.is_multi ? resolvedDefault : resolvedDefault[0],
          });
        }
        setToast({
          type: "success",
          title: t("work_item_types.settings.properties.toast.create.success.title"),
          message: t("work_item_types.settings.properties.toast.create.success.message", { name: name.trim() }),
        });
      }
      handleClose();
    } catch {
      setToast({
        type: "error",
        title: t("work_item_types.settings.properties.toast.create.error.title"),
        message: t("work_item_types.settings.properties.toast.create.error.message"),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} disablePointerDismissal onOpenChange={() => {}}>
      <DialogContent size="md">
        <DialogMain>
          <DialogHeader>
            <DialogHeading>
              <DialogTitle>
                {isEditMode
                  ? t("work_item_types.settings.properties.create_update.title.update")
                  : t("work_item_types.settings.properties.create_update.title.create")}
              </DialogTitle>
            </DialogHeading>
          </DialogHeader>
          <DialogBody render={<div className="flex flex-col gap-4" />}>
            {/* 标题 */}
            <InputField
              size="lg"
              orientation="vertical"
              id="issue-property-name"
              type="text"
              name="name"
              aria-label={t("work_item_types.settings.properties.create_update.form.display_name.placeholder")}
              placeholder={t("work_item_types.settings.properties.create_update.form.display_name.placeholder")}
              value={name}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) => {
                setName(event.target.value);
                setError(undefined);
              }}
              maxLength={255}
              error={error}
            />
            {/* 描述 */}
            <TextAreaField
              size="lg"
              resize="none"
              autoResize
              maxRows={8}
              id="issue-property-description"
              name="description"
              aria-label={t("work_item_types.settings.properties.create_update.form.description.placeholder")}
              placeholder={t("work_item_types.settings.properties.create_update.form.description.placeholder")}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
            {/* 属性类型（编辑时锁定） */}
            <div className="flex flex-col gap-1.5">
              <span className="text-caption-md-medium text-secondary">
                {t("work_item_types.settings.properties.dropdown.label")}*
              </span>
              <Menu>
                <MenuTrigger
                  render={
                    <button
                      type="button"
                      className={
                        "flex w-full items-center justify-between rounded-md border border-subtle bg-layer-1 px-3 py-2 text-body-sm-medium text-primary" +
                        (isEditMode ? "opacity-60" : "")
                      }
                      disabled={isEditMode}
                    >
                      {propertyTypeLabel(propertyType, t)}
                      <ChevronDownOutline className="size-3.5" />
                    </button>
                  }
                />
                <MenuContent side="bottom" align="end">
                  {PROPERTY_TYPE_KEYS.map((typeKey) => (
                    <MenuItem
                      key={typeKey}
                      label={propertyTypeLabel(typeKey, t)}
                      selected={typeKey === propertyType}
                      onClick={() => handleTypeChange(typeKey)}
                    />
                  ))}
                </MenuContent>
              </Menu>
            </div>

            {/* 逐类子配置（57 号 §4.2 3a-3h） */}
            {propertyType === "text" && (
              <div className="flex flex-col gap-1.5">
                <span className="text-caption-md-medium text-secondary">
                  {t("work_item_types.settings.properties.attributes.label")}*
                </span>
                <div className="flex gap-3">
                  {(["single-line", "multi-line", "readonly"] as const).map((formatKey) => (
                    <label key={formatKey} className="flex items-center gap-1.5 text-body-sm-regular text-primary">
                      <input
                        type="radio"
                        name="text_display_format"
                        checked={(settings.display_format ?? "single-line") === formatKey}
                        onChange={() => updateSettings({ display_format: formatKey })}
                      />
                      {t(
                        formatKey === "single-line"
                          ? "work_item_types.settings.properties.attributes.text.single_line.label"
                          : formatKey === "multi-line"
                            ? "work_item_types.settings.properties.attributes.text.multi_line.label"
                            : "work_item_types.settings.properties.attributes.text.readonly.label"
                      )}
                    </label>
                  ))}
                </div>
              </div>
            )}

            {propertyType === "decimal" && (
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <span className="text-caption-md-medium text-secondary">
                    {t("work_item_types.settings.properties.attributes.number.format.label")}
                  </span>
                  <div className="flex gap-3">
                    {(["standard", "percent", "currency"] as const).map((formatKey) => (
                      <label key={formatKey} className="flex items-center gap-1.5 text-body-sm-regular text-primary">
                        <input
                          type="radio"
                          name="number_format"
                          checked={(settings.format ?? "standard") === formatKey}
                          onChange={() => updateSettings({ format: formatKey })}
                        />
                        {t(`work_item_types.settings.properties.attributes.number.format.${formatKey}`)}
                      </label>
                    ))}
                  </div>
                </div>
                <label className="flex items-center gap-2 text-body-sm-regular text-primary">
                  <span className="text-caption-md-medium text-secondary">
                    {t("work_item_types.settings.properties.attributes.number.decimal_places.label")}
                  </span>
                  <input
                    type="number"
                    min={0}
                    max={8}
                    className="w-20 rounded-md border border-subtle bg-layer-1 px-2 py-1 text-body-sm-regular text-primary outline-none focus:border-accent-strong"
                    value={settings.decimal_places ?? 2}
                    onChange={(event) =>
                      updateSettings({ decimal_places: Math.max(0, Math.min(8, Number(event.target.value))) })
                    }
                  />
                </label>
                <label className="flex items-center gap-2 text-body-sm-regular text-primary">
                  <input
                    type="checkbox"
                    checked={settings.thousands_separator ?? false}
                    onChange={(event) => updateSettings({ thousands_separator: event.target.checked })}
                  />
                  {t("work_item_types.settings.properties.attributes.number.thousands_separator.label")}
                </label>
                {/* 默认值（可选，57 号 §4.2 3b） */}
                <label className="flex items-center gap-2 text-body-sm-regular text-primary">
                  <span className="text-caption-md-medium text-secondary">
                    {t("work_item_types.settings.properties.attributes.number.default.label")}
                  </span>
                  <input
                    type="number"
                    className="w-32 rounded-md border border-subtle bg-layer-1 px-2 py-1 text-body-sm-regular text-primary outline-none focus:border-accent-strong"
                    value={defaultNumber}
                    onChange={(event) => setDefaultNumber(event.target.value)}
                    placeholder={t("work_item_types.settings.properties.attributes.number.default.placeholder")}
                  />
                </label>
              </div>
            )}

            {propertyType === "option" && (
              <div className="flex flex-col gap-3">
                {/* 单选/多选（57 号：多选在此实现，非独立类型） */}
                <div className="flex gap-3">
                  <label className="flex items-center gap-1.5 text-body-sm-regular text-primary">
                    <input
                      type="radio"
                      name="option_is_multi"
                      checked={!settings.is_multi}
                      onChange={() => updateSettings({ is_multi: false })}
                    />
                    {t("work_item_types.settings.properties.attributes.relation.single_select.label")}
                  </label>
                  <label className="flex items-center gap-1.5 text-body-sm-regular text-primary">
                    <input
                      type="radio"
                      name="option_is_multi"
                      checked={!!settings.is_multi}
                      onChange={() => updateSettings({ is_multi: true })}
                    />
                    {t("work_item_types.settings.properties.attributes.relation.multi_select.label")}
                  </label>
                </div>
                {/* 选项（回车成 chip） */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-caption-md-medium text-secondary">
                    {t("work_item_types.settings.properties.attributes.option.create_update.label")}*
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    {(settings.options ?? []).map((option) => (
                      <span
                        key={option.name}
                        className="inline-flex items-center gap-1 rounded-full border border-subtle bg-layer-2 px-2 py-0.5 text-caption-md-medium text-primary"
                      >
                        {option.name}
                        <button
                          type="button"
                          className="text-tertiary hover:text-danger-primary"
                          aria-label={t("common.actions.delete")}
                          onClick={() =>
                            updateSettings({
                              options: (settings.options ?? []).filter(
                                (listedOption) => listedOption.name !== option.name
                              ),
                            })
                          }
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                  <input
                    type="text"
                    className="rounded-md border border-subtle bg-layer-1 px-2 py-1 text-body-sm-regular text-primary outline-none focus:border-accent-strong"
                    value={optionDraft}
                    onChange={(event) => setOptionDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        handleAddOption();
                      }
                    }}
                    placeholder={t(
                      "work_item_types.settings.properties.attributes.option.create_update.form.placeholder"
                    )}
                  />
                </div>
                {/* 默认值（可选，从选项中选） */}
                {(settings.options ?? []).length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-caption-md-medium text-secondary">
                      {t("work_item_types.settings.properties.attributes.number.default.label")}
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {(settings.options ?? []).map((option: TIssuePropertyOption) => (
                        <label
                          key={`${option.name}-default`}
                          className="flex items-center gap-1.5 text-body-sm-regular text-primary"
                        >
                          <input
                            type="checkbox"
                            checked={defaultOptions.includes(option.name)}
                            onChange={(event) =>
                              setDefaultOptions((previous) =>
                                event.target.checked
                                  ? settings.is_multi
                                    ? [...previous, option.name]
                                    : [option.name]
                                  : previous.filter((optionId) => optionId !== option.name)
                              )
                            }
                          />
                          {option.name}
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {propertyType === "member" && (
              <div className="flex flex-col gap-3">
                <div className="flex gap-3">
                  <label className="flex items-center gap-1.5 text-body-sm-regular text-primary">
                    <input
                      type="radio"
                      name="member_is_multi"
                      checked={!settings.is_multi}
                      onChange={() => updateSettings({ is_multi: false })}
                    />
                    {t("work_item_types.settings.properties.attributes.relation.single_select.label")}
                  </label>
                  <label className="flex items-center gap-1.5 text-body-sm-regular text-primary">
                    <input
                      type="radio"
                      name="member_is_multi"
                      checked={!!settings.is_multi}
                      onChange={() => updateSettings({ is_multi: true })}
                    />
                    {t("work_item_types.settings.properties.attributes.relation.multi_select.label")}
                  </label>
                </div>
                {/* 默认值 Select a member（57 号 §4.2 3f） */}
                {members.length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-caption-md-medium text-secondary">
                      {t("work_item_types.settings.properties.attributes.number.default.label")}
                    </span>
                    <select
                      className="rounded-md border border-subtle bg-layer-1 px-2 py-1.5 text-body-sm-regular text-primary outline-none focus:border-accent-strong"
                      value={settings.is_multi ? "" : (defaultMemberIds[0] ?? "")}
                      onChange={(event) => setDefaultMemberIds(event.target.value ? [event.target.value] : [])}
                    >
                      <option value="">
                        {t("work_item_types.settings.properties.attributes.relation.no_default_value.label")}
                      </option>
                      {members.map((memberId) => (
                        <option key={memberId} value={memberId}>
                          {memberDetails.get(memberId) ?? memberId}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )}

            {/* 活动 / 必填属性（57 号 §4.2：默认都不勾） */}
            <div className="flex flex-col gap-2 border-t border-subtle pt-3">
              <Checkbox
                checked={isActive}
                label={t("work_item_types.settings.properties.create_update.form.active.label")}
                onCheckedChange={(checked) => setIsActive(checked === true)}
              />
              <Checkbox
                checked={isRequired}
                label={t("work_item_types.settings.properties.create_update.form.required.label")}
                onCheckedChange={(checked) => setIsRequired(checked === true)}
              />
            </div>
          </DialogBody>
        </DialogMain>
        <DialogActions>
          <Button
            type="button"
            variant="secondary"
            size="md"
            stretch="auto"
            label={t("common.cancel")}
            onClick={handleClose}
          />
          <Button
            type="button"
            variant="primary"
            size="md"
            stretch="auto"
            loading={isSubmitting}
            disabled={!name.trim()}
            label={isEditMode ? t("common.save") : t("common.add")}
            onClick={() => void handleSubmit()}
          />
        </DialogActions>
      </DialogContent>
    </Dialog>
  );
});
