from odoo import api, models, fields


class ProjectProject(models.Model):
    _name = "project.project"
    _inherit = ["project.project", "hr.timesheet.time_control.mixin"]

    date_time = fields.Datetime(string="Start Time")
    end_date_time = fields.Datetime(string="End Time")

    @api.model
    def _relation_with_timesheet_line(self):
        return "project_id"

    @api.depends("allow_timesheets")
    def _compute_show_time_control(self):
        result = super()._compute_show_time_control()
        for project in self:
            # Never show button if timesheets are not allowed in project
            if not project.allow_timesheets:
                project.show_time_control = False
        return result

    def button_start_work(self):
        result = super().button_start_work()
        # When triggering from project is usually to start timer without task
        result["context"].update({"default_task_id": False})
        return result

    def action_start_work(self):
        for project in self:
            self.env['account.analytic.line'].create({
                'name': 'Work started on: %s' % project.name,
                'project_id': project.id,
                'user_id': self.env.uid,
                'date': fields.Date.today(),
                'unit_amount': 0.0,
                'employee_id': self.env.user.employee_id.id,
            })
        return True

    def action_stop_work(self):
        for project in self:
            analytic_line = self.env['account.analytic.line'].search([
                ('project_id', '=', project.id),
                ('task_id', '=', False),  # Make sure it's not a task analytic line
                ('user_id', '=', self.env.uid),
                ('date', '=', fields.Date.today()),
                ('unit_amount', '<=', 0.01),
            ], limit=1)

            if analytic_line:
                start_time = project.date_time or fields.Datetime.now()
                end_time = fields.Datetime.now()
                duration = (end_time - start_time).total_seconds() / 3600.0
                duration = round(duration, 2)

                analytic_line.write({
                    'name': analytic_line.name + ' | Work stopped',
                    'unit_amount': duration,
                    'end_date_time': end_time
                })
                project.end_date_time = end_time
            else:
                print(f"[DEBUG] No matching analytic line found for project {project.name}")
        return True
