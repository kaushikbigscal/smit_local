/** @odoo-module **/

import { registry } from "@web/core/registry";
import { calendarView } from "@web/views/calendar/calendar_view";
import { FsmProjectTaskCalendarController } from "./fsm_project_task_calendar_controller";

export const fsmProjectTaskCalendarView = {
    ...calendarView,
    Controller: FsmProjectTaskCalendarController,
};

registry.category("views").add("fsm_project_task_calendar", fsmProjectTaskCalendarView);