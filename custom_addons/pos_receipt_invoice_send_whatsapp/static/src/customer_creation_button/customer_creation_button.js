/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CreateCustomerButton extends Component {
    static template = "point_of_sale.CreateCustomerButton";

    setup() {
        this.pos = usePos();
        this.notification = useService("notification");
        this.rpc = useService("rpc");
        this.state = {
            customerName: "",
            customerMobile: ""
        };
    }

    validateMobile(mobile) {
        return mobile.length === 10 && /^\d+$/.test(mobile);
    }

    async createCustomer() {
        try {
            if (!this.state.customerName) {
                this.notification.add("Please enter customer name", {
                    type: 'warning',
                });
                return;
            }

            if (!this.validateMobile(this.state.customerMobile)) {
                this.notification.add("Please enter valid 10-digit mobile number", {
                    type: 'warning',
                });
                return;
            }

            const result = await this.rpc("/pos/create_customer", {
                partner: {
                    name: this.state.customerName,
                    mobile: this.state.customerMobile,
                }
            });

            if (result.success) {
                // Get the current order
                const order = this.pos.get_order();

                // Create partner object with the returned data
                const partner = {
                    id: result.partnerId,
                    name: this.state.customerName,
                    mobile: this.state.customerMobile
                };

                // Add partner to pos partner list
                this.pos.db.add_partners([partner]);

                // Set the partner to current order
                if (order) {
                    order.set_partner(partner);
                }

                // Clear form
                this.state.customerName = "";
                this.state.customerMobile = "";

                this.notification.add("Customer created and selected successfully!", {
                    type: 'success',
                });
            }
        } catch (error) {
            this.notification.add("Error creating customer: " + (error.message || "Unknown error"), {
                type: 'danger',
            });
        }
    }
}

ProductScreen.addControlButton({
    component: CreateCustomerButton,
    position: ['before', 'RefundButton'],
    condition: function () {
        return true;
    },
});






///** @odoo-module */
//
//import { usePos } from "@point_of_sale/app/store/pos_hook";
//import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
//import { Component, useState } from "@odoo/owl";
//import { useService } from "@web/core/utils/hooks";
//
//export class CreateCustomerButton extends Component {
//    static template = "point_of_sale.CreateCustomerButton";
//
//    setup() {
//        this.pos = usePos();
//        this.notification = useService("notification");
//        this.rpc = useService("rpc");
//        this.state = useState({
//            customerName: "",
//            customerMobile: ""
//        });
//    }
//
//    async createCustomer() {
//        try {
//            if (!this.state.customerName || !this.state.customerMobile) {
//                this.notification.add("Please fill both name and mobile number", {
//                    type: 'warning',
//                });
//                return;
//            }
//
//            const result = await this.rpc("/pos/ui/create_customer", {
//                partner: {
//                    name: this.state.customerName,
//                    mobile: this.state.customerMobile,
//                }
//            });
//
//            if (result.success) {
//                // Clear form
//                this.state.customerName = "";
//                this.state.customerMobile = "";
//
//                this.notification.add("Customer created successfully!", {
//                    type: 'success',
//                });
//            } else {
//                throw new Error(result.message || "Failed to create customer");
//            }
//        } catch (error) {
//            this.notification.add("Error creating customer: " + (error.message || "Unknown error"), {
//                type: 'danger',
//            });
//        }
//    }
//}
//
//ProductScreen.addControlButton({
//    component: CreateCustomerButton,
//    position: ['before', 'RefundButton'],
//    condition: function () {
//        return true;
//    },
//});