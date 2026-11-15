/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";

type TPropertiesTabProps = {
  /** shows the type-detail variant (no tab title) */
  variant?: "tab" | "detail";
};

/**
 * Properties tab — empty state only (1A scope). The custom property system is a later
 * milestone (P2-13): there is deliberately no create entry point, and a "Coming soon"
 * badge prevents users from expecting the feature immediately.
 */
export function PropertiesTab({ variant = "tab" }: TPropertiesTabProps) {
  // hooks
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-6">
      {variant === "tab" && (
        <div className="flex items-center justify-between gap-4">
          <h4 className="text-h5-medium text-primary">{t("work_item_types.settings.properties.description")}</h4>
          <span className="rounded-full border border-subtle bg-layer-2 px-2.5 py-0.5 text-caption-md-medium text-tertiary">
            {t("work_item_types.settings.properties.coming_soon_badge")}
          </span>
        </div>
      )}
      <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-subtle px-6 py-10 text-center">
        <p className="text-body-sm-medium text-secondary">
          {t("work_item_types.settings.properties.empty_state.no_properties_description")}
        </p>
      </div>
    </div>
  );
}
