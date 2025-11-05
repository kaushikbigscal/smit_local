from odoo import models, fields, api
import requests


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    check_in_address = fields.Char(string="Day-in Address")
    check_out_address = fields.Char(string="Day-out Address")

    @api.model
    def create(self, vals):
        res = super(HrAttendance, self).create(vals)
        if res.check_in and res.in_latitude and res.in_longitude:
            res._get_address_from_coords('in')
        return res

    def write(self, vals):
        res = super(HrAttendance, self).write(vals)
        if 'in_latitude' in vals or 'in_longitude' in vals:
            self._get_address_from_coords('in')
        if 'out_latitude' in vals or 'out_longitude' in vals:
            self._get_address_from_coords('out')
        return res

    def _get_address_from_coords(self, check_type):
        provider_id = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.geo_provider')
        provider_tech_name = None

        if provider_id:
            provider = self.env['base.geo_provider'].sudo().browse(int(provider_id))
            provider_tech_name = provider.tech_name

        apikey = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')

        for attendance in self:
            lat_field = f'{check_type}_latitude'
            lon_field = f'{check_type}_longitude'
            address_field = f'check_{check_type}_address'

            # Skip if address already set
            if attendance[address_field]:
                continue

            latitude = getattr(attendance, lat_field)
            longitude = getattr(attendance, lon_field)

            if not latitude or not longitude:
                continue

            # Use a temporary variable, not the final address directly
            result_address = None

            try:
                if provider_tech_name == 'googlemap' and apikey:
                    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={latitude},{longitude}&key={apikey}"
                    response = requests.get(url)
                    data = response.json()
                    if 'results' in data and len(data['results']) > 0:
                        result_address = data['results'][0].get('formatted_address')

                elif provider_tech_name == 'openstreetmap':
                    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"
                    response = requests.get(url, headers={'User-Agent': 'Odoo HR Attendance'})
                    response.raise_for_status()
                    data = response.json()
                    result_address = data.get('display_name')

            except requests.RequestException as e:
                result_address = f"Error fetching address: {str(e)}"

            # Set the address: use the result if available, otherwise the default text.
            address = result_address or 'Address not found'
            setattr(attendance, address_field, address)

    @api.model
    def _update_check_out_address(self):
        attendances = self.search([('check_out', '!=', False), ('check_out_address', '=', False)])
        for attendance in attendances:
            attendance._get_address_from_coords('out')

#
# from odoo import models, fields, api
# import requests
#
#
# class HrAttendance(models.Model):
#     _inherit = 'hr.attendance'
#
#     check_in_address = fields.Char(string="Day-in Address")
#     check_out_address = fields.Char(string="Day-out Address")
#
#     @api.model
#     def create(self, vals):
#         res = super(HrAttendance, self).create(vals)
#         if res.check_in and res.in_latitude and res.in_longitude:
#             res._get_address_from_coords('in')
#         return res
#
#     def write(self, vals):
#         res = super(HrAttendance, self).write(vals)
#         if 'in_latitude' in vals or 'in_longitude' in vals:
#             self._get_address_from_coords('in')
#         if 'out_latitude' in vals or 'out_longitude' in vals:
#             self._get_address_from_coords('out')
#         return res
#
# def _get_address_from_coords(self, check_type):
#     for attendance in self:
#         lat_field = f'{check_type}_latitude'
#         lon_field = f'{check_type}_longitude'
#         address_field = f'check_{check_type}_address'
#
#         latitude = getattr(attendance, lat_field)
#         longitude = getattr(attendance, lon_field)
#
#         if latitude and longitude:
#             url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"
#             try:
#                 response = requests.get(url, headers={'User-Agent': 'Odoo HR Attendance'})
#                 response.raise_for_status()
#                 data = response.json()
#                 address = data.get('display_name', 'Address not found')
#             except requests.RequestException as e:
#                 address = f"Error fetching address: {str(e)}"
#
#             setattr(attendance, address_field, address)
#
#     @api.model
#     def _update_check_out_address(self):
#         attendances = self.search([('check_out', '!=', False), ('check_out_address', '=', False)])
#         for attendance in attendances:
#             attendance._get_address_from_coords('out')


# def _get_address_from_coords(self, check_type):
#     for attendance in self:
#         lat_field = f'{check_type}_latitude'
#         lon_field = f'{check_type}_longitude'
#         address_field = f'check_{check_type}_address'
#
#         # Skip if address already set
#         if attendance[address_field]:
#             continue
#
#         latitude = getattr(attendance, lat_field)
#         longitude = getattr(attendance, lon_field)
#
#         if latitude and longitude:
#             apikey = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')
#
#             url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={latitude},{longitude}&key={apikey}"
#
#             try:
#                 response = requests.get(url)
#                 data = response.json()
#
#                 # Get the formatted address from the first result
#                 if 'results' in data and len(data['results']) > 0:
#                     address = data['results'][0].get('formatted_address', 'Address not found')
#                 else:
#                     address = 'address not found.'
#
#             except requests.RequestException as e:
#                 address = f"Error fetching address: {str(e)}"
#
#             setattr(attendance, address_field, address)
