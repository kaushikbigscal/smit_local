from datetime import datetime, timedelta, time

import pytz

from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    day_in_reminder_enabled = fields.Boolean(
        string="Enable Day In Reminder",
        help="Use working schedule for day-based reminders")
    day_out_reminder_enabled = fields.Boolean(string="Enable Day Out Reminder")
    auto_day_out = fields.Boolean(string="Auto Day Out")

    @api.model
    def generate_day_in_out_reminders(self):
        now_utc = fields.Datetime.now()
        today = fields.Date.today()
        weekday = str(today.weekday())

        config = self.env['ir.config_parameter'].sudo()
        day_in_offset = int(config.get_param('reminder.day_in_offset_minutes', '0'))
        day_out_offset = int(config.get_param('reminder.day_out_offset_minutes', '0'))

        company = self.env.company
        users = self.search([('resource_calendar_id', '!=', False)])

        for user in users:
            user_tz = user.tz or 'UTC'
            timezone = pytz.timezone(user_tz)
            now_local = pytz.utc.localize(now_utc).astimezone(timezone)

            #  Day In Reminder
            if company.day_in_reminder_enabled and user.day_in_reminder_enabled:
                attendances = self.env['resource.calendar.attendance'].search([
                    ('calendar_id', '=', user.resource_calendar_id.id),
                    ('dayofweek', '=', weekday),
                    ('hour_from', '!=', False),
                ])

                if attendances:
                    earliest = min(att.hour_from for att in attendances)
                    hour, minute = int(earliest), int((earliest - int(earliest)) * 60)
                    reminder_time = datetime.combine(today, time(hour, minute)) + timedelta(minutes=day_in_offset)
                    reminder_time_local = timezone.localize(reminder_time)

                    if now_local.replace(second=0, microsecond=0) == reminder_time_local.replace(second=0,
                                                                                                 microsecond=0):
                        user._send_attendance_reminder("Day In Reminder", "start", reminder_time, earliest,
                                                       max(att.hour_to for att in attendances))

            # Day Out Reminder
            if company.day_out_reminder_enabled and user.day_out_reminder_enabled:
                attendances = self.env['resource.calendar.attendance'].search([
                    ('calendar_id', '=', user.resource_calendar_id.id),
                    ('dayofweek', '=', weekday),
                    ('hour_to', '!=', False),
                ])

                if attendances:
                    latest = max(att.hour_to for att in attendances)
                    hour, minute = int(latest), int((latest - int(latest)) * 60)
                    reminder_time = datetime.combine(today, time(hour, minute)) + timedelta(minutes=day_out_offset)
                    reminder_time_local = timezone.localize(reminder_time)

                    if now_local.replace(second=0, microsecond=0) == reminder_time_local.replace(second=0,
                                                                                                 microsecond=0):
                        user._send_attendance_reminder("Day Out Reminder", "end", reminder_time,
                                                       min(att.hour_from for att in attendances), latest)

    def _send_attendance_reminder(self, title, type_str, reminder_time, hour_from, hour_to):
        # Get company's language record and fetch format fields
        company_lang_code = self.env.company.partner_id.lang or 'en_US'
        lang_record = self.env['res.lang'].search([('code', '=', company_lang_code)], limit=1)

        # Fetch language format fields
        time_format = lang_record.time_format if lang_record else '%H:%M:%S'
        date_format = lang_record.date_format if lang_record else '%d/%m/%Y'

        # Function to format time using fetched time_format
        def format_time_with_lang_format(hour_float):
            hours = int(hour_float)
            minutes = int(round((hour_float - hours) * 60))
            time_obj = datetime.combine(fields.Date.today(), time(hours, minutes))
            return time_obj.strftime(time_format)

        # Format start and end times using company's time format
        start_time_str = format_time_with_lang_format(hour_from)

        if hour_to is not None:
            end_time_str = format_time_with_lang_format(hour_to)
            time_str = f"{start_time_str} to {end_time_str}"
        else:
            time_str = start_time_str

        today_formatted = fields.Date.today().strftime(date_format)

        # Customize message based on reminder type
        if type_str == "start":
            msg = f"Reminder: Your workday is scheduled to start at {time_str} on {today_formatted}."
        else:  # type_str == "end"
            msg = f"Reminder: Your workday is scheduled to end at {time_str} on {today_formatted}."

        Reminder = self.env['task.reminder']
        today = fields.Date.today()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        existing = Reminder.search([
            ('name', '=', title),
            ('related_model', '=', 'res.users'),
            ('related_id', '=', self.id),
            ('create_date', '>=', start_of_day),
            ('create_date', '<=', end_of_day),
        ], limit=1)

        if existing:
            return

        if self.partner_id:
            self.partner_id.message_notify(
                subject=title,
                body=msg,
                partner_ids=[self.partner_id.id],
                subtype_xmlid='mail.mt_note'
            )

            # Convert reminder_time to UTC for storage
            user_tz = self.tz or 'UTC'
            user_timezone = pytz.timezone(user_tz)

            # If reminder_time is naive (no timezone), localize it to user's timezone first
            if reminder_time.tzinfo is None:
                reminder_time_local = user_timezone.localize(reminder_time)
            else:
                reminder_time_local = reminder_time.astimezone(user_timezone)

            # Convert to UTC for storage in Odoo
            reminder_time_utc = reminder_time_local.astimezone(pytz.UTC)

            # Remove timezone info for Odoo datetime field (Odoo expects naive UTC datetime)
            reminder_time_naive_utc = reminder_time_utc.replace(tzinfo=None)

            reminder_vals = {
                'name': title,
                'author_id': self.env.user.id,
                'related_model': 'res.users',
                'related_id': self.id,
                'body': msg,
                'deadline': reminder_time_naive_utc,
                'user_ids': [(6, 0, [self.id])],
            }
            self.env['task.reminder'].create(reminder_vals)
