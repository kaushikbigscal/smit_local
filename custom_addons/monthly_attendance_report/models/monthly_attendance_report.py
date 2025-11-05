from odoo import models, fields, api
from datetime import datetime, timedelta, time
from calendar import monthrange
import json
import pytz


class MonthlyAttendanceReportLine(models.Model):
    _name = 'monthly.attendance.report.line'
    _description = 'Monthly Attendance Report Line'
    _order = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    department_id = fields.Many2one(related='employee_id.department_id', string="Department")
    company_id = fields.Many2one(related='employee_id.company_id', string="Company")

    report_date = fields.Date(string="Report Date")
    total_days = fields.Integer(string="Total Days")
    working_days = fields.Float(string="Working Days")
    present_days = fields.Float(string="Present Days")
    deduction_days = fields.Float(string="Deduction Days")
    late_in = fields.Integer(string="Late In")
    early_out = fields.Integer(string="Early Out")
    extra_days = fields.Float(string="Extra Days")
    paid_leaves = fields.Float(string="Paid Leaves")
    unpaid_leaves = fields.Float(string="Unpaid Leaves")
    pay_days = fields.Float(string="Pay Days")
    employee_code = fields.Char(string="Employee Code", related="employee_id.x_empCode", readonly=True, store=True)
    date_nums = fields.Text(string="Date Columns")
    daily_attendance_data = fields.Text(string="Daily Attendance Data")
    uninformed_leave = fields.Float(string="Uninformed Leave")
    public_holidays = fields.Integer(string="Public Holidays")
    weekoff = fields.Integer(string="Weekoff")

    @api.model
    def generate_report_lines(self, month, employee_ids=None, department_ids=None):
        employee_ids = employee_ids if employee_ids else []
        department_ids = department_ids if department_ids else []

        start_date, end_date = None, None
        if month:
            try:
                year, month_num = map(int, month.split('-'))
                start_date = fields.Date.to_date(f"{year}-{month_num:02d}-01")
                last_day = monthrange(year, month_num)[1]
                end_date = fields.Date.to_date(f"{year}-{month_num:02d}-{last_day:02d}")
            except Exception as e:
                print(f"Invalid month format or error: {e}")
                return False

        if not start_date or not end_date:
            print("Month filter is required.")
            return False

        # Instead of contract logic, get all employees who have attendance in the period
        attendance_domain = [
            ('check_in', '>=', start_date),
            ('check_in', '<=', end_date),
        ]
        if employee_ids:
            attendance_domain.append(('employee_id', 'in', employee_ids))
        if department_ids:
            attendance_domain.append(('employee_id.department_id', 'in', department_ids))
        attendance_employees = self.env['hr.attendance'].search(attendance_domain).mapped('employee_id')
        employees = attendance_employees
        if not employees:
            print("No matching employees found.")
            return False

        existing_domain = [('report_date', '=', start_date)]
        if employee_ids:
            existing_domain.append(('employee_id', 'in', employee_ids))
        if department_ids:
            existing_domain.append(('department_id', 'in', department_ids))
        self.search(existing_domain).unlink()

        generated_report_lines = []
        tz_kolkata = pytz.timezone('Asia/Kolkata')

        ConfigParameter = self.env['ir.config_parameter'].sudo()
        max_late_check_ins_allowed = int(ConfigParameter.get_param('hr_attendance.max_late_check_ins', default=3))
        max_early_check_outs_allowed = int(ConfigParameter.get_param('hr_attendance.max_early_check_outs', default=3))

        for employee in employees:

            # For compatibility, try to get a calendar, but skip if not found
            calendar = employee.resource_calendar_id or self.env['resource.calendar'].search([], limit=1)
            if not calendar:
                print(f"No calendar for {employee.name}, skipping working days calculation.")
                total_working_days = 0
                working_days_of_week = set()
            else:
                total_working_days = 0
                temp_date_work_days = start_date
                working_days_of_week = set(int(a.dayofweek) for a in calendar.attendance_ids.filtered(
                    lambda a: a.dayofweek in [str(d) for d in range(7)]
                ))
                while temp_date_work_days <= end_date:
                    if temp_date_work_days.weekday() in working_days_of_week:
                        total_working_days += 1
                    temp_date_work_days += timedelta(days=1)

            attendance_records = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', start_date),
                ('check_in', '<=', end_date),
            ])

            formatted_daily_data = {}
            temp_date = start_date
            while temp_date <= end_date:
                day_num = temp_date.day
                actual_date = temp_date

                day_attendance_records = attendance_records.filtered(
                    lambda r: r.check_in and fields.Datetime.from_string(r.check_in).replace(
                        tzinfo=pytz.UTC).astimezone(tz_kolkata).date() == actual_date)

                earliest_actual_in_dt = None
                latest_actual_out_dt = None

                if day_attendance_records:
                    day_attendance_records = day_attendance_records.sorted(
                        key=lambda r: fields.Datetime.from_string(r.check_in).replace(tzinfo=pytz.UTC).astimezone(
                            tz_kolkata))

                    for rec in day_attendance_records:
                        if rec.check_in:
                            check_in_kolkata = fields.Datetime.from_string(rec.check_in).replace(
                                tzinfo=pytz.UTC).astimezone(tz_kolkata)
                            if not earliest_actual_in_dt or check_in_kolkata < earliest_actual_in_dt:
                                earliest_actual_in_dt = check_in_kolkata

                        if rec.check_out:
                            check_out_kolkata = fields.Datetime.from_string(rec.check_out).replace(
                                tzinfo=pytz.UTC).astimezone(tz_kolkata)
                            if not latest_actual_out_dt or check_out_kolkata > latest_actual_out_dt:
                                latest_actual_out_dt = check_out_kolkata

                day_of_week = actual_date.weekday()
                day_attendance_periods = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == day_of_week)
                is_scheduled_working_day = actual_date.weekday() in working_days_of_week

                minutes_allowed = int(ConfigParameter.get_param('hr_attendance.minute_allowed', default='0'))

                allowed_check_in_until = allowed_check_out_from = None
                if day_attendance_periods:
                    day_attendance_periods = day_attendance_periods.sorted(key=lambda a: a.hour_from)
                    expected_start_dt = tz_kolkata.localize(datetime.combine(actual_date, time(
                        int(day_attendance_periods[0].hour_from), int((day_attendance_periods[0].hour_from % 1) * 60))))
                    expected_end_dt = tz_kolkata.localize(datetime.combine(actual_date,
                                                                           time(int(day_attendance_periods[-1].hour_to),
                                                                                int((day_attendance_periods[
                                                                                         -1].hour_to % 1) * 60))))
                    allowed_check_in_until = expected_start_dt + timedelta(minutes=minutes_allowed)
                    allowed_check_out_from = expected_end_dt

                is_late_in_day = earliest_actual_in_dt and allowed_check_in_until and earliest_actual_in_dt > allowed_check_in_until
                is_early_out_day = latest_actual_out_dt and allowed_check_out_from and latest_actual_out_dt < allowed_check_out_from

                leave_records_on_day = self.env['hr.leave'].search([
                    ('employee_id', '=', employee.id),
                    ('request_date_from', '<=', actual_date),
                    ('request_date_to', '>=', actual_date),
                    ('state', '=', 'validate'),
                ], limit=1)
                is_on_leave = bool(leave_records_on_day)

                is_public_holiday = bool(self.env['resource.calendar.leaves'].search([
                    ('company_id', '=', self.env.user.company_id.id),
                    ('resource_id', '=', False),
                    ('date_from', '<=', actual_date),
                    ('date_to', '>=', actual_date),
                ], limit=1))

                if is_public_holiday:
                    day_status = 'public_holiday'
                elif day_attendance_records:
                    if not is_scheduled_working_day and employee.Allow_work_on_sunday:
                        day_status = 'extra_day'
                    elif is_late_in_day or is_early_out_day:
                        day_status = 'late_early'
                    else:
                        day_status = 'present'
                elif is_on_leave:
                    day_status = 'leave'
                else:
                    day_status = 'absent'

                day_entries = []
                if earliest_actual_in_dt:
                    day_entries.append({'type': 'in', 'time': earliest_actual_in_dt.strftime('%H:%M')})
                if latest_actual_out_dt:
                    day_entries.append({'type': 'out', 'time': latest_actual_out_dt.strftime('%H:%M')})

                formatted_daily_data[day_num] = {
                    'status': day_status,
                    'entries': day_entries,
                    'is_late_in': is_late_in_day,
                    'is_early_out': is_early_out_day,
                    'is_on_leave': is_on_leave,
                    'is_public_holiday': is_public_holiday,
                    'is_scheduled_working_day': is_scheduled_working_day,
                }

                temp_date += timedelta(days=1)

            daily_attendance_str = json.dumps(formatted_daily_data)
            employee_late_in_count_actual = sum(1 for d in formatted_daily_data.values() if d.get('is_late_in'))
            employee_early_out_count_actual = sum(1 for d in formatted_daily_data.values() if d.get('is_early_out'))

            monthly_late_in_count_adjusted = max(0, employee_late_in_count_actual - max_late_check_ins_allowed)
            monthly_early_out_count_adjusted = max(0, employee_early_out_count_actual - max_early_check_outs_allowed)

            deduction_days = (monthly_late_in_count_adjusted + monthly_early_out_count_adjusted) / 2.0
            present_days = sum(1 for d in formatted_daily_data.values() if d.get('status') in ['present', 'late_early'])
            today = fields.Date.context_today(self)
            uninformed_leave = sum(1 for day, d in formatted_daily_data.items() if
                                   d.get('status') == 'absent' and d.get('is_scheduled_working_day') and (
                                               start_date + timedelta(days=int(day) - 1)) < today)

            # Weekoff (days not scheduled as working days)
            weekoff = sum(1 for d in formatted_daily_data.values() if not d.get('is_scheduled_working_day'))
            # Holidays
            holidays = sum(1 for d in formatted_daily_data.values() if d.get('status') == 'public_holiday')

            # Paid and Unpaid leave calculation with requires_allocation logic
            all_leaves = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('request_date_from', '>=', start_date),
                ('request_date_to', '<=', end_date),
                ('state', '=', 'validate'),
            ])
            paid_leave_days = 0.0
            unpaid_leave_days = 0.0
            for leave in all_leaves:
                leave_type = leave.holiday_status_id
                # If requires_allocation is 'no' (No Limit), treat as unpaid
                if getattr(leave_type, 'requires_allocation', 'yes') == 'no':
                    unpaid_leave_days += leave.number_of_days_display or 0.0
                elif leave_type.unpaid:
                    unpaid_leave_days += leave.number_of_days_display or 0.0
                else:
                    paid_leave_days += leave.number_of_days_display or 0.0
            paid_leaves = round(paid_leave_days, 2)

            unpaid_leaves = round(unpaid_leave_days, 2)

            extra_days = sum(1 for d in formatted_daily_data.values() if d.get('status') == 'extra_day')
            # New pay_days formula
            pay_days = present_days + paid_leaves + holidays + extra_days - unpaid_leaves
            if pay_days < 0:
                pay_days = 0

            report_line = self.create({
                'employee_id': employee.id,
                'department_id': employee.department_id.id,
                'report_date': start_date,
                'total_days': (end_date - start_date).days + 1,
                'working_days': total_working_days,
                'present_days': present_days,
                'deduction_days': deduction_days,
                'late_in': monthly_late_in_count_adjusted,
                'early_out': monthly_early_out_count_adjusted,
                'extra_days': extra_days,
                'paid_leaves': paid_leaves,
                'unpaid_leaves': unpaid_leaves,
                'pay_days': pay_days,
                'uninformed_leave': uninformed_leave,
                'public_holidays': holidays,
                'weekoff': weekoff,
                'date_nums': ','.join(str(i) for i in range(1, (end_date - start_date).days + 2)),
                'daily_attendance_data': daily_attendance_str,
            })
            generated_report_lines.append(report_line)

        return generated_report_lines
