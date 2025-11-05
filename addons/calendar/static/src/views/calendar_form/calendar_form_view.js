/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { CalendarFormController } from "@calendar/views/calendar_form/calendar_form_controller";
//import { CalendarDashboard } from "../components/calendar_dashboard/calendar_dashboard";

export const CalendarFormView = {
    ...formView,
    Controller: CalendarFormController,
};

registry.category("views").add("calendar_form", CalendarFormView);
