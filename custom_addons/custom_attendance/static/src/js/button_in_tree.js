/** @odoo-module */
import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
export class buttonListController extends ListController {
setup() {
        super.setup();
        console.log("Custom controller loaded");
    }



}
registry.category("views").add("button_in_tree", {
   ...listView,
   Controller: buttonListController,
   buttonTemplate: "button.ListView.Buttons",
});
