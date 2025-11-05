from datetime import datetime, timedelta, date, time
import pytz
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.populate import compute


class MailActivitySchedule(models.TransientModel):
    _inherit = 'mail.activity.schedule'

    set_reminder = fields.Boolean(string="Reminder")
    reminder_type_ids = fields.Many2many(
        'reminder.types', 'activity_schedule_reminder_type_rel', 'schedule_id', 'reminder_type_id',
        string="Reminder Types"
    )
    custom_reminder_datetime = fields.Datetime(string="Custom Reminder Time")
    is_custom_selected = fields.Boolean(compute='_compute_is_custom_selected')
    char_time = fields.Char("Time (HH:MM)")
    datetime_combined = fields.Datetime("Combined Datetime", compute="_compute_datetime_combined", store=True)
    name = fields.Char(string="Reminder Types")

    # is_meeting_type = fields.Boolean(string="Is Meeting Type", compute="_compute_is_meeting_type")
    #
    # @api.depends('activity_type_id')
    # def _compute_is_meeting_type(self):
    #     for rec in self:
    #         rec.is_meeting_type = rec.activity_type_id.name == "Meeting"

    @api.depends('char_time', 'date_deadline')
    def _compute_datetime_combined(self):
        for rec in self:
            if rec.char_time and rec.date_deadline:
                try:
                    # Convert char to time object
                    time_obj = datetime.strptime(rec.char_time, '%H:%M').time()
                    # Combine with date
                    rec.datetime_combined = datetime.combine(rec.date_deadline, time_obj)
                except ValueError:
                    rec.datetime_combined = False
            else:
                rec.datetime_combined = False

    def _action_schedule_activities(self):
        return self._get_applied_on_records().activity_schedule(
            set_reminder=self.set_reminder,
            reminder_type_ids=self.reminder_type_ids,
            date_deadline=self.date_deadline,
            char_time=self.char_time,
            is_custom_selected=self.is_custom_selected,
            custom_reminder_datetime=self.custom_reminder_datetime,
            activity_type_id=self.activity_type_id.id,
            summary=self.summary,
            automated=False,
            note=self.note,
            user_id=self.activity_user_id.id,
            name=self.name,
        )

    @api.depends('reminder_type_ids')
    def _compute_is_custom_selected(self):
        for schedule in self:
            schedule.is_custom_selected = any(
                rt.name.lower() == 'custom' for rt in schedule.reminder_type_ids
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

    def write(self, vals):
        """Override write method to clear reminder_type_ids when set_reminder is disabled"""
        if 'set_reminder' in vals and not vals['set_reminder']:
            vals['reminder_type_ids'] = [(5, 0, 0)]  # Clear all records
        return super(MailActivitySchedule, self).write(vals)


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    set_reminder = fields.Boolean(string="Reminder")
    reminder_type_ids = fields.Many2many(
        'reminder.types', 'activity_reminder_type_rel', 'activity_id', 'reminder_type_id',
        string="Reminder Types")
    custom_reminder_datetime = fields.Datetime(string="Custom Reminder Time")
    is_custom_selected = fields.Boolean(compute="_compute_is_custom_selected")
    user_id = fields.Many2one('res.users', string='Activity User')
    char_time = fields.Char("Time (HH:MM)")
    datetime_combined = fields.Datetime("Combined Datetime", compute="_compute_datetime_combined", store=True)
    name = fields.Char(string="Reminder Types")

    # is_meeting_type = fields.Boolean(string="Is Meeting Type", compute="_compute_is_meeting_type")
    #
    # @api.depends('activity_type_id')
    # def _compute_is_meeting_type(self):
    #     for rec in self:
    #         rec.is_meeting_type = rec.activity_type_id.name == "Meeting"

    def unlink(self):
        queue_model = self.env['reminder.task.queue']
        for activity in self:
            queue_model.search([
                ('activity_id', '=', activity.id)
            ]).unlink()
        return super(MailActivity, self).unlink()

    def action_done(self):
        res = super().action_done()
        self.env['reminder.task.queue'].search([
            ('activity_id', 'in', self.ids)
        ]).unlink()
        return res

    @api.depends('char_time', 'date_deadline')
    def _compute_datetime_combined(self):
        for rec in self:
            if rec.char_time and rec.date_deadline:
                try:
                    time_obj = datetime.strptime(rec.char_time, '%H:%M').time()
                    # Create naive datetime
                    naive_dt = datetime.combine(rec.date_deadline, time_obj)

                    # Get user's timezone
                    user_tz = pytz.timezone(rec.user_id.tz or self.env.user.tz or 'UTC')

                    # Localize to user's timezone, then convert to UTC
                    local_dt = user_tz.localize(naive_dt)
                    rec.datetime_combined = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
                except ValueError:
                    rec.datetime_combined = False
            else:
                rec.datetime_combined = False

    @api.depends('reminder_type_ids')
    def _compute_is_custom_selected(self):
        for activity in self:
            activity.is_custom_selected = any(
                rt.name.lower() == 'custom' for rt in activity.reminder_type_ids
            )

    @api.onchange('reminder_type_ids')
    def _onchange_reminder_type_ids(self):
        for record in self:
            if not any(rt.name.lower() == 'custom' for rt in record.reminder_type_ids):
                record.custom_reminder_datetime = False

    @api.constrains('char_time')
    def _check_char_time_format(self):
        for rec in self:
            if rec.char_time:
                try:
                    datetime.strptime(rec.char_time, '%H:%M')
                except ValueError:
                    raise ValidationError("Time must be in HH:MM format only (e.g., 09:30).")

    @api.model
    def create(self, vals):
        activity = super().create(vals)
        activity._generate_reminder_queue()
        return activity

    def write(self, vals):
        result = super().write(vals)
        if any(key in vals for key in
               ['set_reminder', 'reminder_type_ids', 'char_time', 'date_deadline', 'datetime_combined',
                'custom_reminder_datetime']):
            self._generate_reminder_queue()
        return result

    def _generate_reminder_queue(self):
        queue_model = self.env['reminder.task.queue']
        for activity in self:
            # Delete old reminders
            queue_model.search([('activity_id', '=', activity.id)]).unlink()

            # Skip invalid cases
            if not (activity.set_reminder and activity.date_deadline and activity.reminder_type_ids):
                continue

            for rt in activity.reminder_type_ids:
                # Handle custom
                if rt.name.lower() == 'custom' and activity.custom_reminder_datetime:
                    reminder_dt = activity.custom_reminder_datetime
                else:
                    if rt.reminder_minutes is None or not activity.char_time:
                        continue
                    try:
                        time_obj = datetime.strptime(activity.char_time, '%H:%M').time()
                    except ValueError:
                        continue

                    # Create naive datetime
                    naive_dt = datetime.combine(activity.date_deadline, time_obj)

                    # Get user's timezone and convert properly
                    user_tz = pytz.timezone(activity.user_id.tz or self.env.user.tz or 'UTC')
                    local_dt = user_tz.localize(naive_dt)
                    deadline_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)

                    reminder_dt = deadline_dt - timedelta(minutes=rt.reminder_minutes)

                # Create queue entry
                self.env['reminder.task.queue'].create({
                    'activity_id': activity.id,
                    'task_id': activity.res_model == 'project.task' and activity.res_id or False,
                    'user_id': activity.user_id.id,
                    'reminder_datetime': reminder_dt,
                })
