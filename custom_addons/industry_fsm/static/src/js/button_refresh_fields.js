/** @odoo-module */

import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { _t } from "@web/core/l10n/translation";

export class ItemReceiptListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
        console.log("ItemReceiptListController initialized");
    }

    async action_refresh_fields() {
        await this.orm.call(
            this.props.resModel,
            'action_refresh_fields',
            [],
            {}
        );

        await this.model.load(); // Reload the model data

        this.notification.add(_t("Fields refreshed successfully"), {
            type: 'success',
        });
    }
}

registry.category("views").add("item_receipt_refresh_list", {
    ...listView,
    Controller: ItemReceiptListController,
    buttonTemplate: "item_receipt.ListView.Buttons",
});
