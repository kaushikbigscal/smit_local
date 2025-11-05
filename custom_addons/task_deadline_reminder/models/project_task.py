from datetime import timedelta, datetime

from odoo import models, api, fields


class Task(models.Model):
    _inherit = "project.task"

    set_reminder = fields.Boolean(string="Reminder")

    names = fields.Char(string='Reminder Label')
    reminder_type_ids = fields.Many2many(
        'reminder.types',
        'task_reminder_type_rel',
        'task_id',
        'reminder_type_id',
        string="Reminder Types"
    )

    custom_reminder_datetime = fields.Datetime(string="Custom Reminder Time")
    is_custom_selected = fields.Boolean(compute='_compute_is_custom_selected')

    @api.depends('reminder_type_ids')
    def _compute_is_custom_selected(self):
        for task in self:
            task.is_custom_selected = any(
                rt.name.lower() == 'custom' for rt in task.reminder_type_ids
            )

    @api.onchange('reminder_type_ids')
    def _onchange_reminder_type_ids(self):
        for record in self:
            if not any(rt.name.lower() == 'custom' for rt in record.reminder_type_ids):
                record.custom_reminder_datetime = False

    @api.onchange('set_reminder')
    def _onchange_set_reminder(self):
        """Clear reminder_type_ids when set_reminder is disabled"""
        if not self.set_reminder:
            self.reminder_type_ids = [(5, 0, 0)]  # Clear all records

    @api.model
    def create(self, vals):
        task = super().create(vals)
        task._generate_reminder_queue()
        return task

    def write(self, vals):
        result = super().write(vals)
        if any(key in vals for key in
               ['set_reminder', 'reminder_type_ids', 'date_deadline', 'custom_reminder_datetime']):
            # Only regenerate if task is not in closed state
            for task in self:
                if not self._is_task_completed(task):
                    self._generate_reminder_queue()

        """Override write method to clear reminder_type_ids when set_reminder is disabled"""
        if 'set_reminder' in vals and not vals['set_reminder']:
            vals['reminder_type_ids'] = [(5, 0, 0)]  # Clear all records

        # Check if state changed to closed states - delete reminders
        if 'state' in vals:
            CLOSED_STATES = ['1_done', '1_canceled']
            if vals['state'] in CLOSED_STATES:
                self._delete_task_reminders()
        return result

    def _is_task_completed(self, task):
        """Check if task is in completed state"""
        CLOSED_STATES = ['1_done', '1_canceled']
        # Check state field
        if hasattr(task, 'state') and task.state in CLOSED_STATES:
            return True
        return False

    def _delete_task_reminders(self):
        """Delete all reminders for this task from queue and task.reminder"""
        for task in self:
            # Delete from reminder queue
            queue_reminders = self.env['reminder.task.queue'].search([('task_id', '=', task.id)])
            if queue_reminders:
                queue_reminders.unlink()

    def _generate_reminder_queue(self):
        for task in self:
            # Remove old reminders
            self.env['reminder.task.queue'].search([('task_id', '=', task.id)]).unlink()

            if not (task.set_reminder and task.date_deadline and task.reminder_type_ids):
                continue

            for rt in task.reminder_type_ids:
                # Handle custom reminders
                if rt.name.lower() == 'custom' and task.custom_reminder_datetime:
                    reminder_dt = task.custom_reminder_datetime
                else:
                    if rt.reminder_minutes is None:
                        continue  # Skip if no minute value
                    reminder_dt = task.date_deadline - timedelta(minutes=rt.reminder_minutes)

                # Store in queue
                self.env['reminder.task.queue'].create({
                    'task_id': task.id,
                    'user_id': task.user_ids and task.user_ids[0].id or None,
                    'reminder_datetime': reminder_dt,
                })
