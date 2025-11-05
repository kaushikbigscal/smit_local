from datetime import datetime
import pytz
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.fields import Datetime


class HRAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model
    def create(self, vals):
        check_in = vals.get('check_in')
        employee_id = vals.get('employee_id')
        print(Datetime.today())
        if check_in and employee_id:
            try:
                print(check_in)
                # Convert check-in time to datetime object if needed
                check_in_datetime = (
                    datetime.strptime(check_in, '%Y-%m-%d %H:%M:%S')
                    if isinstance(check_in, str)
                    else check_in
                )
                print(check_in_datetime)
                check_in_date = check_in_datetime.date()
                print(check_in_date)
                employee = self.env['hr.employee'].browse(employee_id)
                resource_calendar = employee.resource_calendar_id
                weekday = check_in_date.weekday()

                if not resource_calendar:
                    return super().create(vals)

                    # Get the user's timezone (default to UTC if not set)
                user_tz = self.env.user.tz or 'UTC'
                tz = pytz.timezone(user_tz)

                # Convert UTC time to local timezone
                check_in_local = check_in_datetime.astimezone(tz)

                # if on leave and leave has approved, restrict from checkin
                leave_model = self.env['hr.leave']
                if leave_model.is_leave_approved_today(employee_id, check_in_datetime):
                    raise ValidationError(
                        _("Cannot check in while on leave. Employee: %s, Date: %s")
                        % (employee.name, check_in_local.strftime('%d/%m/%Y'))
                    )

                # Validate against holidays and work schedule
                self._validate_check_in_date(resource_calendar, check_in_date, employee)

            except ValueError as e:
                raise ValidationError(_(f"Invalid check-in time format.{e}"))

        return super().create(vals)

    def _validate_check_in_date(self, calendar, check_date, employee):
        if self._is_public_holiday(calendar, check_date):
            raise ValidationError(_(
                "Cannot check in on a public holiday. Employee: %s, Date: %s"
            ) % (employee.name, check_date))

        if not self._is_working_day(calendar, check_date, employee):
            raise ValidationError(_(
                "Cannot check in on a non-working day. Employee: %s, Date: %s"
            ) % (employee.name, check_date))

    def _is_public_holiday(self, resource_calendar, check_in_date):
        # Ensure the check_in_date is of type 'date' (in case it's a datetime object)
        if isinstance(check_in_date, datetime):
            check_in_date = check_in_date.date()

        # Ensure that global leaves are taken into account and match the given date
        public_holiday = self.env['resource.calendar.leaves'].search([
            ('date_from', '<=', check_in_date),
            ('date_to', '>=', check_in_date),
            ('company_id', '=', self.env.user.company_id.id),  # Ensure it's for the same company
            ('resource_id', '=', False)
        ], limit=1)

        if public_holiday:
            return True
        return False

    def _is_working_day(self, resource_calendar, check_in_date, employee):
        weekday = check_in_date.weekday()
        # Get the weekday (0 = Monday, 6 = Sunday)

        if resource_calendar:
            for attendance in resource_calendar.attendance_ids:
                if int(attendance.dayofweek) == weekday:
                    return True
        if employee.company_id.Enable_Sunday_Rule:
            if employee.Allow_work_on_sunday:
                return True

        return False


class HRAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model
    def create(self, vals):
        check_in = vals.get('check_in')
        if check_in:
            if isinstance(check_in, datetime):
                check_in_date = check_in
            else:
                check_in_date = fields.Datetime.from_string(check_in)

            user_tz = self.env.user.tz or 'UTC'
            local_tz = pytz.timezone(user_tz)
            utc_tz = pytz.UTC
            check_in_date = utc_tz.localize(check_in_date).astimezone(local_tz)

            if check_in_date:
                weekday = check_in_date.weekday()  # Monday = 0, Sunday = 6
                employee = self.env['hr.employee'].browse(vals.get('employee_id'))
                existing_attendance = self.search([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', check_in_date.replace(hour=0, minute=0, second=0)),
                    ('check_in', '<=', check_in_date.replace(hour=23, minute=59, second=59))
                ])

                if not existing_attendance:
                    resource_calendar = employee.resource_calendar_id
                    work_from_time = 9.0  # Default to 9 AM if the day is not in the contract

                    if resource_calendar:
                        day_in_contract = False  # Flag to check if the weekday is in the contract

                        for attendance in resource_calendar.attendance_ids:
                            if int(attendance.dayofweek) == weekday and attendance.day_period == 'morning':
                                work_from_time = attendance.hour_from
                                day_in_contract = True
                                break  # Exit loop once a matching record is found

                        if not day_in_contract:
                            work_from_time = 9.0  # Set to 9 AM if the day is out of contract

                    allowed_minutes = int(
                        self.env['ir.config_parameter'].sudo().get_param('hr_attendance.minute_allowed', default=0)
                    )

                    total_minutes = int(work_from_time * 60) + allowed_minutes
                    allowed_time = f"{total_minutes // 60:02}:{total_minutes % 60:02}"
                    check_in_time = check_in_date.strftime('%H:%M')

                    notify_late = bool(
                        self.env['ir.config_parameter'].sudo().get_param('hr_attendance.notification_late_day_in',
                                                                         default=False))
                    if notify_late and check_in_time > allowed_time:
                        self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                            'type': 'danger',
                            'message': _(
                                "You are reporting late for work. Your pay might be impacted"),
                            'sticky': True,
                        })

        return super(HRAttendance, self).create(vals)


class AttendanceSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    notification_late_day_in = fields.Boolean(string="Notificttion For Late Day in", default=False)

    @api.model
    def set_values(self):
        super(AttendanceSettings, self).set_values()
        self.env['ir.config_parameter'].set_param('hr_attendance.notification_late_day_in',
                                                  self.notification_late_day_in)

    @api.model
    def get_values(self):
        res = super(AttendanceSettings, self).get_values()
        res.update(
            notification_late_day_in=bool(
                self.env['ir.config_parameter'].sudo().get_param('hr_attendance.notification_late_day_in',
                                                                 default=False))
        )

        return res


class Menu(models.Model):
    _inherit = 'ir.ui.menu'

    is_quick = fields.Boolean(string="Quick Action", default=False)

    @api.constrains('is_quick', 'action')
    def _check_quick_action_requires_action(self):
        for record in self:
            if record.is_quick and not record.action:
                raise ValidationError("Quick Action menu must have an associated action.")
