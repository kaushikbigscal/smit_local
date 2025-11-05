# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class PartnerMapController(http.Controller):

    @http.route('/partner/nearby', type='json', auth='user', methods=['POST'])
    def nearby_partners(self, lat, lon, radius=2000, **kwargs):
        """
        Get nearby partners based on coordinates

        :param lat: Latitude
        :param lon: Longitude
        :param radius: Search radius in meters (default: 2000)
        :return: List of partner data
        """
        try:
            # Validate input parameters
            lat = float(lat)
            lon = float(lon)
            radius = int(radius)

            # Validate coordinate ranges
            if not (-90 <= lat <= 90):
                return {'error': 'Invalid latitude. Must be between -90 and 90'}
            if not (-180 <= lon <= 180):
                return {'error': 'Invalid longitude. Must be between -180 and 180'}
            if radius <= 0:
                return {'error': 'Radius must be positive'}

        except (ValueError, TypeError):
            return {'error': 'Invalid parameters provided'}

        try:
            partners = request.env['partner.nearby.locator'].get_nearby_partners(lat, lon, radius)

            # Return structured data
            partner_data = []
            for partner in partners:
                partner_data.append({
                    'id': partner.id,
                    'name': partner.name or '',
                    'street': partner.street or '',
                    'city': partner.city or '',
                    'state': partner.state_id.name if partner.state_id else '',
                    'country': partner.country_id.name if partner.country_id else '',
                    'phone': partner.phone or '',
                    'email': partner.email or '',
                    'latitude': partner.partner_latitude,
                    'longitude': partner.partner_longitude,
                })

            return {
                'success': True,
                'count': len(partner_data),
                'partners': partner_data
            }

        except Exception as e:
            _logger.error("Error fetching nearby partners: %s", str(e))
            return {'error': 'Failed to fetch nearby partners'}

    @http.route('/partner/update_location', type='json', auth='user', methods=['POST'])
    def update_employee_location(self, lat, lon, **kwargs):
        """
        Update current user's employee location

        :param lat: Latitude
        :param lon: Longitude
        :return: Success status
        """
        try:
            lat = float(lat)
            lon = float(lon)

            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return {'error': 'Invalid coordinates'}

        except (ValueError, TypeError):
            return {'error': 'Invalid parameters'}

        try:
            employee = request.env.user.employee_id
            if employee:
                employee.sudo().write({
                    'live_latitude': lat,
                    'live_longitude': lon
                })
                return {'success': True}
            else:
                return {'error': 'No employee record found for current user'}

        except Exception as e:
            _logger.error("Error updating employee location: %s", str(e))
            return {'error': 'Failed to update location'}