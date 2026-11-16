/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo } from "react";
import { observer } from "mobx-react";
import { v4 as uuidv4 } from "uuid";
// plane imports
import type { TSaveViewOptions, TUpdateViewOptions } from "@plane/constants";
import type { IWorkItemFilterInstance } from "@plane/shared-state";
import type { IIssueFilters, TWorkItemFilterExpression } from "@plane/types";
// store hooks
import { useWorkItemFilters } from "@/hooks/store/work-item-filters/use-work-item-filters";
// plane web imports
import type { TWorkItemFiltersEntityProps } from "@/hooks/work-item-filters/use-work-item-filters-config";
import { useWorkItemFiltersConfig } from "@/hooks/work-item-filters/use-work-item-filters-config";
// local imports
import type { TSharedWorkItemFiltersHOCProps, TSharedWorkItemFiltersProps } from "./shared";

type TAdditionalWorkItemFiltersProps = {
  saveViewOptions?: TSaveViewOptions<TWorkItemFilterExpression>;
  updateViewOptions?: TUpdateViewOptions<TWorkItemFilterExpression>;
} & TWorkItemFiltersEntityProps;

type TWorkItemFiltersHOCProps = TSharedWorkItemFiltersHOCProps & TAdditionalWorkItemFiltersProps;

export const WorkItemFiltersHOC = observer(function WorkItemFiltersHOC(props: TWorkItemFiltersHOCProps) {
  const { children, initialWorkItemFilters } = props;

  // Only initialize filter instance when initial work item filters are defined
  if (!initialWorkItemFilters)
    return <>{typeof children === "function" ? children({ filter: undefined }) : children}</>;

  return (
    <WorkItemFilterRoot {...props} initialWorkItemFilters={initialWorkItemFilters}>
      {children}
    </WorkItemFilterRoot>
  );
});

type TWorkItemFilterProps = TSharedWorkItemFiltersProps &
  TAdditionalWorkItemFiltersProps & {
    initialWorkItemFilters: IIssueFilters;
    children: React.ReactNode | ((props: { filter: IWorkItemFilterInstance | undefined }) => React.ReactNode);
  };

const WorkItemFilterRoot = observer(function WorkItemFilterRoot(props: TWorkItemFilterProps) {
  const {
    children,
    entityType,
    entityId,
    filtersToShowByLayout,
    initialWorkItemFilters,
    isTemporary,
    saveViewOptions,
    updateFilters,
    updateViewOptions,
    showOnMount,
    ...entityConfigProps
  } = props;
  // store hooks
  const { getOrCreateFilter, deleteFilter, getFilter } = useWorkItemFilters();
  // derived values
  const workItemEntityID = useMemo(
    () => (isTemporary ? `TEMP-${entityId ?? uuidv4()}` : entityId),
    [isTemporary, entityId]
  );
  // memoize initial values to prevent re-computations when reference changes
  const initialUserFilters = useMemo(() => initialWorkItemFilters.richFilters, [initialWorkItemFilters]);
  const workItemFiltersConfig = useWorkItemFiltersConfig({
    allowedFilters: filtersToShowByLayout ? filtersToShowByLayout : [],
    ...entityConfigProps,
  });

  // Own the filter instance lifecycle at the entity scope: create it on mount and delete it on
  // unmount. React StrictMode (development only) runs mount effects as setup -> cleanup ->
  // setup, so the simulated-unmount cleanup deletes the instance and the follow-up setup
  // re-creates it, keeping the store consistent with the mounted tree. Registering from an
  // effect (instead of during render) also keeps the store as the single source of truth: the
  // render-time read below re-renders this observer whenever the instance is (re)created.
  useEffect(
    () => {
      getOrCreateFilter({
        entityType,
        entityId: workItemEntityID,
        initialExpression: initialUserFilters,
        onExpressionChange: updateFilters,
        expressionOptions: {
          saveViewOptions,
          updateViewOptions,
        },
        showOnMount,
      });
      // delete filter instance when component unmounts
      return () => {
        deleteFilter(entityType, workItemEntityID);
      };
    },
    // The instance must not be re-created (losing its local state) when the expression options
    // change; those are synced to the existing instance by the effect underneath.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [deleteFilter, entityType, getOrCreateFilter, workItemEntityID]
  );

  // Keep the current instance's expression options and change callback up to date without
  // resetting its lifecycle (mirrors the update path that the store's getOrCreateFilter takes
  // for existing instances).
  useEffect(() => {
    const existingFilter = getFilter(entityType, workItemEntityID);
    if (!existingFilter) return;
    if (saveViewOptions || updateViewOptions) {
      existingFilter.updateExpressionOptions({
        saveViewOptions,
        updateViewOptions,
      });
    }
    if (updateFilters) {
      existingFilter.onExpressionChange = updateFilters;
    }
  }, [entityType, getFilter, saveViewOptions, updateFilters, updateViewOptions, workItemEntityID]);

  // read the instance from the store so this observer re-renders when it is (re)created
  const workItemLayoutFilter = getFilter(entityType, workItemEntityID);

  useEffect(() => {
    if (!workItemLayoutFilter) return;
    workItemLayoutFilter.configManager.setAreConfigsReady(workItemFiltersConfig.areAllConfigsInitialized);
    workItemLayoutFilter.configManager.registerAll(workItemFiltersConfig.configs);
  }, [workItemFiltersConfig.areAllConfigsInitialized, workItemFiltersConfig.configs, workItemLayoutFilter]);

  return <>{typeof children === "function" ? children({ filter: workItemLayoutFilter }) : children}</>;
});
