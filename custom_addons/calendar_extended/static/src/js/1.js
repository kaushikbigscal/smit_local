/** @odoo-module **/
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { patch } from "@web/core/utils/patch";

patch(CalendarCommonRenderer.prototype, {
    async onEventClick(info) {
        info.jsEvent.preventDefault();
        const recordId = parseInt(info.event.id, 10);

        // --- Project Task case ---
        if (this.props.model.resModel === "project.task") {
            const [task] = await this.env.services.orm.read(
                "project.task",
                [recordId],
                ["is_fsm"]
            );

            if (task?.is_fsm) {
                // Default behavior
                return super.onEventClick?.(info);
            }

            // Open custom FSM form
            await this.env.services.action.doAction({
                type: "ir.actions.act_window",
                name: "Service Call",
                res_model: "project.task",
                res_id: recordId,
                views: [[false, "form"]],
                target: "new",
                context: this.props.context,
                view_id: "field_service_tracking.view_task_calendar_form", // task form
            });
            return;
        }

        // --- CRM Lead case ---
        if (this.props.model.resModel === "crm.lead") {
            const [lead] = await this.env.services.orm.read(
                "crm.lead",
                [recordId],
                ["lead_type"]
            );

            await this.env.services.action.doAction({
                type: "ir.actions.act_window",
                name: "Lead",
                res_model: "crm.lead",
                res_id: recordId,
                views: [[false, "form"]],
                target: "new",
                context: this.props.context,
                view_id: "crm.view_lead_calendar_form",  // 👈 replace with your XML ID
            });
            return;
        }

        // --- Fallback to default behavior ---
        return super.onEventClick?.(info);
    },
});

