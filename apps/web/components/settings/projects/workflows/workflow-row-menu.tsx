/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@makeplane/propel/components/menu";
import { HideOutline, HistoryOutline, MoreHorizontalOutline } from "@makeplane/propel/icons";

type TWorkflowRowMenuProps = {
  onRequestDisable: () => void;
  onRequestHistory: () => void;
};

/**
 * The Default Workflow row's "…" menu — exactly two entries, matching the cloud
 * Business tier (58号 screenshot 3): Disable (opens the shared confirm dialog)
 * and View change history. No rule-editor entry exists at this tier.
 */
export const WorkflowRowMenu = observer(function WorkflowRowMenu(props: TWorkflowRowMenuProps) {
  const { onRequestDisable, onRequestHistory } = props;
  // hooks
  const { t } = useTranslation();

  return (
    <Menu>
      <MenuTrigger
        render={
          <IconButton
            type="button"
            variant="ghost"
            size="xs"
            aria-label={t("aria_labels.common.more_actions")}
            icon={<Icon icon={MoreHorizontalOutline} />}
          />
        }
      />
      <MenuContent side="bottom" align="end">
        <MenuItem
          icon={<Icon icon={HideOutline} />}
          label={t("workflows.settings.row_menu.disable")}
          onClick={onRequestDisable}
        />
        <MenuItem
          icon={<Icon icon={HistoryOutline} />}
          label={t("workflows.quick_actions.view_change_history")}
          onClick={onRequestHistory}
        />
      </MenuContent>
    </Menu>
  );
});
