from odoo import http
from odoo.http import request
from odoo.tools.float_utils import float_round


class HrAttendanceCustom(http.Controller):
    @http.route('/custom_attendance/user_data', type='json', auth='user')
    def get_user_attendance_data(self):
        employee = request.env.user.employee_id
        if not employee:
            return {}

        capture_mode = employee.user_id.attendance_capture_mode or ''

        return {
            'id': employee.id,
            'hours_today': float_round(employee.hours_today, precision_digits=2),
            'hours_previously_today': float_round(employee.hours_previously_today, precision_digits=2),
            'last_attendance_worked_hours': float_round(employee.last_attendance_worked_hours, precision_digits=2),
            'last_check_in': employee.last_check_in,
            'attendance_state': employee.attendance_state,
            'display_systray': employee.company_id.attendance_from_systray,
            'attendance_capture_mode': capture_mode,
            'attendance_web': capture_mode in ['web', 'mobile-web'],
            'attendance_mobile': capture_mode in ['mobile', 'mobile-web'],
            'attendance_biometric': capture_mode == 'biometric',
        }
