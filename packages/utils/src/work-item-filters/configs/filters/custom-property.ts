/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import type { IIssueProperty, IUserLite, TFilterProperty } from "@plane/types";
import { COLLECTION_OPERATOR, EQUALITY_OPERATOR } from "@plane/types";
// local imports
import type { IFilterIconConfig, TCreateFilterConfig, TCreateFilterConfigParams } from "../../../rich-filters";
import {
  createFilterConfig,
  createOperatorConfigEntry,
  getDatePickerConfig,
  getMultiSelectConfig,
  getSingleSelectConfig,
} from "../../../rich-filters";

/**
 * 自定义属性筛选（段 4 属性贯穿）：按属性类型分派控件与操作符。
 * 裁剪面见段 4 产品方案 §3：text/decimal/url/rich_text 不出筛选 config
 * （rich filters 体系暂无文本输入控件，isEnabled=false 兜底）；date 仅 exact（不做 range）。
 */

export type TCreateCustomPropertyFilterParams = TCreateFilterConfigParams &
  IFilterIconConfig & {
    property: IIssueProperty;
    propertyDisplayName: string;
    members?: IUserLite[];
  };

type TOptionItem = { id: string; name: string };

/**
 * Get the custom property filter config
 * @param key - The filter key（`customproperty_<属性id>`）
 * @returns A function that takes parameters and returns the filter config
 */
export const getCustomPropertyFilterConfig =
  <P extends TFilterProperty>(key: P): TCreateFilterConfig<P, TCreateCustomPropertyFilterParams> =>
  (params: TCreateCustomPropertyFilterParams) => {
    const { property } = params;
    const settings = (property.settings ?? {}) as { is_multi?: boolean; options?: TOptionItem[] };

    // 下拉属性（单选/多选）：选项多选（in）
    if (property.property_type === "option") {
      const options = (settings.options ?? []).map((option) => ({ id: option.id, name: option.name }));
      return createFilterConfig<P>({
        id: key,
        label: params.propertyDisplayName,
        ...params,
        icon: params.filterIcon,
        supportedOperatorConfigsMap: new Map([
          createOperatorConfigEntry(COLLECTION_OPERATOR.IN, params, (updatedParams) =>
            getMultiSelectConfig<TOptionItem, string, undefined>(
              {
                items: options,
                getId: (option) => option.id,
                getLabel: (option) => option.name,
                getValue: (option) => option.id,
              },
              {
                singleValueOperator: EQUALITY_OPERATOR.EXACT,
                ...updatedParams,
              }
            )
          ),
        ]),
      });
    }

    // 成员属性：成员多选（exact）
    if (property.property_type === "member") {
      return createFilterConfig<P>({
        id: key,
        label: params.propertyDisplayName,
        ...params,
        isEnabled: params.isEnabled && !!params.members,
        icon: params.filterIcon,
        supportedOperatorConfigsMap: new Map([
          createOperatorConfigEntry(EQUALITY_OPERATOR.EXACT, params, (updatedParams) =>
            getMultiSelectConfig<IUserLite, string, undefined>(
              {
                items: params.members ?? [],
                getId: (member) => member.id,
                getLabel: (member) => member.display_name,
                getValue: (member) => member.id,
              },
              {
                singleValueOperator: EQUALITY_OPERATOR.EXACT,
                ...updatedParams,
              }
            )
          ),
        ]),
      });
    }

    // 日期属性：日期选择（exact，range 裁剪不做）
    if (property.property_type === "date") {
      return createFilterConfig<P>({
        id: key,
        label: params.propertyDisplayName,
        ...params,
        allowMultipleFilters: true,
        icon: params.filterIcon,
        supportedOperatorConfigsMap: new Map([
          createOperatorConfigEntry(EQUALITY_OPERATOR.EXACT, params, (updatedParams) =>
            getDatePickerConfig(updatedParams)
          ),
        ]),
      });
    }

    // 布尔属性：是/否单选（exact）
    if (property.property_type === "boolean") {
      return createFilterConfig<P>({
        id: key,
        label: params.propertyDisplayName,
        ...params,
        icon: params.filterIcon,
        supportedOperatorConfigsMap: new Map([
          createOperatorConfigEntry(EQUALITY_OPERATOR.EXACT, params, (updatedParams) =>
            getSingleSelectConfig<TOptionItem, string, undefined>(
              {
                items: [
                  { id: "true", name: "true" },
                  { id: "false", name: "false" },
                ],
                getId: (option) => option.id,
                getLabel: (option) => option.name,
                getValue: (option) => option.id,
              },
              {
                ...updatedParams,
              }
            )
          ),
        ]),
      });
    }

    // text / decimal / url / rich_text：无筛选 config（裁剪，见产品方案 §3）
    return createFilterConfig<P>({
      id: key,
      label: params.propertyDisplayName,
      ...params,
      isEnabled: false,
      icon: params.filterIcon,
      supportedOperatorConfigsMap: new Map(),
    });
  };
