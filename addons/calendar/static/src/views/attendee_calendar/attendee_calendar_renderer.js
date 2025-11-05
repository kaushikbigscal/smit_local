/** @odoo-module **/

import { CalendarRenderer } from "@web/views/calendar/calendar_renderer";
import { AttendeeCalendarCommonRenderer } from "@calendar/views/attendee_calendar/common/attendee_calendar_common_renderer";
import { AttendeeCalendarYearRenderer } from "@calendar/views/attendee_calendar/year/attendee_calendar_year_renderer";
//import { CalendarDashboard } from "@calendar/components/calendar_dashboard/calendar_dashboard"; // Import your dashboard

export class AttendeeCalendarRenderer extends CalendarRenderer {}
AttendeeCalendarRenderer.components = {
    ...CalendarRenderer.components,
    day: AttendeeCalendarCommonRenderer,
    week: AttendeeCalendarCommonRenderer,
    month: AttendeeCalendarCommonRenderer,
    year: AttendeeCalendarYearRenderer,
};
