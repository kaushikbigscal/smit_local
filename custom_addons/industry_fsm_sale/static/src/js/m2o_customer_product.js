/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onWillStart } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup();

        if (this.props.resModel === "customer.product.mapping") {
            const customerId = this.props.context?.default_customer_id;
            const orm = this.env.services.orm;  // ORM service for RPC

            onWillStart(() => {
                console.log("Wizard is about to start. Context:", this.props.context);
            });

            onMounted(async () => {
                console.log("Wizard mounted. Injecting customer_id:", customerId);

                if (customerId && !this.model.root.data.customer_id) {
                    try {
                        //fetch proper display_name from backend
                        const [partner] = await orm.read("res.partner", [customerId], ["display_name"]);
                        this.model.root.update({
                            customer_id: [partner.id, partner.display_name],
                        });

                    } catch (err) {
                        console.error("Failed to fetch customer display_name", err);
                    }
                }
            });
        }
    },
});
