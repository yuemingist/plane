/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useContext } from "react";
// store
import { StoreContext } from "@/lib/store-context";
import type { IIssuePropertyStore } from "@/store/issue-property.store";

export const useIssueProperty = (): IIssuePropertyStore => {
  const storeContext = useContext(StoreContext);
  if (storeContext === undefined) throw new Error("useIssueProperty must be used within StoreProvider");
  return storeContext.issueProperty;
};
