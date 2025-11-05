from odoo import models, fields

class ProjectReportLine(models.TransientModel):
    _name = 'project.report.line'
    _description = 'Project Report Line'

    project_id = fields.Many2one('project.project', string="Project")
    task_id = fields.Many2one('project.task', string="Task")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    start_time = fields.Datetime("Start Time")
    end_time = fields.Datetime("End Time")
    hours_taken = fields.Float("Hours Taken")

    # group by and filter

    date_start = fields.Date(
        string='Start Date',
        related='project_id.date_start',
        store=True,
        tracking=True
    )

    date = fields.Date(
        string='End Date',
        related='project_id.date',
        store=True,
        tracking=True
    )
    customer_id = fields.Many2one('res.partner', string="Customer", related='project_id.partner_id', store=True)
    template = fields.Char(string="Template", related='project_id.x_template', store=True)
    department_id = fields.Many2one('hr.department', string="Department", related='project_id.x_department', store=True)
    stage_id = fields.Many2one(
        'project.project.stage',
        string='Stage',
        related='project_id.stage_id',
        store=True,
    )
    user_id = fields.Many2one('res.users', string='Project Manager', related='project_id.user_id', store=True)

    def open_filter_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate Timesheet Report',
            'res_model': 'project.timesheet.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }