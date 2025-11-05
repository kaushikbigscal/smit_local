# -*- coding: utf-8 -*-
from odoo import models, api
import logging
from datetime import datetime, time, timedelta

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # def _compute_leave_hours_in_schedule(self, employee, date):
    #     """Compute leave hours for a given date respecting schedule and breaks."""
    #     import pytz
    #     from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
    #
    #     # Calendar attendance lines
    #     calendar = employee.contract_id.resource_calendar_id or employee.resource_calendar_id or employee.company_id.resource_calendar_id
    #     lines = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == date.weekday())
    #
    #     if not lines:
    #         return 0.0
    #
    #     # Localize leave start/end to user's timezone
    #     user_tz = self.env.user.tz or 'UTC'
    #     leave_start = self.date_from.astimezone(pytz.timezone(user_tz))
    #     leave_end = self.date_to.astimezone(pytz.timezone(user_tz))
    #
    #     # Limit leave_start/leave_end to this date
    #     leave_start = max(leave_start, datetime.combine(date, time.min, tzinfo=leave_start.tzinfo))
    #     leave_end = min(leave_end, datetime.combine(date, time.max, tzinfo=leave_end.tzinfo))
    #
    #     total_leave_hours = 0.0
    #
    #     for line in lines:
    #         # Convert float hour to time
    #         work_start_time = (datetime.min + timedelta(hours=line.hour_from)).time()
    #         work_end_time = (datetime.min + timedelta(hours=line.hour_to)).time()
    #
    #         # Convert to datetime for this date
    #         work_start = datetime.combine(date, work_start_time, tzinfo=leave_start.tzinfo)
    #         work_end = datetime.combine(date, work_end_time, tzinfo=leave_end.tzinfo)
    #
    #         # Compute overlap
    #         overlap_start = max(leave_start, work_start)
    #         overlap_end = min(leave_end, work_end)
    #
    #         if overlap_end > overlap_start:
    #             total_leave_hours += (overlap_end - overlap_start).total_seconds() / 3600.0
    #
    #     return total_leave_hours
    #
    # def _get_leave_hours_for_day(self, employee, date):
    #     """Compute number of hours of leave for the given date."""
    #     correction_model = self.env['temp.attendance.correction']
    #     expected_hours = correction_model._get_expected_hours(employee, date)
    #
    #     if self.request_unit_half:
    #         # Morning or afternoon half-day
    #         half_type = 'morning' if self.date_from.hour < 12 else 'afternoon'
    #         calendar = employee.contract_id.resource_calendar_id or employee.resource_calendar_id or employee.company_id.resource_calendar_id
    #         lines = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == date.weekday())
    #         return correction_model._calculate_half_day_leave_hours(
    #             [{'hour_from': a.hour_from, 'hour_to': a.hour_to} for a in lines],
    #             half_type,
    #             expected_hours
    #         )
    #
    #     # elif self.request_unit_hours:
    #     #     return self.number_of_days * expected_hours
    #
    #     elif self.request_unit_hours:
    #         # Compute leave hours according to schedule
    #         leave_hours = self._compute_leave_hours_in_schedule(employee, date)
    #         expected_hours = correction_model._get_expected_hours(employee, date)
    #         print(leave_hours, expected_hours)
    #
    #         # Compute fraction of day
    #         fraction_of_day = leave_hours / expected_hours if expected_hours else 0.0
    #         # Truncate to 3 decimal places
    #         fraction_of_day = int(fraction_of_day * 1000) / 1000.0
    #         print('fraction_of_day', fraction_of_day)
    #
    #         # Round fraction of day to nearest 1 day equivalent and multiply back
    #         final_hours = fraction_of_day * expected_hours
    #         print('final_hours', final_hours)
    #         return final_hours
    #
    #     else:
    #         return expected_hours  # Full day leave

    def _compute_leave_hours_in_schedule(self, employee, date):
        """Compute leave hours for a given date respecting schedule and breaks."""
        import pytz
        from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

        # Calendar attendance lines
        calendar = employee.contract_id.resource_calendar_id or employee.resource_calendar_id or employee.company_id.resource_calendar_id
        lines = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == date.weekday())

        _logger.info("Computing scheduled leave hours for Employee: %s, Date: %s", employee.name, date)
        _logger.info("Attendance lines found: %s", [(a.hour_from, a.hour_to) for a in lines])

        if not lines:
            _logger.info("No attendance lines for this date, returning 0 hours")
            return 0.0

        # Localize leave start/end to user's timezone
        user_tz = self.env.user.tz or 'UTC'
        leave_start = self.date_from.astimezone(pytz.timezone(user_tz))
        leave_end = self.date_to.astimezone(pytz.timezone(user_tz))

        _logger.info("Localized leave start: %s, leave end: %s, timezone: %s", leave_start, leave_end, user_tz)

        # Limit leave_start/leave_end to this date
        leave_start = max(leave_start, datetime.combine(date, time.min, tzinfo=leave_start.tzinfo))
        leave_end = min(leave_end, datetime.combine(date, time.max, tzinfo=leave_end.tzinfo))

        total_leave_hours = 0.0

        for line in lines:
            # Convert float hour to time
            work_start_time = (datetime.min + timedelta(hours=line.hour_from)).time()
            work_end_time = (datetime.min + timedelta(hours=line.hour_to)).time()

            # Convert to datetime for this date
            work_start = datetime.combine(date, work_start_time, tzinfo=leave_start.tzinfo)
            work_end = datetime.combine(date, work_end_time, tzinfo=leave_end.tzinfo)

            # Compute overlap
            overlap_start = max(leave_start, work_start)
            overlap_end = min(leave_end, work_end)

            if overlap_end > overlap_start:
                hours = (overlap_end - overlap_start).total_seconds() / 3600.0
                total_leave_hours += hours
                _logger.info(
                    "Overlap found: work_start=%s, work_end=%s, leave_start=%s, leave_end=%s, hours=%s",
                    work_start, work_end, overlap_start, overlap_end, hours
                )
            else:
                _logger.info(
                    "No overlap for this attendance line: work_start=%s, work_end=%s", work_start, work_end
                )

        _logger.info("Total leave hours for date %s: %s", date, total_leave_hours)
        return total_leave_hours

    def _get_leave_hours_for_day(self, employee, date):
        """Compute number of hours of leave for the given date."""
        correction_model = self.env['temp.attendance.correction']
        expected_hours = correction_model._get_expected_hours(employee, date)
        _logger.info("Computing leave hours for Employee: %s, Date: %s", employee.name, date)
        _logger.info("Expected hours for this employee on this date: %s", expected_hours)

        if self.request_unit_half:
            # Morning or afternoon half-day
            half_type = 'morning' if self.date_from.hour < 12 else 'afternoon'
            calendar = employee.contract_id.resource_calendar_id or employee.resource_calendar_id or employee.company_id.resource_calendar_id
            lines = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == date.weekday())
            _logger.info("Half-day leave detected (%s), attendance lines: %s", half_type,
                         [(a.hour_from, a.hour_to) for a in lines])
            hours = correction_model._calculate_half_day_leave_hours(
                [{'hour_from': a.hour_from, 'hour_to': a.hour_to} for a in lines],
                half_type,
                expected_hours
            )
            _logger.info("Computed half-day leave hours: %s", hours)
            return hours

        elif self.request_unit_hours:
            # Compute leave hours according to schedule
            leave_hours = self._compute_leave_hours_in_schedule(employee, date)
            expected_hours = correction_model._get_expected_hours(employee, date)
            _logger.info("Leave hours from schedule computation: %s", leave_hours)
            _logger.info("Expected hours: %s", expected_hours)

            # Compute fraction of day
            fraction_of_day = leave_hours / expected_hours if expected_hours else 0.0
            # Truncate to 3 decimal places
            fraction_of_day = int(fraction_of_day * 1000) / 1000.0
            _logger.info("Fraction of day (truncated 3 decimals): %s", fraction_of_day)

            # Multiply back to expected hours
            final_hours = fraction_of_day * expected_hours
            _logger.info("Final leave hours returned: %s", final_hours)
            return final_hours

        else:
            _logger.info("Full day leave detected, returning expected hours: %s", expected_hours)
            return expected_hours  # Full day leave

    # --- Leave Validate ---
    def action_validate(self):
        """On leave approval, adjust attendance corrections."""
        res = super(HrLeave, self).action_validate()
        correction_model = self.env['temp.attendance.correction'].sudo()

        for leave in self:
            employee = leave.employee_id
            current_date = leave.request_date_from
            while current_date <= leave.request_date_to:
                leave_hours = leave._get_leave_hours_for_day(employee, current_date)
                _logger.info(f" leave hours for date: {current_date}, {leave_hours}")
                correction_model.adjust_for_leave(employee, current_date, leave_hours, reverse=False)
                current_date += timedelta(days=1)

        return res

    # --- Leave Cancel ---
    def action_refuse(self):
        """On leave cancellation, restore/recheck corrections."""
        res = super(HrLeave, self).action_refuse()
        correction_model = self.env['temp.attendance.correction'].sudo()

        for leave in self:
            employee = leave.employee_id
            current_date = leave.request_date_from
            while current_date <= leave.request_date_to:
                leave_hours = leave._get_leave_hours_for_day(employee, current_date)
                correction_model.adjust_for_leave(employee, current_date, leave_hours, reverse=True)
                current_date += timedelta(days=1)

        return res

# # -*- coding: utf-8 -*-
# from odoo import models, api
# from datetime import datetime, timedelta, time
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class HrLeave(models.Model):
#     _inherit = 'hr.leave'
#
#     def action_validate(self):
#         """Override leave approval to auto-adjust attendance corrections."""
#         res = super(HrLeave, self).action_validate()
#         correction_model = self.env['temp.attendance.correction'].sudo()
#
#         for leave in self:
#             employee = leave.employee_id
#             start_date = leave.request_date_from
#             end_date = leave.request_date_to
#
#             # Iterate over all dates in the leave range
#             current_date = start_date
#             while current_date <= end_date:
#                 corrections = correction_model.search([
#                     ('employee_id', '=', employee.id),
#                     ('date', '=', current_date),
#                     ('reason_code', 'in', ['SHORT_HOURS', 'NO_SHOW'])
#                 ])
#                 if not corrections:
#                     current_date += timedelta(days=1)
#                     continue
#
#                 # Get leave hours for this specific day
#                 expected_hours = correction_model._get_expected_hours(employee, current_date)
#                 leave_hours = 0.0
#
#                 if leave.request_unit_half:
#                     # Determine morning/afternoon type
#                     half_type = 'morning' if leave.date_from.hour < 12 else 'afternoon'
#                     calendar = employee.contract_id.resource_calendar_id or employee.resource_calendar_id or employee.company_id.resource_calendar_id
#                     attendance_lines = calendar.attendance_ids.filtered(
#                         lambda a: int(a.dayofweek) == current_date.weekday())
#                     leave_hours = correction_model._calculate_half_day_leave_hours(
#                         [{'hour_from': a.hour_from, 'hour_to': a.hour_to} for a in attendance_lines],
#                         half_type,
#                         expected_hours
#                     )
#                 elif leave.request_unit_hours:
#                     leave_hours = leave.number_of_days * expected_hours
#                 else:
#                     leave_hours = expected_hours  # Full day leave
#
#                 for correction in corrections:
#                     # If leave fully covers expected hours → remove correction
#                     if leave_hours >= correction.expected_hours:
#                         _logger.info(f"Removing correction for full-day leave on {current_date} ({employee.name})")
#                         correction.unlink()
#                     else:
#                         # Partial leave – reduce expected/shortfall proportionally
#                         new_expected = max(0.0, correction.expected_hours - leave_hours)
#                         new_shortfall = max(0.0, correction.shortfall - leave_hours)
#                         if new_shortfall < 0.1:
#                             _logger.info(
#                                 f"Shortfall covered by leave; removing correction on {current_date} ({employee.name})")
#                             correction.unlink()
#                         else:
#                             correction.write({
#                                 'expected_hours': new_expected,
#                                 'shortfall': new_shortfall,
#                             })
#                             _logger.info(
#                                 f"Updated correction for {employee.name} on {current_date}: -{leave_hours}h from leave")
#
#                 current_date += timedelta(days=1)
#
#         return res
