/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { registry } from "@web/core/registry";
import { Navbar } from "@point_of_sale/app/navbar/navbar";

export class TotalSales extends Component {
    static template = "point_of_sale.TotalSales";

    setup() {
        this.pos = usePos();
        this.state = { total: '...' };
        this.updateTotal();

        // Update every 5 minutes
        setInterval(() => this.updateTotal(), 5 * 60 * 1000);
    }

    async updateTotal() {
        try {
            const result = await this.pos.env.services.rpc(
                '/web/dataset/call_kw/pos.order/get_today_total_sales',
                {
                    model: 'pos.order',
                    method: 'get_today_total_sales',
                    args: [],
                    kwargs: {},
                }
            );

            if (result && result.formatted_total) {
                this.state.total = result.formatted_total;
                this.render();
            }
        } catch (error) {
            console.error('Failed to fetch total sales:', error);
            this.state.total = 'Error loading total';
            this.render();
        }
    }
}

// Register the component
Navbar.components = {
    ...Navbar.components,
    TotalSales,
};

registry.category("pos_components").add("TotalSales", TotalSales);