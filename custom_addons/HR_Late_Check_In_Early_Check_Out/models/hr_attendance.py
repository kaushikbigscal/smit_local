from odoo import models, api, fields, _
from odoo.exceptions import UserError
import pytz
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class HRAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model
    def create(self, vals):
        _logger.info(f"Creating Attendance Record with values: {vals}")
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
                        })
        return super(HRAttendance, self).create(vals)

    def write(self, vals):
        _logger.info(f"Updating Attendance record with values: {vals}")
        return super(HRAttendance, self).write(vals)

    @api.model
    def process_daily_attendance(self):
        _logger.info("==== Starting Daily Attendance Processing ====")
        yesterday = fields.Date.today() - timedelta(days=1)
        _logger.info(f"Processing attendance for date: {yesterday}")
        employees = self.env['hr.employee'].search([])
        _logger.info(f"Found {len(employees)} employees to process")

        for employee in employees:
            _logger.info(f"Processing attendance for employee: {employee.name} (ID: {employee.id})")
            self._process_employee_monthly_attendance(employee, yesterday)

        _logger.info("==== Complete d Daily Attendance Processing ====")

    def _process_employee_monthly_attendance(self, employee, date):
        _logger.info(f"Processing monthly attendance for employee {employee.name} (ID: {employee.id}) for the month of {date}")
        start_of_month = date.replace(day=1)
        end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        _logger.info(f"Date range: {start_of_month} to {end_of_month}")

        attendances = self.search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', start_of_month),
            ('check_in', '<=', end_of_month)
        ], order='check_in')

        if not attendances:
            _logger.info(f"No attendance records found for employee {employee.name} (ID: {employee.id}) in the month of {date}")
            return

        _logger.info(f"Found {len(attendances)} attendance records for employee {employee.name} (ID: {employee.id})")

        ist = pytz.timezone('Asia/Kolkata')
        late_check_ins = 0
        early_check_outs = 0

        # Group attendances by day
        daily_attendances = {}
        for attendance in attendances:
            check_in_date = attendance.check_in.astimezone(ist).date()
            if check_in_date not in daily_attendances:
                daily_attendances[check_in_date] = {'first_check_in': None, 'last_check_out': None}

            if (daily_attendances[check_in_date]['first_check_in'] is None or attendance.check_in <
                    daily_attendances[check_in_date]['first_check_in']):
                daily_attendances[check_in_date]['first_check_in'] = attendance.check_in

            if attendance.check_out and (
                    daily_attendances[check_in_date]['last_check_out'] is None or attendance.check_out >
                    daily_attendances[check_in_date]['last_check_out']):
                daily_attendances[check_in_date]['last_check_out'] = attendance.check_out

        _logger.info(f"Processed {len(daily_attendances)} days of attendance for employee {employee.name} (ID: {employee.id})")

        max_late_check_ins = int(self.env['ir.config_parameter'].sudo().get_param('hr_attendance.max_late_check_ins', default=3))
        max_early_check_outs = int(self.env['ir.config_parameter'].sudo().get_param('hr_attendance.max_early_check_outs', default=3))

        for day, day_attendance in daily_attendances.items():
            _logger.info(f"Processing attendance for {employee.name} (ID: {employee.id}) on {day}")
            is_late = False
            is_early = False

            if day_attendance['first_check_in']:
                first_check_in = day_attendance['first_check_in'].astimezone(ist).replace(tzinfo=None)
                if self._is_late_check_in(employee, first_check_in):
                    late_check_ins += 1
                    is_late = True
                    _logger.info(f"{employee.name} (ID: {employee.id}) had a late check-in on {day}. Total late check-ins: {late_check_ins}")

            if day_attendance['last_check_out']:
                last_check_out = day_attendance['last_check_out'].astimezone(ist).replace(tzinfo=None)
                if self._is_early_check_out(employee, last_check_out):
                    early_check_outs += 1
                    is_early = True
                    _logger.info(f"{employee.name} (ID: {employee.id}) had an early check-out on {day}. Total early check-outs: {early_check_outs}")

            if is_late and late_check_ins > max_late_check_ins:
                _logger.info(f"Attempting to create late check-in leave for employee {employee.name} (ID: {employee.id}) on {day}")
                self._create_late_check_in_leave(employee, day)

            if is_early and early_check_outs > max_early_check_outs:
                _logger.info(f"Attempting to create early check-out leave for employee {employee.name} (ID: {employee.id}) on {day}")
                self._create_early_check_out_leave(employee, day)

        _logger.info(f"Employee {employee.name} (ID: {employee.id}) has {late_check_ins} late check-ins and {early_check_outs} early check-outs this month")

        employee.late_check_in_count = late_check_ins
        employee.early_check_out_count = early_check_outs
        employee.update({
            'late_check_in_count': employee.late_check_in_count,
            'early_check_out_count': employee.early_check_out_count,
        })
    # def _is_late_check_in(self, employee, check_in_time):
    #     work_start_time = self._get_work_start_time(employee, check_in_time)
    #     minute_allowed = int(self.env['ir.config_parameter'].sudo().get_param('hr_attendance.minute_allowed', default=15))
    #     minute_allowed = timedelta(minutes=minute_allowed)
    #     is_late = check_in_time > (work_start_time + minute_allowed)
    #     _logger.info(f"Employee {employee.name} (ID: {employee.id}) - Check-in at {check_in_time}, Work start at {work_start_time}, Is late: {is_late}")
    #     return is_late
    #
    # def _is_early_check_out(self, employee, check_out_time):
    #     work_end_time = self._get_work_end_time(employee, check_out_time)
    #     is_early = check_out_time < work_end_time
    #     _logger.info(f"Employee {employee.name} (ID: {employee.id}) - Check-out at {check_out_time}, Work end at {work_end_time}, Is early: {is_early}")
    #     return is_early

    def _is_late_check_in(self, employee, check_in_time):
        work_start_time = self._get_work_start_time(employee, check_in_time)
        if not work_start_time:
            return False  # Skip this check-in if work start time not found

        minute_allowed = int(
            self.env['ir.config_parameter'].sudo().get_param('hr_attendance.minute_allowed', default=15))
        minute_allowed = timedelta(minutes=minute_allowed)
        is_late = check_in_time > (work_start_time + minute_allowed)
        _logger.info(
            f"Employee {employee.name} (ID: {employee.id})  Check-in at {check_in_time}, Work start at {work_start_time}, Is late: {is_late}")
        return is_late

    def _is_early_check_out(self, employee, check_out_time):
        work_end_time = self._get_work_end_time(employee, check_out_time)
        if not work_end_time:
            return False  # Skip this check-out if work end time not found

        is_early = check_out_time < work_end_time
        _logger.info(
            f"Employee {employee.name} (ID: {employee.id})  Check-out at {check_out_time}, Work end at {work_end_time}, Is early: {is_early}")
        return is_early

    def _get_work_start_time(self, employee, date):
        return self._get_work_time(employee, date, 'morning')

    def _get_work_end_time(self, employee, date):
        return self._get_work_time(employee, date, 'afternoon')

    # def _get_work_time(self, employee, date, period):
    #     _logger.info(f"Getting {period} work time for employee {employee.name} (ID: {employee.id}) on {date}")
    #     contract = self.env['hr.contract'].search([('employee_id', '=', employee.id), ('state', '=', 'open')], limit=1)
    #     if not contract or not contract.resource_calendar_id:
    #         _logger.error(f"No active contract or working hours defined for employee {employee.name} (ID: {employee.id})")
    #         raise UserError(f"No active contract or working hours defined for employee {employee.name} (ID: {employee.id})")
    #
    #     calendar = contract.resource_calendar_id
    #     work_time = calendar.attendance_ids.filtered(
    #         lambda a: a.dayofweek == str(date.weekday()) and a.day_period == period
    #     )
    #
    #     if not work_time:
    #         _logger.error(f"Work {period} time not defined for {date.strftime('%A')} in the calendar for employee {employee.name} (ID: {employee.id})")
    #         raise UserError(f"Work {period} time is not defined for {date.strftime('%A')} in the calendar for employee {employee.name} (ID: {employee.id})")
    #
    #     time_float = work_time[0].hour_from if period == 'morning' else work_time[0].hour_to
    #     work_time = date.replace(hour=int(time_float), minute=int((time_float % 1) * 60), second=0, microsecond=0)
    #     _logger.info(f"Work {period} time for employee {employee.name} (ID: {employee.id}) on {date}: {work_time}")
    #     return work_time

    def _get_work_time(self, employee, date, period):
        _logger.info(f"Getting {period} work time for employee {employee.name} (ID: {employee.id}) on {date}")
        # contract = self.env['hr.contract'].search([('employee_id', '=', employee.id), ('state', '=', 'open')], limit=1)
        # if not contract or not contract.resource_calendar_id:
        #     _logger.warning(f"Skipping employee {employee.name} (ID: {employee.id}) no active contract or calendar")
        #     return None

        calendar = employee.resource_calendar_id
        if not calendar:
            _logger.warning(f"Skipping employee {employee.name} (ID: {employee.id}) - no resource calendar set")
            return None

        work_time = calendar.attendance_ids.filtered(
            lambda a: a.dayofweek == str(date.weekday()) and a.day_period == period
        )

        if not work_time:
            _logger.warning(
                f"Skipping employee {employee.name} (ID: {employee.id})  no {period} work time for {date.strftime('%A')}")
            return None

        time_float = work_time[0].hour_from if period == 'morning' else work_time[0].hour_to
        work_time = date.replace(hour=int(time_float), minute=int((time_float % 1) * 60), second=0, microsecond=0)
        _logger.info(f"Work {period} time for employee {employee.name} (ID: {employee.id}) on {date}: {work_time}")
        return work_time

    def _create_late_check_in_leave(self, employee, date):
        _logger.info(f"Creating late check-in leave for employee {employee.name} (ID: {employee.id}) on {date}")

        # Get the leave type from the configuration
        leave_type = self.env['ir.config_parameter'].sudo().get_param('hr_attendance.leave_type_id')
        leave_type_record = self.env['hr.leave.type'].browse(int(leave_type)) if leave_type else None

        if not leave_type_record:
            _logger.error("Leave type not found in configuration")
            raise UserError("Leave type not found in configuration. Please set it up.")

        # Check if there are allocations for the selected leave type
        allocations = self.env['hr.leave.allocation'].search([
            ('holiday_status_id', '=', leave_type_record.id),
            ('employee_id', '=', employee.id)
        ])

        total_allocated = sum(allocation.number_of_days for allocation in allocations)
        total_taken = sum(leave.number_of_days for leave in self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('holiday_status_id', '=', leave_type_record.id),
            ('state', 'in', ['confirm', 'validate'])
        ]))

        remaining_leaves = total_allocated - total_taken

        if remaining_leaves > 0:
            self._create_leave(employee, date, leave_type_record, 'Late Day-In Leave', 'am')
        else:
            _logger.info(f"No remaining leaves in {leave_type_record.name}, falling back to UNPAID leave")
            unpaid_leave_type = self.env['hr.leave.type'].search([('name', '=', 'Unpaid')], limit=1)
            if unpaid_leave_type:
                self._create_leave(employee, date, unpaid_leave_type, 'Late Day-In Leave (UNPAID)', 'am')
            else:
                _logger.error("UNPAID leave type not found")
                raise UserError("UNPAID leave type not found. Please create it first.")

    def _create_early_check_out_leave(self, employee, date):
        _logger.info(f"Creating early check-out leave for employee {employee.name} (ID: {employee.id}) on {date}")

        # Get the leave type from the configuration
        leave_type_id = self.env['ir.config_parameter'].sudo().get_param('hr_attendance.leave_type_id')

        if leave_type_id:
            leave_type_id = int(leave_type_id)  # Convert to integer
            leave_type_record = self.env['hr.leave.type'].browse(leave_type_id)
        else:
            leave_type_record = None

        if not leave_type_record or len(leave_type_record) != 1:
            _logger.error("Leave type not found in configuration or multiple records found")
            raise UserError(
                "Leave type not found in configuration or multiple records found. Please set it up correctly.")

        # Check if there are allocations for the selected leave type
        allocations = self.env['hr.leave.allocation'].search([
            ('id', '=', leave_type_record.id),
            ('employee_id', '=', employee.id)
        ])
        _logger.info(f"Leave allocations {allocations}")
        total_allocated = sum(allocation.number_of_days for allocation in allocations)
        total_taken = sum(leave.number_of_days for leave in self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('holiday_status_id', '=', leave_type_record.id),
            ('state', 'in', ['confirm', 'validate'])
        ]))

        _logger.info(f"Leave allocations {total_allocated} or {total_taken}")

        remaining_leaves = total_allocated - total_taken

        _logger.info(f"Leave allocations {remaining_leaves}")

        if remaining_leaves > 0:
            self._create_leave(employee, date, leave_type_record, 'Early Day-Out Leave', 'pm')
        else:
            _logger.info(f"No remaining leaves in {leave_type_record.name}, falling back to UNPAID leave")
            unpaid_leave_type = self.env['hr.leave.type'].search([('name', '=', 'Unpaid')], limit=1)
            if unpaid_leave_type:
                self._create_leave(employee, date, unpaid_leave_type, 'Early Day-Out Leave (UNPAID)', 'pm')
            else:
                _logger.error("UNPAID leave type not found")
                raise UserError("UNPAID leave type not found. Please create it first.")

    # def _create_late_check_in_leave(self, employee, date):
    #     _logger.info(f"Creating late check-in leave for employee {employee.name} (ID: {employee.id}) on {date}")
    #     leave_type = self.env['hr.leave.type'].search([('name', '=', 'Half Day Leave')], limit=1)
    #     if not leave_type:
    #         _logger.error("Half Day Leave type not found")
    #         raise UserError("Leave type 'Half Day Leave' not found. Please create it first.")
    #
    #     self._create_leave(employee, date, leave_type, 'Late Check-In Leave', 'am')
    #
    # def _create_early_check_out_leave(self, employee, date):
    #     _logger.info(f"Creating early check-out leave for employee {employee.name} (ID: {employee.id}) on {date}")
    #     leave_type = self.env['hr.leave.type'].search([('name', '=', 'Half Day Leave')], limit=1)
    #     if not leave_type:
    #         _logger.error("Half Day Leave type not found")
    #         raise UserError("Leave type 'Half Day Leave' not found. Please create it first.")
    #
    #     self._create_leave(employee, date, leave_type, 'Early Check-Out Leave', 'pm')

    def _create_leave(self, employee, date, leave_type, leave_name, period):
        _logger.info(f"Attempting to create {leave_name} for employee {employee.name} (ID: {employee.id}) on {date}")
        existing_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('request_date_from', '=', date),
            ('request_date_to', '=', date),
            ('request_date_from_period', '=', period),
            ('state', 'in', ['confirm', 'validate'])
        ])

        if existing_leaves:
            _logger.info(f"Existing leave found for {employee.name} (ID: {employee.id}) on {date}, skipping leave creation")
            return

        leave_vals = {
            'name': leave_name,
            'employee_id': employee.id,
            'holiday_status_id': leave_type.id,
            'request_date_from': date,
            'request_date_to': date,
            'request_date_from_period': period,
            'request_unit_half': True,
            'state': 'confirm'
        }
        _logger.info(f"Creating leave with values: {leave_vals}")
        leave = self.env['hr.leave'].create(leave_vals)
        _logger.info(f"{leave_name} Created successfully for employee {employee.name} (ID: {employee.id}) on {date} with leave ID: {leave.id}")

    @api.model
    def run_daily_attendance_processing(self):
        _logger.info("Starting daily attendance processing")
        self.process_daily_attendance()
        _logger.info("Completed daily attendance processing")
