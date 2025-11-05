/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { jsonrpc } from "@web/core/network/rpc_service";

const cogMenuRegistry = registry.category("cogMenu");

export class ExportWithTimesheets extends Component {
    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
    }

async onExport() {
    try {
        const allVisibleIds = this.env.model.root.records.map(record => record.resId);
        const model = this.props.list?.model || "service.call.count";



        console.log("All record IDs:", allVisibleIds);

        if (!allVisibleIds.length) {
            this.notification.add(_t("No records available for export."), { type: "warning" });
            return;
        }

        await this.action.doAction("industry_fsm.action_service_call_export", {
            additionalContext: {
                active_model: model,
                active_ids: allVisibleIds,
            },
        });

    } catch (error) {
        console.error("Export failed error:", error);
        this.notification.add(_t("Export failed."), { type: "danger" });
    }
}




}

ExportWithTimesheets.template = "industry_fsm.ExportWithTimesheets";


export const exportWithTimesheetsItem = {
    Component: ExportWithTimesheets,
    groupNumber: 10,
    isDisplayed: ({ config }) => {
        const { actionType, viewType, viewId } = config;



        return actionType === "ir.actions.act_window"
            && viewType === "list"
            && viewId === 6801;
    },
};

cogMenuRegistry.add("export-with-timesheets", exportWithTimesheetsItem, { sequence: 15 });