/** @odoo-module **/

import { registry } from "@web/core/registry";
import { calendarView } from "@web/views/calendar/calendar_view";
import { CalendarRenderer } from "@web/views/calendar/calendar_renderer";
import { CalendarController } from "@web/views/calendar/calendar_controller";
import { CalendarDashboard } from '@home_page/views/calendar_dashboard';
import { CalendarRulesSidebar } from "@home_page/views/calendar_rules";

// Custom Renderer for Dashboard
export class CalendarDashboardRenderer extends CalendarRenderer {
    setup() {
        try {
            super.setup();
            console.log("CalendarDashboardRenderer setup");
        } catch (e) {
            console.error("Error in CalendarDashboardRenderer setup:", e);
        }
    }
}

// Don't set template - let it inherit from parent
CalendarDashboardRenderer.components = {
    ...CalendarRenderer.components,
    CalendarDashboard,
};

// Custom Controller for Sidebar
export class CalendarDashboardController extends CalendarController {
    setup() {
        try {
            super.setup();
            console.log("CalendarDashboardController setup");
        } catch (e) {
            console.error("Error in CalendarDashboardController setup:", e);
        }
    }

}

// Don't set template - let it inherit from parent
CalendarDashboardController.components = {
    ...CalendarController.components,
    CalendarRulesSidebar,
};

// Combined View
export const CalendarDashboardView = {
    ...calendarView,
    Controller: CalendarDashboardController,
    Renderer: CalendarDashboardRenderer,
};

registry.category("views").add("calendar_dashboard", CalendarDashboardView);