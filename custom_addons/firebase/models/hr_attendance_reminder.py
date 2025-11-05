from datetime import timedelta

from odoo import fields, api, models


class HrAttendanceReminder(models.Model):
    _inherit = 'hr.employee'

    def send_checkin_reminder(self):
        """
        Send check-in reminders to employees who haven't checked in
        30 minutes after their standard starting time.
        """
        config = self.env['ir.config_parameter'].sudo()
        allow_reminder = config.get_param('hr_attendance.allow_notification_reminder_attendance')
        reminder_time_limit = config.get_param('hr_attendance.attendance_reminder_time_limit', '00:30')

        if not allow_reminder:
            return

        try:
            reminder_hours, reminder_minutes = map(int, reminder_time_limit.split(':'))
        except ValueError:
            return

        # Get current date and time
        current_datetime = fields.Datetime.now()
        current_date = fields.Date.today()

        # Find employees with active contracts
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('contract_id', '!=', False)
        ])

        for employee in employees:
            # Skip if no user or no contract
            if not employee.user_id or not employee.contract_id:
                continue

            leave_check = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', current_date),
                ('date_to', '>=', current_date)
            ])

            if leave_check:
                continue

            # Get today's weekday (0=Monday, 6=Sunday)
            weekday = str(current_date.weekday())

            # Get the standard start time for today
            attendance = employee.contract_id.resource_calendar_id.attendance_ids.filtered(
                lambda a: a.dayofweek == weekday)
            if attendance:
                standard_start_time = attendance[0].hour_from
            else:
                # Skip if no attendance is defined for today
                continue
                # Convert float time to timedelta
            start_hours = int(standard_start_time)  # Get hours (e.g., 10)
            start_minutes = int((standard_start_time - start_hours) * 60)  # Get minutes (e.g., 30 for 10.5)

            expected_checkin_datetime = fields.Datetime.from_string(
                f"{current_date} {start_hours:02}:{start_minutes:02}:00"
            ) + timedelta(hours=reminder_hours, minutes=reminder_minutes)
            print(current_datetime)
            print(expected_checkin_datetime)
            # Check if current time is past expected check-in time
            if current_datetime >= expected_checkin_datetime:
                # Check if already checked in today
                attendance_record = self.env['hr.attendance'].search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', fields.Datetime.to_string(current_date)),
                    ('check_out', '=', False)
                ], limit=1)

                # If no check-in, send a reminder
                if not attendance_record:
                    existing_reminder = self.env['mail.message'].search([
                        ('model', '=', 'hr.attendance'),
                        ('res_id', '=', employee.id),
                        ('message_type', '=', 'notification'),
                        ('subject', '=', 'Check-in Reminder'),
                        ('date', '>=', fields.Datetime.to_string(current_date))
                    ], limit=1)

                    if existing_reminder:
                        continue
                    payload = {
                        'model': 'hr.attendance',
                        'action': 'check_in_reminder'
                    }

                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=employee.user_id.id,
                        title='Check-in Reminder',
                        body=f'You haven\'t checked in yet. Please check in for {current_date}.',
                        payload=payload
                    )

                    self.env['mail.message'].create({
                        'model': 'hr.attendance',
                        'res_id': employee.id,
                        'message_type': 'notification',
                        'subject': 'Check-in Reminder',
                        'body': f'Check-in reminder sent to {employee.name} for {current_date}.'
                    })

    def send_checkout_reminder(self):
        """
        Send check-out reminders to employees who haven't checked out
        a certain time before their standard ending time.
        """
        config = self.env['ir.config_parameter'].sudo()
        allow_reminder = config.get_param('hr_attendance.allow_notification_reminder_attendance')
        reminder_time_limit = config.get_param('hr_attendance.attendance_checkout_reminder_time_limit',
                                               '00:15')  # Default 15 minutes before shift end

        if not allow_reminder:
            return

        try:
            reminder_hours, reminder_minutes = map(int, reminder_time_limit.split(':'))
        except ValueError:
            return

        # Get current date and time
        current_datetime = fields.Datetime.now()
        current_date = fields.Date.today()

        # Find employees with active contracts
        employees = self.env['hr.employee'].search([
            ('active', '=', True),
            ('contract_id', '!=', False)
        ])

        for employee in employees:
            # Skip if no user or no contract
            if not employee.user_id or not employee.contract_id:
                continue

            leave_check = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', current_date),
                ('date_to', '>=', current_date)
            ])

            if leave_check:
                continue
            # Get today's weekday (0=Monday, 6=Sunday)
            weekday = str(current_date.weekday())

            # Get the standard end time for today
            attendance = employee.contract_id.resource_calendar_id.attendance_ids.filtered(
                lambda a: a.dayofweek == weekday)
            if attendance:
                standard_end_time = attendance[0].hour_to  # Ending hour of the shift
            else:
                continue  # Skip if no attendance rule is set for today

            # Convert float time to timedelta
            end_hours = int(standard_end_time)  # Get hours (e.g., 18)
            end_minutes = int((standard_end_time - end_hours) * 60)  # Get minutes (e.g., 30 for 18.5)

            expected_checkout_datetime = fields.Datetime.from_string(
                f"{current_date} {end_hours:02}:{end_minutes:02}:00"
            ) - timedelta(hours=reminder_hours, minutes=reminder_minutes)  # Reminder before shift end
            print(current_date)
            print(expected_checkout_datetime)
            # Check if current time is past expected check-out reminder time
            if current_datetime >= expected_checkout_datetime:
                # Check if employee has already checked out today
                attendance_record = self.env['hr.attendance'].search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', fields.Datetime.to_string(current_date)),
                    ('check_out', '=', False)
                ], limit=1)

                # If check-out is pending, send a reminder
                if attendance_record:
                    payload = {
                        'model': 'hr.attendance',
                        'action': 'check_out_reminder'
                    }

                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=employee.user_id.id,
                        title='Check-out Reminder',
                        body=f'Your shift is ending soon. Please check out for {current_date}.',
                        payload=payload
                    )
