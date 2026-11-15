/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Logo } from "@plane/blocks/emoji-icon-picker";
import type { TLogoProps } from "@plane/types";
import type { IIssueType } from "@plane/types";

type TTypeIconProps = {
  issueType: Pick<IIssueType, "logo_props"> | undefined;
  size?: number;
};

/**
 * Normalizes the issue type `logo_props` into the shape the shared `Logo` component
 * expects. Accepts both the canonical `{ in_use: "icon", icon: {...} }` shape and the
 * `{ in_app_icon: {...} }` shape written by the backend seed.
 */
export const getIssueTypeLogoProps = (logoProps: IIssueType["logo_props"]): TLogoProps | undefined => {
  if (!logoProps) return undefined;
  const anyProps = logoProps as Record<string, unknown>;
  if ("in_use" in anyProps) return logoProps as TLogoProps;
  if ("in_app_icon" in anyProps && anyProps.in_app_icon) {
    const icon = anyProps.in_app_icon as { name?: string; color?: string };
    return { in_use: "icon", icon: { name: icon.name, color: icon.color } };
  }
  return undefined;
};

export function TypeIcon({ issueType, size = 16 }: TTypeIconProps) {
  const logoProps = getIssueTypeLogoProps(issueType?.logo_props);
  if (!logoProps?.in_use) {
    return <span className="rounded-sm bg-layer-1" style={{ height: size, width: size }} />;
  }
  return <Logo logo={logoProps} size={size} type="lucide" />;
}
