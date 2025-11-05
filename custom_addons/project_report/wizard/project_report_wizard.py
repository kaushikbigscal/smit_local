from odoo import models, fields, api

class ProjectTimesheetReportWizard(models.TransientModel):
    _name = 'project.timesheet.report.wizard'
    _description = 'Wizard for Project Timesheet Report'

    x_template = fields.Selection(
        selection='_get_used_templates',
        string="Template"
    )
    customer_ids = fields.Many2many('res.partner', string="Customers",domain="[('is_company', '=', True), ('parent_id', '=', False)]")
    project_ids = fields.Many2many('project.project', string="Projects")
    department_ids = fields.Many2many('hr.department', string="Departments")
    date_from = fields.Date("Start Date")
    date_to = fields.Date("End Date")
    available_project_ids = fields.Many2many('project.project', compute="_compute_available_projects")

    def _get_used_templates(self):
        templates = self.env['project.project'].search_read(
            [('x_template', '!=', False) ,('is_fsm', '=', False)],
            ['x_template']
        )
        unique_templates = sorted(set(t['x_template'] for t in templates if t['x_template']))
        return [(t, t) for t in unique_templates]

    @api.depends('x_template')
    def _compute_available_projects(self):
        """Compute the available projects based on the selected template"""
        for record in self:
            domain = [('is_fsm', '=', False)]
            if record.x_template:
                domain = [('x_template', '=', record.x_template)]
            record.available_project_ids = self.env['project.project'].search(domain)

    @api.onchange('x_template')
    def _onchange_x_template(self):
        """Clear project selections when template changes"""
        # When template changes, clear project selections to avoid keeping invalid selections
        if self.x_template:
            # Keep only projects matching the template
            valid_projects = self.env['project.project'].search([
                ('id', 'in', self.project_ids.ids),
                ('x_template', '=', self.x_template),
                ('is_fsm', '=', False)
            ])
            self.project_ids = valid_projects
        else:
            # Optional: you can choose to clear all selections when template is removed
            # or keep the current selections (comment this line if you want to keep them)
            self.project_ids = [(5, 0, 0)]  # Clear all selections

# projects those are done and have not compulsory timesheets
    def action_generate_report(self):
        self.env['project.report.line'].search([]).unlink()

        # Get completed projects
        project_domain = [('is_fsm', '=', False), ('stage_id.name', '=', 'Done')]

        if self.x_template:
            project_domain += [('x_template', '=', self.x_template)]

        if self.customer_ids:
            project_domain += [('partner_id', 'in', self.customer_ids.ids)]

        if self.project_ids:
            project_domain += [('id', 'in', self.project_ids.ids)]

        if self.department_ids:
            project_domain += [('x_department', 'in', self.department_ids.ids)]

        projects = self.env['project.project'].search(project_domain)

        report_lines = []

        for project in projects:
            task_domain = [('project_id', '=', project.id)]
            tasks = self.env['project.task'].search(task_domain)

            for task in tasks:
                timesheet_domain = [('task_id', '=', task.id)]

                timesheets = self.env['account.analytic.line'].search(timesheet_domain)

                if timesheets:
                    for line in timesheets:
                        report_lines.append((0, 0, {
                            'project_id': line.project_id.id,
                            'task_id': line.task_id.id,
                            'employee_id': line.employee_id.id,
                            'start_time': line.date_time,
                            'end_time': line.end_date_time,
                            'hours_taken': line.unit_amount,
                        }))
                # Optional: include tasks without timesheets
                # else:
                #     report_lines.append((0, 0, {
                #         'project_id': project.id,
                #         'task_id': task.id,
                #         'hours_taken': 0.0,
                #     }))

        self.env['project.report.line'].create([line[2] for line in report_lines])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Project Timesheet Report',
            'res_model': 'project.report.line',
            'view_mode': 'tree',
            'context': {'group_by': ['project_id', 'task_id']},
            'target': 'current',
        }

