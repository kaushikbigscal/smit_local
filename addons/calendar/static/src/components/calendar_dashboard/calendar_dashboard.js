/** @odoo-module **/
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, onMounted } = owl;

export class CalendarDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.onCardClick = this.onCardClick.bind(this);
        this.toggleDashboard = this.toggleDashboard.bind(this);

        // Dashboard visibility state - using simple reactive property
        this.isDashboardVisible = true;

        onWillStart(async () => {
            try {
                const context = this.env.searchModel?.context || this.props?.context || {};
                if (context.show_dashboard !== false) {
                    const response = await this.orm.call("calendar.event", "retrieve_dashboard", []);
                    this.calendarData = response;
                    this.moduleInfo = response.module_info || {};
                    this.menuAccess = response.menu_access || {};
                    this.showDashboard = true;
                } else {
                    this.showDashboard = false;
                }
            } catch (error) {
                this.showDashboard = false;
                this.calendarData = {};
                this.moduleInfo = {};
                this.menuAccess = {};
            }
        });

        onMounted(() => {
            // Ensure proper positioning
            const dashboardEl = document.querySelector('.o_calendar_dashboard');
            const calendarEl = document.querySelector('.o_calendar_container');
            if (dashboardEl && calendarEl) {
                calendarEl.parentNode.insertBefore(dashboardEl, calendarEl);
            }
        });
    }

    toggleDashboard() {
        this.isDashboardVisible = !this.isDashboardVisible;
        this.render();
    }

    async onCardClick(ev) {
        const type = ev.currentTarget.dataset.type;
        const userId = this.env.services.user.userId;
        if (!type) return;
        let actionParams = {};
        switch (type) {
            case 'task':
                actionParams = {
                    name: "My Tasks",
                    type: 'ir.actions.act_window',
                    res_model: 'project.task',
                    view_mode: 'tree',
                    views: [[false, 'tree'], [false, 'form']],
                    domain: [['user_ids', '=', userId], ['is_fsm', '=', false]],
                };
                break;
            case 'project':
                actionParams = {
                    name: "My Projects",
                    type: 'ir.actions.act_window',
                    res_model: 'project.project',
                    view_mode: 'tree',
                    views: [[false, 'tree'], [false, 'form']],
                    domain: [['user_id', '=', userId]],
                };
                break;
            case 'lead':
                actionParams = {
                    name: "My Leads",
                    type: 'ir.actions.act_window',
                    res_model: 'crm.lead',
                    view_mode: 'tree',
                    views: [[false, 'tree'], [false, 'form']],
                    domain: [['user_id', '=', userId]],
                };
                break;
            case 'call':
                actionParams = {
                    name: "FSM Calls",
                    type: 'ir.actions.act_window',
                    res_model: 'project.task',
                    view_mode: 'tree',
                    views: [[false, 'tree'], [false, 'form']],
                    domain: [['user_ids', '=', userId], ['is_fsm', '=', true]],
                };
                break;
            case 'meeting':
                actionParams = {
                    name: "My Meetings",
                    type: 'ir.actions.act_window',
                    res_model: 'calendar.event',
                    view_mode: 'tree',
                    views: [[false, 'tree'], [false, 'form']],
                    domain: [['user_id', '=', userId]],
                };
                break;
            case 'visits':
                actionParams = {
                    name: "My Visits",
                    type: 'ir.actions.act_window',
                    res_model: 'field.visit',
                    view_mode: 'tree',
                    views: [[false, 'tree'], [false, 'form']],
                    domain: [['user_id', '=', userId]],
                };
                break;
            default:
                return;
        }
        this.action.doAction(actionParams);
    }
}
CalendarDashboard.template = 'calendar.CalendarDashboard';