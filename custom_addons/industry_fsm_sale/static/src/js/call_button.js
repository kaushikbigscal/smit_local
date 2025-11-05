/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

console.log("Registered");

export class CallPartnerAction extends Component {
    setup() {
        console.log("✅ call_partner_action loaded");
        console.log("📦 Props received:", this.props);

        const phone = this.props.action?.params?.phone;
        console.log("📞 Phone from props:", phone);

        if (phone) {
            window.open(`tel:${phone}`, "_self");
            setTimeout(() => window.history.back(), 1000);
        } else {
            console.warn("⚠️ No phone number provided.");
        }
    }



    static template = "industry_fsm_sale.call_partner_action_template"; // dummy to satisfy Owl
}

registry.category("actions").add("call_partner_action", CallPartnerAction);
