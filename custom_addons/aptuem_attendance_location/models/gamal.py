# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)

from odoo import fields, models, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_geofence = fields.Boolean(string="Enable Location Based on Attendance", default=False,
                                     help="Enable Location-based attendance checking for the company")
    enable_geofence_day_out = fields.Boolean(string="Enable Day Out Location For Attendance", default=False)

    company_latitude = fields.Float(string='Company Latitude', digits=(16, 6),
                                    help='Set Company Latitude here')
    company_longitude = fields.Float(string='Company Longitude', digits=(16, 6),
                                     help='Set Company Longitude here')
    allowed_distance = fields.Float(
        string='Allowed Distance (KM)', digits=(16, 2),
        help='Set the allowed distance for check-in or check-out in kilometers. Example: 2.5 for 2.5 kilometers.'
    )

    day_in_reminder_enabled = fields.Boolean(
        string="Enable Day In Reminder",
        help="Use working schedule for day-based reminders")

    day_out_reminder_enabled = fields.Boolean(string="Enable Day Out Reminder")

    auto_day_out = fields.Boolean(string="Auto Day Out")

# class ResConfigSettings(models.TransientModel):
#     _inherit = 'res.config.settings'
#     enable_geofence = fields.Boolean(
#         string='Enable Location Based Attendance',
#         related='company_id.enable_geofence',
#         readonly=False
#     )
#     company_latitude = fields.Float(string='Company Latitude', related='company_id.company_latitude', readonly=False)
#     company_longitude = fields.Float(string='Company Longitude', related='company_id.company_longitude', readonly=False)
#     allowed_distance = fields.Float(string='Allowed Distance (km)', related='company_id.allowed_distance', readonly=False)
#
#     def execute(self):
#         res = super(ResConfigSettings, self).execute()
#         _logger.info(f"company Latitude: {self.company_latitude}, company Longitude: {self.company_longitude}, Allowed Distance: {self.allowed_distance}")
#         return res
