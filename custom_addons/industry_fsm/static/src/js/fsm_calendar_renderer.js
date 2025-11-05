/** @odoo-module **/
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { patch } from "@web/core/utils/patch";

patch(CalendarCommonRenderer.prototype, {
    async onEventClick(info) {
        if (info?.jsEvent?.defaultPrevented) {
            return;
        }

        if (this.props.model.resModel === "project.task") {
            info.jsEvent.preventDefault();
            const recordId = parseInt(info.event.id, 10);

            // Step 1: Read the 'is_fsm' field of the task
            const [task] = await this.env.services.orm.read(
                "project.task",
                [recordId],
                ["is_fsm"]
            );

            // If is_fsm is false, fallback to original behavior
            if (!task?.is_fsm) {
                return super.onEventClick?.(info);
            }

            // Step 2: Get the custom FSM view ID using a backend method
            const result = await this.env.services.orm.call(
                "project.task",
                "get_fsm_calendar_view_id",
                []
            );

            if (!result) {
                console.error("Custom FSM view not found");
                return;
            }

            // Step 3: Open custom FSM form
            await this.env.services.action.doAction({
                type: "ir.actions.act_window",
                name: "Service Call",
                res_model: this.props.model.resModel,
                res_id: recordId,
                views: [[result, "form"]],
                target: "new",
                context: this.props.context,
            });
        } else {
            return super.onEventClick?.(info);
        }
    },
});
