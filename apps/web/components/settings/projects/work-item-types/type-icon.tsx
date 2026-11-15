/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { getLucideIconElementByName, Logo } from "@plane/blocks/emoji-icon-picker";
import type { IIssueType, TLogoProps } from "@plane/types";

type TTypeIconProps = {
  issueType: Pick<IIssueType, "logo_props"> | undefined;
  size?: number;
};

/**
 * Normalizes the issue type `logo_props` into the shape the shared `Logo` component
 * expects. Accepts every shape seen in the wild (BUG-07):
 * - `{ in_use: "emoji" | "icon", ... }` (canonical TLogoProps)
 * - `{ in_app_icon: { name, color } }` (backend enable seed / cloud shape)
 * - bare `{ icon: {...} }` / `{ emoji: {...} }` payloads without `in_use`
 */
export const getIssueTypeLogoProps = (logoProps: IIssueType["logo_props"]): TLogoProps | undefined => {
  if (!logoProps || typeof logoProps !== "object") return undefined;
  const anyProps = logoProps as Record<string, unknown>;
  if ("in_use" in anyProps) return logoProps as TLogoProps;
  if ("in_app_icon" in anyProps && anyProps.in_app_icon) {
    const icon = anyProps.in_app_icon as { name?: string; color?: string };
    if (!icon.name) return undefined;
    return { in_use: "icon", icon: { name: icon.name, color: icon.color } };
  }
  if ("icon" in anyProps && anyProps.icon) {
    const icon = anyProps.icon as { name?: string; color?: string };
    if (!icon.name) return undefined;
    return { in_use: "icon", icon: { name: icon.name, color: icon.color } };
  }
  if ("emoji" in anyProps && anyProps.emoji) {
    const emoji = anyProps.emoji as { value?: string } | string;
    const value = typeof emoji === "string" ? emoji : emoji.value;
    if (!value) return undefined;
    return { in_use: "emoji", emoji: { value } };
  }
  return undefined;
};

/**
 * Renders a work item type's icon. Emoji and curated-picker icon names render through the
 * shared `Logo`; other lucide names resolve via the full registry (helper in blocks);
 * anything else falls back to a colored square instead of an empty skeleton (BUG-07).
 */
export function TypeIcon({ issueType, size = 16 }: TTypeIconProps) {
  const logoProps = getIssueTypeLogoProps(issueType?.logo_props);
  if (!logoProps) {
    return <span className="rounded-sm bg-layer-1" style={{ height: size, width: size }} />;
  }
  if (logoProps.in_use === "icon") {
    const iconName = logoProps.icon?.name ?? "";
    const iconColor = logoProps.icon?.color;
    const LucideElement = getLucideIconElementByName(iconName);
    if (LucideElement) {
      return <LucideElement style={{ color: iconColor, height: size, width: size }} />;
    }
    return (
      <span
        className="shrink-0 rounded-sm"
        style={{ height: size, width: size, backgroundColor: iconColor ?? "var(--background-color-layer-1)" }}
      />
    );
  }
  return <Logo logo={logoProps} size={size} type="lucide" />;
}
