import requests
from odoo import models, api, fields, _
from math import radians, sin, cos, sqrt, atan2
from odoo.exceptions import AccessError
from datetime import timedelta


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    def _compute_distance(self, lat1, lon1, lat2, lon2):
        R = 6371000.0  # Earth radius in meter
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c  # Return in meters

    def _validate_geofence_checkin(self, task, lat, lon):
        user = self.env.user
        company = self.env.company

        if not task.project_id.is_fsm:
            return True

        if not (company.enable_geofencing_on_checkin and user.enable_geofencing_on_checkin):
            return True

        if task.service_types and task.service_types.bypass_geofencing_for_service_call:
            return True

        cust_lat = task.partner_id.partner_latitude
        cust_lon = task.partner_id.partner_longitude
        if not cust_lat or not cust_lon:
            raise AccessError(_("Customer latitude and longitude are required."))

        if not lat or not lon:
            raise AccessError(_("Missing check-in location data."))

        allowed_distance = company.allowed_distance_service
        if allowed_distance <= 0:
            raise AccessError(_("Allowed distance must be configured in company settings."))

        distance = self._compute_distance(lat, lon, cust_lat, cust_lon)
        if distance > allowed_distance:
            raise AccessError(_("Check-in location too far! Distance: %.2f meters. Allowed: %.2f meters.") % (
                distance, allowed_distance
            ))
        return True

    def _validate_geofence_checkout(self, task, lat, lon):
        user = self.env.user
        company = self.env.company

        if not task.project_id.is_fsm:
            return True

        if not (company.enable_geofencing_on_checkout and user.enable_geofencing_on_checkout):
            return True

        if task.service_types and task.service_types.bypass_geofencing_for_service_call:
            return True

        cust_lat = task.partner_id.partner_latitude
        cust_lon = task.partner_id.partner_longitude
        if not cust_lat or not cust_lon:
            raise AccessError(_("Customer latitude and longitude are required."))

        if not lat or not lon:
            raise AccessError(_("Missing check-out location data."))

        allowed_distance = company.allowed_distance_service
        if allowed_distance <= 0:
            raise AccessError(_("Allowed distance must be configured in company settings."))

        distance = self._compute_distance(lat, lon, cust_lat, cust_lon)
        if distance > allowed_distance:
            raise AccessError(_("Check-out location too far! Distance: %.2f meters. Allowed: %.2f meters.") % (
                distance, allowed_distance
            ))
        return True
