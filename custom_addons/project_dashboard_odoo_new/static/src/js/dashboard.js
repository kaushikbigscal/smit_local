/** @odoo-module */
import { registry} from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, onMounted, useState} = owl
import { jsonrpc } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";

export class ProjectDashboard extends Component {
    /**
     * Setup method to initialize required services and register event handlers.
     */
	setup() {
	    super.setup();
		this.action = useService("action");
		this.orm = useService("orm");
		this.rpc = this.env.services.rpc
		this.departments = []
		this.selectedDepartment = null
	    this.employeeChart = null;
	    this.tagsChart = null;
	    this.templates = []
	    this.project_template = null;
        this.startDate = null;
        this.endDate = null;
		this.state = useState({
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
        });

		onWillStart(this.onWillStart);
		onMounted(this.onMounted);

	}
	async onStartDateChange(event) {
        this.startDate = event.target.value; // Capture start date
        await this.applyFilters(); // Reapply filters
    }

    async onEndDateChange(event) {
        this.endDate = event.target.value; // Capture end date
        await this.applyFilters(); // Reapply filters
    }

    async onStartDateChange(event) {
        this.startDate = event.target.value; // Capture start date
        await this.applyFilters(); // Reapply filters
    }

    async onEndDateChange(event) {
        this.endDate = event.target.value; // Capture end date
        await this.applyFilters(); // Reapply filters
    }

	async applyFilters() {
        // Fetch data and update charts
        await this.fetch_data();
        await this.loadCharts();
    }

    async onWillStart() {
        await this.loadDepartments();
        await this.loadProjectTemplate();
        await this.fetch_data();

    }

    async loadDepartment(companyId) {
        try {
            const departments = await jsonrpc("/get/departments/by_company", {
                company_id: companyId
            });
            this.state.department_data = departments; // Changed from this.state.departments to this.state.department_data
            console.log("Departments", this.state.department_data);
        } catch (error) {
            console.error("Error loading departments:", error);
            this.state.department_data = []; // Changed from this.state.departments to this.state.department_data
        }
    }

	async onMounted() {
		// Render other components after fetching data
        this.loadCharts();
	}

	async loadDepartments(){
	    try{
	        this.departments = await jsonrpc("/get/departments");
	    } catch (error){
	        console.error("Error Loading Departments", error);
	        this.departments = [];
	    }
	}
	async onDepartmentChange(){
	    this.selectedDepartment = event.target.value
	}

	async loadProjectTemplate(){
	    try{
	        this.templates = await jsonrpc("/get/project_template");
	    } catch (error){
	        console.error("Error Loading Template", error);
	        this.templates = [];
	    }
	}

    async onTemplateChange(event){
	    this.project_template = event.target.value;
//	    await this.fetch_data();
//	    await this.loadCharts();
	}

    async loadCharts() {
        await this.render_task_tags_chart();
        await this.render_employee_task_chart();
    }


async render_employee_task_chart() {
    try {
        if (this.employeeChart) {
            this.employeeChart.destroy();
        }
        // Fetching data via RPC
        const data = await jsonrpc("/project/task/by_employee", {department_id: this.selectedDepartment, x_template: this.project_template});
        if (!data) {
            console.error("No data received for employee task chart.");
            return null;
        }
        console.log("Data received for employee task chart:", data);

        const ctx = $("#employee_task_chart")[0];
        if (!ctx) {
            console.error("Canvas context not found.");
            return null;
        }

        try {
            // Creating the chart
            this.employeeChart = new Chart(ctx, {
                type: 'bar',
                    data: {
                        labels: data.labels || [],
                        datasets: [{
                            label: 'Number of Tasks',
                            data: data.data || [],
                            backgroundColor: data.colors,
                            borderColor: data.colors,
                            borderWidth: 1
                        }]
                    },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    animation: {
                        duration: 0, // Disable animations for faster rendering
                        onComplete: function() {
                            const chartInstance = this.chart;
                            if (!chartInstance) {
                                console.error("Chart Instance is Undefined");
                                return;
                            }
                            const ctx = chartInstance.ctx;
                            if (!ctx) {
                                console.error("Chart Context is Undefined");
                                return;
                            }

                            try {
                                ctx.font = Chart.helpers.fontString(Chart.defaults.global.defaultFontSize, Chart.defaults.global.defaultFontStyle, Chart.defaults.global.defaultFontFamily);
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'bottom';

                                this.data.datasets.forEach(function(dataset, i) {
                                    var meta = chartInstance.controller.getDatasetMeta(i);
                                    meta.data.forEach(function(bar, index) {
                                        var data = dataset.data[index];
                                        ctx.fillText(data, bar._model.x, bar._model.y - 5);
                                    });
                                });
                            } catch (err) {
                                console.error('Error in chart onComplete:', err);
                            }
                        }
                    },
                    onClick: (evt, activeElements) => {
                        try {
                            if (activeElements && activeElements.length > 0) {
                                const clickedElement = activeElements[0];
                                const clickedLabel = clickedElement._model.label;

                                console.log("Clicked employee:", clickedLabel);

                                if (clickedLabel) {
                                    this.show_tasks_by_employee(clickedLabel);
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
                                maxRotation: 30,
                                minRotation: 30
                            }
                        }]
                    },
                    legend: {
                        display: true
                    },
                }
            });
        } catch (err) {
            console.error("Error creating the chart:", err);
            return null;
        }
    } catch (error) {
        console.error("Error rendering employee task chart:", error);
        return null;
    }
}

async render_task_tags_chart() {
    try {

        // Fetching data via RPC
         if (this.tagsChart) {
            this.tagsChart.destroy();
        }

        const data = await jsonrpc("/project/task/by_tags", { department_id: this.selectedDepartment, x_template: this.project_template});
        if (!data) {
            console.error("No data received for task tags chart.");
            return null;
        }
        console.log("Data received for task tags chart:", data);

        const ctx = $("#task_tags_chart")[0];
        if (!ctx || ctx.length === 0) {
            return null;
        }

        try {
            // Creating the chart
            this.tagsChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels || [],
                    datasets: [{
                        label: 'Number of Tasks',
                        data: data.data || [],
                        backgroundColor: data.colors,
                        borderColor: data.colors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    animation: {
                        duration: 0, // Disable animations for faster rendering
                        onComplete: function() {
                            try {
                                const chartInstance = this.chart;
                                if (!chartInstance) {
                                    console.error("Chart Instance is Undefined");
                                    return;
                                }
                                const ctx = chartInstance.ctx;
                                if (!ctx) {
                                    console.error("Chart Context is Undefined");
                                    return;
                                }

                                // For Chart.js 2.9, fontString must be manually constructed
                                ctx.font = Chart.helpers.fontString(
                                    Chart.defaults.global.defaultFontSize,
                                    Chart.defaults.global.defaultFontStyle,
                                    Chart.defaults.global.defaultFontFamily
                                );
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'bottom';

                                this.data.datasets.forEach(function(dataset, i) {
                                    const meta = chartInstance.controller.getDatasetMeta(i);
                                    meta.data.forEach(function(bar, index) {
                                        const data = dataset.data[index];
                                        ctx.fillText(data, bar._model.x, bar._model.y - 5);
                                    });
                                });
                            } catch (err) {
                                console.error('Error in chart onComplete:', err);
                            }
                        }
                    },
                    onClick: (evt, activeElements) => {
                        try {
                            if (activeElements && activeElements.length > 0) {
                                const clickedElement = activeElements[0];
                                const clickedLabel = clickedElement._model.label;

                                console.log("Clicked element:", clickedElement);
                                console.log("Clicked label:", clickedLabel);

                                if (clickedLabel) {
                                    this.show_tasks_by_tag(clickedLabel);
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
                                minRotation: 45
                            }
                        }]
                    },
                    legend: {
                            display: true,
                            position: 'top', // Place the legend at the top
                    },
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

	/**
	function for getting values when page is loaded
	*/
async fetch_data() {
        try {
            const result = await jsonrpc('/get/tiles/data', {
                department_id: this.selectedDepartment,
                x_template: this.project_template,
                start_date: this.startDate,
                end_date: this.endDate
            });

            // Update the state with the new data
            this.state = {
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
                expired_projects: result.expired_projects || 0
            };

            // Trigger a re-render
            this.render();

        } catch (error) {
            console.error("Error fetching dashboard data:", error);
        }
    }

	/**
     * Event handler to open a list of projects and display them to the user.
     */
	tot_projects(e) {
		e.stopPropagation();
		e.preventDefault();
		var options = {
			on_reverse_breadcrumb: this.on_reverse_breadcrumb,
		};
		if (this.flag == 0) {
			this.action.doAction({
				name: _t("Projects"),
				type: 'ir.actions.act_window',
				res_model: 'project.project',
				domain: [
					["id", "in", this.total_projects_ids]
				],
				view_mode: 'kanban,form',
				views: [
					[false, 'kanban'],
					[false, 'form']
				],
				target: 'current'
			}, options)
		} else {
			if (this.tot_project) {
				this.action.doAction({
					name: _t("Projects"),
					type: 'ir.actions.act_window',
					res_model: 'project.project',
					domain: [
						["id", "in", this.tot_project]
					],
					view_mode: 'kanban,form',
					views: [
						[false, 'kanban'],
						[false, 'form']
					],
					target: 'current'
				}, options)
			}
		}
	}
	/**
     * Event handler to open a list of tasks and display them to the user.
     */
	tot_tasks(e) {
		e.stopPropagation();
		e.preventDefault();
		var options = {
			on_reverse_breadcrumb: this.on_reverse_breadcrumb,
		};
		this.action.doAction({
			name: _t("Tasks"),
			type: 'ir.actions.act_window',
			res_model: 'project.task',
			domain: [
				["id", "in", this.tot_task]
			],
			view_mode: 'tree,kanban,form',
			views: [
				[false, 'list'],
				[false, 'form']
			],
			target: 'current'
		}, options)
	}

    show_tasks_by_tag(tag) {
        if (!tag) {
            console.error("Invalid tag provided");
            return;
        }

        try {
            console.log("Navigating to tasks for tag:", tag);

            let domain = [['tag_ids.name', 'ilike', tag],['project_id','!=',false]];

            if (this.selectedDepartment) {
                domain.push(['project_id.x_department', '=', parseInt(this.selectedDepartment)]);
            }

            if (this.project_template){
                domain.push(['project_id.x_template','=', this.project_template]);
            }

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

            let domain = [['user_ids.name', '=', employee],['project_id','!=',false]];
            if (this.selectedDepartment) {
                domain.push(['project_id.x_department', '=', parseInt(this.selectedDepartment)]);
            }

            if (this.project_template){
                domain.push(['project_id.x_template','=', this.project_template]);
            }

            this.action.doAction({
                name: _t(`Tasks for Employee: ${employee}`),
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: [['user_ids.name', '=', employee]], // Adjust the domain based on your employee field
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

    show_running_tasks(e) {
        e.stopPropagation();
        e.preventDefault();

        let domain = [['state', 'in', ['01_in_progress', '02_changes_requested', '03_approved']],['project_id','!=',false]];
        if (this.selectedDepartment) {
            domain.push(['project_id.x_department', '=', parseInt(this.selectedDepartment)]);
        }

        if (this.project_template){
            domain.push(['project_id.x_template','=', this.project_template]);
        }

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
            context: {
                'search_default_group_by_stage_id': 0,  // Disable stage grouping
                'search_default_group_by_project_id': 0, // Disable project grouping
                'group_by': [],
            },
            view_mode: 'list',  // Default to list view without grouping
            target: 'current',
            flags: {
                withBreadcrumbs: true,
                clearBreadcrumbs: true,
                noDefaultReload: true,
            },
        });
    }



    show_canceled_task(e) {
        e.stopPropagation();
        e.preventDefault();

        let domain = [['state', 'in', ['1_canceled']], ['project_id','!=',false]];
        if (this.selectedDepartment) {
            domain.push(['project_id.x_department', '=', parseInt(this.selectedDepartment)]);
        }

        if (this.project_template){
            domain.push(['project_id.x_template','=', this.project_template]);
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

        });
    }

    show_active_projects(e) {
        e.stopPropagation();
        e.preventDefault();

        let domain = [['stage_id.name', 'not in', ['Done','Canceled']]];
        if (this.selectedDepartment) {
            domain.push(['x_department', '=', parseInt(this.selectedDepartment)]);
        }

        if (this.project_template){
            domain.push(['x_template','=', this.project_template]);
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

        });
    }
    show_running_projects(e) {
        e.stopPropagation();
        e.preventDefault();

        let domain = [['stage_id.name', 'in', ['In Progress']]];
        if (this.selectedDepartment) {
            domain.push(['x_department', '=', parseInt(this.selectedDepartment)]);
        }

        if (this.project_template){
            domain.push(['x_template','=', this.project_template]);
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

        });
    }

    show_done_projects(e) {
        e.stopPropagation();
        e.preventDefault();

        let domain = [['stage_id.name', 'in', ['Done']]];
        if (this.selectedDepartment) {
            domain.push(['x_department', '=', parseInt(this.selectedDepartment)]);
        }

        if (this.project_template){
            domain.push(['x_template','=', this.project_template]);
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

        });
    }

    show_canceled_projects(e) {
        e.stopPropagation();
        e.preventDefault();

        let domain = [['stage_id.name', 'in', ['Canceled']]];
        if (this.selectedDepartment) {
            domain.push(['x_department', '=', parseInt(this.selectedDepartment)]);
        }

        if (this.project_template){
            domain.push(['x_template','=', this.project_template]);
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

        });
    }

    show_expired_projects(e) {
        e.stopPropagation();
        e.preventDefault();

        const today = new Date();
        const formattedDate = today.toLocaleDateString('en-US', {
            month: '2-digit',
            day: '2-digit',
            year: 'numeric'
        }).replace(/\//g, '-');

        let domain = [['date', '<', today], ['stage_id.name', '!=', 'Done']];
        if (this.selectedDepartment) {
            domain.push(['x_department', '=', parseInt(this.selectedDepartment)]);
        }

        if (this.project_template){
            domain.push(['x_template','=', this.project_template]);
        }
        this.action.doAction({
            name: _t("Expiring Project"),
            type: 'ir.actions.act_window',
            res_model: 'project.project',
            domain: domain,
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }

    show_done_task(e) {
        e.stopPropagation();
        e.preventDefault();

        let domain = [['state', '=', '1_done'],['project_id','!=', false]];
        if (this.selectedDepartment) {
            domain.push(['project_id.x_department', '=', parseInt(this.selectedDepartment)]);
        }

        if (this.project_template){
            domain.push(['project_id.x_template','=', this.project_template]);
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

        });
    }

    show_expired_yesterday(e) {
        e.stopPropagation();
        e.preventDefault();
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        const formattedDate = yesterday.toLocaleDateString('en-US', {
            month: '2-digit',
            day: '2-digit',
            year: 'numeric'
        }).replace(/\//g, '-');

        let domain = [['date', '=', yesterday]];
        if (this.selectedDepartment) {
            domain.push(['x_department', '=', parseInt(this.selectedDepartment)]);
        }

        if (this.project_template){
            domain.push(['x_template','=', this.project_template]);
        }
        this.action.doAction({
            name: _t("Project Expired Yesterday"),
            type: 'ir.actions.act_window',
            res_model: 'project.project',
            domain: domain,
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }

     show_will_expire_tomorrow(e) {
        e.stopPropagation();
        e.preventDefault();
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const formattedDate = tomorrow.toLocaleDateString('en-US', {
            month: '2-digit',
            day: '2-digit',
            year: 'numeric'
        }).replace(/\//g, '-');

        let domain = [['date', '=', tomorrow]];
        if (this.selectedDepartment) {
            domain.push(['x_department', '=', parseInt(this.selectedDepartment)]);
        }
        if (this.project_template){
            domain.push(['x_template','=', this.project_template]);
        }
        this.action.doAction({
            name: _t("Project Expiring Tomorrow"),
            type: 'ir.actions.act_window',
            res_model: 'project.project',
            domain: domain,
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }

    show_expired_today(e) {
        e.stopPropagation();
        e.preventDefault();
        const today = new Date();
        const formattedDate = today.toLocaleDateString('en-US', {
            month: '2-digit',
            day: '2-digit',
            year: 'numeric'
        }).replace(/\//g, '-');

        let domain = [['date', '=', today]];
        if (this.selectedDepartment) {
            domain.push(['x_department', '=', parseInt(this.selectedDepartment)]);
        }

        if (this.project_template){
            domain.push(['x_template','=', this.project_template]);
        }
        this.action.doAction({
            name: _t("Project Expiring Today"),
            type: 'ir.actions.act_window',
            res_model: 'project.project',
            domain: domain,
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    }
}

ProjectDashboard.template = "ProjectDashboard"
registry.category("actions").add("project_dashboard", ProjectDashboard)
