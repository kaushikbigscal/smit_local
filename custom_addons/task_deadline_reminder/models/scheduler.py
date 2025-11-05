from odoo import models, fields, api
from datetime import datetime, time

class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    @api.model
    def process_attendance_and_day_out(self):
        today_date = fields.Date.today()

        open_attendances = self.env['hr.attendance'].search([
            ('check_in', '!=', False),
            ('check_out', '=', False),
        ])
        company = self.env.company
        company_auto_day_out = getattr(company, 'auto_day_out', False)

        for attendance in open_attendances:
            employee = attendance.employee_id
            user = getattr(employee, 'user_id', False)

            user_auto_day_out = getattr(user, 'auto_day_out', False)

            # Proceed only if both user and company have auto_day_out enabled
            if not (user_auto_day_out and company_auto_day_out):
                continue

            calendar = employee.resource_calendar_id
            weekday = today_date.weekday()  # Monday=0

            # Filter attendance rules for today
            today_shift_lines = calendar.attendance_ids.filtered(
                lambda line: int(line.dayofweek) == weekday
            )
            if not today_shift_lines:
                continue

            # Get latest shift end time
            latest_shift = max(today_shift_lines, key=lambda l: l.hour_to)
            shift_hour_to = latest_shift.hour_to

            hour = int(shift_hour_to)
            minute = int((shift_hour_to % 1) * 60)
            check_out_time = datetime.combine(today_date, time(hour, minute))

            # Only update if check_out is after check_in
            if check_out_time > attendance.check_in:
                attendance.write({'check_out': check_out_time})









    # @api.model
    # def process_attendance_and_day_out(self):
    #     today_date = fields.Date.today()
    #     print("1",today_date)
    #
    #     open_attendances = self.env['hr.attendance'].search([
    #         ('check_in', '!=', False),
    #         ('check_out', '=', False),
    #     ])
    #     print("2",open_attendances)
    #
    #     for attendance in open_attendances:
    #         employee = attendance.employee_id
    #         user = employee.user_id
    #         company = self.env.company
    #
    #         user_flag = user.auto_day_out if user else False
    #         print("3",user_flag)
    #         company_flag = company.auto_day_out if company else False
    #         print("4",company_flag)
    #
    #         if user_flag and company_flag:
    #             calendar = employee.resource_calendar_id
    #             weekday = today_date.weekday()  # Monday = 0
    #             print("5",weekday)
    #
    #             # Find today's attendance rules
    #             shift_lines = calendar.attendance_ids.filtered(
    #                 lambda l: int(l.dayofweek) == weekday
    #             )
    #             if not shift_lines:
    #                 continue
    #
    #             # Pick the latest shift's end time
    #             latest_shift = max(shift_lines, key=lambda l: l.hour_to)
    #             shift_hour_to = latest_shift.hour_to
    #
    #             # Convert to datetime
    #             hour = int(shift_hour_to)
    #             minute = int((shift_hour_to % 1) * 60)
    #             check_out_time = datetime.combine(today_date, time(hour, minute))
    #             print("6",check_out_time)
    #
    #             # Only write if check_out is after check_in
    #             if check_out_time > attendance.check_in:
    #                 attendance.write({'check_out': check_out_time})
    #             print("done")





