/** @odoo-module */
import { useService } from "@web/core/utils/hooks";

const { Component, onWillStart, onMounted } = owl;

export class CalendarDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        onWillStart(async () => {
            try {
                const context = this.env.searchModel?.context || this.props?.context || {};
                console.log('Dashboard Context:', context);

                if (context.show_dashboard !== false) {
                    const response = await this.orm.call("calendar.event", "retrieve_dashboard", []);
                    this.calendarData = response;
                    this.moduleInfo = response.module_info || {};
                    this.showDashboard = true;
                    console.log('Dashboard data loaded:', this.calendarData);
                } else {
                    this.showDashboard = false;
                }
            } catch (error) {
                console.error('Error in dashboard setup:', error);
                this.showDashboard = false;
                this.calendarData = {};
                this.moduleInfo = {};
            }
        });

        onMounted(() => {
            // Ensure proper positioning
            const dashboardEl = document.querySelector('.o_calendar_dashboard');
            const calendarEl = document.querySelector('.o_calendar_container');

            if (dashboardEl && calendarEl) {
                // Make sure dashboard appears first
                calendarEl.parentNode.insertBefore(dashboardEl, calendarEl.nextSibling);
                const container = dashboardEl.parentElement;
                if (container && dashboardEl.nextElementSibling !== calendarEl) {
                    container.insertBefore(dashboardEl, calendarEl);
                }
            }
        });
    }

    /**
     * This method clears the current search query and activates
     * the filters found in `filter_name` attribute from button pressed
     */
    setSearchContext(ev) {
        try {
            let filter_name = ev.currentTarget.getAttribute("filter_name");
            console.log('Filter clicked:', filter_name);

            if (!filter_name || !this.env.searchModel) return;

            let filters = filter_name.split(',');
            let searchItems = this.env.searchModel.getSearchItems((item) =>
                item && item.name && filters.includes(item.name)
            );

            console.log('Found search items:', searchItems);

            // Clear current search
            this.env.searchModel.query = [];

            // Apply new filters
            for (const item of searchItems) {
                if (item && item.id) {
                    this.env.searchModel.toggleSearchItem(item.id);
                }
            }

            // Special handling for "all_events" - clear all filters
            if (filter_name === 'all_events') {
                this.env.searchModel.query = [];
            }
        } catch (error) {
            console.error('Error setting search context:', error);
        }
    }
}

CalendarDashboard.template = 'CalendarDashboard';