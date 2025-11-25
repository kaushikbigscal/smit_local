///** @odoo-module **/
//
//import { StockReportSearchModel } from "@stock/views/search/stock_report_search_model";
//import { patch } from "@web/core/utils/patch";
//
//console.log("🔧 Patching StockReportSearchModel with distributor-aware filtering");
//
//const original_loadWarehouses = StockReportSearchModel.prototype._loadWarehouses;
//
//patch(StockReportSearchModel.prototype, {
//    async _loadWarehouses() {
//        const actionId = this.context?.actionId;
//        let domain;
//
//        if (actionId === 'action_product_stock_distributor') {
//            console.log("🏭 Distributor Stock action → excluding distributor warehouses");
//            domain = [['is_distributor_warehouse', '=', true]];
//        } else {
//            console.log("📦 Other stock actions → including only distributor warehouses");
//            domain = [['is_distributor_warehouse', '=', false]];
//        }
//
//        try {
//            this.warehouses = await this.orm.call(
//                'stock.warehouse',
//                'get_current_warehouses',
//                [domain],
//                { context: this.context },
//            );
//            console.log("✅ Warehouses loaded:", this.warehouses);
//        } catch (error) {
//            console.error("❌ Error in patched _loadWarehouses:", error);
//            // fallback to original method
//            await original_loadWarehouses.apply(this, arguments);
//        }
//    }
//});
//
//console.log("✅ Conditional StockReportSearchModel patch applied successfully");

/** @odoo-module **/

import { StockReportSearchModel } from "@stock/views/search/stock_report_search_model";
import { patch } from "@web/core/utils/patch";

console.log("Patching StockReportSearchModel");

const originalLoad = StockReportSearchModel.prototype._loadWarehouses;

patch(StockReportSearchModel.prototype, {
    async _loadWarehouses() {
        console.log("_loadWarehouses called");
        const actionId = this.context?.actionId;
        console.log("actionId =", actionId);

        this.isDistributorStock = (actionId === 'action_product_stock_distributor');
        console.log("isDistributorStock =", this.isDistributorStock);

        const domain = this.isDistributorStock
            ? [['is_distributor_warehouse', '=', true]]
            : [];
        console.log("domain =", domain);

        try {
            console.log("Calling stock.warehouse.get_current_warehouses");
            const warehouses = await this.orm.call(
                'stock.warehouse',
                'get_current_warehouses',
                [domain],
                { context: this.context },
            );
            console.log("warehouses returned:", warehouses);

            this.warehouses = warehouses;
            console.log("this.warehouses set");

            if (this.isDistributorStock) {
                console.log("Hiding 'All Warehouses' for distributor stock");
                this._toggleAllWarehouses(false); // hide

                // ✅ after the panel has rendered, select the first warehouse
                if (warehouses.length > 0) {
                    const firstId = warehouses[0].id;
                    console.log("Will select first warehouse ID:", firstId);

                    // wait for DOM to exist then select
                    setTimeout(() => {
                        console.log("Selecting first warehouse now…");
                        this.applyWarehouseContext(firstId);

                        // add bold class to the first one
                        const spans = document.querySelectorAll(
                            ".o_search_panel .o_search_panel_section.o_search_panel_warehouse span"
                        );

                        spans.forEach(span => {
                            if (span.textContent?.trim() === warehouses[0].name) {
                                span.classList.add("fw-bolder");
                            } else {
                                span.classList.remove("fw-bolder");
                            }

                            // attach click event once
                            if (!span.dataset.boldHandlerAdded) {
                                span.addEventListener("click", () => {
                                    spans.forEach(s => s.classList.remove("fw-bolder"));
                                    span.classList.add("fw-bolder");
                                });
                                span.dataset.boldHandlerAdded = "true";
                            }
                        });
                    }, 400);
                }
            } else {
                console.log("Showing 'All Warehouses' for normal stock");
                this._toggleAllWarehouses(true); // show
            }
        } catch (error) {
            console.error("Error in patched _loadWarehouses:", error);
            return originalLoad.apply(this, arguments);
        }

        console.log("Returning warehouses from _loadWarehouses");
    },

    _toggleAllWarehouses(show) {
        const applyToggle = () => {
            console.log("Looking for All Warehouses span...");
            document.querySelectorAll(
                ".o_search_panel .o_search_panel_section.o_search_panel_warehouse span"
            ).forEach(span => {
                if (span.textContent?.trim() === 'All Warehouses') {
                    const li = span.closest("li");
                    if (li) {
                        li.style.removeProperty('display');
                        if (!show) {
                            console.log("Hiding All Warehouses");
                            li.style.setProperty('display', 'none', 'important');
                        } else {
                            console.log("Showing All Warehouses");
                            li.style.removeProperty('display');
                        }
                    }
                }
            });
        };

        requestAnimationFrame(applyToggle);
        setTimeout(applyToggle, 300);

        if (!this._warehouseObserver) {
            this._warehouseObserver = new MutationObserver(() => applyToggle());
            this._warehouseObserver.observe(document.body, { childList: true, subtree: true });
            setTimeout(() => this._warehouseObserver.disconnect(), 10000);
        }
    },
});

console.log("Patch applied");



//
///** @odoo-module **/
//
//import { StockReportSearchModel } from "@stock/views/search/stock_report_search_model";
//import { patch } from "@web/core/utils/patch";
//
//console.log("Patching StockReportSearchModel");
//
//const originalLoad = StockReportSearchModel.prototype._loadWarehouses;
//
//patch(StockReportSearchModel.prototype, {
//    async _loadWarehouses() {
//        console.log("_loadWarehouses called");
//        const actionId = this.context?.actionId;
//        console.log("actionId =", actionId);
//
//        this.isDistributorStock = (actionId === 'action_product_stock_distributor');
//        console.log("isDistributorStock =", this.isDistributorStock);
//
//        const domain = this.isDistributorStock
//            ? [['is_distributor_warehouse', '=', true]]
//            : [];
//        console.log(" domain =", domain);
//
//        try {
//            console.log("Calling stock.warehouse.get_current_warehouses");
//            const warehouses = await this.orm.call(
//                'stock.warehouse',
//                'get_current_warehouses',
//                [domain],
//                { context: this.context },
//            );
//            console.log("warehouses returned:", warehouses);
//
//            this.warehouses = warehouses;
//            console.log("this.warehouses set");
//
//            if (this.isDistributorStock) {
//                console.log("Hiding 'All Warehouses' for distributor stock");
//                this._toggleAllWarehouses(false); // hide
//            } else {
//                console.log("Showing 'All Warehouses' for normal stock");
//                this._toggleAllWarehouses(true); // show
//            }
//        } catch (error) {
//            console.error("Error in patched _loadWarehouses:", error);
//            return originalLoad.apply(this, arguments);
//        }
//
//        console.log("Returning warehouses from _loadWarehouses");
//    },
//
//    _toggleAllWarehouses(show) {
//        const applyToggle = () => {
//            console.log("Looking for All Warehouses span...");
//            document.querySelectorAll(
//                ".o_search_panel .o_search_panel_section.o_search_panel_warehouse span"
//            ).forEach(span => {
//                if (span.textContent?.trim() === 'All Warehouses') {
//                    const li = span.closest("li");
//                    if (li) {
//                        li.style.removeProperty('display');
//                        if (!show) {
//                            console.log("Hiding All Warehouses");
//                            li.style.setProperty('display', 'none', 'important');
//                        } else {
//                            console.log("Showing All Warehouses");
//                            li.style.removeProperty('display');
//                        }
//                    }
//                }
//            });
//        };
//
//        // initial apply
//        requestAnimationFrame(applyToggle);
//        setTimeout(applyToggle, 300);
//
//        // observe for later DOM re-renders (both show and hide)
//        if (!this._warehouseObserver) {
//            this._warehouseObserver = new MutationObserver(() => applyToggle());
//            this._warehouseObserver.observe(document.body, { childList: true, subtree: true });
//            // optional: disconnect after some time if you want
//            setTimeout(() => this._warehouseObserver.disconnect(), 10000);
//        }
//    },
//});
//
//console.log("Patch applied");



///** @odoo-module **/
//
//import { StockReportSearchModel } from "@stock/views/search/stock_report_search_model";
//import { patch } from "@web/core/utils/patch";
//
//console.log("🔧 Patching StockReportSearchModel conditionally for distributor filtering");
//
//const original_loadWarehouses = StockReportSearchModel.prototype._loadWarehouses;
//
//patch(StockReportSearchModel.prototype, {
//    async _loadWarehouses() {
//        const actionId = this.context?.actionId;
//        if (actionId === 'action_product_stock_distributor') {
//            console.log("🏭 Filtering distributor warehouses");
//
//            const domain = [['is_distributor_warehouse', '=', false]];
//
//            try {
//                this.warehouses = await this.orm.call(
//                    'stock.warehouse',
//                    'get_current_warehouses',
//                    [domain],
//                    { context: this.context },
//                );
//                console.log("✅ Filtered warehouses loaded:", this.warehouses);
//            } catch (error) {
//                console.error("❌ Error in patched _loadWarehouses:", error);
//                // fallback to original method
//                await original_loadWarehouses.apply(this, arguments);
//            }
//        } else {
//            // For other actions, just call the original method
//            await original_loadWarehouses.apply(this, arguments);
//        }
//    }
//});
//
//console.log("✅ Conditional StockReportSearchModel patch applied successfully");







///** @odoo-module **/
//
//import { StockReportSearchModel } from "@stock/views/search/stock_report_search_model";
//import { patch } from "@web/core/utils/patch";
//
//console.log("🔧 Patching StockReportSearchModel for distributor filtering");
//
//// Patch the original StockReportSearchModel to filter distributor warehouses
//patch(StockReportSearchModel.prototype, {
//    async _loadWarehouses() {
//        console.log("🏭 Patched _loadWarehouses called - filtering distributor warehouses");
//
//        // Apply the distributor filter
//        const domain = [['is_distributor_warehouse', '=', false]];
//        console.log("🎯 Using domain filter:", domain);
//
//        try {
//            this.warehouses = await this.orm.call(
//                'stock.warehouse',
//                'get_current_warehouses',
//                [domain],
//                { context: this.context },
//            );
//
//            console.log("✅ Filtered warehouses loaded:", this.warehouses);
//            console.log("📊 Filtered count:", this.warehouses?.length);
//
//        } catch (error) {
//            console.error("❌ Error in patched _loadWarehouses:", error);
//            // Fallback to original behavior
//            this.warehouses = await this.orm.call(
//                'stock.warehouse',
//                'get_current_warehouses',
//                [[]],
//                { context: this.context },
//            );
//        }
//    }
//});
//
//console.log("✅ StockReportSearchModel patch applied successfully");