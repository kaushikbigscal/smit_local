/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import  paymentForm  from "@payment/js/payment_form";


patch(paymentForm.prototype, {
    /**
     * Override to send user-entered amount instead of the default full amount.
     */
    _prepareTransactionRouteParams() {
        // Call original
        const params = super._prepareTransactionRouteParams(...arguments);

        // Find custom input
        const input = document.querySelector("#payment_amount");
        if (input) {
            const customAmount = parseFloat(input.value);
            if (!isNaN(customAmount) && customAmount > 0) {
                params.amount = customAmount; 
            }
        }

        return params;
    },
});
