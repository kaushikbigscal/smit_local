# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
import math

_logger = logging.getLogger(__name__)


class NearbyLocator(models.AbstractModel):
    _name = "partner.nearby.locator"
    _description = "Nearby Partner Locator"

    @api.model
    def get_nearby_partners(self, emp_lat, emp_lon, radius=2000):
        """
        Fetch nearby partners within a radius (meters).
        Fallback priority:
          1. PostGIS ST_DWithin (most accurate)
          2. Haversine SQL formula
          3. Python Haversine calculation (fallback)
        """
        cr = self.env.cr

        # Input validation
        try:
            emp_lat = float(emp_lat)
            emp_lon = float(emp_lon)
            radius = int(radius)
        except (ValueError, TypeError):
            _logger.error("Invalid parameters for nearby search")
            return self.env["res.partner"]

        # Method 1: Try PostGIS (most accurate for geographic calculations)
        try:
            cr.execute("SELECT PostGIS_Version()")
            postgis_version = cr.fetchone()
            if postgis_version:
                _logger.info("Using PostGIS version: %s", postgis_version[0])

                query = """
                    SELECT id, 
                           ST_Distance(
                               ST_SetSRID(ST_MakePoint(partner_longitude, partner_latitude), 4326)::geography,
                               ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                           ) as distance
                    FROM res_partner
                    WHERE partner_latitude IS NOT NULL
                      AND partner_longitude IS NOT NULL
                      AND ST_DWithin(
                          ST_SetSRID(ST_MakePoint(partner_longitude, partner_latitude), 4326)::geography,
                          ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                          %s
                      )
                    ORDER BY distance
                """
                cr.execute(query, (emp_lon, emp_lat, emp_lon, emp_lat, radius))
                results = cr.fetchall()
                ids = [r[0] for r in results]

                _logger.info("PostGIS found %d partners within %dm", len(ids), radius)
                return self.env["res.partner"].browse(ids)

        except Exception as e:
            _logger.warning("PostGIS not available or failed: %s", str(e))

        # Method 2: SQL Haversine formula (good compromise)
        try:
            query = """
                SELECT id, distance
                FROM (
                    SELECT id,
                           (6371000 * acos(
                               LEAST(1.0, GREATEST(-1.0,
                                   cos(radians(%s)) * cos(radians(partner_latitude)) *
                                   cos(radians(partner_longitude) - radians(%s)) +
                                   sin(radians(%s)) * sin(radians(partner_latitude))
                               ))
                           )) AS distance
                    FROM res_partner
                    WHERE partner_latitude IS NOT NULL
                      AND partner_longitude IS NOT NULL
                      AND partner_latitude BETWEEN %s AND %s
                      AND partner_longitude BETWEEN %s AND %s
                ) sub
                WHERE distance <= %s
                ORDER BY distance
            """

            # Rough bounding box for performance (about 1 degree = 111km)
            lat_delta = (radius / 111000) * 1.5  # Add buffer for safety
            lon_delta = (radius / (111000 * abs(math.cos(math.radians(emp_lat))))) * 1.5

            cr.execute(query, (
                emp_lat, emp_lon, emp_lat,
                emp_lat - lat_delta, emp_lat + lat_delta,
                emp_lon - lon_delta, emp_lon + lon_delta,
                radius
            ))

            results = cr.fetchall()
            ids = [r[0] for r in results]

            _logger.info("SQL Haversine found %d partners within %dm", len(ids), radius)
            return self.env["res.partner"].browse(ids)

        except Exception as e:
            _logger.warning("SQL Haversine failed: %s", str(e))

        # Method 3: Python fallback (least efficient but most reliable)
        try:
            _logger.info("Using Python Haversine fallback")
            partners = self.env["res.partner"].search([
                ('partner_latitude', '!=', False),
                ('partner_longitude', '!=', False)
            ])

            nearby_ids = []
            for partner in partners:
                distance = self._haversine_distance(
                    emp_lat, emp_lon,
                    partner.partner_latitude, partner.partner_longitude
                )
                if distance <= radius:
                    nearby_ids.append(partner.id)

            _logger.info("Python Haversine found %d partners within %dm", len(nearby_ids), radius)
            return self.env["res.partner"].browse(nearby_ids)

        except Exception as e:
            _logger.error("All nearby search methods failed: %s", str(e))
            return self.env["res.partner"]

    @api.model
    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points
        on the earth (specified in decimal degrees)
        Returns distance in meters
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        # Earth radius in meters
        r = 6371000

        return c * r


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    live_latitude = fields.Float(
        "Live Latitude",
        digits=(10, 7),
        help="Current latitude coordinates"
    )
    live_longitude = fields.Float(
        "Live Longitude",
        digits=(10, 7),
        help="Current longitude coordinates"
    )
    location_updated = fields.Datetime(
        "Location Last Updated",
        help="Timestamp of last location update"
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Set location update timestamp when coordinates are provided"""
        for vals in vals_list:
            if vals.get('live_latitude') or vals.get('live_longitude'):
                vals['location_updated'] = fields.Datetime.now()
        return super().create(vals_list)

    def write(self, vals):
        """Update timestamp when location changes"""
        if 'live_latitude' in vals or 'live_longitude' in vals:
            vals['location_updated'] = fields.Datetime.now()
        return super().write(vals)


class ResPartner(models.Model):
    _inherit = "res.partner"

    partner_latitude = fields.Float(
        "Latitude",
        digits=(10, 7),
        help="Latitude coordinates for mapping"
    )
    partner_longitude = fields.Float(
        "Longitude",
        digits=(10, 7),
        help="Longitude coordinates for mapping"
    )
    location_source = fields.Selection([
        ('manual', 'Manual Entry'),
        ('geocoded', 'Auto-Geocoded'),
        ('gps', 'GPS Device')
    ], string="Location Source", default='manual')

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **kwargs):
        """Inject nearby filter for map view with improved logic"""
        ctx = self.env.context

        # Handle non-integer offset values (like arrays)
        try:
            offset = int(offset) if offset else 0
        except (ValueError, TypeError):
            offset = 0

        if ctx.get("nearby_map_filter"):
            employee = self.env.user.employee_id
            if employee and employee.live_latitude and employee.live_longitude:
                # Get radius from context or use default
                radius = ctx.get('nearby_radius', 3000)  # 3km default
                try:
                    nearby_partners = self.env["partner.nearby.locator"].get_nearby_partners(
                        employee.live_latitude,
                        employee.live_longitude,
                        radius=radius
                    )

                    if nearby_partners:
                        domain = domain + [("id", "in", nearby_partners.ids)]
                        _logger.info("Applied nearby filter: found %d partners within %dm",
                                     len(nearby_partners), radius)
                    else:
                        # No partners found - return empty result
                        domain = domain + [("id", "=", 0)]
                        _logger.info("No nearby partners found within %dm", radius)

                except Exception as e:
                    _logger.error("Error applying nearby filter: %s", str(e))
                    # Don't modify domain on error - show all partners

            else:
                _logger.warning("Nearby filter requested but employee location not available")
                # Could choose to show all partners or none - showing all for better UX

        return super().search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order, **kwargs)


    @api.constrains('partner_latitude', 'partner_longitude')
    def _check_coordinates(self):
        """Validate coordinate ranges"""
        for record in self:
            if record.partner_latitude and not (-90 <= record.partner_latitude <= 90):
                raise models.ValidationError("Latitude must be between -90 and 90 degrees")
            if record.partner_longitude and not (-180 <= record.partner_longitude <= 180):
                raise models.ValidationError("Longitude must be between -180 and 180 degrees")