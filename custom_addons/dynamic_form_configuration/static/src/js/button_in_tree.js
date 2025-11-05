/** @odoo-module */
import { useService } from "@web/core/utils/hooks";
import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { _t } from "@web/core/l10n/translation";

export class ButtonListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        console.log("ButtonListController initialized");
    }

    async action_create_fields() {
        const result = await this.orm.call(
            this.props.resModel,
            'action_create_fields',
            [], // Empty array for args since we don't need to pass any
            {} // Empty object for kwargs
        );

        // Reload the view
        await this.model.load();

        // If you want to show a notification of success
        const notification = this.env.services.notification;
        notification.add(_t("Fields created successfully"), {
            type: 'success',
        });
    }
}

registry.category("views").add("button_in_tree", {
    ...listView,
    Controller: ButtonListController,
    buttonTemplate: "button.ListView.Buttons",
});