import datetime

from odoo import models, fields, api


class ReminderTaskQueue(models.Model):
    _name = 'reminder.task.queue'
    _description = 'Queued Task for Reminder'

    task_id = fields.Many2one('project.task', ondelete='cascade')
    user_id = fields.Many2one('res.users', string="User")
    activity_id = fields.Many2one('mail.activity', string="Activity")
    reminder_datetime = fields.Datetime(
        string="Reminder Datetime")
    datetime_combined = fields.Datetime("Combined Datetime", store=True)






