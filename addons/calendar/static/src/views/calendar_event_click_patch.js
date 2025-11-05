/** @odoo-module **/
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { patch } from "@web/core/utils/patch";

patch(CalendarCommonRenderer.prototype, {
    async onEventClick(info) {
        if (info?.jsEvent?.defaultPrevented) return;

        const eventId = parseInt(info.event.id, 10);
        if (!isNaN(eventId)) {
            // Get the record from the model to access rawRecord
            const record = this.props.model.records[eventId];
            if (record && record.rawRecord && record.rawRecord.calendar_rule_id) {
                // Event has calendar_rule_id, call server method to get custom form
                const action = await this.env.services.orm.call(
                    "calendar.event",
                    "get_linked_form_action",
                    [eventId]
                );
                if (action) {
                    info.jsEvent.preventDefault();
                    return this.env.services.action.doAction(action);
                }
            }
        }

        return super.onEventClick?.(info);
    },
});