from odoo import http
from odoo.http import request
from odoo.tools import float_round
import datetime


class CustomHrAttendanceController(http.Controller):

    @http.route('/web/attendance/check_in_out', type="json", auth="user")
    def custom_attendance_check_in_out(self, latitude=False, longitude=False,
                                       check_in_address=None, check_out_address=None):
        user = request.env.user
        employee = user.employee_id

        if not employee:
            return {'error': 'No employee linked to user'}

        # Determine attendance action: check-in or check-out
        attendance = employee.attendance_ids.filtered(lambda att: not att.check_out)
        mode = 'check_out' if attendance else 'check_in'
        now = datetime.datetime.now()

        vals = {
            'employee_id': employee.id,
        }

        if mode == 'check_in':
            vals.update({
                'check_in': now,
                'in_latitude': latitude,
                'in_longitude': longitude,
                'check_in_address': check_in_address,
                'in_mode': 'systray',
            })
        else:
            attendance = attendance[0]
            vals.update({
                'check_out': now,
                'out_latitude': latitude,
                'out_longitude': longitude,
                'check_out_address': check_out_address,
                'out_mode': 'systray',
            })
            attendance.write(vals)
            return {'message': 'Checked Out',
                    'attendance_id': attendance.id,
                    'employee_name': employee.name,
                    'employee_avatar': employee.image_256,
                    'total_overtime': float_round(employee.total_overtime, precision_digits=2),
                    'kiosk_delay': employee.company_id.attendance_kiosk_delay * 1000,
                    'attendance': {'check_in': employee.last_attendance_id.check_in,
                                   'check_out': employee.last_attendance_id.check_out},
                    'overtime_today': request.env['hr.attendance.overtime'].sudo().search([
                        ('employee_id', '=', employee.id), ('date', '=', datetime.date.today()),
                        ('adjustment', '=', False)]).duration or 0,
                    'use_pin': employee.company_id.attendance_kiosk_use_pin,
                    'display_overtime': employee.company_id.hr_attendance_display_overtime}

        # Create new attendance
        new_attendance = request.env['hr.attendance'].sudo().create(vals)
        return {'message': 'Checked In',
                'attendance_id': new_attendance.id,
                'employee_name': employee.name,
                'employee_avatar': employee.image_256,
                'total_overtime': float_round(employee.total_overtime, precision_digits=2),
                'kiosk_delay': employee.company_id.attendance_kiosk_delay * 1000,
                'attendance': {'check_in': employee.last_attendance_id.check_in,
                               'check_out': employee.last_attendance_id.check_out},
                'overtime_today': request.env['hr.attendance.overtime'].sudo().search([
                    ('employee_id', '=', employee.id), ('date', '=', datetime.date.today()),
                    ('adjustment', '=', False)]).duration or 0,
                'use_pin': employee.company_id.attendance_kiosk_use_pin,
                'display_overtime': employee.company_id.hr_attendance_display_overtime
                }
