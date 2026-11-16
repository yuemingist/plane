/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { EIssuesStoreType } from "@plane/types";
import { WorkItemFilterStore } from "./filter.store";

/**
 * Contract tests for the WorkItemFilterStore instance registry.
 *
 * BUG-08 context: the filter HOC registers its instance on mount and deletes it on unmount.
 * React StrictMode (development) runs mount effects as setup -> cleanup -> setup, so the store
 * must support the exact sequence create -> delete -> create for the same entity key while
 * keeping the second instance fully functional. The HOC (apps/web components/work-item-filters
 * filters-hoc/base.tsx) relies on this contract after the BUG-08 fix.
 */

const createStore = () => new WorkItemFilterStore();

const onChangeA = (_expression: unknown) => {};
const onChangeB = (_expression: unknown) => {};

const baseParams = (overrides: Record<string, unknown> = {}) => ({
  entityType: EIssuesStoreType.PROJECT,
  entityId: "project-1",
  ...overrides,
});

describe("WorkItemFilterStore.getOrCreateFilter", () => {
  it("creates and registers a filter instance for the entity key", () => {
    const store = createStore();
    const filter = store.getOrCreateFilter(baseParams());

    expect(filter).toBeDefined();
    expect(store.getFilter(EIssuesStoreType.PROJECT, "project-1")).toBe(filter);
  });

  it("returns the same instance for repeated calls (idempotent registration)", () => {
    const store = createStore();
    const first = store.getOrCreateFilter(baseParams());
    const second = store.getOrCreateFilter(baseParams());

    expect(second).toBe(first);
    expect(store.filters.size).toBe(1);
  });

  it("keeps instances of different entity keys or types isolated", () => {
    const store = createStore();
    const projectFilter = store.getOrCreateFilter(baseParams());
    const cycleFilter = store.getOrCreateFilter(
      baseParams({ entityType: EIssuesStoreType.CYCLE, entityId: "cycle-1" })
    );

    expect(projectFilter).not.toBe(cycleFilter);
    expect(store.filters.size).toBe(2);
  });
});

describe("WorkItemFilterStore.deleteFilter", () => {
  it("removes the instance so getFilter returns undefined", () => {
    const store = createStore();
    store.getOrCreateFilter(baseParams());
    store.deleteFilter(EIssuesStoreType.PROJECT, "project-1");

    expect(store.getFilter(EIssuesStoreType.PROJECT, "project-1")).toBeUndefined();
  });

  it("supports the StrictMode create -> delete -> create sequence with a functional instance", () => {
    const store = createStore();
    // setup (mount effect)
    const first = store.getOrCreateFilter(baseParams());
    // cleanup (StrictMode simulated unmount)
    store.deleteFilter(EIssuesStoreType.PROJECT, "project-1");
    expect(store.getFilter(EIssuesStoreType.PROJECT, "project-1")).toBeUndefined();
    // setup again (StrictMode re-run)
    const second = store.getOrCreateFilter(baseParams());

    expect(second).toBeDefined();
    expect(second).not.toBe(first);
    expect(store.getFilter(EIssuesStoreType.PROJECT, "project-1")).toBe(second);
    // the recreated instance exposes a working visibility toggle (what the header toggle calls)
    expect(second.isVisible).toBe(false);
    second.toggleVisibility(true);
    expect(second.isVisible).toBe(true);
  });
});

describe("WorkItemFilterStore.getOrCreateFilter option updates", () => {
  it("updates expression options and callback on an existing instance without resetting it", () => {
    const store = createStore();
    const filter = store.getOrCreateFilter(
      baseParams({
        onExpressionChange: onChangeA,
        expressionOptions: { updateViewOptions: { onViewUpdate: onChangeA, label: "update" } },
      })
    );

    const updated = store.getOrCreateFilter(
      baseParams({
        onExpressionChange: onChangeB,
        expressionOptions: { updateViewOptions: { onViewUpdate: onChangeB, label: "updated" } },
      })
    );

    expect(updated).toBe(filter);
    expect(filter.onExpressionChange).toBe(onChangeB);
    expect(filter.updateViewOptions?.label).toBe("updated");
  });
});
