from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    reminder_day_in_offset_minutes = fields.Integer(
        string="Day In Reminder Offset (in minutes)",
        config_parameter='reminder.day_in_offset_minutes'
    )
    reminder_day_out_offset_minutes = fields.Integer(
        string="Day Out Reminder Offset (in minutes)",
        config_parameter='reminder.day_out_offset_minutes'
    )
    enable_overdue_reminder = fields.Boolean(string="Overdue Task Reminders")
    overdue_reminder_times = fields.Char(
        string="Reminder Times (24h format, comma-separated)",
        help="Example: 09:00,13:30,18:45",
        config_parameter='overdue_task_reminder.times'
    )
    amc_contract_reminder_days = fields.Integer(
        string="AMC Contract Days Limit",
        config_parameter='reminder.amc_days_limit'
    )

    @api.onchange('enable_overdue_reminder')
    def _onchange_enable_overdue_reminder(self):
        if not self.enable_overdue_reminder:
            self.overdue_reminder_times = False

    @api.model
    def set_values(self):
        super().set_values()
        config = self.env['ir.config_parameter'].sudo()
        config.set_param('task_deadline_reminder.reminder_day_in_offset_minutes',
                         str(self.reminder_day_in_offset_minutes))
        config.set_param('task_deadline_reminder.reminder_day_out_offset_minutes',
                         str(self.reminder_day_out_offset_minutes))
        config.set_param('task_deadline_reminder.enable_overdue_reminder', str(bool(self.enable_overdue_reminder)))
        config.set_param('task_deadline_reminder.overdue_reminder_times', self.overdue_reminder_times or '')

    @api.model
    def get_values(self):
        res = super().get_values()
        config = self.env['ir.config_parameter'].sudo()
        res.update({
            'reminder_day_in_offset_minutes': int(
                config.get_param('task_deadline_reminder.reminder_day_in_offset_minutes', '0')),
            'reminder_day_out_offset_minutes': int(
                config.get_param('task_deadline_reminder.reminder_day_out_offset_minutes', '0')),
            'enable_overdue_reminder': config.get_param('task_deadline_reminder.enable_overdue_reminder',
                                                        'False') == 'True',
            'overdue_reminder_times': config.get_param('task_deadline_reminder.overdue_reminder_times', ''),
        })
        return res
