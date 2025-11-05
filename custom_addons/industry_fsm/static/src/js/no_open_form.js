/** @odoo-module **/

import { PivotRenderer } from "@web/views/pivot/pivot_renderer";
import { patch } from "@web/core/utils/patch";

// Patch the PivotRenderer to override the openView behavior
patch(PivotRenderer.prototype, {
    /**
     * Override openView to only show list view, no form view
     * @param {Array} domain
     * @param {Array} views
     * @param {Object} context
     */
    openView(domain, views, context) {
        // Check if this is for your specific model
        if (this.model.metaData.resModel === 'service.charge.report') {
            // Only use list view, remove form view
            const listViews = views.filter(view => view[1] === 'list');

            this.actionService.doAction({
                type: "ir.actions.act_window",
                name: this.model.metaData.title,
                res_model: this.model.metaData.resModel,
                views: listViews,
                view_mode: "list",
                target: "current",
                context,
                domain,
            });
        } else {
            // For other models, use the original behavior
            super.openView(domain, views, context);
        }
    },

    /**
     * Override onOpenView to customize the views array
     * @param {Object} cell
     */
    onOpenView(cell) {
        if (cell.value === undefined || this.model.metaData.disableLinking) {
            return;
        }

        const context = Object.assign({}, this.model.searchParams.context);
        Object.keys(context).forEach((x) => {
            if (x === "group_by" || x.startsWith("search_default_")) {
                delete context[x];
            }
        });

        // For service.charge.report model, only include list view
        if (this.model.metaData.resModel === 'service.charge.report') {
            const { views = [] } = this.env.config;
            this.views = ["list"].map((viewType) => {
                const view = views.find((view) => view[1] === viewType);
                return [view ? view[0] : false, viewType];
            });
        } else {
            // For other models, use the original behavior
            const { views = [] } = this.env.config;
            this.views = ["list", "form"].map((viewType) => {
                const view = views.find((view) => view[1] === viewType);
                return [view ? view[0] : false, viewType];
            });
        }

        const group = {
            rowValues: cell.groupId[0],
            colValues: cell.groupId[1],
            originIndex: cell.originIndexes[0],
        };
        this.openView(this.model.getGroupDomain(group), this.views, context);
    }
});