/** @odoo-module **/

import { StockReportSearchPanel } from "@stock/views/search/stock_report_search_panel";

export class ProductInstallationSearchPanel extends StockReportSearchPanel {
    setup() {
        super.setup(...arguments);
    }

    //---------------------------------------------------------------------
    // Actions / Getters
    //---------------------------------------------------------------------

    get warehouses() {
        const allWarehouses = this.env.searchModel.getWarehouses();

        // Check if current action is action_product_stock_distributor
        if (this.isDistributorAction()) {
            // Filter warehouses where is_distributor_warehouse is false
            return allWarehouses.filter(warehouse => !warehouse.is_distributor_warehouse);
        }

        return allWarehouses;
    }

    get filteredWarehouseCount() {
        // Get count of warehouses based on current context/action
        if (this.isDistributorAction()) {
            const allWarehouses = this.env.searchModel.getWarehouses();
            return allWarehouses.filter(warehouse => !warehouse.is_distributor_warehouse).length;
        }
        return this.env.searchModel.getWarehouses().length;
    }

    isDistributorAction() {
        // Check if current action is action_product_stock_distributor
        const currentAction = this.env.services.action.currentController?.action;
        return currentAction && currentAction.xml_id === 'product_installation.action_product_stock_distributor';
    }

    clearWarehouseContext() {
        // Apply conditional logic for clearWarehouseContext
        if (this.isDistributorAction()) {
            // For distributor action, clear context but maintain distributor filter
            this.env.searchModel.clearWarehouseContext();
            // You might want to apply additional domain here for non-distributor warehouses
            this.env.searchModel.applyDistributorWarehouseFilter();
        } else {
            // Default behavior for other actions
            super.clearWarehouseContext();
        }
        this.selectedWarehouse = null;
    }

    applyWarehouseContext(warehouse_id) {
        super.applyWarehouseContext(warehouse_id);
    }
}

ProductInstallationSearchPanel.template = "product_installation.ProductInstallationSearchPanel";