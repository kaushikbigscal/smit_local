from math import radians, sin, cos, sqrt, atan2
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    enable_geofence = fields.Boolean(
        string='Enable Day In Location For Attendance',
        help='Enable location-based attendance checking for this user'
    )
    enable_geofence_day_out = fields.Boolean(string='Enable Day Out Location For Attendance')
    day_in_reminder_enabled = fields.Boolean(
        string="Enable Day In Reminder",
        help="Use working schedule for day-based reminders")

    day_out_reminder_enabled = fields.Boolean(string="Enable Day Out Reminder")

    auto_day_out = fields.Boolean(string="Auto Day Out")

    attendance_capture_mode = fields.Selection([
        ('web', 'Web'),
        ('mobile', 'Mobile'),
        ('mobile-web', 'Mobile-Web'),
        ('biometric', 'Biometric'),
    ], string="Attendance Capture Mode", default="mobile-web")


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model
    def create(self, values):
        attendance = super(HrAttendance, self).create(values)
        attendance._check_company_range()
        return attendance

    def write(self, values):
        res = super(HrAttendance, self).write(values)
        self._check_company_range()
        return res

    def _compute_distance(self, lat1, lon1, lat2, lon2):
        # Radius of the earth in kilometers
        R = 6371.0

        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Calculate the change in coordinates
        dlon = lon2 - lon1
        dlat = lat2 - lat1

        # Apply Haversine formula
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c

        return distance

    def _check_company_range(self):
        company = self.env.company
        user = self.env.user

        company_latitude = company.company_latitude or 0.0
        company_longitude = company.company_longitude or 0.0
        allowed_distance_meters = company.allowed_distance or 100  # meters

        _logger.info(
            f'Company Location: ({company_latitude}, {company_longitude}), Allowed Distance: {allowed_distance_meters}m')

        for attendance in self:
            is_check_in = attendance.check_in and not attendance.check_out
            is_check_out = attendance.check_out

            # For check-in
            if is_check_in:
                if not (company.enable_geofence and user.enable_geofence):
                    continue

                if not (attendance.in_latitude and attendance.in_longitude):
                    raise UserError(
                        _("Missing location for check-in. Please enable location services."))

                distance_meters = self._compute_distance(
                    company_latitude, company_longitude,
                    attendance.in_latitude, attendance.in_longitude
                ) * 1000

                if distance_meters > allowed_distance_meters:
                    raise UserError(_(
                        "You are outside the allowed range for check-in."
                    ))

            # For check-out
            if is_check_out:
                if not (company.enable_geofence_day_out and user.enable_geofence_day_out):
                    continue

                if not (attendance.out_latitude and attendance.out_longitude):
                    raise UserError(
                        _("Missing location for check-out. Please enable location services."))

                distance_meters = self._compute_distance(
                    company_latitude, company_longitude,
                    attendance.out_latitude, attendance.out_longitude
                ) * 1000

                if distance_meters > allowed_distance_meters:
                    raise UserError(_(
                        "You are outside the allowed range for check-out."
                    ))

    @api.model
    def get_gps_required_flag(self):
        """Compute GPS required flag based on user and company settings"""
        user = self.env.user
        company = user.company_id

        # Safe field access with getattr() and default values
        user_settings = {
            'enable_gps_tracking': getattr(user, 'enable_gps_tracking', False),
            'enable_geofence': getattr(user, 'enable_geofence', False),
            'enable_geofence_day_out': getattr(user, 'enable_geofence_day_out', False),
        }

        company_settings = {
            'enable_geofence': getattr(company, 'enable_geofence', False),
            'enable_geofence_day_out': getattr(company, 'enable_geofence_day_out', False),
        }

        gps_required = False

        try:
            if user_settings['enable_gps_tracking']:
                gps_required = True
            elif (company_settings['enable_geofence'] and user_settings['enable_geofence']) or \
                    (company_settings['enable_geofence_day_out'] and user_settings['enable_geofence_day_out']):
                gps_required = True
        except Exception as e:
            _logger.warning("GPS required computation failed: %s", str(e))
            gps_required = False

        return {
            'gps_required': gps_required,
            'user_settings': user_settings,
            'company_settings': company_settings,
        }

# from math import radians, sin, cos, sqrt, atan2
# from odoo import models, fields, api, _
# from odoo.exceptions import UserError
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class ResUsers(models.Model):
#     _inherit = 'res.users'
#
#     enable_geofence = fields.Boolean(
#         string='Enable Location Based Attendance',
#         help='Enable location-based attendance checking for this user'
#     )
#
#
# class HrAttendance(models.Model):
#     _inherit = 'hr.attendance'
#
#     @api.model
#     def create(self, values):
#         attendance = super(HrAttendance, self).create(values)
#         attendance._check_company_range()
#         return attendance
#
#     def write(self, values):
#         res = super(HrAttendance, self).write(values)
#         self._check_company_range()
#         return res
#
#     def _compute_distance(self, lat1, lon1, lat2, lon2):
#         # Radius of the earth in kilometers
#         R = 6371.0
#
#         # Convert latitude and longitude from degrees to radians
#         lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
#
#         # Calculate the change in coordinates
#         dlon = lon2 - lon1
#         dlat = lat2 - lat1
#
#         # Apply Haversine formula
#         a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
#         c = 2 * atan2(sqrt(a), sqrt(1 - a))
#         distance = R * c
#
#         return distance
#
#     def _check_company_range(self):
#         company = self.env.company
#
#         if not company.enable_geofence:
#             return True
#
#         user = self.env.user
#         if not user.enable_geofence:
#             return True
#
#         company_latitude = company.company_latitude or 0.000000
#         company_longitude = company.company_longitude or 0.0000000
#         allowed_distance_meters = company.allowed_distance or 100  # Default allowed distance is 1100 meters
#
#         _logger.info(
#             f'company Latitude: {company_latitude}, company Longitude: {company_longitude}, Allowed Distance: {allowed_distance_meters} meters')
#
#         for attendance in self:
#             if not (attendance.in_latitude and attendance.in_longitude):
#                 raise UserError(
#                     _("Oops! It seems we're missing your location information. Could you please allow us to access your location so we can proceed?"))
#
#             # Compute the distance between company and attendance location
#             distance_meters = self._compute_distance(
#                 company_latitude, company_longitude,
#                 attendance.in_latitude, attendance.in_longitude
#             ) * 1000  # Convert kilometers to meters
#
#             if distance_meters > allowed_distance_meters:
#                 raise UserError(_(
#                     "You are outside the allowed range of the company location. "
#                     "Please ensure that you are within the company Location. "
#                     "The distance exceeds the allowed distance."
#                 ))
