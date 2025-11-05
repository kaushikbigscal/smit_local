# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, time, date, timedelta
import pytz
from odoo.tools import format_date
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

# Batch size for processing employees
BATCH_SIZE = 100


class HrAttendance(models.Model):
    """Extend HR Attendance to add notes field"""
    _inherit = 'hr.attendance'

    attendance_note = fields.Text(string='Note', tracking=True)

    def write(self, vals):
        """Override write to handle attendance corrections after manual edits"""
        result = super(HrAttendance, self).write(vals)

        # Check if this write came from correction editing
        if self.env.context.get('from_correction'):
            # Add note for manual adjustment if not already present
            if 'attendance_note' not in vals or not vals.get('attendance_note'):
                vals_with_note = {'attendance_note': 'Short hours manual adjustment'}
                super(HrAttendance, self).write(vals_with_note)

            # Re-evaluate corrections for affected records
            for record in self:
                if record.check_in:
                    check_date = record.check_in.date()
                    self._handle_correction_after_edit(record.employee_id.id, check_date)

        return result

    def _adjust_expected_for_leave(self, employee, date, expected_hours):
        Leave = self.env['hr.leave']
        leaves = Leave.sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('request_date_from', '<=', date),
            ('request_date_to', '>=', date),
        ])
        if leaves:
            total_leave_hours = sum(
                l.number_of_hours_display or 0.0 for l in leaves if l.number_of_hours_display
            )
            if total_leave_hours >= expected_hours:
                return 0.0
            elif total_leave_hours > 0:
                return max(0.0, expected_hours - total_leave_hours)
        return expected_hours

    def _handle_correction_after_edit(self, employee_id, check_date):
        """Handle correction record updates/deletion after attendance edit"""
        AttendanceCorrection = self.env['temp.attendance.correction']

        # Get all attendance records for this employee on this date
        date_start = datetime.combine(check_date, time.min)
        date_end = datetime.combine(check_date, time.max)

        day_attendances = self.search([
            ('employee_id', '=', employee_id),
            ('check_in', '>=', date_start),
            ('check_in', '<=', date_end),
        ])
        # Only completed attendances  ('check_out', '!=', False)

        # Calculate total worked hours
        total_worked_hours = 0.0
        for attendance in day_attendances:
            if attendance.check_out:  # Only count complete attendance
                total_worked_hours += attendance.worked_hours or 0.0

        # Get expected hours for this employee
        employee = self.env['hr.employee'].browse(employee_id)
        correction_model = AttendanceCorrection.sudo()
        expected_hours = correction_model._get_expected_hours(employee, check_date)
        expected_hours = self._adjust_expected_for_leave(employee, check_date, expected_hours)

        # Get grace minutes
        minute_allowed = correction_model._get_minute_allowed()

        # Find existing correction records for this employee and date
        existing_corrections = AttendanceCorrection.search([
            ('employee_id', '=', employee_id),
            ('date', '=', check_date),
            ('reason_code', 'in', ['SHORT_HOURS', 'NO_SHOW'])
        ])

        # Calculate effective expected hours (considering grace for late check-in)
        effective_expected_hours = expected_hours

        if day_attendances:
            # Apply grace period logic
            earliest_check_in = min(day_attendances.mapped('check_in'))
            earliest_start = self._get_scheduled_start_time(employee, check_date)

            if earliest_start and earliest_check_in:
                delay_minutes = max(0, int((earliest_check_in - earliest_start).total_seconds() // 60))
                discount_minutes = min(delay_minutes, minute_allowed)
                effective_expected_hours = max(0.0, expected_hours - (discount_minutes / 60.0))

        # Decision logic
        if not day_attendances:
            # Still no attendance - keep/create NO_SHOW
            no_show_correction = existing_corrections.filtered(lambda r: r.reason_code == 'NO_SHOW')
            if not no_show_correction:
                # Create NO_SHOW if it doesn't exist
                schedule_hours = correction_model._get_schedule_time_range(employee, check_date)
                AttendanceCorrection.create({
                    'employee_id': employee_id,
                    'date': check_date,
                    'reason_code': 'NO_SHOW',
                    'worked_hours': 0.0,
                    'expected_hours': expected_hours,
                    'shortfall': expected_hours,
                    'check_in': None,
                    'check_out': None,
                    'schedule_hours': schedule_hours,
                    'department_id': employee.department_id.id if employee.department_id else None,
                    'company_id': employee.company_id.id if employee.company_id else None,
                })
            # Remove any SHORT_HOURS records
            existing_corrections.filtered(lambda r: r.reason_code == 'SHORT_HOURS').unlink()

        elif total_worked_hours >= effective_expected_hours:
            # Working hours now meet expectations - remove all corrections
            existing_corrections.unlink()
            _logger.info(
                f"Removed correction records for employee {employee.name} on {check_date} - hours now sufficient")

        else:
            ############################################################
            # There is attendance — decide if SHORT_HOURS is necessary using tolerance
            keep, adjusted_shortfall = AttendanceCorrection._shortfall_after_tolerance(expected_hours,
                                                                                       total_worked_hours)

            # Remove NO_SHOW if present (since we have attendance)
            existing_corrections.filtered(lambda r: r.reason_code == 'NO_SHOW').unlink()

            if not keep:
                # Within tolerance: remove any existing SHORT_HOURS
                existing_corrections.filtered(lambda r: r.reason_code == 'SHORT_HOURS').unlink()
                _logger.info(
                    f"No shortfall after tolerance for employee {employee.name} on {check_date} — corrections removed")
                return
            ############################################################

            # Still has shortfall - update SHORT_HOURS record
            short_hours_correction = existing_corrections.filtered(lambda r: r.reason_code == 'SHORT_HOURS')

            # Remove NO_SHOW if exists (since we now have attendance)
            existing_corrections.filtered(lambda r: r.reason_code == 'NO_SHOW').unlink()

            # Get latest attendance times
            check_in_times = day_attendances.mapped('check_in')
            check_out_times = day_attendances.mapped('check_out')

            correction_vals = {
                'worked_hours': total_worked_hours,
                'expected_hours': expected_hours,
                'shortfall': adjusted_shortfall,
                'check_in': min(check_in_times) if check_in_times else None,
                'check_out': max(check_out_times) if check_out_times else None,
            }

            if short_hours_correction:
                # Update existing SHORT_HOURS record
                short_hours_correction.write(correction_vals)
                _logger.info(f"Updated SHORT_HOURS correction for employee {employee.name} on {check_date}")
            else:
                # Create new SHORT_HOURS record
                schedule_hours = correction_model._get_schedule_time_range(employee, check_date)
                correction_vals.update({
                    'employee_id': employee_id,
                    'date': check_date,
                    'reason_code': 'SHORT_HOURS',
                    'schedule_hours': schedule_hours,
                    'department_id': employee.department_id.id if employee.department_id else None,
                    'company_id': employee.company_id.id if employee.company_id else None,
                })
                AttendanceCorrection.create(correction_vals)
                _logger.info(f"Created new SHORT_HOURS correction for employee {employee.name} on {check_date}")

    def _get_scheduled_start_time(self, employee, check_date):
        """Get the scheduled start time for an employee on a given date"""
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', check_date),
            '|', ('date_end', '=', False), ('date_end', '>=', check_date)
        ], limit=1)

        calendar = None
        if contract and contract.resource_calendar_id:
            calendar = contract.resource_calendar_id
        elif employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
        elif employee.company_id.resource_calendar_id:
            calendar = employee.company_id.resource_calendar_id

        if not calendar:
            return None

        weekday = check_date.weekday()
        attendance_lines = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == weekday)

        if not attendance_lines:
            return None

        earliest_start = min(attendance_lines.mapped('hour_from'))

        # Convert to datetime
        scheduled_start = datetime.combine(
            check_date,
            time(int(earliest_start), int((earliest_start % 1) * 60))
        )

        # Convert to UTC if needed
        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)
        scheduled_start_local = local_tz.localize(scheduled_start)

        return scheduled_start_local.astimezone(pytz.UTC).replace(tzinfo=None)


class AttendanceCorrection(models.Model):
    _name = 'temp.attendance.correction'
    _description = 'Attendance Shortfall Correction'
    _order = 'date desc, employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    date = fields.Date(string='Date', required=True)
    reason_code = fields.Selection([
        ('SHORT_HOURS', 'Short Hours'),
        ('NO_SHOW', 'No Show')
    ], string='Reason Code', required=True)
    worked_hours = fields.Float(string='Worked Hours')
    expected_hours = fields.Float(string='Expected Hours')
    shortfall = fields.Float(string='Shortfall')
    check_in = fields.Datetime(string='In Time')
    check_out = fields.Datetime(string='Out Time')
    schedule_hours = fields.Char(string='Work Schedule')
    department_id = fields.Many2one('hr.department', string='Department')
    company_id = fields.Many2one('res.company', string='Company')

    @api.model
    def check_attendance_for_date(self, check_date=None, employee_ids=None):
        """
        Optimized attendance checking with bulk operations and batch processing
        """
        if not check_date:
            check_date = date.today()

        _logger.info(f"Checking attendance for date: {check_date}")

        # Get employees with active contracts only
        if employee_ids:
            # Filter specific employees who also have active contracts
            contract_employee_ids = self.env['hr.contract'].search([
                ('employee_id', 'in', employee_ids),
                ('state', '=', 'open'),
                ('date_start', '<=', check_date),
                '|', ('date_end', '=', False), ('date_end', '>=', check_date)
            ]).mapped('employee_id.id')

            domain = [
                ('active', '=', True),
                ('id', 'in', contract_employee_ids),
                ('disable_tracking', '=', False)
            ]
        else:
            # Get all employees with active contracts
            active_contracts = self.env['hr.contract'].search([
                ('state', '=', 'open'),
                ('date_start', '<=', check_date),
                '|', ('date_end', '=', False), ('date_end', '>=', check_date)
            ])

            domain = [
                ('active', '=', True),
                ('id', 'in', active_contracts.mapped('employee_id.id')),
                ('disable_tracking', '=', False)
            ]

        # Get all active employees with required fields only
        employee_fields = ['id', 'name', 'resource_calendar_id', 'department_id', 'company_id']
        employees_data = self.env['hr.employee'].sudo().search_read(domain, employee_fields)

        if not employees_data:
            return 0

        total_employees = len(employees_data)
        created_records = 0

        # Process employees in batches to manage memory and performance
        for i in range(0, total_employees, BATCH_SIZE):
            batch_employees = employees_data[i:i + BATCH_SIZE]
            employee_ids = [emp['id'] for emp in batch_employees]

            _logger.info(
                f"Processing batch {i // BATCH_SIZE + 1}: employees {i + 1}-{min(i + BATCH_SIZE, total_employees)}")

            # Bulk fetch all required data for this batch
            batch_data = self._bulk_fetch_batch_data(employee_ids, check_date)

            # Process this batch
            batch_corrections = self._process_employee_batch(batch_employees, check_date, batch_data)

            # Bulk create correction records
            if batch_corrections:
                self.create(batch_corrections)
                created_records += len(batch_corrections)

        _logger.info(f"Created {created_records} attendance correction records for {check_date}")
        return created_records

    def _is_morning_half_day(self, leave_datetime, attendance_lines):
        """
        Determine if a half-day leave is morning or afternoon based on leave start time

        Args:
            leave_datetime: datetime when leave starts
            attendance_lines: list of attendance line dicts

        Returns:
            bool: True if morning, False if afternoon
        """
        if not leave_datetime or not attendance_lines:
            return True  # Default to morning

        # Convert datetime to hour float (9.0, 14.5, etc.)
        leave_hour = leave_datetime.hour + (leave_datetime.minute / 60.0)

        # Sort attendance lines by start time
        sorted_lines = sorted(attendance_lines, key=lambda x: x['hour_from'])

        if not sorted_lines:
            return True

        # Calculate midpoint of working day
        total_hours = sum(line['hour_to'] - line['hour_from'] for line in sorted_lines)
        target_hours = total_hours / 2.0

        # Find the time when we reach midpoint
        accumulated_hours = 0.0
        midpoint_hour = None

        for line in sorted_lines:
            line_hours = line['hour_to'] - line['hour_from']
            if accumulated_hours + line_hours >= target_hours:
                # Midpoint is in this session
                remaining = target_hours - accumulated_hours
                midpoint_hour = line['hour_from'] + remaining
                break
            accumulated_hours += line_hours

        if midpoint_hour is None:
            midpoint_hour = sorted_lines[-1]['hour_to']

        # If leave starts before midpoint = morning, otherwise = afternoon
        return leave_hour < midpoint_hour

    def _calculate_half_day_leave_hours(self, attendance_lines, half_day_type, expected_hours_per_day):
        """
        Calculate actual leave hours based on morning/afternoon schedule
        NOW USES ACTUAL SESSION BOUNDARIES, NOT MATHEMATICAL MIDPOINT
        """
        if not attendance_lines:
            return expected_hours_per_day / 2.0

        # Sort attendance lines by start time
        sorted_lines = sorted(attendance_lines, key=lambda x: x['hour_from'])

        if not half_day_type or half_day_type == 'morning':
            # Morning: Sum all sessions BEFORE the longest break
            return self._calculate_morning_hours_by_break(sorted_lines)
        else:
            # Afternoon: Sum all sessions AFTER the longest break
            return self._calculate_afternoon_hours_by_break(sorted_lines)

    def _calculate_morning_hours_by_break(self, sorted_lines):
        """
        Calculate morning hours: All sessions before the longest break

        Example:
        - 09:00-12:00 (3h)
        - Break 12:00-13:00 (1h) <- longest gap
        - 13:00-18:00 (5h)
        Morning = 3 hours (not 4!)
        """
        if len(sorted_lines) == 1:
            # Single session - split mathematically
            hours = sorted_lines[0]['hour_to'] - sorted_lines[0]['hour_from']
            return hours / 2.0

        # Find the longest break between sessions
        max_gap = 0
        split_index = 1

        for i in range(len(sorted_lines) - 1):
            gap = sorted_lines[i + 1]['hour_from'] - sorted_lines[i]['hour_to']
            if gap > max_gap:
                max_gap = gap
                split_index = i + 1

        # Sum hours before the split (morning sessions)
        morning_hours = 0.0
        for i in range(split_index):
            morning_hours += sorted_lines[i]['hour_to'] - sorted_lines[i]['hour_from']

        return morning_hours

    def _calculate_afternoon_hours_by_break(self, sorted_lines):
        """
        Calculate afternoon hours: All sessions after the longest break

        Example:
        - 09:00-12:00 (3h)
        - Break 12:00-13:00 (1h) <- longest gap
        - 13:00-18:00 (5h)
        Afternoon = 5 hours (not 4!)
        """
        if len(sorted_lines) == 1:
            # Single session - split mathematically
            hours = sorted_lines[0]['hour_to'] - sorted_lines[0]['hour_from']
            return hours / 2.0

        # Find the longest break between sessions
        max_gap = 0
        split_index = 1

        for i in range(len(sorted_lines) - 1):
            gap = sorted_lines[i + 1]['hour_from'] - sorted_lines[i]['hour_to']
            if gap > max_gap:
                max_gap = gap
                split_index = i + 1

        # Sum hours after the split (afternoon sessions)
        afternoon_hours = 0.0
        for i in range(split_index, len(sorted_lines)):
            afternoon_hours += sorted_lines[i]['hour_to'] - sorted_lines[i]['hour_from']

        return afternoon_hours

    def _bulk_fetch_batch_data(self, employee_ids, check_date):
        """
        Bulk fetch all required data for a batch of employees to minimize database queries
        """
        date_start = datetime.combine(check_date, time.min)
        date_end = datetime.combine(check_date, time.max)

        # 1. Bulk fetch attendance records
        attendance_data = self.env['hr.attendance'].search_read([
            ('employee_id', 'in', employee_ids),
            ('check_in', '>=', date_start),
            ('check_in', '<=', date_end)
        ], ['employee_id', 'check_in', 'check_out', 'worked_hours'])

        # Group attendance by employee_id
        attendance_by_employee = {}
        for att in attendance_data:
            emp_id = att['employee_id'][0]
            if emp_id not in attendance_by_employee:
                attendance_by_employee[emp_id] = []
            attendance_by_employee[emp_id].append(att)

        # 2. Bulk fetch active contracts
        contract_data = self.env['hr.contract'].search_read([
            ('employee_id', 'in', employee_ids),
            ('state', '=', 'open'),
            ('date_start', '<=', check_date),
            '|', ('date_end', '=', False), ('date_end', '>=', check_date)
        ], ['employee_id', 'resource_calendar_id'])

        # Group contracts by employee_id
        contracts_by_employee = {}
        for contract in contract_data:
            emp_id = contract['employee_id'][0]
            contracts_by_employee[emp_id] = contract

        # 3. Bulk fetch calendar data (ONLY ONCE)
        calendar_ids = set()

        # Get calendar IDs from contracts
        for contract in contract_data:
            if contract['resource_calendar_id']:
                calendar_ids.add(contract['resource_calendar_id'][0])

        # Get calendar IDs from employees
        employee_calendar_data = self.env['hr.employee'].search_read([
            ('id', 'in', employee_ids),
            ('resource_calendar_id', '!=', False)
        ], ['id', 'resource_calendar_id'])

        for emp_cal in employee_calendar_data:
            if emp_cal['resource_calendar_id']:
                calendar_ids.add(emp_cal['resource_calendar_id'][0])

        # Get calendar IDs from companies
        company_data = self.env['hr.employee'].search_read([
            ('id', 'in', employee_ids)
        ], ['company_id'])

        for comp in company_data:
            if comp['company_id']:
                company_calendar = self.env['res.company'].browse(comp['company_id'][0]).resource_calendar_id
                if company_calendar:
                    calendar_ids.add(company_calendar.id)

        # Bulk fetch calendar data
        calendar_data = {}
        if calendar_ids:
            calendars = self.env['resource.calendar'].search_read([
                ('id', 'in', list(calendar_ids))
            ], ['id', 'hours_per_day'])

            for cal in calendars:
                calendar_data[cal['id']] = cal

            # Fetch attendance lines for working day calculation
            weekday = check_date.weekday()
            attendance_lines_data = self.env['resource.calendar.attendance'].search_read([
                ('calendar_id', 'in', list(calendar_ids)),
                ('dayofweek', '=', str(weekday))
            ], ['calendar_id', 'hour_from', 'hour_to'])

            # Group attendance lines by calendar
            attendance_lines_by_calendar = {}
            for line in attendance_lines_data:
                cal_id = line['calendar_id'][0]
                if cal_id not in attendance_lines_by_calendar:
                    attendance_lines_by_calendar[cal_id] = []
                attendance_lines_by_calendar[cal_id].append(line)

            # Add attendance lines to calendar data
            for cal_id, lines in attendance_lines_by_calendar.items():
                if cal_id in calendar_data:
                    calendar_data[cal_id]['attendance_lines'] = lines

        # 4. Bulk fetch leave records (AFTER calendar data is ready)
        leave_data = self.env['hr.leave'].search_read([
            ('employee_id', 'in', employee_ids),
            ('state', '=', 'validate'),
            ('request_date_from', '<=', check_date),
            ('request_date_to', '>=', check_date)
        ], ['employee_id', 'request_unit_half', 'request_unit_hours', 'date_from', 'date_to',
            'number_of_days', 'request_date_from', 'request_date_to'])

        # Calculate leave impact per employee
        leave_hours_by_employee = {}
        for leave in leave_data:
            emp_id = leave['employee_id'][0]

            # Get employee's expected hours per day
            employee = self.env['hr.employee'].browse(emp_id)
            expected_hours_per_day = self._get_expected_hours(employee, check_date)

            leave_hours = 0.0

            # 1. Half day leave
            if leave.get('request_unit_half'):
                # Get calendar for this employee
                contract = contracts_by_employee.get(emp_id)
                calendar_id = None
                if contract and contract['resource_calendar_id']:
                    calendar_id = contract['resource_calendar_id'][0]
                elif employee.resource_calendar_id:
                    calendar_id = employee.resource_calendar_id.id

                # Get attendance lines
                attendance_lines = []
                if calendar_id and calendar_id in calendar_data:
                    attendance_lines = calendar_data[calendar_id].get('attendance_lines', [])

                # Determine morning or afternoon from date_from time
                is_morning = self._is_morning_half_day(leave.get('date_from'), attendance_lines)

                leave_hours = self._calculate_half_day_leave_hours(
                    attendance_lines,
                    'morning' if is_morning else 'afternoon',
                    expected_hours_per_day
                )

            # 2. Custom hours leave
            elif leave.get('request_unit_hours'):
                # number_of_days contains the hours/days value
                leave_hours = leave.get('number_of_days', 0) * expected_hours_per_day

            # 3. Full day leave
            elif leave['request_date_from'] == check_date and leave['request_date_to'] == check_date:
                leave_hours = expected_hours_per_day

            # 4. Multi-day leave
            else:
                leave_hours = expected_hours_per_day

            leave_hours_by_employee[emp_id] = leave_hours

        # 5. Fetch existing correction records
        existing_corrections = self.search_read([
            ('employee_id', 'in', employee_ids),
            ('date', '=', check_date)
        ], ['employee_id', 'reason_code'])

        # Group existing corrections by employee and reason
        existing_by_employee = {}
        for correction in existing_corrections:
            emp_id = correction['employee_id'][0]
            reason = correction['reason_code']
            if emp_id not in existing_by_employee:
                existing_by_employee[emp_id] = set()
            existing_by_employee[emp_id].add(reason)

        # 6. Bulk fetch public holidays
        holidays_by_employee = {}
        employees_with_calendars = self.env['hr.employee'].browse(employee_ids)

        for employee in employees_with_calendars:
            # Get employee's resource calendar
            contract = contracts_by_employee.get(employee.id)
            if contract and contract['resource_calendar_id']:
                calendar_id = contract['resource_calendar_id'][0]
                calendar = self.env['resource.calendar'].browse(calendar_id)
            elif employee.resource_calendar_id:
                calendar = employee.resource_calendar_id
            else:
                calendar = employee.company_id.resource_calendar_id

            if calendar:
                holiday_impact = self._get_holiday_impact(calendar, check_date)
                holidays_by_employee[employee.id] = holiday_impact

        return {
            'attendance_by_employee': attendance_by_employee,
            'contracts_by_employee': contracts_by_employee,
            'leave_hours_by_employee': leave_hours_by_employee,
            'existing_by_employee': existing_by_employee,
            'calendar_data': calendar_data,
            'holidays_by_employee': holidays_by_employee
        }

    # def _process_employee_batch(self, employees_data, check_date, batch_data):
    #     """
    #     Process a batch of employees and return correction records to create
    #     """
    #     corrections_to_create = []
    #     minute_allowed = self._get_minute_allowed()
    #
    #     for employee_data in employees_data:
    #         employee_id = employee_data['id']
    #
    #         # Skip employees without active contracts
    #         if employee_id not in batch_data['contracts_by_employee']:
    #             continue
    #
    #         # Get expected hours and schedule
    #         expected_hours = self._get_expected_hours_optimized(employee_data, batch_data)
    #         schedule_hours = self._get_schedule_time_range_optimized(employee_data, check_date, batch_data)
    #
    #         # Handle public holidays
    #         holiday_impact = batch_data['holidays_by_employee'].get(employee_id, 'none')
    #         if holiday_impact == 'full_day':
    #             continue  # Skip full day holidays completely
    #
    #         if isinstance(holiday_impact, float) and holiday_impact > 0:
    #             expected_hours = max(0.0, expected_hours - holiday_impact)
    #
    #         # FIXED: Handle leave hours (instead of skipping entire day)
    #         leave_hours = batch_data['leave_hours_by_employee'].get(employee_id, 0.0)
    #
    #         # If full-day leave, skip (no attendance expected)
    #         if leave_hours >= expected_hours:
    #             continue
    #
    #         # Reduce expected hours by leave hours (half-day or custom hours)
    #         if leave_hours > 0:
    #             expected_hours = max(0.0, expected_hours - leave_hours)
    #
    #         # If no hours expected after adjustments, skip
    #         if expected_hours <= 0:
    #             continue
    #
    #         # Get employee's attendance for the date
    #         employee_attendance = batch_data['attendance_by_employee'].get(employee_id, [])
    #
    #         # Check if it's a working day
    #         if not self._is_working_day_optimized(employee_data, check_date, batch_data):
    #             continue
    #
    #         if not employee_attendance:
    #             # NO_SHOW case (but only if they were expected to work)
    #             if 'NO_SHOW' not in batch_data['existing_by_employee'].get(employee_id, set()):
    #                 corrections_to_create.append({
    #                     'employee_id': employee_id,
    #                     'date': check_date,
    #                     'reason_code': 'NO_SHOW',
    #                     'worked_hours': 0.0,
    #                     'expected_hours': expected_hours,  # Already adjusted for leave
    #                     'shortfall': expected_hours,
    #                     'check_in': None,
    #                     'check_out': None,
    #                     'schedule_hours': schedule_hours,
    #                     'department_id': employee_data['department_id'][0] if employee_data['department_id'] else None,
    #                     'company_id': employee_data['company_id'][0] if employee_data['company_id'] else None,
    #                 })
    #         else:
    #             # Check for SHORT_HOURS
    #             completed_attendance = [att for att in employee_attendance]
    #             if completed_attendance:
    #                 total_worked_hours = sum(att['worked_hours'] or 0 for att in completed_attendance)
    #
    #                 if total_worked_hours < expected_hours:  # expected_hours already adjusted
    #                     # Apply grace period logic
    #                     calendar_id = None
    #                     contract = batch_data['contracts_by_employee'].get(employee_id)
    #                     if contract and contract['resource_calendar_id']:
    #                         calendar_id = contract['resource_calendar_id'][0]
    #                     elif employee_data.get('resource_calendar_id'):
    #                         calendar_id = employee_data['resource_calendar_id'][0]
    #
    #                     earliest_start = None
    #                     if calendar_id and calendar_id in batch_data['calendar_data']:
    #                         cal = batch_data['calendar_data'][calendar_id]
    #                         lines = cal.get('attendance_lines', []) or []
    #                         if lines:
    #                             earliest_start = min(line['hour_from'] for line in lines)
    #
    #                     check_in_times = [att['check_in'] for att in completed_attendance if att['check_in']]
    #                     check_out_times = [att['check_out'] for att in completed_attendance if att['check_out']]
    #
    #                     effective_expected_hours = expected_hours
    #                     if earliest_start is not None and check_in_times:
    #                         scheduled_start_dt = datetime.combine(
    #                             check_date,
    #                             time(int(earliest_start), int((earliest_start % 1) * 60))
    #                         )
    #                         actual_first_check_in = min(check_in_times)
    #                         delay_minutes = max(0,
    #                                             int((actual_first_check_in - scheduled_start_dt).total_seconds() // 60))
    #                         discount_minutes = min(delay_minutes, minute_allowed)
    #                         effective_expected_hours = max(0.0, expected_hours - (discount_minutes / 60.0))
    #
    #                     if total_worked_hours < effective_expected_hours:
    #                         if 'SHORT_HOURS' not in batch_data['existing_by_employee'].get(employee_id, set()):
    #                             corrections_to_create.append({
    #                                 'employee_id': employee_id,
    #                                 'date': check_date,
    #                                 'reason_code': 'SHORT_HOURS',
    #                                 'worked_hours': total_worked_hours,
    #                                 'expected_hours': expected_hours,  # Store original adjusted expected hours
    #                                 'shortfall': effective_expected_hours - total_worked_hours,
    #                                 'check_in': min(check_in_times) if check_in_times else None,
    #                                 'check_out': max(check_out_times) if check_out_times else None,
    #                                 'schedule_hours': schedule_hours,
    #                                 'department_id': employee_data['department_id'][0] if employee_data[
    #                                     'department_id'] else None,
    #                                 'company_id': employee_data['company_id'][0] if employee_data[
    #                                     'company_id'] else None,
    #                             })
    #
    #     return corrections_to_create

    #############################################################################################
    def _shortfall_after_tolerance(self, expected_hours, worked_hours):
        """
        Returns (keep_record: bool, shortfall_hours: float)

        - If expected_hours <= worked_hours -> (False, 0.0)
        - raw_shortfall = expected_hours - worked_hours
        - If raw_shortfall (in minutes) <= minute_allowed -> don't keep
        - Else keep and return shortfall = raw_shortfall - (minute_allowed / 60)
        """
        minute_allowed = int(self.env['ir.config_parameter'].sudo().get_param('hr_attendance.minute_allowed', 15))
        raw_shortfall = max(0.0, float(expected_hours) - float(worked_hours or 0.0))
        if raw_shortfall <= 0.0:
            return False, 0.0
        raw_minutes = raw_shortfall * 60.0
        if raw_minutes <= minute_allowed:
            return False, 0.0
        adjusted = raw_shortfall - (minute_allowed / 60.0)
        # round to 4 decimals to be safe for storage/display
        return True, round(adjusted, 4)

    def _process_employee_batch(self, employees_data, check_date, batch_data):
        """
        Process a batch of employees and return correction records to create
        Applies tolerance rule: only create SHORT_HOURS if raw shortfall (mins) > minute_allowed.
        """
        corrections_to_create = []

        for employee_data in employees_data:
            employee_id = employee_data['id']

            # Skip employees without active contracts
            if employee_id not in batch_data['contracts_by_employee']:
                continue

            # Get expected hours and schedule
            expected_hours = self._get_expected_hours_optimized(employee_data, batch_data)
            schedule_hours = self._get_schedule_time_range_optimized(employee_data, check_date, batch_data)

            # Handle public holidays
            holiday_impact = batch_data['holidays_by_employee'].get(employee_id, 'none')
            if holiday_impact == 'full_day':
                continue

            if isinstance(holiday_impact, float) and holiday_impact > 0:
                expected_hours = max(0.0, expected_hours - holiday_impact)

            # Handle leave impact
            leave_hours = batch_data['leave_hours_by_employee'].get(employee_id, 0.0)
            if leave_hours >= expected_hours:
                continue
            if leave_hours > 0:
                expected_hours = max(0.0, expected_hours - leave_hours)

            if expected_hours <= 0:
                continue

            # Get employee's attendance for the date
            employee_attendance = batch_data['attendance_by_employee'].get(employee_id, [])

            # Check if it's a working day
            if not self._is_working_day_optimized(employee_data, check_date, batch_data):
                continue

            # === NO_SHOW ===
            if not employee_attendance:
                if 'NO_SHOW' not in batch_data['existing_by_employee'].get(employee_id, set()):
                    corrections_to_create.append({
                        'employee_id': employee_id,
                        'date': check_date,
                        'reason_code': 'NO_SHOW',
                        'worked_hours': 0.0,
                        'expected_hours': expected_hours,
                        'shortfall': expected_hours,
                        'check_in': None,
                        'check_out': None,
                        'schedule_hours': schedule_hours,
                        'department_id': employee_data['department_id'][0] if employee_data['department_id'] else None,
                        'company_id': employee_data['company_id'][0] if employee_data['company_id'] else None,
                    })
                continue

            # === SHORT_HOURS candidate ===
            # Use only completed attendance records' worked_hours (search_read style dicts)
            completed_attendance = [att for att in employee_attendance]
            if not completed_attendance:
                continue

            total_worked_hours = sum((att.get('worked_hours') or 0.0) for att in completed_attendance)
            # Decide based on raw shortfall vs tolerance
            keep, adjusted_shortfall = self._shortfall_after_tolerance(expected_hours, total_worked_hours)
            if not keep:
                # within tolerance -> do not create SHORT_HOURS
                continue

            # If a SHORT_HOURS already exists, skip creating duplicate
            if 'SHORT_HOURS' in batch_data['existing_by_employee'].get(employee_id, set()):
                continue

            # collect times (optional)
            check_in_times = [att.get('check_in') for att in completed_attendance if att.get('check_in')]
            check_out_times = [att.get('check_out') for att in completed_attendance if att.get('check_out')]

            corrections_to_create.append({
                'employee_id': employee_id,
                'date': check_date,
                'reason_code': 'SHORT_HOURS',
                'worked_hours': total_worked_hours,
                'expected_hours': expected_hours,
                'shortfall': adjusted_shortfall,
                'check_in': min(check_in_times) if check_in_times else None,
                'check_out': max(check_out_times) if check_out_times else None,
                'schedule_hours': schedule_hours,
                'department_id': employee_data['department_id'][0] if employee_data['department_id'] else None,
                'company_id': employee_data['company_id'][0] if employee_data['company_id'] else None,
            })

        return corrections_to_create

    #############################################################################################

    def _get_holiday_impact(self, calendar, check_date):
        """
        Returns holiday impact: 'none', 'full_day', or hours_reduced (float)
        """
        date_start = datetime.combine(check_date, time.min)
        date_end = datetime.combine(check_date, time.max)

        public_holidays = self.env['resource.calendar.leaves'].search([
            ('resource_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
            ('date_from', '<=', date_end),
            ('date_to', '>=', date_start),
            '|',
            ('calendar_id', '=', False),
            ('calendar_id', '=', calendar.id),
        ])

        if not public_holidays:
            return 'none'

        # Get calendar's normal working hours for this day
        weekday = check_date.weekday()
        attendance_lines = calendar.attendance_ids.filtered(
            lambda a: int(a.dayofweek) == weekday
        )

        if not attendance_lines:
            return 'none'

        total_scheduled_hours = sum(
            line.hour_to - line.hour_from for line in attendance_lines
        )

        # Calculate overlap with holidays
        holiday_hours = 0.0
        for holiday in public_holidays:
            # Convert holiday times to hours of day
            holiday_start = holiday.date_from
            holiday_end = holiday.date_to

            # Calculate intersection with working day
            day_start = datetime.combine(check_date, time.min)
            day_end = datetime.combine(check_date, time.max)

            overlap_start = max(holiday_start, day_start)
            overlap_end = min(holiday_end, day_end)

            if overlap_start < overlap_end:
                overlap_hours = (overlap_end - overlap_start).total_seconds() / 3600
                holiday_hours += min(overlap_hours, total_scheduled_hours)

        if holiday_hours >= total_scheduled_hours:
            return 'full_day'
        else:
            return holiday_hours  # Partial day reduction

    @api.model
    def _get_minute_allowed(self) -> int:
        # Grace minutes allowed (global setting)
        return int(self.env['ir.config_parameter'].sudo().get_param('hr_attendance.minute_allowed', 15))

    def _get_expected_hours_optimized(self, employee_data, batch_data):
        """
        Optimized version using pre-fetched data
        """
        employee_id = employee_data['id']

        # Try contract calendar first
        contract = batch_data['contracts_by_employee'].get(employee_id)
        if contract and contract['resource_calendar_id']:
            calendar_id = contract['resource_calendar_id'][0]
            calendar = batch_data['calendar_data'].get(calendar_id)
            if calendar and calendar.get('hours_per_day'):
                return calendar['hours_per_day']

        # Try employee calendar
        if employee_data['resource_calendar_id']:
            calendar_id = employee_data['resource_calendar_id'][0]
            calendar = batch_data['calendar_data'].get(calendar_id)
            if calendar and calendar.get('hours_per_day'):
                return calendar['hours_per_day']

        # Default to 8 hours (company calendar lookup omitted for simplicity)
        return 8.0

    def _get_schedule_time_range_optimized(self, employee_data, check_date, batch_data):
        """
        Optimized version using pre-fetched calendar data
        """
        employee_id = employee_data['id']

        # Get calendar ID
        calendar_id = None
        contract = batch_data['contracts_by_employee'].get(employee_id)
        if contract and contract['resource_calendar_id']:
            calendar_id = contract['resource_calendar_id'][0]
        elif employee_data['resource_calendar_id']:
            calendar_id = employee_data['resource_calendar_id'][0]

        if not calendar_id or calendar_id not in batch_data['calendar_data']:
            return "No Schedule"

        calendar = batch_data['calendar_data'][calendar_id]
        attendance_lines = calendar.get('attendance_lines', [])

        if not attendance_lines:
            return "No Schedule"

        # Find earliest start time and latest end time
        earliest_start = min(line['hour_from'] for line in attendance_lines)
        latest_end = max(line['hour_to'] for line in attendance_lines)

        # Format as HH:MM-HH:MM
        start_time = f"{int(earliest_start):02d}:{int((earliest_start % 1) * 60):02d}"
        end_time = f"{int(latest_end):02d}:{int((latest_end % 1) * 60):02d}"

        return f"{start_time}-{end_time}"

    def _is_working_day_optimized(self, employee_data, check_date, batch_data):
        """
        Optimized working day check using pre-fetched data,
        but allows Sunday/holiday work if company and employee rules permit,
        only when `paid_leave_sunday` module is installed.
        """
        employee_id = employee_data['id']

        # Get calendar ID
        calendar_id = None
        contract = batch_data['contracts_by_employee'].get(employee_id)
        if contract and contract['resource_calendar_id']:
            calendar_id = contract['resource_calendar_id'][0]
        elif employee_data['resource_calendar_id']:
            calendar_id = employee_data['resource_calendar_id'][0]

        # Default flags
        company_rule_enabled = False
        allow_on_non_working_day = False

        # Check if `paid_leave_sunday` is installed
        module_installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'paid_leave_sunday'),
            ('state', '=', 'installed')
        ]) > 0

        if module_installed:
            # Get company record
            company_id = employee_data['company_id'][0] if employee_data['company_id'] else None
            if company_id:
                company = self.env['res.company'].browse(company_id)
                company_rule_enabled = bool(company.Enable_Sunday_Rule)

            # Get employee record
            emp_record = self.env['hr.employee'].browse(employee_id)
            if emp_record.Allow_work_on_sunday:
                allow_on_non_working_day = True

        # If no calendar data
        if not calendar_id or calendar_id not in batch_data['calendar_data']:
            if company_rule_enabled and allow_on_non_working_day:
                return True
            return False

        calendar = batch_data['calendar_data'][calendar_id]
        attendance_lines = calendar.get('attendance_lines', [])

        if attendance_lines:
            return True

        if company_rule_enabled and allow_on_non_working_day:
            return True

        return False

    # Keep the original methods for backward compatibility and individual operations
    def _get_expected_hours(self, employee, check_date):
        """Original method - kept for backward compatibility"""
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', check_date),
            '|', ('date_end', '=', False), ('date_end', '>=', check_date)
        ], limit=1)

        if contract and contract.resource_calendar_id:
            return contract.resource_calendar_id.hours_per_day

        if employee.resource_calendar_id:
            return employee.resource_calendar_id.hours_per_day

        if employee.company_id.resource_calendar_id:
            return employee.company_id.resource_calendar_id.hours_per_day

        return 8.0

    def _get_schedule_time_range(self, employee, check_date):
        """Original method - kept for backward compatibility"""
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', check_date),
            '|', ('date_end', '=', False), ('date_end', '>=', check_date)
        ], limit=1)

        calendar = None
        if contract and contract.resource_calendar_id:
            calendar = contract.resource_calendar_id
        elif employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
        elif employee.company_id.resource_calendar_id:
            calendar = employee.company_id.resource_calendar_id

        if not calendar:
            return "No Schedule"

        weekday = check_date.weekday()
        attendance_lines = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == weekday)
        if not attendance_lines:
            return "No Schedule"

        earliest_start = min(attendance_lines.mapped('hour_from'))
        latest_end = max(attendance_lines.mapped('hour_to'))

        start_time = f"{int(earliest_start):02d}:{int((earliest_start % 1) * 60):02d}"
        end_time = f"{int(latest_end):02d}:{int((latest_end % 1) * 60):02d}"

        return f"{start_time}-{end_time}"

    def _is_working_day(self, employee, check_date):
        """Original method - kept for backward compatibility"""
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', check_date),
            '|', ('date_end', '=', False), ('date_end', '>=', check_date)
        ], limit=1)

        calendar = None
        if contract and contract.resource_calendar_id:
            calendar = contract.resource_calendar_id
        elif employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
        elif employee.company_id.resource_calendar_id:
            calendar = employee.company_id.resource_calendar_id

        if not calendar:
            return False

        day_of_week = check_date.weekday()
        return calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == day_of_week)

    @api.model
    def scheduled_attendance_check(self):
        """
        Scheduled action method to check attendance for the previous day
        """
        yesterday = date.today() - timedelta(days=1)
        _logger.info(f"Scheduled attendance check running at {datetime.now()}")
        _logger.info(f"Checking attendance for previous day: {yesterday}")

        records_created = self.check_attendance_for_date(yesterday)
        _logger.info(f"Scheduled check completed. Created {records_created} records for {yesterday}")
        return records_created

    @api.model
    def manual_attendance_check(self, check_date=None, employee_ids=None):
        if not check_date:
            check_date = date.today()

        # Step 1: get employees
        employees = self.env['hr.employee']
        if employee_ids:
            employees = employees.browse(employee_ids)
        else:
            employees = employees.search([])  # all employees

        # Step 2: filter out those with disable_tracking = True
        employees = employees.filtered(lambda e: not e.disable_tracking)
        if not employees:
            _logger.info(f"No eligible employees for manual attendance on {check_date}")
            return 0

        _logger.info(f"Manual attendance check for date: {check_date}, employees: {[e.name for e in employees]}")
        return self.check_attendance_for_date(check_date, employee_ids=employees.ids)

    def action_bulk_no_show_create(self):
        """
        Optimized bulk create attendance for selected NO_SHOW corrections
        """
        Attendance = self.env['hr.attendance']
        # Case 1: No record selected at all
        if not self:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("No Records"),
                    'message': _("Please select at least one record."),
                    'sticky': False,
                    'type': 'warning',
                }
            }

        # Case 2: Records selected, but none are NO_SHOW
        no_show_records = self.sudo().filtered(lambda r: r.reason_code == 'NO_SHOW')
        if not no_show_records:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("No Add Records"),
                    'message': _("Please select at least one 'NO SHOW' record."),
                    'sticky': False,
                    'type': 'warning',
                }
            }

        created = 0
        errors = []
        attendance_to_create = []
        records_to_delete = []

        # Bulk fetch existing attendance data to avoid N+1 queries
        employee_ids = no_show_records.mapped('employee_id.id')
        dates = list(set(no_show_records.mapped('date')))

        # Create date ranges for bulk query
        existing_attendance = {}
        for check_date in dates:
            date_start = datetime.combine(check_date, time.min)
            date_end = datetime.combine(check_date, time.max)

            attendance_data = Attendance.sudo().search_read([
                ('employee_id', 'in', employee_ids),
                ('check_in', '>=', date_start),
                ('check_in', '<=', date_end)
            ], ['employee_id', 'worked_hours'])

            for att in attendance_data:
                key = (att['employee_id'][0], check_date)
                if key not in existing_attendance:
                    existing_attendance[key] = []
                existing_attendance[key].append(att)

        for rec in no_show_records:
            # Check if employee already has sufficient attendance for this date
            key = (rec.employee_id.id, rec.date)
            existing_att = existing_attendance.get(key, [])

            if existing_att:
                total_worked_hours = sum(att['worked_hours'] or 0 for att in existing_att)
                expected_hours = rec.expected_hours or 8.0

                if total_worked_hours >= (expected_hours * 0.8):
                    errors.append(
                        f"Employee {rec.employee_id.name} already has {total_worked_hours:.1f}h attendance on {rec.date}")
                    records_to_delete.append(rec.id)
                    continue

            # Get work schedule start and end times
            check_in, check_out = self._get_workday_start_end_times(rec.employee_id, rec.date)
            if not check_in or not check_out:
                errors.append(f"No work schedule found for {rec.employee_id.name} on {rec.date}")
                continue

            # Prepare attendance record for bulk creation
            attendance_to_create.append({
                'employee_id': rec.employee_id.id,
                'check_in': check_in,
                'check_out': check_out,
                'attendance_note': 'No show manual adjustment',
            })
            records_to_delete.append(rec.id)
            created += 1

        # Bulk create attendance records
        if attendance_to_create:
            try:
                Attendance.sudo().create(attendance_to_create)
            except Exception as e:
                raise UserError(f"Failed to create attendance records: {str(e)}")

        # Bulk delete correction records
        if records_to_delete:
            self.browse(records_to_delete).unlink()

        # === Sticky Notification Response ===
        message = f"Created {created} attendance records."
        if errors:
            message += f"\n{len(errors)} issues encountered."
            for error in errors[:3]:
                message += f"\n- {error}"
            if len(errors) > 3:
                message += f"\n... and {len(errors) - 3} more"

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Attendance Bulk Update"),
                'message': message,
                'sticky': False,
                'type': 'success' if created else 'warning',
                "next": {
                    "type": "ir.actions.act_window_close",
                }
            }
        }

    def _get_workday_start_end_times(self, employee, work_date):
        """Get the earliest start time and latest end time for the employee's workday."""
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', work_date),
            '|', ('date_end', '=', False), ('date_end', '>=', work_date)
        ], limit=1)

        calendar = None
        if contract and contract.resource_calendar_id:
            calendar = contract.resource_calendar_id
        elif employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
        elif employee.company_id.resource_calendar_id:
            calendar = employee.company_id.resource_calendar_id

        if not calendar:
            return (None, None)

        weekday = work_date.weekday()
        attendance_lines = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == weekday)

        # Fallback: if no schedule found for this day (holiday/week off), pick first available working day
        if not attendance_lines:
            # All attendance lines sorted by dayofweek
            all_days_with_attendance = calendar.attendance_ids.sorted(key=lambda a: a.dayofweek)

            if all_days_with_attendance:
                # Get the earliest dayofweek in the schedule
                first_day = all_days_with_attendance[0].dayofweek

                # Filter lines for just that first day
                first_day_lines = all_days_with_attendance.filtered(lambda l: l.dayofweek == first_day)

                earliest_start = min(first_day_lines.mapped('hour_from'))
                latest_end = max(first_day_lines.mapped('hour_to'))
            else:
                return (None, None)
        else:
            earliest_start = min(attendance_lines.mapped('hour_from'))
            latest_end = max(attendance_lines.mapped('hour_to'))

        # Get user timezone
        user_tz = self.env.user.tz or 'UTC'
        check_in_local = datetime.combine(work_date, time(int(earliest_start), int((earliest_start % 1) * 60)))
        check_out_local = datetime.combine(work_date, time(int(latest_end), int((latest_end % 1) * 60)))

        local_tz = pytz.timezone(user_tz)
        utc_tz = pytz.UTC

        check_in_local = local_tz.localize(check_in_local)
        check_out_local = local_tz.localize(check_out_local)

        check_in_utc = check_in_local.astimezone(utc_tz).replace(tzinfo=None)
        check_out_utc = check_out_local.astimezone(utc_tz).replace(tzinfo=None)

        return (check_in_utc, check_out_utc)

    def action_add_attendance(self):
        """For NO_SHOW: Create a single attendance record for this employee/date and remove the correction."""
        self.ensure_one()
        if self.reason_code != 'NO_SHOW':
            raise UserError("This action is only for NO SHOW records.")

        check_in, check_out = self._get_workday_start_end_times(self.employee_id, self.date)
        if not check_in or not check_out:
            raise UserError("No work schedule found for this employee on this date.")

        self.env['hr.attendance'].create({
            'employee_id': self.employee_id.id,
            'check_in': check_in,
            'check_out': check_out,
            'attendance_note': 'No show manual adjustment',
        })
        self.unlink()
        return True

    def action_edit_attendance(self):
        """For SHORT_HOURS: Open the related attendance record(s) for editing."""
        self.ensure_one()

        if self.reason_code != 'SHORT_HOURS':
            raise UserError("This action is only for SHORT HOURS records.")

        return {
            'name': _('Edit Attendance'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance',
            'view_mode': 'tree,form',
            'domain': [
                ('employee_id', '=', self.employee_id.id),
                ('check_in', '>=', datetime.combine(self.date, time.min)),
                ('check_in', '<=', datetime.combine(self.date, time.max))
            ],
            'context': {
                'default_employee_id': self.employee_id.id,
                'default_check_in': self.date,
                'from_correction': True,  # Important flag for the write override
                'correction_record_id': self.id,  # Optional: track which correction triggered this
            },
            'target': 'current',
        }

    # def adjust_for_leave(self, employee, date, leave_hours, reverse=False):
    #     """
    #     Adjust or recreate correction records based on leave approval or cancellation.
    #
    #     :param employee: hr.employee record
    #     :param date: date object
    #     :param leave_hours: number of hours the leave covered
    #     :param reverse: True if leave is cancelled
    #     """
    #     _logger.info(f"{'Reversing' if reverse else 'Adjusting'} corrections for {employee.name} on {date}")
    #
    #     Attendance = self.env['hr.attendance']
    #     date_start = datetime.combine(date, time.min)
    #     date_end = datetime.combine(date, time.max)
    #
    #     # --- Case 1: Leave cancellation (reverse=True) ---
    #     if reverse:
    #         # Fetch all attendance for that employee/date
    #         attendances = Attendance.sudo().search([
    #             ('employee_id', '=', employee.id),
    #             ('check_in', '>=', date_start),
    #             ('check_in', '<=', date_end)
    #         ])
    #
    #         total_worked_hours = sum(att.worked_hours or 0.0 for att in attendances)
    #         expected_hours = self._get_expected_hours(employee, date)
    #         minute_allowed = self._get_minute_allowed()
    #
    #         # Apply grace period (if late)
    #         if attendances:
    #             earliest_check_in = min(attendances.mapped('check_in'))
    #             scheduled_start = self.env['hr.attendance']._get_scheduled_start_time(employee, date)
    #             if scheduled_start:
    #                 delay_minutes = max(0, int((earliest_check_in - scheduled_start).total_seconds() // 60))
    #                 discount_minutes = min(delay_minutes, minute_allowed)
    #                 expected_hours = max(0.0, expected_hours - (discount_minutes / 60.0))
    #
    #         # Check if record already exists
    #         existing_correction = self.search([
    #             ('employee_id', '=', employee.id),
    #             ('date', '=', date),
    #         ])
    #
    #         # Decision logic
    #         if total_worked_hours == 0:
    #             reason_code = 'NO_SHOW'
    #         elif total_worked_hours < expected_hours:
    #             reason_code = 'SHORT_HOURS'
    #         else:
    #             # Hours sufficient → remove any old corrections
    #             if existing_correction:
    #                 existing_correction.unlink()
    #             return
    #
    #         shortfall = expected_hours - total_worked_hours
    #
    #         vals = {
    #             'employee_id': employee.id,
    #             'date': date,
    #             'reason_code': reason_code,
    #             'worked_hours': total_worked_hours,
    #             'expected_hours': expected_hours,
    #             'shortfall': shortfall,
    #             'check_in': min(attendances.mapped('check_in')) if attendances else None,
    #             'check_out': max(attendances.mapped('check_out')) if attendances else None,
    #             'schedule_hours': self._get_schedule_time_range(employee, date),
    #             'department_id': employee.department_id.id if employee.department_id else None,
    #             'company_id': employee.company_id.id if employee.company_id else None,
    #         }
    #
    #         if existing_correction:
    #             existing_correction.write(vals)
    #             _logger.info(f"Updated correction after leave cancellation for {employee.name} on {date}")
    #         else:
    #             self.create(vals)
    #             _logger.info(f"Created correction after leave cancellation for {employee.name} on {date}")
    #
    #         return
    #
    #     # --- Case 2: Leave validated (reverse=False) ---
    #     corrections = self.search([
    #         ('employee_id', '=', employee.id),
    #         ('date', '=', date),
    #         ('reason_code', 'in', ['SHORT_HOURS', 'NO_SHOW'])
    #     ])
    #     if not corrections:
    #         return
    #
    #     for correction in corrections:
    #         if leave_hours >= correction.expected_hours:
    #             # Leave fully covers expected hours → remove correction
    #             _logger.info(f"Removing correction for full-day leave on {date} ({employee.name})")
    #             correction.unlink()
    #         else:
    #             # Partial leave → reduce expected/shortfall
    #             new_expected = max(0.0, correction.expected_hours - leave_hours)
    #             new_shortfall = max(0.0, correction.shortfall - leave_hours)
    #
    #             if new_shortfall < 0.1:
    #                 correction.unlink()
    #                 _logger.info(f"Shortfall fully covered by leave; removed correction for {employee.name} on {date}")
    #             else:
    #                 correction.write({
    #                     'expected_hours': new_expected,
    #                     'shortfall': new_shortfall,
    #                 })
    #                 _logger.info(f"Adjusted correction for {employee.name} on {date} due to leave (-{leave_hours}h)")

    #########################################################################
    def adjust_for_leave(self, employee, date, leave_hours, reverse=False):
        """
        Adjust or recreate correction records based on leave approval or cancellation.
        Uses the same tolerance rule: only keep SHORT_HOURS if raw_shortfall_minutes > minute_allowed.
        """
        _logger.info(f"{'Reversing' if reverse else 'Adjusting'} corrections for {employee.name} on {date}")

        Attendance = self.env['hr.attendance']
        date_start = datetime.combine(date, time.min)
        date_end = datetime.combine(date, time.max)

        # Fetch attendance for that employee/date
        attendances = Attendance.sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', date_start),
            ('check_in', '<=', date_end)
        ])

        total_worked_hours = sum(att.worked_hours or 0.0 for att in attendances)

        # Compute expected hours after leave effect (if validating leave), or normal expected (if reversing)
        base_expected = self._get_expected_hours(employee, date)
        if not reverse:
            # leave validated → reduce expected by leave_hours for that date
            expected_hours = max(0.0, base_expected - (leave_hours or 0.0))
        else:
            expected_hours = base_expected

        # If no attendance -> NO_SHOW (unless leave covers full day)
        existing_correction = self.search([('employee_id', '=', employee.id), ('date', '=', date)])

        if not attendances:
            # If leave approved and it covered full day expected_hours, then remove correction
            if not reverse and (leave_hours >= base_expected):
                if existing_correction:
                    existing_correction.unlink()
                return

            # Create NO_SHOW if no attendance (we keep older behavior)
            no_show = existing_correction.filtered(lambda r: r.reason_code == 'NO_SHOW')
            if not no_show:
                self.create({
                    'employee_id': employee.id,
                    'date': date,
                    'reason_code': 'NO_SHOW',
                    'worked_hours': 0.0,
                    'expected_hours': expected_hours,
                    'shortfall': expected_hours,
                    'check_in': None,
                    'check_out': None,
                    'schedule_hours': self._get_schedule_time_range(employee, date),
                    'department_id': employee.department_id.id if employee.department_id else None,
                    'company_id': employee.company_id.id if employee.company_id else None,
                })
            # Remove any SHORT_HOURS (no attendance)
            existing_correction.filtered(lambda r: r.reason_code == 'SHORT_HOURS').unlink()
            return

        # With attendance, compute raw shortfall and apply tolerance rule
        keep, adjusted_shortfall = self._shortfall_after_tolerance(expected_hours, total_worked_hours)

        # If within tolerance -> remove corrections
        if not keep:
            if existing_correction:
                existing_correction.unlink()
                _logger.info(
                    f"Removed corrections for {employee.name} on {date} after leave adjustment (within tolerance)")
            return

        # Keep / create SHORT_HOURS record with adjusted_shortfall
        short_rec = existing_correction.filtered(lambda r: r.reason_code == 'SHORT_HOURS')
        adjusted_shortfall = round(adjusted_shortfall, 2)
        vals = {
            'employee_id': employee.id,
            'date': date,
            'reason_code': 'SHORT_HOURS',
            'worked_hours': total_worked_hours,
            'expected_hours': expected_hours,
            'shortfall': adjusted_shortfall,
            'check_in': min(attendances.mapped('check_in')) if attendances else None,
            'check_out': max(attendances.mapped('check_out')) if attendances else None,
            'schedule_hours': self._get_schedule_time_range(employee, date),
            'department_id': employee.department_id.id if employee.department_id else None,
            'company_id': employee.company_id.id if employee.company_id else None,
        }
        if short_rec:
            short_rec.write(vals)
            _logger.info(f"Updated SHORT_HOURS for {employee.name} on {date} after leave adjustment")
        else:
            self.create(vals)
            _logger.info(f"Created SHORT_HOURS for {employee.name} on {date} after leave adjustment")

    #########################################################################


class AttendanceCheckWizard(models.TransientModel):
    _name = 'attendance.check.wizard'
    _description = 'Manual Attendance Check Wizard'

    check_date_from = fields.Date(string="From Date", required=True, default=fields.Date.today)
    check_date_to = fields.Date(string="To Date", required=True, default=fields.Date.today)
    employee_ids = fields.Many2many(
        'hr.employee',
        string="Employees",
        help="Select employees to check. Leave empty to check all employees."
    )

    @api.constrains('check_date_from', 'check_date_to')
    def _check_date_range(self):
        for record in self:
            if record.check_date_from > record.check_date_to:
                raise ValidationError("From Date must be earlier than or equal to To Date.")

            # Optional: limit range to prevent performance issues
            date_diff = (record.check_date_to - record.check_date_from).days
            if date_diff > 31:  # More than 31 days
                raise ValidationError("Date range cannot exceed 31 days.")

    def action_run_manual_check(self):
        AttendanceCorrection = self.env['temp.attendance.correction']
        total_records = 0

        current_date = self.check_date_from
        while current_date <= self.check_date_to:
            # Pass only employee ids selected in wizard
            employee_ids = self.employee_ids.ids if self.employee_ids else None
            daily_records = AttendanceCorrection.manual_attendance_check(
                current_date,
                employee_ids=employee_ids
            )
            total_records += daily_records
            _logger.info(f"Processed {daily_records} records for {current_date}")
            current_date += timedelta(days=1)

        _logger.info(f"Manual attendance check completed. Total records created: {total_records}")

        # Notification
        lang = self.env.user.lang or "en_US"
        date_from_str = format_date(self.env, self.check_date_from, lang_code=lang)
        date_to_str = format_date(self.env, self.check_date_to, lang_code=lang)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Attendance Check Completed',
                'message': f'Created {total_records} correction records from {date_from_str} to {date_to_str}',
                'type': 'success',
                'sticky': False,
                "next": {"type": "ir.actions.act_window_close"}
            }
        }
