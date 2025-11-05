from datetime import timedelta

from odoo import api, models, exceptions, fields, _


class ProjectTask(models.Model):
    _name = "project.task"
    _inherit = ["project.task", "hr.timesheet.time_control.mixin"]

    date_time = fields.Datetime(string="Start Date-Time", required=True, default=fields.Datetime.now)
    end_date_time = fields.Datetime(string="End Date-Time", compute="_compute_end_date_time",
                                    inverse="_inverse_end_date_time")
    unit_amount = fields.Float(string="Duration (Hours)", required=True, default=0.0, store=True,
                               compute="_compute_unit_amount")

    @api.depends("date_time", "end_date_time")
    def _compute_unit_amount(self):
        for record in self:
            if record.date_time and record.end_date_time:
                duration = (record.end_date_time - record.date_time).total_seconds() / 3600.0
                record.unit_amount = round(duration, 2)
            else:
                record.unit_amount = 0.0

    @api.depends("date_time", "unit_amount")
    def _compute_end_date_time(self):
        """Compute End Date-Time based on Start Date-Time and Duration."""
        for record in self:
            if record.date_time and record.unit_amount:
                record.end_date_time = record.date_time + timedelta(hours=record.unit_amount)
            else:
                record.end_date_time = False

    def _inverse_end_date_time(self):
        """Recalculate unit_amount when End Date-Time is manually changed."""
        for record in self:
            if record.date_time and record.end_date_time:
                duration = (record.end_date_time - record.date_time).total_seconds() / 3600
                record.unit_amount = duration

    @api.model
    def _relation_with_timesheet_line(self):
        return "task_id"

    @api.depends(
        "project_id.allow_timesheets",
        "timesheet_ids.employee_id",
        "timesheet_ids.unit_amount",
    )
    def _compute_show_time_control(self):
        result = super()._compute_show_time_control()
        for task in self:
            # Never show button if timesheets are not allowed in project
            if not task.project_id.allow_timesheets:
                task.show_time_control = False
        return result

    def button_start_work(self):
        if not self.user_ids:
            raise exceptions.UserError(_("Please select an assignee before starting work."))
        result = super().button_start_work()
        result["context"].update({"default_project_id": self.project_id.id})
        return result

    def action_start_work(self):
        for task in self:
            self.env['account.analytic.line'].create({
                'name': 'Work started on: %s' % task.name,
                'task_id': task.id,
                'project_id': task.project_id.id,
                'user_id': self.env.uid,
                'date': fields.Date.today(),
                'unit_amount': 0.0,
                'employee_id': self.env.user.employee_id.id,
            })
        return True

    def action_stop_work(self):
        for task in self:
            analytic_line = self.env['account.analytic.line'].search([
                ('task_id', '=', task.id),
                ('user_id', '=', self.env.uid),
                ('date', '=', fields.Date.today()),
                ('unit_amount', '<=', 0.01),
            ], limit=1)

            if analytic_line:
                start_time = task.date_time or fields.Datetime.now()
                end_time = fields.Datetime.now()
                duration = (end_time - start_time).total_seconds() / 3600.0
                duration = round(duration, 2)

                analytic_line.write({
                    'name': analytic_line.name + ' | Work stopped',
                    'unit_amount': duration,
                    'end_date_time': end_time
                })
                task.end_date_time = end_time
            else:
                print(f"[DEBUG] No matching analytic line found for task {task.name}")
            return True
