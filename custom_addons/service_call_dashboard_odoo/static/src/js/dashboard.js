/** @odoo-module */
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, onMounted } = owl;
import { jsonrpc } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { Dialog } from "@web/core/dialog/dialog";


export class ProjectDashboard extends Component {
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.rpc = useService("rpc");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.flag = 0;

        onWillStart(this.onWillStart.bind(this));
        onMounted(() => {
            // Remove the automatic chart rendering on mount
            // this.render_task_tags_chart();
            // this.render_employee_task_chart();

            // Add filter button event listener
            const filterButton = document.querySelector('.apply-date-filter');
            if (filterButton) {
                filterButton.addEventListener('click', async () => {
                    await this.updateTotals();
                });
            }

            // Add chart loading button event listener
            const loadChartsButton = document.querySelector('.load-charts-button');
            if (loadChartsButton) {
                loadChartsButton.addEventListener('click', async () => {
                    await this.loadCharts();
                });
            }

            document.querySelectorAll(".load-form-button").forEach(button => {
               button.addEventListener("click", this.onClickOpenTaskForm.bind(this));
            });

//             const refreshButton = document.querySelector('.refresh-form-button');
//                if (refreshButton) {
//                    refreshButton.addEventListener('click', this.refreshDashboard.bind(this));
//                }

             document.querySelector('.load-charts-button').addEventListener('click', function() {
                    document.querySelector('.charts-section_data').style.display = 'block';
                });

        });
    }

    async onWillStart() {
        await this.fetch_data();
    }

    async onMounted() {
        this.render_filter();
        await this.render_task_tags_chart();
        await this.render_employee_task_chart();
    }

    async fetch_data() {
        try {
            // Get the date values from the filter inputs
            const fromDate = document.querySelector('.from-date')?.value;
            const toDate = document.querySelector('.to-date')?.value;

            // Get previous totals data with date filtering
            const previousTotalsData = await this.rpc("/previous/total", {
                start_date: fromDate || null,
                end_date: toDate || null
            });

            // Update the state with the totals
            this.all_assigned_tasks_total = previousTotalsData.all_assigned_tasks_total || 0;
            this.all_unassigned_tasks_total = previousTotalsData.all_unassigned_tasks_total || 0;
            this.all_on_hold_tasks_total = previousTotalsData.all_on_hold_tasks_total || 0;
            this.all_closed_tasks_total = previousTotalsData.all_closed_tasks_total || 0;

            // Get other data...
            const tilesData = await this.rpc("/get/call/tiles/data");
            const todayCallsData = await this.rpc("/call/today");

            // Update other state properties...
            Object.assign(this, {
                total_projects: tilesData.total_projects,
                total_tasks: tilesData.total_tasks,
                un_assigned_task: tilesData.un_assigned_task,
                total_closed_task: tilesData.total_closed_task,
                active_projects: tilesData.active_projects,
                running_projects: tilesData.running_projects,
                done_projects: tilesData.done_projects,
                running_tasks: tilesData.running_tasks,
                done_tasks: tilesData.done_tasks,
                expired_yesterday: tilesData.expired_yesterday,
                will_expire_tomorrow: tilesData.will_expire_tomorrow,
                expired_today: tilesData.expired_today,

                // Add today's calls data
                new_stage_tasks_today: todayCallsData.new_stage_tasks_today || 0,
                calls_assigned_today: todayCallsData.calls_assigned_today || 0,
                calls_unassigned_today: todayCallsData.calls_unassigned_today || 0,
                calls_closed_today: todayCallsData.calls_closed_today || 0,
                calls_on_hold_today: todayCallsData.calls_on_hold_today || 0,
            });

            // Get hours data
//            const hoursData = await this.rpc("/get/hours");
//            Object.assign(this, {
//                hour_recorded: hoursData.hour_recorded,
//                hour_recorde: hoursData.hour_recorde,
//                billable_fix: hoursData.billable_fix,
//                non_billable: hoursData.non_billable,
//                total_hr: hoursData.total_hr
//            });

            // Get call data
            const callData = await this.rpc("/get/call/data");
            this.task_data = callData.project;

        } catch (error) {
            console.error("Error fetching dashboard data:", error);
        }
    }

    async render_employee_task_chart() {
        try {
            const data = await this.rpc("/call/task/by_employee");
            console.log("Data received for employee task chart:", data);

            const ctx = document.getElementById("employee_task_chart");
            if (!ctx) {
                throw new Error("Chart context not found");
            }

            // Store the chart instance
            ctx.__chart__ = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Number of Tasks',
                        data: data.data,
                        backgroundColor: data.colors,
                        borderColor: data.colors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (evt, elements) => {
                        if (elements && elements.length > 0) {
                            const clickedElement = elements[0];
                            const clickedLabel = data.labels[clickedElement.index];

                            if (clickedLabel) {
                                this.show_tasks_by_employee(clickedLabel);
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1,
                                callback: function(value) {
                                    if (Math.floor(value) === value) {
                                        return value;
                                    }
                                }
                            }
                        },
                        x: {
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: 'Tasks per Employee',
                            font: {
                                size: 16
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `Tasks: ${context.raw}`;
                                }
                            }
                        }
                    }
                }
            });

            return ctx.__chart__;
        } catch (error) {
            console.error("Error rendering employee task chart:", error);
            throw error;
        }
    }

    async render_task_tags_chart() {
        try {
            const data = await this.rpc("/call/task/by_tags");
            console.log("Data received for task tags chart:", data);

            const ctx = document.getElementById("task_tags_chart");
            if (!ctx) {
                throw new Error("Chart context not found");
            }

            // Store the chart instance
            ctx.__chart__ = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Number of Tasks',
                        data: data.data,
                        backgroundColor: data.colors,
                        borderColor: data.colors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (evt, elements) => {
                        if (elements && elements.length > 0) {
                            const clickedElement = elements[0];
                            const clickedLabel = data.labels[clickedElement.index];

                            if (clickedLabel) {
                                this.show_tasks_by_tag(clickedLabel);
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1,
                                callback: function(value) {
                                    if (Math.floor(value) === value) {
                                        return value;
                                    }
                                }
                            }
                        }
                    },
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: 'Tasks by Tags',
                        font: {
                            size: 16
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Tasks: ${context.raw}`;
                            }
                        }
                    }
                }
            });

            return ctx.__chart__;
        } catch (error) {
            console.error("Error rendering task tags chart:", error);
            throw error;
        }
    }

    async render_filter() {
        try {
            const data = await this.rpc('/calls/filter');
            const [projects, employees] = data;

            const projectSelect = document.getElementById('project_selection');
            const employeeSelect = document.getElementById('employee_selection');

            if (projectSelect && employeeSelect) {
                projects.forEach(project => {
                    projectSelect.insertAdjacentHTML('beforeend',
                        `<option value="${project.id}">${project.name}</option>`);
                });

                employees.forEach(employee => {
                    employeeSelect.insertAdjacentHTML('beforeend',
                        `<option value="${employee.id}">${employee.name}</option>`);
                });
            }
        } catch (error) {
            console.error("Error rendering filters:", error);
        }
    }

    show_tasks_by_tag(tag) {
        if (!tag) {
            console.error("Invalid tag provided");
            return;
        }

        try {
            console.log("Navigating to tasks for tag:", tag);
            this.action.doAction({
                name: _t(`Tasks for Tag: ${tag}`),  // Fixed template string syntax
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: [['tag_ids.name', 'ilike', tag], ['is_fsm', '=', true]],
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current'
            });
        } catch (error) {
            console.error("Error showing tasks for tag:", tag, error);
        }
    }

    show_tasks_by_employee(employee) {
        if (!employee) {
            console.error("Employee name is undefined or null");
            return;
        }

        try {
            console.log("Navigating to tasks for employee:", employee);
            this.action.doAction({
                name: _t(`Tasks for Employee: ${employee}`),  // Fixed template string syntax
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: [['user_ids.name', '=', employee], ['is_fsm', '=', true]],
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current'
            });
        } catch (error) {
            console.error("Error showing tasks for employee:", employee, error);
        }
    }

//    show_running_tasks(e) {
//        e.stopPropagation();
//        e.preventDefault();
//
//        this.action.doAction({
//            name: _t("Running Tasks"),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            domain: [['state', '=', '01_in_progress'],['is_fsm', '=', true]],
//            views: [
//                [false, 'list'],
//                [false, 'form'],
//                [false, 'kanban']
//            ],
//            target: 'current',
//            context: {
//                search_default_in_progress: 1
//            }
//        });
//    }
//
//    show_active_projects(e) {
//        e.stopPropagation();
//        e.preventDefault();
//
//        this.action.doAction({
//            name: _t("Active Projects"),
//            type: 'ir.actions.act_window',
//            res_model: 'project.project',
//            domain: [['stage_id.name', 'not in', ['Done','Canceled']],['is_fsm', '=', true]],
//            views: [
//                [false, 'list'],
//                [false, 'form'],
//                [false, 'kanban']
//            ],
//            target: 'current',
//
//        });
//    }
//    show_running_projects(e) {
//        e.stopPropagation();
//        e.preventDefault();
//        this.action.doAction({
//            name: _t("Running Projects"),
//            type: 'ir.actions.act_window',
//            res_model: 'project.project',
//            domain: [['stage_id.name', 'in', ['In Progress']]],
//            views: [
//                [false, 'list'],
//                [false, 'form'],
//                [false, 'kanban']
//            ],
//            target: 'current',
//        });
//    }
//
//    show_done_projects(e) {
//        e.stopPropagation();
//        e.preventDefault();
//
//        this.action.doAction({
//            name: _t("Done Projects"),
//            type: 'ir.actions.act_window',
//            res_model: 'project.project',
//            domain: [['stage_id.name', 'in', ['Done']],['is_fsm', '=', true]],
//            views: [
//                [false, 'list'],
//                [false, 'form'],
//                [false, 'kanban']
//            ],
//            target: 'current',
//
//        });
//    }
//
//    show_done_task(e) {
//        e.stopPropagation();
//        e.preventDefault();
//
//        this.action.doAction({
//            name: _t("Done Tasks"),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            domain: [['stage_id', '=', 'Done'], ['is_fsm', '=', true]],
//            views: [
//                [false, 'list'],
//                [false, 'form'],
//                [false, 'kanban']
//            ],
//            target: 'current',
//
//        });
//    }
//
//    show_expired_yesterday(e) {
//        e.stopPropagation();
//        e.preventDefault();
//        const yesterday = new Date();
//        yesterday.setDate(yesterday.getDate() - 1);
//
//        // Convert to IST (Indian Standard Time)
//        const istOffset = 5.5 * 60; // IST is UTC +5:30
//        const localTime = yesterday.getTime() + yesterday.getTimezoneOffset() * 60000;
//        const istTime = new Date(localTime + istOffset * 60000);
//
//        console.log(" istOffset",istOffset)
//        console.log("localTime",localTime)
//        console.log(" istTime",istTime)
//
//        // Format the date to match the Odoo date format (YYYY-MM-DD)
//        const formattedDate = istTime.toISOString().split('T')[0];
//
//        console.log(" istTime...",istTime)
//        this.action.doAction({
//            name: _t("Project Expired Yesterday"),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            domain: [
//                ['date_deadline', '>=', formattedDate + ' 00:00:00'],
//                ['date_deadline', '<=', formattedDate + ' 23:59:59'],
//                 ['is_fsm', '=', true]
//            ],
//            views: [
//                [false, 'list'],
//                [false, 'form'],
//                [false, 'kanban']
//            ],
//            target: 'current'
//        });
//    }
//
//    show_will_expire_tomorrow(e) {
//        e.stopPropagation();
//        e.preventDefault();
//
//        // Get tomorrow's date
//        const tomorrow = new Date();
//        tomorrow.setDate(tomorrow.getDate() + 1);
//
//        // Convert to IST (Indian Standard Time)
//        const istOffset = 5.5 * 60; // IST is UTC +5:30
//        const localTime = tomorrow.getTime() + tomorrow.getTimezoneOffset() * 60000;
//        const istTime = new Date(localTime + istOffset * 60000);
//
//        // Format the date to match the Odoo date format (YYYY-MM-DD)
//        const formattedDate = istTime.toISOString().split('T')[0];
//
//        // Construct domain query
//        this.action.doAction({
//            name: _t("Project Expiring Tomorrow"),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            domain: [
//                ['date_deadline', '>=', formattedDate + ' 00:00:00'],
//                ['date_deadline', '<=', formattedDate + ' 23:59:59'],
//                 ['is_fsm', '=', true]
//            ],
//            views: [
//                [false, 'list'],
//                [false, 'form'],
//                [false, 'kanban']
//            ],
//            target: 'current'
//        });
//    }

    show_expired_today(e) {
        e.stopPropagation();
        e.preventDefault();

        const today = new Date();
        const formatDate = (date) => {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        };

        const startDate = `${formatDate(today)} 00:00:00`;
        const endDate = `${formatDate(today)} 23:59:59`;

        const domain = [
            ['date_deadline', '>=', startDate],
            ['date_deadline', '<=', endDate],
            ['is_fsm', '=', true]
        ];

        this.action.doAction({
            name: _t("Project Expiring Today"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: domain,
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }

    tot_tasks(e) {
        e.stopPropagation();
        e.preventDefault();

        this.action.doAction({
            name: _t("Total Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: [['is_fsm', '=', true]],
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }

    click_total_closed_task(e) {
        e.stopPropagation();
        e.preventDefault();

        this.action.doAction({
            name: _t("Closed Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
//            domain: [['state', 'in', ['1_done', '1_canceled']], ['is_fsm', '=', true]],
              domain: [['stage_id.name', '=', 'Done'], ['is_fsm', '=', true]],
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }

    total_unassigned_task(e) {
        e.stopPropagation();
        e.preventDefault();

        this.action.doAction({
            name: _t("Unassigned Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: [['user_ids', '=', false], ['is_fsm', '=', true]],
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }


     show_assigned_calls_today(e) {
        e.stopPropagation();
        e.preventDefault();

        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];

        this.action.doAction({
            name: _t("Today's Assigned Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: [
                ['user_ids', '!=', false],
                ['create_date', '>=', `${formattedDate} 00:00:00`],
                ['create_date', '<=', `${formattedDate} 23:59:59`],
                ['is_fsm', '=', true]
            ],
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }

    show_unassigned_calls_today(e) {
        e.stopPropagation();
        e.preventDefault();

        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];
        this.action.doAction({
            name: _t("Today's Unassigned Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: [
                ['user_ids', '=', false],
                ['create_date', '>=', `${formattedDate} 00:00:00`],
                ['create_date', '<=', `${formattedDate} 23:59:59`],
                ['is_fsm', '=', true]
            ],
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }


//    new added code


 calls_on_hold_today_click(e) {
        e.stopPropagation();
        e.preventDefault();
        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];

        this.action.doAction({
            name: _t("Today's On Hold Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: [
                ['user_ids', '!=', false],
                   ['stage_id.name', '=', 'On Hold'],
                ['create_date', '>=', `${formattedDate} 00:00:00`],
                ['create_date', '<=', `${formattedDate} 23:59:59`],
                ['is_fsm', '=', true]
            ],
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }
//new added code

    show_closed_calls_today(e) {
        e.stopPropagation();
        e.preventDefault();

        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];

        this.action.doAction({
            name: _t("Today's Closed Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: [
                ['stage_id.name', '=', 'Done'],
                ['create_date', '>=', `${formattedDate} 00:00:00`],
                ['create_date', '<=', `${formattedDate} 23:59:59`],
                ['is_fsm', '=', true]
            ],
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }




     new_stage_tasks_today_click(e) {
        e.stopPropagation();
        e.preventDefault();

        const today = new Date();
        const formattedDate = today.toISOString().split('T')[0];

        this.action.doAction({
            name: _t("Today's Closed Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: [
                ['stage_id.name', '=', 'New'],
                ['create_date', '>=', `${formattedDate} 00:00:00`],
                ['create_date', '<=', `${formattedDate} 23:59:59`],
                ['is_fsm', '=', true]
            ],
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }


     all_assigned_tasks_total_click(e) {
        e.preventDefault();
        const fromDate = document.querySelector('.from-date').value;
        const toDate = document.querySelector('.to-date').value;

        let domain = [['user_ids', '!=', false], ['is_fsm', '=', true]];
        if (fromDate && toDate) {
            domain.push(['create_date', '>=', `${fromDate} 00:00:00`]);
            domain.push(['create_date', '<=', `${toDate} 23:59:59`]);
        }

        this.action.doAction({
            name: _t("Assigned Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: domain,
            views: [[false, 'list'], [false, 'form'], [false, 'kanban']],
            target: 'current'
        });
    }

      all_unassigned_tasks_total_click(e) {
        e.stopPropagation();
        e.preventDefault();

        const fromDate = document.querySelector('.from-date').value;
        const toDate = document.querySelector('.to-date').value;

        let domain = [['user_ids', '=', false], ['is_fsm', '=', true]];

        // Add date filtering to domain if dates are selected
        if (fromDate && toDate) {
            domain.push(['create_date', '>=', `${fromDate} 00:00:00`]);
            domain.push(['create_date', '<=', `${toDate} 23:59:59`]);
        }

        this.action.doAction({
            name: _t("Unassigned Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: domain,
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }


     all_on_hold_tasks_total_click(e) {
        e.stopPropagation();
        e.preventDefault();

        const fromDate = document.querySelector('.from-date').value;
        const toDate = document.querySelector('.to-date').value;

        let domain = [['stage_id.name', '=', 'On Hold'], ['is_fsm', '=', true]];

        // Add date filtering to domain if dates are selected
        if (fromDate && toDate) {
            domain.push(['create_date', '>=', `${fromDate} 00:00:00`]);
            domain.push(['create_date', '<=', `${toDate} 23:59:59`]);
        }

        this.action.doAction({
            name: _t("On Hold Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: domain,
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }

     all_closed_tasks_total_click(e) {
        e.stopPropagation();
        e.preventDefault();

        const fromDate = document.querySelector('.from-date').value;
        const toDate = document.querySelector('.to-date').value;

        let domain = [['stage_id.name', '=', 'Done'], ['is_fsm', '=', true]];

        // Add date filtering to domain if dates are selected
        if (fromDate && toDate) {
            domain.push(['create_date', '>=', `${fromDate} 00:00:00`]);
            domain.push(['create_date', '<=', `${toDate} 23:59:59`]);
        }

        this.action.doAction({
            name: _t("Closed Calls"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: domain,
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }

    // Update the updateTotals method
    async updateTotals() {
        try {
            const fromDate = document.querySelector('.from-date')?.value;
            const toDate = document.querySelector('.to-date')?.value;

            const previousTotalsData = await this.rpc("/previous/total", {
                start_date: fromDate || null,
                end_date: toDate || null
            });

            // Update the state directly
            this.all_assigned_tasks_total = previousTotalsData.all_assigned_tasks_total || 0;
            this.all_unassigned_tasks_total = previousTotalsData.all_unassigned_tasks_total || 0;
            this.all_on_hold_tasks_total = previousTotalsData.all_on_hold_tasks_total || 0;
            this.all_closed_tasks_total = previousTotalsData.all_closed_tasks_total || 0;

            // Force a re-render
            this.render();
        } catch (error) {
            console.error("Error updating totals:", error);
        }
    }

    // Add new method to load charts
    async loadCharts() {
        try {
            // Clear existing charts if they exist
            const tagChartCanvas = document.getElementById('task_tags_chart');
            const employeeChartCanvas = document.getElementById('employee_task_chart');

            if (tagChartCanvas.__chart__) {
                tagChartCanvas.__chart__.destroy();
            }
            if (employeeChartCanvas.__chart__) {
                employeeChartCanvas.__chart__.destroy();
            }

            // Render both charts
            await this.render_task_tags_chart();
            await this.render_employee_task_chart();
        } catch (error) {
            console.error("Error loading charts:", error);
        }
    }

        async onClickOpenTaskForm(ev) {
            try {
                // First get the Field Service project and user info
                const fsProject = await this.rpc("/get/fsm/project");

                // Open a new task form with default project and user
                await this.action.doAction({
                    type: 'ir.actions.act_window',
                    res_model: 'project.task',
                    views: [[false, 'form']],
                    target: 'new',
                    context: {
                        'form_view_initial_mode': 'edit',
                        'default_is_fsm': true,
                        'default_project_id': fsProject.id,  // Set default project
                        'default_user_ids': [[6, 0, [fsProject.user_id]]], // Set default user
                    },
                });
            } catch (error) {
                console.error("Error opening new task form:", error);
                this.notification.add(
                    "Error opening task form",
                    { type: 'danger' }
                );
            }
        }

//        async refreshDashboard(e) {
//            if (e) {
//                e.stopPropagation();
//                e.preventDefault();
//            }
//            try {
//                // Show loading state
//                const refreshButton = document.querySelector('.refresh-form-button');
//                if (refreshButton) {
//                    refreshButton.textContent = "Refreshing...";
//                    refreshButton.disabled = true;
//                }
//
//                // Clear existing charts
//                const tagChartCanvas = document.getElementById('task_tags_chart');
//                const employeeChartCanvas = document.getElementById('employee_task_chart');
//
//                if (tagChartCanvas?.__chart__) {
//                    tagChartCanvas.__chart__.destroy();
//                }
//                if (employeeChartCanvas?.__chart__) {
//                    employeeChartCanvas.__chart__.destroy();
//                }
//
//                // Fetch fresh data from all endpoints
//                const [tilesData, todayCallsData] = await Promise.all([
//                    this.rpc("/get/call/tiles/data"),
//                    this.rpc("/call/today")
//                ]);
//
//                // Update component state with new data
//                Object.assign(this, {
//                    // Today's calls data
//                    new_stage_tasks_today: todayCallsData.new_stage_tasks_today || 0,
//                    calls_assigned_today: todayCallsData.calls_assigned_today || 0,
//                    calls_unassigned_today: todayCallsData.calls_unassigned_today || 0,
//                    calls_closed_today: todayCallsData.calls_closed_today || 0,
//                    calls_on_hold_today: todayCallsData.calls_on_hold_today || 0,
//
//                    // Tiles data
//                    total_projects: tilesData.total_projects,
//                    total_tasks: tilesData.total_tasks,
//                    un_assigned_task: tilesData.un_assigned_task,
//                    total_closed_task: tilesData.total_closed_task,
//                    active_projects: tilesData.active_projects,
//                    running_projects: tilesData.running_projects,
//                    done_projects: tilesData.done_projects,
//                    running_tasks: tilesData.running_tasks,
//                    done_tasks: tilesData.done_tasks,
//                    expired_yesterday: tilesData.expired_yesterday,
//                    will_expire_tomorrow: tilesData.will_expire_tomorrow,
//                    expired_today: tilesData.expired_today,
//                });
//
//                // Update previous totals if date filter is applied
//                const fromDate = document.querySelector('.from-date')?.value;
//                const toDate = document.querySelector('.to-date')?.value;
//
//                if (fromDate || toDate) {
//                    const previousTotalsData = await this.rpc("/previous/total", {
//                        start_date: fromDate || null,
//                        end_date: toDate || null
//                    });
//
//                    Object.assign(this, {
//                        all_assigned_tasks_total: previousTotalsData.all_assigned_tasks_total || 0,
//                        all_unassigned_tasks_total: previousTotalsData.all_unassigned_tasks_total || 0,
//                        all_on_hold_tasks_total: previousTotalsData.all_on_hold_tasks_total || 0,
//                        all_closed_tasks_total: previousTotalsData.all_closed_tasks_total || 0,
//                    });
//                }
//
//                // Force component re-render
//                await this.render();
//
//                // Reload charts if they're visible
//                const chartsSection = document.querySelector('.charts-section_data');
//                if (chartsSection && chartsSection.style.display !== 'none') {
//                    await this.render_task_tags_chart();
//                    await this.render_employee_task_chart();
//                }
//
//                // Reset button state
//                if (refreshButton) {
//                    refreshButton.textContent = "Refresh Form";
//                    refreshButton.disabled = false;
//                }
//
//                // Show success message
//                this.notification.add(
//                    "Dashboard refreshed successfully",
//                    { type: 'success' }
//                );
//
//            } catch (error) {
//                console.error("Error refreshing dashboard:", error);
//
//                // Reset button state
//                const refreshButton = document.querySelector('.refresh-form-button');
//                if (refreshButton) {
//                    refreshButton.textContent = "Refresh Form";
//                    refreshButton.disabled = false;
//                }
//
//                // Show error message
//                this.notification.add(
//                    "Failed to refresh dashboard",
//                    { type: 'danger' }
//                );
//            }
//        }

          async refreshPage() {
           // Show success message
                this.notification.add(
                    "Dashboard refreshed successfully",
                    { type: 'success' }
                );
            window.location.reload();
       }


}

ProjectDashboard.template = "service_call_dashboard_odoo.ProjectDashboard";
registry.category("actions").add("service_call_dashboard", ProjectDashboard);