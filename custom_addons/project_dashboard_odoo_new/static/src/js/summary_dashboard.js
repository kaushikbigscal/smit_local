/** @odoo-module */
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, useState, onMounted, onWillUnmount } = owl;
import { jsonrpc } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";

export class ProjectDashboard extends Component {
    setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");
        this.rpc = this.env.services.rpc;
        this.user = useService("user");

        // Initialize state before any async operations
        this.state = useState({
            departments: [],
            selectedDepartments: new Set(),
            departmentsExpanded: false,
            templatesExpanded: false,
            sidebarOpen: false,
            total_projects: 0,
            total_tasks: 0,
            active_projects: 0,
            running_projects: 0,
            canceled_projects: 0,
            canceled_tasks: 0,
            done_projects: 0,
            running_tasks: 0,
            done_tasks: 0,
            expired_yesterday: 0,
            will_expire_tomorrow: 0,
            expired_today: 0,
            expired_projects: 0,
            expired_tasks: 0,
            expired_yesterday_tasks: 0,
            expired_today_tasks: 0,
            will_expire_tomorrow_tasks: 0,
            startDate: null,
            endDate: null,
            templates: [],
            project_template: null,
            department_data: [],
            selectedTemplates: new Set(),
            selectedDate: null,
            selectedDateRange: null,
            expandedCompanyIds: new Set(),
            selectedCompanies: new Set(),
            has_project_admin_rights: false,
        });

        onWillStart(async () => {
            await this.initialize();
        });

        onMounted(() => {
            this.initDatePicker();
            this.loadCharts();
        });

        onWillUnmount(() => {
            this.cleanup();
        });
    }

    async initialize() {
        try {
            const isRefresh = this.isPageRefresh();
            await this.loadDepartments();
            await this.loadTemplates();

            const stored = sessionStorage.getItem("dashboardFilterState");
            if (stored) {
                const filterState = JSON.parse(stored);
                this.state.selectedDepartments = new Set(filterState.selectedDepartments || []);
                this.state.selectedTemplates = new Set(filterState.selectedTemplates || []);
                this.state.startDate = filterState.startDate || null;
                this.state.endDate = filterState.endDate || null;
                this.state.activeDepartmentIds = filterState.selectedDepartments || [];
                this.state.project_template = filterState.selectedTemplates || [];

            }
            await this.fetch_data();
        } catch (error) {
        }
    }

    cleanup() {
        // Cleanup any resources, charts, etc.
        if (this.employeeChart) {
            this.employeeChart.destroy();
        }
        if (this.tagsChart) {
            this.tagsChart.destroy();
        }
    }

    onDateChange(event) {
        console.log("Date changed:", event.target.value);
    }

    initDatePicker() {
        const dateInput = document.querySelector("#date_input");
        if (!dateInput) {
            console.error("date_input not found!");
            return;
        }

        if (typeof flatpickr !== "undefined") {
            flatpickr(dateInput, {
                mode: "range",
                dateFormat: "Y-m-d",
                position: "auto right",
                static: false,
                onChange: (selectedDates, dateStr) => {
                    if (selectedDates.length === 2) {
                        // Format dates directly without timezone conversion
                        const formatDate = (date) => {
                            const year = date.getFullYear();
                            const month = String(date.getMonth() + 1).padStart(2, '0');
                            const day = String(date.getDate()).padStart(2, '0');
                            return `${year}-${month}-${day}`;
                        };
                        const startDate = formatDate(selectedDates[0]);
                        const endDate = formatDate(selectedDates[1]);

                        // Update state with formatted dates
                        this.state.selectedDateRange = dateStr;
                        this.state.startDate = startDate;
                        this.state.endDate = endDate;
                        this.filters(); // Automatically apply filters when date range changes
                    }
                }
            });
        } else {
            console.error("Flatpickr is not loaded. Check asset loading!");
        }
    }

    async loadDepartments() {
        try {
            const response = await this.rpc('/get/departments');

            if (!Array.isArray(response)) {
                this.state.departments = [];
                return;
            }

            // Process department data
            this.state.departments = response.map(dept => {
                // Handle the name whether it's a string or an object with translations
                let name = dept.name;
                if (typeof name === 'object' && name !== null) {
                    // Try to get the name in the current language or fall back to en_US
                    name = name[this.env.lang] || name['en_US'] || Object.values(name)[0] || '';
                }
                return {
                    id: dept.id,
                    name: name
                };
            }).filter(dept => dept.name); // Filter out departments without names

        } catch (error) {
            this.state.departments = [];
        }
    }

    toggleSelection(departmentId) {
        try {
            console.log("toggleSelection called with departmentId:", departmentId);

            if (!departmentId) {
                console.error("Invalid department ID: null or undefined");
                return;
            }

            const id = parseInt(departmentId);
            if (isNaN(id)) {
                console.error("Invalid department ID:", departmentId);
                return;
            }

            if (!this.state) {
                console.error("State is not initialized");
                return;
            }

            if (!this.state.selectedDepartments) {
                console.error("selectedDepartments Set is not initialized");
                this.state.selectedDepartments = new Set();
            }

            if (this.state.selectedDepartments.has(id)) {
                this.state.selectedDepartments.delete(id);
            } else {
                this.state.selectedDepartments.add(id);
            }
            console.log("Current selected departments:", Array.from(this.state.selectedDepartments));
            this.render();
        } catch (error) {
            console.error("Error in toggleSelection:", error);
        }
    }

    isDepartmentActive(departmentId) {
        try {
            if (!departmentId || !this.state || !this.state.selectedDepartments) {
                return false;
            }
            const id = parseInt(departmentId);
            return !isNaN(id) && this.state.selectedDepartments.has(id);
        } catch (error) {
            console.error("Error in isDepartmentActive:", error);
            return false;
        }
    }

    async loadTemplates() {
        try {
            const templates = await jsonrpc("/get/project_template");
            console.log("Raw templates response:", templates);

            if (!templates || !Array.isArray(templates)) {
                console.error("Invalid templates response:", templates);
                this.state.templates = [];
                return;
            }
            // Templates now contain name as both id and name
            this.state.templates = templates;
            console.log("Loaded templates:", this.state.templates);
        } catch (error) {
            console.error("Error loading templates:", error);
            this.state.templates = [];
        }
    }

    async fetch_data() {
        try {
            // Convert Sets to Arrays and ensure proper format
            const selectedDepartments = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
            const selectedTemplates = Array.from(this.state.selectedTemplates);

            console.log("Fetching dashboard data with filters:", {
                departments: selectedDepartments,
                templates: selectedTemplates,
                startDate: this.state.startDate,
                endDate: this.state.endDate
            });

            const result = await this.rpc('/get/tiles/data', {
                department_id: selectedDepartments.length > 0 ? selectedDepartments : null,
                x_template: selectedTemplates.length > 0 ? selectedTemplates : null,
                start_date: this.state.startDate || null,
                end_date: this.state.endDate || null
            });

            console.log("Received dashboard data:", result);

            if (!result) {
                console.error("No data received from server");
                return;
            }

            // Update state with the received data
            Object.assign(this.state, {
                total_projects: result.total_projects || 0,
                total_tasks: result.total_tasks || 0,
                active_projects: result.active_projects || 0,
                running_projects: result.running_projects || 0,
                canceled_projects: result.canceled_projects || 0,
                canceled_tasks: result.canceled_tasks || 0,
                done_projects: result.done_projects || 0,
                running_tasks: result.running_tasks || 0,
                done_tasks: result.done_tasks || 0,
                expired_yesterday: result.expired_yesterday || 0,
                will_expire_tomorrow: result.will_expire_tomorrow || 0,
                expired_today: result.expired_today || 0,
                expired_projects: result.expired_projects || 0,
                expired_tasks: result.expired_tasks || 0,
                expired_yesterday_tasks: result.expired_yesterday_tasks || 0,
                expired_today_tasks: result.expired_today_tasks || 0,
                will_expire_tomorrow_tasks: result.will_expire_tomorrow_tasks || 0,
                has_project_admin_rights: result.has_project_admin_rights || false
            });

            // Log the updated state for debugging
            console.log("Updated dashboard state:", {
                has_project_admin_rights: this.state.has_project_admin_rights,
                total_projects: this.state.total_projects,
                total_tasks: this.state.total_tasks,
                active_projects: this.state.active_projects,
                running_projects: this.state.running_projects,
                done_projects: this.state.done_projects,
                canceled_projects: this.state.canceled_projects,
                expired_projects: this.state.expired_projects,
                expired_yesterday: this.state.expired_yesterday,
                expired_today: this.state.expired_today,
                will_expire_tomorrow: this.state.will_expire_tomorrow,
                expired_tasks: this.state.expired_tasks,
                expired_yesterday_tasks: this.state.expired_yesterday_tasks,
                expired_today_tasks: this.state.expired_today_tasks,
                will_expire_tomorrow_tasks: this.state.will_expire_tomorrow_tasks,
                running_tasks: this.state.running_tasks,
                done_tasks: this.state.done_tasks,
                canceled_tasks: this.state.canceled_tasks
            });

            // Update charts with new data
            await this.loadCharts();
            await this.render();

        } catch (error) {
            console.error("Error fetching dashboard data:", error);
        }
    }

    async loadCharts() {
        // Don't load charts if it's a page refresh
        if (this.isPageRefresh()) {
            await this.render_task_tags_chart();
            await this.render_employee_task_chart();
            return;
        }

        // Load charts with stored filters
        const storedState = this.getStoredState();
        await this.render_task_tags_chart();
        await this.render_employee_task_chart();
    }

    async render_employee_task_chart() {
        try {
            if (this.employeeChart) {
                this.employeeChart.destroy();
            }

            const filters = {
                department_id: Array.from(this.state.selectedDepartments),
                x_template: Array.from(this.state.selectedTemplates),
                start_date: this.state.startDate,
                end_date: this.state.endDate
            };

            console.log("Sending filters to employee task chart:", filters);

            const data = await jsonrpc("/project/task/by_employee", filters);

            if (!data || !data.labels || !data.data) {
                console.error("No data received for employee task chart.");
                return null;
            }

            console.log("Received data for employee task chart:", {
                labels: data.labels,
                data: data.data,
                colors: data.colors
            });

        const canvasEl = document.getElementById("employee_task_chart");
        if (!canvasEl) {
            console.warn("Canvas element #employee_task_chart not found in DOM.");
            return;
        }
        const ctx = canvasEl.getContext("2d");
        if (!ctx) {
            console.error("Canvas context not found.");
            return;
        }
            try {
                this.employeeChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: data.labels.map(label => String(label)),
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
                        maintainAspectRatio: true,
                        animation: {
                            duration: 0
                        },
                        onClick: (evt, activeElements) => {
                            try {
                                if (activeElements && activeElements.length > 0) {
                                    const clickedElement = activeElements[0];
                                    const clickedLabel = data.labels[clickedElement._index];
                                    if (clickedLabel) {
                                        this.show_tasks_by_employee(clickedLabel, filters);
                                    }
                                }
                            } catch (err) {
                                console.error("Error in chart onClick:", err);
                            }
                        },
                        scales: {
                            yAxes: [{
                                ticks: {
                                    beginAtZero: true,
                                    callback: function(value) {
                                        if (Math.floor(value) === value) {
                                            return value;
                                        }
                                    }
                                }
                            }],
                            xAxes: [{
                                ticks: {
                                    maxRotation: 45,
                                    minRotation: 45,
                                    callback: function(value) {
                                        return String(value);
                                    }
                                }
                            }]
                        },
                        legend: {
                            display: true,
                            position: 'top',
                        },
                        tooltips: {
                            callbacks: {
                                label: function(tooltipItem, data) {
                                    return `Tasks: ${tooltipItem.yLabel}`;
                                }
                            }
                        }
                    }
                });
            } catch (err) {
                console.error("Error creating the employee task chart:", err);
                return null;
            }
        } catch (error) {
            console.error("Error rendering employee task chart:", error);
            return null;
        }
    }

    async render_task_tags_chart() {
        try {
            if (this.tagsChart) {
                this.tagsChart.destroy();
            }

            const filters = {
                department_id: Array.from(this.state.selectedDepartments),
                x_template: Array.from(this.state.selectedTemplates),
                start_date: this.state.startDate,
                end_date: this.state.endDate
            };

            const data = await jsonrpc("/project/task/by_tags", filters);

            if (!data || !data.labels || !data.data) {
                console.error("No data received for task tags chart.");
                return null;
            }

            // Debug logging
            console.log("Received data for task tags chart:", {
                labels: data.labels,
                data: data.data,
                colors: data.colors
            });

            const ctx = $("#task_tags_chart")[0];
            if (!ctx || ctx.length === 0) {
                return null;
            }

            try {
                this.tagsChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: data.labels.map(label => String(label)), // Ensure labels are strings
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
                        maintainAspectRatio: true,
                        animation: {
                            duration: 0
                        },
                        onClick: (evt, activeElements) => {
                            try {
                                if (activeElements && activeElements.length > 0) {
                                    const clickedElement = activeElements[0];
                                    const clickedLabel = data.labels[clickedElement._index]; // Get label from data
                                    if (clickedLabel) {
                                        this.show_tasks_by_tag(clickedLabel, filters);
                                    }
                                }
                            } catch (err) {
                                console.error("Error in chart onClick:", err);
                            }
                        },
                        scales: {
                            yAxes: [{
                                ticks: {
                                    beginAtZero: true,
                                    callback: function(value) {
                                        if (Math.floor(value) === value) {
                                            return value;
                                        }
                                    }
                                }
                            }],
                            xAxes: [{
                                ticks: {
                                    maxRotation: 45,
                                    minRotation: 45,
                                    callback: function(value) {
                                        return String(value); // Ensure labels are strings
                                    }
                                }
                            }]
                        },
                        legend: {
                            display: true,
                            position: 'top',
                        },
                        tooltips: {
                            callbacks: {
                                label: function(tooltipItem, data) {
                                    return `Tasks: ${tooltipItem.yLabel}`;
                                }
                            }
                        }
                    }
                });
            } catch (err) {
                console.error("Error creating the task tags chart:", err);
                return null;
            }
        } catch (error) {
            console.error("Error rendering task tags chart:", error);
            return null;
        }
    }


    async show_tasks_by_tag(tag, filters = {}) {
        if (!tag) {
            console.error("Invalid tag provided");
            return;
        }

        try {
            const userId = this.user?.userId;
            const isAdmin = this.user?.isAdmin;

            let domain = [
                ['tag_ids.name', 'ilike', tag],
                ['project_id', '!=', false],
                ['active', '=', true],
                ['depend_on_ids', '=', false],
                ['project_id.is_fsm', '=', false],
                ['project_id.is_project_template', '=', false],
                ['project_id.active', '=', true],
            ];

            if (!isAdmin && userId) {
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]],
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIds = pmProjects.map(p => p.id);

                if (projectIds.length > 0) {
                    domain.push('|');
                    domain.push(['user_ids', 'in', [userId]]);
                    domain.push(['project_id', 'in', projectIds]);
                    domain.push('|');
                    domain.push(['state', '!=', '1_done']);
                    domain.push(['state', '!=', '1_canceled']);
                    console.log("User is PM — showing tasks from their projects or assigned to them");
                } else {
                    domain.push(['user_ids', 'in', [userId]]);
                    domain.push(['state', '!=', '1_done']);
                    domain.push(['state', '!=', '1_canceled']);
                    console.log("User is not PM — showing only assigned tasks");
                }
            }

            // Filters
            if (filters.department_id?.length) {
                const deptIds = Array.isArray(filters.department_id) ? filters.department_id : [filters.department_id];
                domain.push(['project_id.x_department', 'in', deptIds]);
            }

            if (filters.x_template?.length) {
                const templates = Array.isArray(filters.x_template) ? filters.x_template : [filters.x_template];
                domain.push(['project_id.x_template', 'in', templates]);
            }

            if (filters.start_date && filters.end_date) {
                domain.push(['project_id.date', '>=', filters.start_date]);
                domain.push(['project_id.date', '<=', filters.end_date]);
            }

            console.log("Final domain for tag-based filtering:", domain);

            this.action.doAction({
                name: _t(`Tasks for Tag: ${tag}`),
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    group_by: ['state']
                }
            });

        } catch (error) {
            console.error("Error fetching tasks by tag:", error);
        }
    }


    async show_tasks_by_employee(employee, filters = {}) {
        if (!employee) {
            console.error("Invalid employee provided");
            return;
        }

        try {
            const userId = this.user?.userId;
            const isAdmin = this.user?.isAdmin;

            let domain = [
                ['user_ids.name', 'ilike', employee],
                ['project_id', '!=', false],
                ['active', '=', true],
                ['depend_on_ids', '=', false],
                ['project_id.is_fsm', '=', false],
                ['project_id.is_project_template', '=', false],
                ['project_id.active', '=', true],
            ];

            if (isAdmin) {
                // Admin sees all, including done/canceled
                domain.push(['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved', '1_done', '1_canceled']]);
                console.log("Admin: showing all tasks including done/canceled");
            } else if (userId) {
                // Check if current user is PM of any project
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]],
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIds = pmProjects.map(p => p.id);

                if (projectIds.length > 0) {
                    // PM sees all employee tasks in their projects (including done/canceled)
                    domain.push(['project_id', 'in', projectIds]);
                    domain.push(['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved', '1_done', '1_canceled']]);
                    console.log("Project Manager: showing all employee tasks in their managed projects");
                } else {
                    // Regular user: only see own tasks, not done/canceled
                    domain.push(['user_ids', 'in', [userId]]);
                    domain.push(['state', 'not in', ['1_done', '1_canceled']]);
                    console.log("Normal user: showing only their own active tasks");
                }
            }

            // Department filter
            if (filters.department_id?.length) {
                const deptIds = Array.isArray(filters.department_id) ? filters.department_id : [filters.department_id];
                domain.push(['project_id.x_department', 'in', deptIds]);
            }

            // Template filter
            if (filters.x_template?.length) {
                const templates = Array.isArray(filters.x_template) ? filters.x_template : [filters.x_template];
                domain.push(['project_id.x_template', 'in', templates]);
            }

            // Date range filter
            if (filters.start_date && filters.end_date) {
                domain.push(['project_id.date', '>=', filters.start_date]);
                domain.push(['project_id.date', '<=', filters.end_date]);
            }

            console.log("Final domain for employee-based filtering:", domain);

            this.action.doAction({
                name: _t(`Tasks for Employee: ${employee}`),
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    group_by: ['state']
                }
            });

        } catch (error) {
            console.error("Error fetching tasks by employee:", error);
        }
    }

   async show_not_started(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            console.log("Showing not Started tasks with current state:", {
                selectedDepartments: this.state.selectedDepartments,
                selectedTemplates: this.state.selectedTemplates,
                dateRange: {
                    startDate: this.state.startDate,
                    endDate: this.state.endDate
                },
                has_project_admin_rights: this.state.has_project_admin_rights
            });

            let domain = [
                ['state', 'in', ['05_not_started']],
                ['project_id', '!=', false],
                ['active', '=', true],
                ['project_id.is_fsm', '=', false],
                ['project_id.is_project_template', '=', false],
                ['project_id.active', '=', true]
            ];

            const userId = this.user.userId;

            if (!userId) {
                console.error("Could not determine current user ID");
                return;
            }

             if (!this.state.has_project_admin_rights) {
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]],
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIds = pmProjects.map(p => p.id);

                if (projectIds.length > 0) {
                    domain = [
                        ['state', 'in', ['05_not_started']],
                        ['project_id', '!=', false],
                        ['active', '=', true],
//                        ['depend_on_ids', '=', false],
                        ['project_id.is_fsm', '=', false],
                        ['project_id.is_project_template', '=', false],
                        ['project_id.active', '=', true],
                        '|',
                        ['user_ids', 'in', [userId]],
                        ['project_id', 'in', projectIds]
                    ];
                    console.log("User is PM — filtered by assigned tasks or managed projects");
                } else {
                    domain.push(['user_ids', 'in', [userId]]);
                    domain.push(['state','in',['05_not_started']])
//                    domain.push(['depend_on_ids', '=', false]);
                    console.log("User is not PM of any project — only assigned tasks shown",domain);
                }
            }

            // Handle department filter
            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                domain.push(['project_id.x_department', 'in', deptIds]);
            }

            const selectedTemplates = Array.from(this.state.selectedTemplates || []);
            if (selectedTemplates.length > 0) {
                domain.push(['project_id.x_template', 'in', selectedTemplates]);
            }

            // Add date range filter
            if (this.state.startDate && this.state.endDate) {
                domain.push(['project_id.date', '>=', this.state.startDate]);
                domain.push(['project_id.date', '<=', this.state.endDate]);
            }

            const hasTasks = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                model: 'project.task',
                method: 'search_read',
                args: [domain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasTasks.length) {
                console.warn("No not started tasks found matching filters.");
                return;
            }

            console.log("Final domain for running tasks:", domain);

            this.action.doAction({
                name: _t("Running Tasks"),
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    group_by: ['state']
                }
            });

        } catch (error) {
            console.error("Error showing not started tasks:", error);
        }
    }

    async show_running_tasks(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            console.log("Showing running tasks with current state:", {
                selectedDepartments: this.state.selectedDepartments,
                selectedTemplates: this.state.selectedTemplates,
                dateRange: {
                    startDate: this.state.startDate,
                    endDate: this.state.endDate
                },
                has_project_admin_rights: this.state.has_project_admin_rights
            });

            let domain = [
                ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],
                ['project_id', '!=', false],
                ['active', '=', true],
                ['project_id.is_fsm', '=', false],
                ['project_id.is_project_template', '=', false],
                ['project_id.active', '=', true]
            ];

            const userId = this.user.userId;

            if (!userId) {
                console.error("Could not determine current user ID");
                return;
            }

             if (!this.state.has_project_admin_rights) {
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]],
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIds = pmProjects.map(p => p.id);

                if (projectIds.length > 0) {
                    domain = [
                        ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],
                        ['project_id', '!=', false],
                        ['active', '=', true],
                        ['depend_on_ids', '=', false],
                        ['project_id.is_fsm', '=', false],
                        ['project_id.is_project_template', '=', false],
                        ['project_id.active', '=', true],
                        '|',
                        ['user_ids', 'in', [userId]],
                        ['project_id', 'in', projectIds]
                    ];
                    console.log("User is PM — filtered by assigned tasks or managed projects");
                } else {
                    domain.push(['user_ids', 'in', [userId]]);
                    domain.push(['depend_on_ids', '=', false]);
                    console.log("User is not PM of any project — only assigned tasks shown");
                }
            }

            const hasProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.task',
                method: 'search_read',
                args: [domain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasProjects.length) {
                console.warn("No show running tasks found matching filters.");
                return;
            }

            // Handle department filter
            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                domain.push(['project_id.x_department', 'in', deptIds]);
            }

            const selectedTemplates = Array.from(this.state.selectedTemplates || []);
            if (selectedTemplates.length > 0) {
                domain.push(['project_id.x_template', 'in', selectedTemplates]);
            }

            // Add date range filter
            if (this.state.startDate && this.state.endDate) {
                domain.push(['project_id.date', '>=', this.state.startDate]);
                domain.push(['project_id.date', '<=', this.state.endDate]);
            }

            console.log("Final domain for running tasks:", domain);

            this.action.doAction({
                name: _t("Running Tasks"),
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    group_by: ['state']
                }
            });

        } catch (error) {
            console.error("Error showing running tasks:", error);
        }
    }


    async show_canceled_task(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            const userId = this.user.userId;

            if (!userId) {
                console.error("Could not determine current user ID");
                return;
            }

            let domain = [
                ['state', '=', '1_canceled'],
                ['project_id', '!=', false],
                ['active', '=', true],
                ['project_id.is_fsm', '=', false],
                ['project_id.is_project_template', '=', false],
                ['project_id.active', '=', true]
            ];

            if (this.state.has_project_admin_rights) {
                // Full access for project admins — no restriction on projects
                console.log("Project Admin: Full access to canceled tasks");
            } else {
                // Check if user is a Project Manager
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]],
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIds = pmProjects.map(p => p.id);

                if (projectIds.length > 0) {
                    domain.push(['project_id', 'in', projectIds]);
                    console.log("Project Manager: Limited to own projects' canceled tasks");
                } else {
                    // Not a PM of any project, deny access
                    console.warn("Access denied: Not a project admin or manager");
                    return;
                }
            }

            // Department filter
            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                domain.push(['project_id.x_department', 'in', deptIds]);
            }

            // Template filter
            const selectedTemplates = Array.from(this.state.selectedTemplates || []);
            if (selectedTemplates.length > 0) {
                domain.push(['project_id.x_template', 'in', selectedTemplates]);
            }

            // Date range filter
            if (this.state.startDate && this.state.endDate) {
                domain.push(['project_id.date', '>=', this.state.startDate]);
                domain.push(['project_id.date', '<=', this.state.endDate]);
            }

            this.action.doAction({
                name: _t("Canceled Tasks"),
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    group_by: ['state']
                }
            });
        } catch (error) {
            console.error("Error showing canceled tasks:", error);
        }
    }


    async show_active_projects(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            console.log("Showing active projects for user:", this.user.userId);
            const isAdmin = this.state.has_project_admin_rights;
            const userId = this.user.userId;

            if (!userId) {
                console.error("User ID not found — cannot proceed.");
                return;
            }

            let domain = [
                ['stage_id.name', 'not in', ['Done', 'Canceled']],
                ['is_fsm', '=', false],
                ['is_project_template', '=', false],
                ['active', '=', true],
            ];

            // Department filter
            const selectedDepartments = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
            if (selectedDepartments.length > 0) {
                domain.push(['x_department', 'in', selectedDepartments]);
            }

            // Template filter
            const selectedTemplates = Array.from(this.state.selectedTemplates);
            if (selectedTemplates.length > 0) {
                domain.push(['x_template', 'in', selectedTemplates]);
            }

            // Date filter
            if (this.state.startDate && this.state.endDate) {
                domain.push(['date', '>=', this.state.startDate]);
                domain.push(['date', '<=', this.state.endDate]);
            }

            if (!isAdmin) {
                // Get projects from tasks assigned to the current user
                const taskDomain = [['user_ids', 'in', [userId]], ['depend_on_ids', '=', false],
                                    ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],];
                const taskProjects = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                    model: 'project.task',
                    method: 'search_read',
                    args: [taskDomain],
                    kwargs: {
                        fields: ['project_id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromTasks = [...new Set(
                    taskProjects.map(t => Array.isArray(t.project_id) ? t.project_id[0] : t.project_id)
                )].filter(Boolean);

               
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]], // replaced project_manager_id with user_id
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromPM = pmProjects.map(p => p.id);

                // Merge both project sources
                const combinedProjectIds = [...new Set([...projectIdsFromTasks, ...projectIdsFromPM])];

                if (combinedProjectIds.length === 0) {
                    console.warn("No active projects found for the user.");
                    return;
                }
                domain.push(['id', 'in', combinedProjectIds]);
                console.log("Filtered domain for user (task assignee or project manager):", domain);
            } else {
                console.log("Admin user — showing all filtered active projects:", domain);
            }

            const hasProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.project',
                method: 'search_read',
                args: [domain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasProjects.length) {
                console.warn("No active projects found matching filters.");
                return;
            }

            this.action.doAction({
                name: _t("Active Projects"),
                type: 'ir.actions.act_window',
                res_model: 'project.project',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    search_default_group_by_stage_id: 0,
                    search_default_group_by_project_id: 0,
                    group_by: [],
                },
                flags: {
                    withBreadcrumbs: true,
                    clearBreadcrumbs: true,
                    noDefaultReload: true,
                }
            });

        } catch (error) {
            console.error("Error showing active projects:", error);
        }
    }

    async show_running_projects(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            console.log("Showing running projects for user:", this.user.userId);
            const isAdmin = this.state.has_project_admin_rights;
            const userId = this.user.userId;

            if (!userId) {
                console.error("User ID not found — cannot proceed.");
                return;
            }

            let domain = [
                ['stage_id.name', 'in', ['In Progress']],
                ['is_fsm', '=', false],
                ['is_project_template', '=', false],
                ['active', '=', true],
            ];

            // Filter by selected departments
            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                domain.push(['x_department', 'in', deptIds]);
            }

            // Filter by selected templates
            const selectedTemplates = Array.from(this.state.selectedTemplates);
            if (selectedTemplates.length > 0) {
                domain.push(['x_template', 'in', selectedTemplates]);
            }

            // Filter by date range
            if (this.state.startDate && this.state.endDate) {
                domain.push(['date', '>=', this.state.startDate]);
                domain.push(['date', '<=', this.state.endDate]);
            }


            if (!isAdmin) {
                // Get projects from tasks assigned to the current user
                const taskDomain = [['user_ids', 'in', [userId]], ['depend_on_ids', '=', false],
                                    ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],];
                const taskProjects = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                    model: 'project.task',
                    method: 'search_read',
                    args: [taskDomain],
                    kwargs: {
                        fields: ['project_id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromTasks = [...new Set(
                    taskProjects.map(t => Array.isArray(t.project_id) ? t.project_id[0] : t.project_id)
                )].filter(Boolean);

               
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]], // replaced project_manager_id with user_id
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromPM = pmProjects.map(p => p.id);

                // Merge both project sources
                const combinedProjectIds = [...new Set([...projectIdsFromTasks, ...projectIdsFromPM])];

                if (combinedProjectIds.length === 0) {
                    console.warn("No active projects found for the user.");
                    return;
                }

                domain.push(['id', 'in', combinedProjectIds]);
                console.log("Filtered domain for user (task assignee or project manager):", domain);
            } else {
                console.log("Admin user — showing all filtered active projects:", domain);
            }

            const hasProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.project',
                method: 'search_read',
                args: [domain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasProjects.length) {
                console.warn("No running projects found matching filters.");
                return;
            }

            this.action.doAction({
                name: _t("Running Projects"),
                type: 'ir.actions.act_window',
                res_model: 'project.project',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    search_default_group_by_stage_id: 0,
                    search_default_group_by_project_id: 0,
                    group_by: [],
                },
            });

        } catch (error) {
            console.error("Error showing running projects:", error);
        }
    }

    async show_done_projects(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            console.log("Showing done projects for user:", this.user.userId);
            const isAdmin = this.state.has_project_admin_rights;
            const userId = this.user.userId;

            if (!userId) {
                console.error("User ID not found — cannot proceed.");
                return;
            }

            let domain = [
                ['stage_id.name', 'in', ['Done']],
                ['is_fsm', '=', false],
                ['is_project_template', '=', false],
                ['active', '=', true],
            ];

            // Department filter
            const selectedDepartments = Array.from(this.state.selectedDepartments || []).map(id => parseInt(id));
            if (selectedDepartments.length > 0) {
                domain.push(['x_department', 'in', selectedDepartments]);
            }

            // Template filter
            const selectedTemplates = Array.from(this.state.selectedTemplates || []);
            if (selectedTemplates.length > 0) {
                domain.push(['x_template', 'in', selectedTemplates]);
            }

            // Date filter
            if (this.state.startDate && this.state.endDate) {
                domain.push(['date', '>=', this.state.startDate]);
                domain.push(['date', '<=', this.state.endDate]);
            }


            if (!isAdmin) {
                // Get projects from tasks assigned to the current user
                const taskDomain = [['user_ids', 'in', [userId]], ['depend_on_ids', '=', false],
                                    ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],];
                const taskProjects = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                    model: 'project.task',
                    method: 'search_read',
                    args: [taskDomain],
                    kwargs: {
                        fields: ['project_id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromTasks = [...new Set(
                    taskProjects.map(t => Array.isArray(t.project_id) ? t.project_id[0] : t.project_id)
                )].filter(Boolean);

                
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]], // replaced project_manager_id with user_id
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromPM = pmProjects.map(p => p.id);

                // Merge both project sources
                const combinedProjectIds = [...new Set([...projectIdsFromTasks, ...projectIdsFromPM])];

                if (combinedProjectIds.length === 0) {
                    console.warn("No active projects found for the user.");
                    return;
                }

                domain.push(['id', 'in', combinedProjectIds]);
                console.log("Filtered domain for user (task assignee or project manager):", domain);
            } else {
                console.log("Admin user — showing all filtered active projects:", domain);
            }


            const hasProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.project',
                method: 'search_read',
                args: [domain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasProjects.length) {
                console.warn("No done projects found matching filters.");
                return;
            }


            this.action.doAction({
                name: _t("Done Projects"),
                type: 'ir.actions.act_window',
                res_model: 'project.project',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    search_default_group_by_stage_id: 0,
                    search_default_group_by_project_id: 0,
                    group_by: []
                }
            });

        } catch (error) {
            console.error("Error showing done projects:", error);
        }
    }

    async show_canceled_projects(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            console.log("Showing canceled projects for user:", this.user.userId);
            const isAdmin = this.state.has_project_admin_rights;
            const userId = this.user.userId;

            if (!userId) {
                console.error("User ID not found — cannot proceed.");
                return;
            }

            let domain = [
                ['stage_id.name', 'in', ['Canceled']],
                ['is_fsm', '=', false],
                ['is_project_template', '=', false],
                ['active', '=', true],
            ];

            // Filter by selected departments
            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                domain.push(['x_department', 'in', deptIds]);
            }

            // Filter by selected templates
            const selectedTemplates = Array.from(this.state.selectedTemplates);
            if (selectedTemplates.length > 0) {
                domain.push(['x_template', 'in', selectedTemplates]);
            }

            // Filter by date range
            if (this.state.startDate && this.state.endDate) {
                domain.push(['date', '>=', this.state.startDate]);
                domain.push(['date', '<=', this.state.endDate]);
            }


            if (!isAdmin) {
                // Get projects from tasks assigned to the current user
                const taskDomain = [['user_ids', 'in', [userId]], ['depend_on_ids', '=', false],
                                    ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],];
                const taskProjects = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                    model: 'project.task',
                    method: 'search_read',
                    args: [taskDomain],
                    kwargs: {
                        fields: ['project_id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromTasks = [...new Set(
                    taskProjects.map(t => Array.isArray(t.project_id) ? t.project_id[0] : t.project_id)
                )].filter(Boolean);

              
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]], // replaced project_manager_id with user_id
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromPM = pmProjects.map(p => p.id);

                // Merge both project sources
                const combinedProjectIds = [...new Set([...projectIdsFromTasks, ...projectIdsFromPM])];

                if (combinedProjectIds.length === 0) {
                    console.warn("No active projects found for the user.");
                    return;
                }

                domain.push(['id', 'in', combinedProjectIds]);
                console.log("Filtered domain for user (task assignee or project manager):", domain);
            } else {
                console.log("Admin user — showing all filtered active projects:", domain);
            }

            const hasProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.project',
                method: 'search_read',
                args: [domain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasProjects.length) {
                console.warn("No canceled projects found matching filters.");
                return;
            }

            this.action.doAction({
                name: _t("Canceled Projects"),
                type: 'ir.actions.act_window',
                res_model: 'project.project',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    search_default_group_by_stage_id: 0,
                    search_default_group_by_project_id: 0,
                    group_by: [],
                },
            });

        } catch (error) {
            console.error("Error showing canceled projects:", error);
        }
    }

    async show_expired_projects(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            console.log("Showing expired projects for user:", this.user.userId);
            const isAdmin = this.state.has_project_admin_rights;
            const userId = this.user.userId;

            if (!userId) {
                console.error("User ID not found — cannot proceed.");
                return;
            }

            const today = new Date();
            const formattedDate = today.toISOString().split('T')[0];

            let domain = [
                ['date', '<', formattedDate],
                ['stage_id.name', 'not in', ['Done', 'Canceled']],
                ['is_fsm', '=', false],
                ['is_project_template', '=', false],
                ['active', '=', true],
            ];

            // Filter by selected departments
            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                domain.push(['x_department', 'in', deptIds]);
            }

            // Filter by selected templates
            const selectedTemplates = Array.from(this.state.selectedTemplates);
            if (selectedTemplates.length > 0) {
                domain.push(['x_template', 'in', selectedTemplates]);
            }

            // Filter by date range
            if (this.state.startDate && this.state.endDate) {
                domain.push(['date', '>=', this.state.startDate]);
                domain.push(['date', '<=', this.state.endDate]);
            }

            if (!isAdmin) {
                // Get projects from tasks assigned to the current user
                const taskDomain = [['user_ids', 'in', [userId]], ['depend_on_ids', '=', false],
                                    ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],];
                const taskProjects = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                    model: 'project.task',
                    method: 'search_read',
                    args: [taskDomain],
                    kwargs: {
                        fields: ['project_id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromTasks = [...new Set(
                    taskProjects.map(t => Array.isArray(t.project_id) ? t.project_id[0] : t.project_id)
                )].filter(Boolean);

                
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]], // replaced project_manager_id with user_id
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromPM = pmProjects.map(p => p.id);

                // Merge both project sources
                const combinedProjectIds = [...new Set([...projectIdsFromTasks, ...projectIdsFromPM])];

                if (combinedProjectIds.length === 0) {
                    console.warn("No active projects found for the user.");
                    return;
                }

                domain.push(['id', 'in', combinedProjectIds]);
                console.log("Filtered domain for user (task assignee or project manager):", domain);
            } else {
                console.log("Admin user — showing all filtered active projects:", domain);
            }

            const hasProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.project',
                method: 'search_read',
                args: [domain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasProjects.length) {
                console.warn("No expired projects found matching filters.");
                return;
            }

            this.action.doAction({
                name: _t("Expired Projects"),
                type: 'ir.actions.act_window',
                res_model: 'project.project',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    search_default_group_by_stage_id: 0,
                    search_default_group_by_project_id: 0,
                    group_by: [],
                },
            });

        } catch (error) {
            console.error("Error showing expired projects:", error);
        }
    }

    async show_done_task(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            const userId = this.user.userId;

            if (!userId) {
                console.error("Could not determine current user ID");
                return;
            }

            let domain = [
                ['state', '=', '1_done'],
                ['project_id', '!=', false],
                ['active', '=', true],
                ['project_id.is_fsm', '=', false],
                ['project_id.is_project_template', '=', false],
                ['project_id.active', '=', true]
            ];

            if (this.state.has_project_admin_rights) {
                // Admins have full access
                console.log("Project Admin: Viewing all done tasks");
            } else {
                // Check if user is a Project Manager
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]],
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIds = pmProjects.map(p => p.id);

                if (projectIds.length > 0) {
                    domain.push(['project_id', 'in', projectIds]);
                    console.log("Project Manager: Viewing done tasks of managed projects");
                } else {
                    console.warn("Access denied: Not a project admin or manager");
                    return;
                }
            }

            // Department filter
            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                domain.push(['project_id.x_department', 'in', deptIds]);
            }

            // Template filter
            const selectedTemplates = Array.from(this.state.selectedTemplates || []);
            if (selectedTemplates.length > 0) {
                domain.push(['project_id.x_template', 'in', selectedTemplates]);
            }

            // Date range filter
            if (this.state.startDate && this.state.endDate) {
                domain.push(['project_id.date', '>=', this.state.startDate]);
                domain.push(['project_id.date', '<=', this.state.endDate]);
            }

            this.action.doAction({
                name: _t("Done Tasks"),
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    group_by: ['state']
                }
            });
        } catch (error) {
            console.error("Error showing done tasks:", error);
        }
    }


     async show_expired_yesterday(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            console.log("Showing expired yesterday projects for user:", this.user.userId);
            const isAdmin = this.state.has_project_admin_rights;
            const userId = this.user.userId;

            if (!userId) {
                console.error("User ID not found — cannot proceed.");
                return;
            }

            const yesterday = new Date();
            yesterday.setDate(yesterday.getDate() - 1);
            const formattedDate = yesterday.toISOString().split('T')[0];

            let domain = [
                ['date', '=', formattedDate],
                ['stage_id.name', 'not in', ['Done', 'Canceled']],
                ['is_fsm', '=', false],
                ['is_project_template', '=', false],
                ['active', '=', true],
            ];

            // Filter by selected departments
            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                domain.push(['x_department', 'in', deptIds]);
            }

            // Filter by selected templates
            const selectedTemplates = Array.from(this.state.selectedTemplates);
            if (selectedTemplates.length > 0) {
                domain.push(['x_template', 'in', selectedTemplates]);
            }

            // Filter by custom date range
            if (this.state.startDate && this.state.endDate) {
                domain.push(['date', '>=', this.state.startDate]);
                domain.push(['date', '<=', this.state.endDate]);
            }

            if (!isAdmin) {
                // Get projects from tasks assigned to the current user
                const taskDomain = [['user_ids', 'in', [userId]], ['depend_on_ids', '=', false],
                                    ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']]];
                const taskProjects = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                    model: 'project.task',
                    method: 'search_read',
                    args: [taskDomain],
                    kwargs: {
                        fields: ['project_id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromTasks = [...new Set(
                    taskProjects.map(t => Array.isArray(t.project_id) ? t.project_id[0] : t.project_id)
                )].filter(Boolean);

            
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]], // replaced project_manager_id with user_id
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromPM = pmProjects.map(p => p.id);

                // Merge both project sources
                const combinedProjectIds = [...new Set([...projectIdsFromTasks, ...projectIdsFromPM])];

                if (combinedProjectIds.length === 0) {
                    console.warn("No active projects found for the user.");
                    return;
                }

                domain.push(['id', 'in', combinedProjectIds]);
                console.log("Filtered domain for user (task assignee or project manager):", domain);
            } else {
                console.log("Admin user — showing all filtered active projects:", domain);
            }

            const hasProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.project',
                method: 'search_read',
                args: [domain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasProjects.length) {
                console.warn("No expired yesterday projects found matching filters.");
                return;
            }

            this.action.doAction({
                name: _t("Projects Expired Yesterday"),
                type: 'ir.actions.act_window',
                res_model: 'project.project',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    search_default_group_by_stage_id: 0,
                    search_default_group_by_project_id: 0,
                    group_by: [],
                },
            });

        } catch (error) {
            console.error("Error showing expired yesterday projects:", error);
        }
    }

     async show_will_expire_tomorrow(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            console.log("Showing projects that will expire tomorrow with current state:", {
                selectedDepartments: this.state.selectedDepartments,
                selectedTemplates: this.state.selectedTemplates,
                dateRange: {
                    startDate: this.state.startDate,
                    endDate: this.state.endDate
                },
                has_project_admin_rights: this.state.has_project_admin_rights
            });

            const isAdmin = this.state.has_project_admin_rights;
            const userId = this.user.userId;

            if (!userId) {
                console.error("User ID not found — cannot proceed.");
                return;
            }

            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            const formattedDate = tomorrow.toISOString().split('T')[0];

            let domain = [
                ['date', '=', formattedDate],
                ['stage_id.name', 'not in', ['Done', 'Canceled']],
                ['is_fsm', '=', false],
                ['is_project_template', '=', false],
                ['active', '=', true],
            ];

            // Apply department filter
            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                domain.push(['x_department', 'in', deptIds]);
            }

            // Apply template filter
            const selectedTemplates = Array.from(this.state.selectedTemplates);
            if (selectedTemplates.length > 0) {
                domain.push(['x_template', 'in', selectedTemplates]);
            }

            // Apply custom date range filter
            if (this.state.startDate && this.state.endDate) {
                domain.push(['date', '>=', this.state.startDate]);
                domain.push(['date', '<=', this.state.endDate]);
            }


            if (!isAdmin) {
                // Get projects from tasks assigned to the current user
                const taskDomain = [['user_ids', 'in', [userId]], ['depend_on_ids', '=', false],
                                    ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],];
                const taskProjects = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                    model: 'project.task',
                    method: 'search_read',
                    args: [taskDomain],
                    kwargs: {
                        fields: ['project_id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromTasks = [...new Set(
                    taskProjects.map(t => Array.isArray(t.project_id) ? t.project_id[0] : t.project_id)
                )].filter(Boolean);

                
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]], // replaced project_manager_id with user_id
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromPM = pmProjects.map(p => p.id);

                // Merge both project sources
                const combinedProjectIds = [...new Set([...projectIdsFromTasks, ...projectIdsFromPM])];

                if (combinedProjectIds.length === 0) {
                    console.warn("No active projects found for the user.");
                    return;
                }

                domain.push(['id', 'in', combinedProjectIds]);
                console.log("Filtered domain for user (task assignee or project manager):", domain);
            } else {
                console.log("Admin user — showing all filtered active projects:", domain);
            }

            const hasProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.project',
                method: 'search_read',
                args: [domain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasProjects.length) {
                console.warn("No expired tomorrow projects found matching filters.");
                return;
            }

            this.action.doAction({
                name: _t("Projects Expiring Tomorrow"),
                type: 'ir.actions.act_window',
                res_model: 'project.project',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    search_default_group_by_stage_id: 0,
                    search_default_group_by_project_id: 0,
                    group_by: [],
                },
            });

        } catch (error) {
            console.error("Error showing projects expiring tomorrow:", error);
        }
    }

    async show_expired_today(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            console.log("Showing projects expiring today with current state:", {
                selectedDepartments: this.state.selectedDepartments,
                selectedTemplates: this.state.selectedTemplates,
                dateRange: {
                    startDate: this.state.startDate,
                    endDate: this.state.endDate
                },
                has_project_admin_rights: this.state.has_project_admin_rights
            });

            const isAdmin = this.state.has_project_admin_rights;
            const userId = this.user.userId;

            if (!userId) {
                console.error("User ID not found — cannot proceed.");
                return;
            }

            const today = new Date();
            const formattedDate = today.toISOString().split('T')[0];

            let domain = [
                ['date', '=', formattedDate],
                ['stage_id.name', 'not in', ['Done', 'Canceled']],
                ['is_fsm', '=', false],
                ['is_project_template', '=', false],
                ['active', '=', true],
            ];

            // Department filter
            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                domain.push(['x_department', 'in', deptIds]);
            }

            // Template filter
            const selectedTemplates = Array.from(this.state.selectedTemplates);
            if (selectedTemplates.length > 0) {
                domain.push(['x_template', 'in', selectedTemplates]);
            }

            // Date range filter (if explicitly provided)
            if (this.state.startDate && this.state.endDate) {
                domain.push(['date', '>=', this.state.startDate]);
                domain.push(['date', '<=', this.state.endDate]);
            }


            if (!isAdmin) {
                // Get projects from tasks assigned to the current user
                const taskDomain = [['user_ids', 'in', [userId]], ['depend_on_ids', '=', false],
                                    ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],];
                const taskProjects = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                    model: 'project.task',
                    method: 'search_read',
                    args: [taskDomain],
                    kwargs: {
                        fields: ['project_id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromTasks = [...new Set(
                    taskProjects.map(t => Array.isArray(t.project_id) ? t.project_id[0] : t.project_id)
                )].filter(Boolean);

            
                const pmProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [[['user_id', '=', userId]]], // replaced project_manager_id with user_id
                    kwargs: {
                        fields: ['id'],
                        context: this.context || {},
                    },
                });

                const projectIdsFromPM = pmProjects.map(p => p.id);

                // Merge both project sources
                const combinedProjectIds = [...new Set([...projectIdsFromTasks, ...projectIdsFromPM])];

                if (combinedProjectIds.length === 0) {
                    console.warn("No active projects found for the user.");
                    return;
                }

                domain.push(['id', 'in', combinedProjectIds]);
                console.log("Filtered domain for user (task assignee or project manager):", domain);
            } else {
                console.log("Admin user — showing all filtered active projects:", domain);
            }

             const hasProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.project',
                method: 'search_read',
                args: [domain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasProjects.length) {
                console.warn("No expired today projects found matching filters.");
                return;
            }

            this.action.doAction({
                name: _t("Projects Expiring Today"),
                type: 'ir.actions.act_window',
                res_model: 'project.project',
                domain: domain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    search_default_group_by_stage_id: 0,
                    search_default_group_by_project_id: 0,
                    group_by: [],
                },
            });

        } catch (error) {
            console.error("Error showing projects expiring today:", error);
        }
    }


    async show_expired_tasks(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            const userId = this.user.userId;
            const isAdmin = this.state.has_project_admin_rights;

            if (!userId) {
                console.error("User ID not found — cannot proceed.");
                return;
            }

            const today = new Date();
            const formattedDate = today.toISOString().split('T')[0];

            // Base project domain
            let projectDomain = [
                ['date', '<', formattedDate],
                ['stage_id.name', 'not in', ['Done', 'Canceled']],
                ['is_fsm', '=', false],
                ['is_project_template', '=', false],
                ['active', '=', true],
            ];

            // Department filter
            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                projectDomain.push(['x_department', 'in', deptIds]);
            }

            // Template filter
            const selectedTemplates = Array.from(this.state.selectedTemplates || []);
            if (selectedTemplates.length > 0) {
                projectDomain.push(['x_template', 'in', selectedTemplates]);
            }

            // Date range filter
            if (this.state.startDate && this.state.endDate) {
                projectDomain.push(['date', '>=', this.state.startDate]);
                projectDomain.push(['date', '<=', this.state.endDate]);
            }

            // Get expired projects
            const expiredProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.project',
                method: 'search_read',
                args: [projectDomain],
                kwargs: {
                    fields: ['id', 'user_id'],  // Include user_id to check project managers
                    context: this.context || {},
                },
            });

            if (!expiredProjects.length) {
                console.warn("No expired projects found.");
                return;
            }

            let projectIds = expiredProjects.map(p => p.id);

            // Check if user is a project manager of any expired project
            const managedProjectIds = expiredProjects
                .filter(project => project.user_id && project.user_id[0] === userId)
                .map(project => project.id);

            // Task domain
            let taskDomain = [
                ['project_id', 'in', projectIds],
                ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],
                ['active', '=', true],
            ];

            if (!isAdmin) {
                if (managedProjectIds.length) {
                    taskDomain.push('|',
                        ['project_id', 'in', managedProjectIds],
                        ['user_ids', 'in', [userId]]
                    );
                    console.log("Project Manager: viewing own projects and assigned tasks.");
                } else {
                    taskDomain.push(['user_ids', 'in', [userId]]);
                    console.log("Regular User: viewing only assigned tasks.");
                }
            } else {
                console.log("Admin: viewing all expired tasks.");
            }

            // Check if any tasks exist
            const hasTasks = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                model: 'project.task',
                method: 'search_read',
                args: [taskDomain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasTasks.length) {
                console.warn("No expired tasks found.");
                return;
            }

            // Open task list
            this.action.doAction({
                name: _t("Ongoing Tasks in Expired Projects"),
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: taskDomain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    group_by: ['project_id']
                },
            });

        } catch (error) {
            console.error("Error showing expired tasks:", error);
        }
    }
    

        async show_expired_yesterday_tasks(e) {
            e.stopPropagation();
            e.preventDefault();

            try {
                const userId = this.user.userId;
                const isAdmin = this.state.has_project_admin_rights;

                if (!userId) {
                    console.error("User ID not found — cannot proceed.");
                    return;
                }

                const yesterday = new Date();
                yesterday.setDate(yesterday.getDate() - 1);
                const formattedDate = yesterday.toISOString().split('T')[0];

                // Base project domain
                let projectDomain = [
                    ['date', '=', formattedDate],
                    ['stage_id.name', 'not in', ['Done', 'Canceled']],
                    ['is_fsm', '=', false],
                    ['is_project_template', '=', false],
                    ['active', '=', true],
                ];

                // Department filter
                if (this.state.selectedDepartments?.size > 0) {
                    const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                    projectDomain.push(['x_department', 'in', deptIds]);
                }

                // Template filter
                const selectedTemplates = Array.from(this.state.selectedTemplates || []);
                if (selectedTemplates.length > 0) {
                    projectDomain.push(['x_template', 'in', selectedTemplates]);
                }

                // Date range filter
                if (this.state.startDate && this.state.endDate) {
                    projectDomain.push(['date', '>=', this.state.startDate]);
                    projectDomain.push(['date', '<=', this.state.endDate]);
                }

                // Get expired yesterday projects
                const expiredProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                    model: 'project.project',
                    method: 'search_read',
                    args: [projectDomain],
                    kwargs: {
                        fields: ['id', 'user_id'],
                        context: this.context || {},
                    },
                });

                if (!expiredProjects.length) {
                    console.warn("No expired yesterday projects found.");
                    return;
                }

                let projectIds = expiredProjects.map(p => p.id);

                // Identify which expired projects are managed by the user
                const managedProjectIds = expiredProjects
                    .filter(project => project.user_id && project.user_id[0] === userId)
                    .map(project => project.id);

                // Task domain
                let taskDomain = [
                    ['project_id', 'in', projectIds],
                    ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],
                    ['active', '=', true],
                ];

                if (!isAdmin) {
                    if (managedProjectIds.length) {
                        // Project Manager: tasks from their managed projects OR assigned tasks
                        taskDomain.push('|',
                            ['project_id', 'in', managedProjectIds],
                            ['user_ids', 'in', [userId]]
                        );
                        console.log("Project Manager: viewing own projects and assigned tasks.");
                    } else {
                        // Regular user: only assigned tasks
                        taskDomain.push(['user_ids', 'in', [userId]]);
                        console.log("Regular User: viewing only assigned tasks.");
                    }
                } else {
                    console.log("Admin: viewing all expired yesterday tasks.");
                }

                // Check if tasks exist
                const hasTasks = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                    model: 'project.task',
                    method: 'search_read',
                    args: [taskDomain],
                    kwargs: { fields: ['id'], limit: 1 },
                });

                if (!hasTasks.length) {
                    console.warn("No expired yesterday tasks found matching filters.");
                    return;
                }

                // Open the tasks
                this.action.doAction({
                    name: _t("Ongoing Tasks in Projects Expired Yesterday"),
                    type: 'ir.actions.act_window',
                    res_model: 'project.task',
                    domain: taskDomain,
                    views: [
                        [false, 'list'],
                        [false, 'form'],
                        [false, 'kanban']
                    ],
                    target: 'current',
                    context: {
                        group_by: ['project_id']
                    },
                });

            } catch (error) {
                console.error("Error showing expired yesterday tasks:", error);
            }
        }


    async show_expired_today_tasks(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            const userId = this.user.userId;
            const isAdmin = this.state.has_project_admin_rights;

            if (!userId) {
                console.error("User ID not found — cannot proceed.");
                return;
            }

            const today = new Date();
            const formattedDate = today.toISOString().split('T')[0];

            // Project domain
            let projectDomain = [
                ['date', '=', formattedDate],
                ['stage_id.name', 'not in', ['Done', 'Canceled']],
                ['is_fsm', '=', false],
                ['is_project_template', '=', false],
                ['active', '=', true],
            ];

            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                projectDomain.push(['x_department', 'in', deptIds]);
            }

            const selectedTemplates = Array.from(this.state.selectedTemplates || []);
            if (selectedTemplates.length > 0) {
                projectDomain.push(['x_template', 'in', selectedTemplates]);
            }

            if (this.state.startDate && this.state.endDate) {
                projectDomain.push(['date', '>=', this.state.startDate]);
                projectDomain.push(['date', '<=', this.state.endDate]);
            }

            const expiredProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.project',
                method: 'search_read',
                args: [projectDomain],
                kwargs: {
                    fields: ['id', 'user_id'],
                    context: this.context || {},
                },
            });

            if (!expiredProjects.length) {
                console.warn("No projects expiring today found.");
                return;
            }

            const projectIds = expiredProjects.map(p => p.id);
            const managedProjectIds = expiredProjects
                .filter(project => project.user_id && project.user_id[0] === userId)
                .map(project => project.id);

            let taskDomain = [
                ['project_id', 'in', projectIds],
                ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],
                ['active', '=', true],
            ];

            if (!isAdmin) {
                if (managedProjectIds.length) {
                    taskDomain.push('|',
                        ['project_id', 'in', managedProjectIds],
                        ['user_ids', 'in', [userId]]
                    );
                    console.log("PM: tasks in managed projects + assigned.");
                } else {
                    taskDomain.push(['user_ids', 'in', [userId]]);
                    console.log("User: only assigned tasks.");
                }
            }

            const hasTasks = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                model: 'project.task',
                method: 'search_read',
                args: [taskDomain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasTasks.length) {
                console.warn("No expiring today tasks found.");
                return;
            }

            this.action.doAction({
                name: _t("Tasks Expiring Today"),
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: taskDomain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    group_by: ['project_id']
                },
            });

        } catch (error) {
            console.error("Error showing today's expired tasks:", error);
        }
    }

    async show_will_expire_tomorrow_tasks(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            const userId = this.user.userId;
            const isAdmin = this.state.has_project_admin_rights;

            if (!userId) {
                console.error("User ID not found — cannot proceed.");
                return;
            }

            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            const formattedDate = tomorrow.toISOString().split('T')[0];

            let projectDomain = [
                ['date', '=', formattedDate],
                ['stage_id.name', 'not in', ['Done', 'Canceled']],
                ['is_fsm', '=', false],
                ['is_project_template', '=', false],
                ['active', '=', true],
            ];

            if (this.state.selectedDepartments?.size > 0) {
                const deptIds = Array.from(this.state.selectedDepartments).map(id => parseInt(id));
                projectDomain.push(['x_department', 'in', deptIds]);
            }

            const selectedTemplates = Array.from(this.state.selectedTemplates || []);
            if (selectedTemplates.length > 0) {
                projectDomain.push(['x_template', 'in', selectedTemplates]);
            }

            if (this.state.startDate && this.state.endDate) {
                projectDomain.push(['date', '>=', this.state.startDate]);
                projectDomain.push(['date', '<=', this.state.endDate]);
            }

            const expiringProjects = await this.rpc('/web/dataset/call_kw/project.project/search_read', {
                model: 'project.project',
                method: 'search_read',
                args: [projectDomain],
                kwargs: {
                    fields: ['id', 'user_id'],
                    context: this.context || {},
                },
            });

            if (!expiringProjects.length) {
                console.warn("No projects expiring tomorrow found.");
                return;
            }

            const projectIds = expiringProjects.map(p => p.id);
            const managedProjectIds = expiringProjects
                .filter(project => project.user_id && project.user_id[0] === userId)
                .map(project => project.id);

            let taskDomain = [
                ['project_id', 'in', projectIds],
                ['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],
                ['active', '=', true],
            ];

            if (!isAdmin) {
                if (managedProjectIds.length) {
                    taskDomain.push('|',
                        ['project_id', 'in', managedProjectIds],
                        ['user_ids', 'in', [userId]]
                    );
                    console.log("PM: tasks in managed projects + assigned.");
                } else {
                    taskDomain.push(['user_ids', 'in', [userId]]);
                    console.log("User: only assigned tasks.");
                }
            }

            const hasTasks = await this.rpc('/web/dataset/call_kw/project.task/search_read', {
                model: 'project.task',
                method: 'search_read',
                args: [taskDomain],
                kwargs: { fields: ['id'], limit: 1 },
            });

            if (!hasTasks.length) {
                console.warn("No expiring tomorrow tasks found.");
                return;
            }

            this.action.doAction({
                name: _t("Tasks Expiring Tomorrow"),
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: taskDomain,
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current',
                context: {
                    group_by: ['project_id']
                },
            });

        } catch (error) {
            console.error("Error showing tomorrow's expiring tasks:", error);
        }
    }



    toggleTemplateSelection(templateName) {
        if (this.state.selectedTemplates.has(templateName)) {
            this.state.selectedTemplates.delete(templateName);
        } else {
            this.state.selectedTemplates.add(templateName);
        }
    }

    toggleTemplatesSection() {
        try {
            console.log("Toggling templates section. Current state:", this.state.templatesExpanded);
            this.state.templatesExpanded = !this.state.templatesExpanded;
            console.log("New templates section state:", this.state.templatesExpanded);
        } catch (error) {
            console.error("Error toggling templates section:", error);
        }
    }

    isTemplatesExpanded() {
        return this.state.templatesExpanded;
    }

    getStoredState() {
        try {
            // If it's a page refresh, return empty state
            if (this.isPageRefresh()) {
                localStorage.removeItem('dashboard_state');
                return {};
            }
            const stored = localStorage.getItem('dashboard_state');
            return stored ? JSON.parse(stored) : {};
        } catch (e) {
            console.error('Error reading stored state:', e);
            return {};
        }
    }

    hasStoredState() {
        // Don't check stored state if it's a page refresh
        if (this.isPageRefresh()) {
            return false;
        }
        const stored = this.getStoredState();
        return !!(stored.departments?.length || stored.templates?.length ||
                  stored.startDate || stored.sidebarOpen || stored.selectedDateRange);
    }

    storeState() {
        // Don't store state if it's a page refresh
        if (this.isPageRefresh()) {
            return;
        }
        const stateToStore = {
            departments: [...this.state.selectedDepartments],
            templates: [...this.state.selectedTemplates],
            startDate: this.state.startDate,
            endDate: this.state.endDate,
            sidebarOpen: true, // Force sidebar to stay open when filters are applied
            selectedDateRange: this.state.selectedDateRange,
            templatesExpanded: this.state.templatesExpanded,
            expandedCompanyIds: [...this.state.expandedCompanyIds],
            selectedCompanies: [...this.state.selectedCompanies]
        };
        localStorage.setItem('dashboard_state', JSON.stringify(stateToStore));
    }

    applyStoredState() {
        // Don't clear state if coming back from another page
        if (this.isPageRefresh() && window.performance.navigation.type !== 2) {
            this.clearStoredState();
            return;
        }

        const storedState = this.getStoredState();

        // If there are any filters applied, ensure sidebar is open
        const hasFilters = storedState.departments?.length > 0 ||
                          storedState.templates?.length > 0 ||
                          storedState.selectedDateRange;

        // Force sidebar open if filters are applied
        if (hasFilters) {
            this.state.sidebarOpen = true;
        }

        // Restore all stored state
        if (storedState.departments) {
            this.state.selectedDepartments = new Set(storedState.departments);
        }
        if (storedState.templates) {
            this.state.selectedTemplates = new Set(storedState.templates);
            this.state.templatesExpanded = true; // Expand templates section if templates are selected
        }
        if (storedState.startDate && storedState.endDate) {
            this.state.startDate = storedState.startDate;
            this.state.endDate = storedState.endDate;
            this.state.selectedDateRange = storedState.selectedDateRange;
        }
        if (storedState.expandedCompanyIds) {
            this.state.expandedCompanyIds = new Set(storedState.expandedCompanyIds);
        }

        // Initialize date picker with stored date if exists
        if (storedState.selectedDateRange) {
            const dateInput = document.querySelector("#date_input");
            if (dateInput && typeof flatpickr !== "undefined") {
                flatpickr(dateInput, {
                    mode: "range",
                    dateFormat: "Y-m-d",
                    defaultDate: [storedState.startDate, storedState.endDate],
                    position: "auto right",
                    static: false,
                    onChange: (selectedDates, dateStr) => {
                        if (selectedDates.length === 2) {
                            this.state.selectedDateRange = dateStr;
                            this.state.startDate = selectedDates[0].toISOString().split("T")[0];
                            this.state.endDate = selectedDates[1].toISOString().split("T")[0];
                            this.filters();
                        }
                    },
                });
            }
        }

        // Apply filters and load data
        this.filters();
        this.loadCharts();
    }

    clearStoredState() {
        localStorage.removeItem('dashboard_state');
        this.state.selectedDepartments = new Set();
        this.state.selectedTemplates = new Set();
        this.state.startDate = null;
        this.state.endDate = null;
        this.state.selectedDateRange = null;
        this.state.sidebarOpen = false;
        this.state.templatesExpanded = false;
        this.state.expandedCompanyIds = new Set();

        // Clear date picker
        const dateInput = document.querySelector("#date_input");
        if (dateInput) {
            dateInput.value = '';
        }

        this.filters();
    }

    // Add this helper method to expand parent company
    async expandParentCompany(departmentId) {
        for (const company of this.state.companies) {
            const departments = await this.loadDepartments(company.id);
            if (departments.some(dept => dept.id === departmentId)) {
                this.state.expandedCompanyIds.add(company.id);
                break;
            }
        }
    }

    // Add these new methods to handle refresh detection
    setPageRefreshFlag() {
        const timestamp = Date.now();
        sessionStorage.setItem('lastActivity', timestamp);
    }

    isPageRefresh() {
        // Check if it's a back/forward navigation
        if (window.performance) {
            const navType = window.performance.navigation.type;
            const isBackForward = navType === 2; // 2 is TYPE_BACK_FORWARD

            if (isBackForward) {
                return false;
            }
        }
        const lastActivity = sessionStorage.getItem('lastActivity');
        const currentTimestamp = Date.now();

        // Consider it a refresh only if it's a true page reload
        return !lastActivity || (currentTimestamp - lastActivity) > 1000;
    }

    clearPageRefreshFlag() {
        sessionStorage.removeItem('lastActivity');
    }

    toggleSidebar() {
        this.state.sidebarOpen = !this.state.sidebarOpen;
        this.storeState();
    }

    toggleDepartmentsSection() {
        this.state.departmentsExpanded = !this.state.departmentsExpanded;
        this.render();
    }

    async filters() {
        try {
            console.log("Applying filters...");

            // Save filter state
            const filterData = {
                selectedDepartments: Array.from(this.state.selectedDepartments || []),
                selectedTemplates: Array.from(this.state.selectedTemplates || []),
                startDate: this.state.startDate,
                endDate: this.state.endDate,
            };
            sessionStorage.setItem('dashboardFilterState', JSON.stringify(filterData));

            // Update state for fetch
            this.state.activeDepartmentIds = filterData.selectedDepartments;
            this.state.project_template = filterData.selectedTemplates;

            await this.fetch_data();

            console.log("Filters applied and stored successfully.");
        } catch (error) {
            console.error("Error applying filters:", error);
        }
    }

    async clearFilters() {
        try {
            console.log("Clearing filters...");

            // Clear selections
            this.state.selectedDepartments.clear();
            this.state.selectedTemplates.clear();

            // Reset dates
            this.state.startDate = null;
            this.state.endDate = null;
            this.state.selectedDateRange = null;

            // Clear date picker
            const dateInput = document.querySelector("#date_input");
            if (dateInput && dateInput._flatpickr) {
                dateInput._flatpickr.clear();
            }

            // Refresh data
            await this.fetch_data();

            // Clear stored state
            this.clearStoredState();

            console.log("Filters cleared successfully");
        } catch (error) {
            console.error("Error clearing filters:", error);
        }
    }
}

ProjectDashboard.template = "project_dashboard_odoo_new.ProjectDashboardMain"
registry.category("actions").add("project_dashboard_main", ProjectDashboard)
