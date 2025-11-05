from datetime import timedelta
from odoo import models, fields, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    allocated_days_template = fields.Integer(string='Task Duration', help="Enter the Task Duration in Days")
    is_project_template = fields.Boolean(
        related='project_id.is_project_template',
        store=False
    )
    date_deadline = fields.Datetime(
        string='Deadline',
        compute='_compute_date_deadline',
        store=True,
        readonly=False
    )

    @api.depends('project_id.date_start', 'allocated_days_template')
    def _compute_date_deadline(self):
        for task in self:
            if not task.is_fsm:
                if task.state and task.state == '1_done':
                    # Do not change deadline if task is in Done state
                    continue
                start_date = task.project_id.date_start
                days = task.allocated_days_template or 0
                if start_date and days > 0:
                    task.date_deadline = start_date + timedelta(days=days)
                else:
                    task.date_deadline = False

    @api.onchange('allocated_days_template')
    def _onchange_allocated_days_template(self):
        self._compute_date_deadline()

    def _update_project_end_date(self):
        projects = self.mapped('project_id').filtered(lambda p: p.date_start)
        for project in projects:
            last_task = self.env['project.task'].search([
                ('project_id', '=', project.id)
            ], order='sequence desc', limit=1)

            if last_task and last_task.allocated_days_template > 0:
                project.date = project.date_start + timedelta(days=last_task.allocated_days_template)
            else:
                project.date = project.date_start

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('import_file') and any(
                field in vals for field in ['sequence', 'allocated_days_template', 'project_id']):
            self._update_project_end_date()
        return res

    @api.model
    def create(self, vals):
        task = super().create(vals)
        if not self.env.context.get('import_file'):
            task._update_project_end_date()
        return task
