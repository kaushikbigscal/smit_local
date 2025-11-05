/** @odoo-module */

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CalendarSystray extends Component {
    static template = "calendar.CalendarSystray";
    static props = {};

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.state = useState({
            meetingCount: 0,
            loading: true,
        });

        onWillStart(async () => {
            await this.loadMeetingCount();
        });
    }

    async loadMeetingCount() {
        try {
            const count = await this.orm.call("res.users", "systray_get_activities", []);
            const calendarGroup = count.find(group => group.type === "meeting");
            this.state.meetingCount = calendarGroup ? calendarGroup.meetings.length : 0;
        } catch (error) {
            console.error("Error loading meeting count:", error);
            this.state.meetingCount = 0;
        } finally {
            this.state.loading = false;
        }
    }

    onClick() {
        this.action.doAction("calendar.action_calendar_event", {
            additionalContext: {
                default_mode: "day",
                search_default_mymeetings: 1,
            },
            clearBreadcrumbs: true,
        });
    }
}

registry.category("systray").add("calendar.CalendarSystray", {
    Component: CalendarSystray,
    isDisplayed: (env) => {
        return env.services.user.hasGroup("base.group_user");
    },
}, { sequence: 30 });
