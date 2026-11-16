/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { Menu as BaseMenu } from "@base-ui/react/menu";
import { MenuGroup, MenuLabel } from "@makeplane/propel/components/menu";
import { Toggle, ToggleLabel } from "@makeplane/propel/elements/toggle";
// plane constants
import { ISSUE_DISPLAY_PROPERTIES } from "@plane/constants";
// plane i18n
import { useTranslation } from "@plane/i18n";
// types
import type { IIssueDisplayProperties } from "@plane/types";
// hooks
import { useProjectCustomProperties } from "@/hooks/use-project-custom-properties";

type Props = {
  displayProperties: IIssueDisplayProperties;
  displayPropertiesToRender: (keyof IIssueDisplayProperties)[];
  handleUpdate: (updatedDisplayProperties: Partial<IIssueDisplayProperties>) => void;
  cycleViewDisabled?: boolean;
  moduleViewDisabled?: boolean;
  isEpic?: boolean;
};

export const FilterDisplayProperties = observer(function FilterDisplayProperties(props: Props) {
  const {
    displayProperties,
    displayPropertiesToRender,
    handleUpdate,
    cycleViewDisabled = false,
    moduleViewDisabled = false,
    isEpic = false,
  } = props;
  // router
  const { workspaceSlug, projectId } = useParams();
  // hooks
  const { t } = useTranslation();
  // 段 4 属性贯穿：项目已启用自定义属性（动态 chip 组）
  const { properties } = useProjectCustomProperties(workspaceSlug?.toString(), projectId?.toString());
  const activeProperties = properties.filter((property) => property.is_active);

  // Filter out "cycle" and "module" keys if cycleViewDisabled or moduleViewDisabled is true
  // Also filter out display properties that should not be rendered
  const filteredDisplayProperties = ISSUE_DISPLAY_PROPERTIES.filter((property) => {
    if (!displayPropertiesToRender.includes(property.key)) return false;
    switch (property.key) {
      case "cycle":
        return !cycleViewDisabled;
      case "modules":
        return !moduleViewDisabled;
      default:
        return true;
    }
  }).map((property) => {
    if (isEpic && property.key === "sub_issue_count") {
      return {
        key: property.key,
        titleTranslationKey: "issue.display.properties.work_item_count",
      };
    }
    return property;
  });

  return (
    <>
      <MenuGroup>
        <MenuLabel>{t("issue.display.properties.label")}</MenuLabel>
        {/* The toggle pills wrap, so this section fixes the menu's width instead of following it. */}
        <div className="flex w-72 flex-wrap items-center gap-2 px-2 pt-0.5 pb-1.5">
          {filteredDisplayProperties.map((displayProperty) => {
            const isSelected = !!displayProperties?.[displayProperty.key];

            return (
              <BaseMenu.CheckboxItem
                key={displayProperty.key}
                checked={isSelected}
                closeOnClick={false}
                onCheckedChange={(checked) => handleUpdate({ [displayProperty.key]: checked })}
                render={<Toggle size="sm" render={<div />} data-pressed={isSelected ? "" : undefined} />}
              >
                <ToggleLabel>{t(displayProperty.titleTranslationKey)}</ToggleLabel>
              </BaseMenu.CheckboxItem>
            );
          })}
        </div>
      </MenuGroup>
      {/* 段 4 属性贯穿：自定义属性动态列开关（键=issue_property_<id>，默认关闭） */}
      {activeProperties.length > 0 && (
        <MenuGroup>
          <MenuLabel>{t("common.custom_properties")}</MenuLabel>
          <div className="flex w-72 flex-wrap items-center gap-2 px-2 pt-0.5 pb-1.5">
            {activeProperties.map((property) => {
              const propertyKey = `issue_property_${property.id}` as keyof IIssueDisplayProperties;
              const isSelected = !!displayProperties?.[propertyKey];

              return (
                <BaseMenu.CheckboxItem
                  key={property.id}
                  checked={isSelected}
                  closeOnClick={false}
                  onCheckedChange={(checked) => handleUpdate({ [propertyKey]: checked })}
                  render={<Toggle size="sm" render={<div />} data-pressed={isSelected ? "" : undefined} />}
                >
                  <ToggleLabel>{property.name}</ToggleLabel>
                </BaseMenu.CheckboxItem>
              );
            })}
          </div>
        </MenuGroup>
      )}
    </>
  );
});
