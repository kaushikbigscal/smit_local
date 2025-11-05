from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import math, re, requests
from odoo.tools import html2plaintext
import logging

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    lead_type_id = fields.Many2one('lead.type', string="Lead Type", required=True)
    lead_type_code = fields.Char(related='lead_type_id.code', store=True)
    partner_latitude = fields.Float(string='Latitude', digits=(10, 7))
    partner_longitude = fields.Float(string='Longitude', digits=(10, 7))
    date_localization = fields.Date(string='Geolocation Date')
    store_id = fields.Many2one('store.code', string="Store Code")

    def write(self, vals):
        address_fields = ['street', 'zip', 'city', 'state_id', 'country_id']
        geo_fields = ['partner_latitude', 'partner_longitude']

        # If address updated but not latitude/longitude manually set, reset coords
        if any(f in vals for f in address_fields) and not all(f in vals for f in geo_fields):
            vals.update({
                'partner_latitude': 0.0,
                'partner_longitude': 0.0,
            })

        res = super().write(vals)

        # Trigger geo localize when address changed
        if any(f in vals for f in address_fields):
            self.geo_localize_lead()
        return res

    def geo_localize_lead(self):
        geocoder = self.env['base.geocoder']
        ctx = dict(self.env.context, lang='en_US')

        for lead in self.with_context(ctx):
            search = geocoder.geo_query_address(
                street=lead.street,
                zip=lead.zip,
                city=lead.city,
                state=lead.state_id.name,
                country=lead.country_id.name,
            )
            result = geocoder.geo_find(search, force_country=lead.country_id.name)

            if not result:
                search = geocoder.geo_query_address(
                    city=lead.city,
                    state=lead.state_id.name,
                    country=lead.country_id.name,
                )
                result = geocoder.geo_find(search, force_country=lead.country_id.name)

            if result:
                lead.write({
                    'partner_latitude': result[0],
                    'partner_longitude': result[1],
                    'date_localization': fields.Date.context_today(lead)
                })
            else:
                self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                    'type': 'danger',
                    'title': _("Warning"),
                    'message': _("No match found for Lead Address: %s") % lead.name,
                })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            self._send_nearest_store_email(record)

        return records

    def _send_nearest_store_email(self, lead):
        """
        Find nearest store based on lead contact location and send email
        Only sends email if lead_type_code is 'med_order'
        """
        try:
            # Check if lead type is med_order
            if not lead.lead_type_code or lead.lead_type_code != 'med_order':
                _logger.info("Lead %s has lead_type_code '%s', skipping email",
                             lead.id, lead.lead_type_code)
                return

            _logger.info("Lead %s has lead_type_code 'med_order', proceeding with email", lead.id)

            # Get lead contact coordinates
            if not lead.partner_id:
                _logger.warning("Lead %s has no partner assigned", lead.id)
                return

            lead_lat = lead.partner_latitude
            lead_lon = lead.partner_longitude

            if not lead_lat or not lead_lon:
                _logger.warning("Lead %s has no geolocation. Skipping nearest store assignment.", lead.id)
                return

            # Find nearest store (PostGIS first, then Haversine fallback)
            nearest_store = self._get_nearest_store(lead_lat, lead_lon)

            if not nearest_store:
                _logger.warning("No stores found for lead %s", lead.id)
                return

            # Send email to nearest store
            self._send_store_notification_email(lead, nearest_store)

        except Exception as e:
            _logger.error("Error in _send_nearest_store_email: %s", str(e))

    def _get_nearest_store(self, lead_lat, lead_lon, radius=50000):
        """
        Find nearest store - tries PostGIS first, falls back to Haversine
        """
        # Method 1: Try PostGIS
        nearest_store = self._get_nearest_store_postgis(lead_lat, lead_lon, radius)

        if nearest_store:
            return nearest_store

        # Method 2: Fallback to Haversine
        _logger.info("PostGIS failed, using Haversine fallback")
        nearest_store = self._get_nearest_store_haversine(lead_lat, lead_lon, radius)

        return nearest_store

    def _get_nearest_store_postgis(self, lead_lat, lead_lon, radius=50000):
        """
        Find the nearest store using PostGIS (most accurate)
        Returns single store.code record or None
        """
        try:
            cr = self.env.cr

            # Check if PostGIS is available
            cr.execute("SELECT PostGIS_Version()")
            postgis_version = cr.fetchone()

            if not postgis_version:
                _logger.warning("PostGIS not available")
                return None

            _logger.info("Using PostGIS version: %s for store location", postgis_version[0])

            # PostGIS query to find nearest store
            query = """
                SELECT id, 
                       ST_Distance(
                           ST_SetSRID(ST_MakePoint(store_longitude, store_latitude), 4326)::geography,
                           ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                       ) as distance
                FROM store_code
                WHERE store_latitude IS NOT NULL
                  AND store_longitude IS NOT NULL
                  AND store_latitude != 0
                  AND store_longitude != 0
                  AND is_active = true
                  AND ST_DWithin(
                      ST_SetSRID(ST_MakePoint(store_longitude, store_latitude), 4326)::geography,
                      ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                      %s
                  )
                ORDER BY distance ASC
                LIMIT 1
            """

            cr.execute(query, (lead_lon, lead_lat, lead_lon, lead_lat, radius))
            result = cr.fetchone()

            if result:
                store_id = result[0]
                distance = result[1]

                store = self.env['store.code'].browse(store_id)
                _logger.info("PostGIS found nearest store %s at distance %d meters",
                             store.name, int(distance))
                return store
            else:
                _logger.info("No stores found within %d meters radius using PostGIS", radius)
                return None

        except Exception as e:
            _logger.warning("PostGIS query failed, will try Haversine: %s", str(e))
            return None

    def _get_nearest_store_haversine(self, lead_lat, lead_lon, radius=50000):
        """
        Fallback: Find nearest store using Haversine formula (Python calculation)
        Returns single store.code record or None
        """
        try:
            store_model = self.env['store.code']

            # Get all active stores with coordinates
            stores = store_model.search([
                ('is_active', '=', True),
                ('store_latitude', '!=', 0),
                ('store_longitude', '!=', 0)
            ])

            _logger.info("Haversine: Checking %d stores", len(stores))

            nearest_store = None
            min_distance = float('inf')

            for store in stores:
                if not store.store_latitude or not store.store_longitude:
                    continue

                # Calculate distance using Haversine
                distance = self._haversine_distance(
                    lead_lat, lead_lon,
                    store.store_latitude, store.store_longitude
                )

                _logger.debug("Store %s distance: %d meters", store.name, int(distance))

                # Keep track of nearest store
                if distance < min_distance and distance <= radius:
                    min_distance = distance
                    nearest_store = store

            if nearest_store:
                _logger.info("Haversine found nearest store %s at distance %d meters",
                             nearest_store.name, int(min_distance))
                return nearest_store
            else:
                _logger.warning("No stores found within %d meters radius using Haversine", radius)
                return None

        except Exception as e:
            _logger.error("Haversine fallback failed: %s", str(e))
            return None

    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points
        on the earth (specified in decimal degrees)
        Returns distance in meters
        """
        try:
            # Convert to float
            lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)

            # Convert decimal degrees to radians
            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)

            # Haversine formula
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad

            a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
            c = 2 * math.asin(math.sqrt(a))

            # Earth radius in meters
            r = 6371000

            distance = c * r
            return distance

        except Exception as e:
            _logger.error("Haversine calculation failed: %s", str(e))
            return float('inf')

    def _send_store_notification_email(self, lead, store):
        """
        Send email to nearest store about new lead
        """
        try:
            if not store.store_email:
                _logger.warning("Store %s has no email address", store.name)
                return

            self._send_inline_email(lead, store)
            _logger.info("Email sent to store %s (%s) for lead %s", store.name, store.store_email, lead.name)

        except Exception as e:
            _logger.error("Failed to send email: %s", str(e))

    def _send_inline_email(self, lead, store):
        """
        Send inline email without template
        """
        try:
            mail_values = {
                'subject': f"New Lead: {lead.name}",
                'body_html': f"""
                    <html>
                    <body>
                        <p>Dear {store.name} Team,</p>
                        <p>A new lead has been created and assigned to your store based on location proximity:</p>
                        <table border="1" cellpadding="10" style="border-collapse: collapse;">
                            <tr>
                                <td><strong>Lead Name:</strong></td>
                                <td>{lead.name}</td>
                            </tr>
                            <tr>
                                <td><strong>Lead Type:</strong></td>
                                <td>{lead.lead_type_id.name if lead.lead_type_id else 'N/A'}</td>
                            </tr>
                            <tr>
                                <td><strong>Contact:</strong></td>
                                <td>{lead.partner_id.name if lead.partner_id else 'N/A'}</td>
                            </tr>
                            <tr>
                                <td><strong>Email:</strong></td>
                                <td>{lead.email_from or 'N/A'}</td>
                            </tr>
                            <tr>
                                <td><strong>Phone:</strong></td>
                                <td>{lead.phone or 'N/A'}</td>
                            </tr>
                        </table>
                        <p>Please follow up on this lead at your earliest convenience.</p>
                        <p>Best regards,<br/>Lead Management System</p>
                    </body>
                    </html>
                """,
                'email_to': store.store_email,
                'email_from': self.env.user.email or 'noreply@odoo.local',
                'model': 'crm.lead',
                'res_id': lead.id,
            }

            mail = self.env['mail.mail'].create(mail_values)
            mail.send()

        except Exception as e:
            _logger.error("Error sending inline email: %s", str(e))

    def _send_store_notification_whatsapp(self, lead, store):
        """
        Send WhatsApp message to nearest store about new lead
        """
        try:
            if not store.store_phone:
                _logger.warning("Store %s has no WhatsApp phone number", store.name)
                return

            # Fetch WhatsApp template for CRM leads
            whatsapp_template = self.env['template.whatsapp'].search([
                ('model_id.model', '=', 'crm.lead'),
            ], limit=1)

            if not whatsapp_template:
                _logger.info("No WhatsApp template found for lead %s", lead.id)
                return

            message = html2plaintext(
                whatsapp_template.message or f"Dear {store.name} Team, A new lead has been created and assigned to your store based on location proximity.")

            message = (
                message.replace('{{lead_name}}', lead.name or '')
                .replace('{{contact_name}}', lead.partner_name if lead.partner_name else lead.contact_name)
                .replace('{{email}}', lead.email_from or '')
                .replace('{{phone}}', lead.phone or '')
                .replace('{{store_name}}', store.name)
            )

            phone_number = re.sub(r'\+\d{1,3}\s*', '', str(store.store_phone or '')).replace(" ", "")

            self._send_whatsapp_api_call(phone_number, message, whatsapp_template)

            _logger.info("WhatsApp sent to store %s (%s) for lead %s",
                         store.name, store.store_phone, lead.name)

        except Exception as e:
            _logger.error("Failed to send WhatsApp message: %s", str(e))

    def _send_whatsapp_api_call(self, phone_number, message, whatsapp_template):
        config = self.env['manager.configuration'].search([], limit=1, order="id desc")
        if not config:
            _logger.error("No WhatsApp configuration found")
            return

        base_url = f"http://{config.ip_address}:{config.port}/api"
        token_url = f"{base_url}/{config.instance}/{config.token}/generate-token"
        token_response = requests.post(token_url)
        token_response.raise_for_status()
        token = token_response.json().get("token")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        if whatsapp_template and message:
            self._send_whatsapp_message(
                base_url, config.instance, headers,
                phone_number, message
            )
        # attachments support
        # if whatsapp_template.attachment_ids:
        #     self._send_whatsapp_with_attachments(
        #         base_url, config.instance, headers,
        #         phone_number, message, whatsapp_template.attachment_ids
        #     )
        # else:
        #     self._send_whatsapp_message(
        #         base_url, config.instance, headers,
        #         phone_number, message
        #     )

    def _send_whatsapp_message(self, base_url, session_id, headers, phone_number, message):
        """
        Send WhatsApp text message using configured gateway.
        Returns True/False based on success.
        """

        if not phone_number:
            _logger.error("No valid phone number for WhatsApp send")
            return False

        payload = {
            "phone": phone_number,
            "isGroup": False,
            "isNewsletter": False,
            "isLid": False,
            "message": message,
            "sanitize": False
        }

        try:
            url = f"{base_url}/{session_id}/send-message"

            response = requests.post(url, json=payload, headers=headers, timeout=15)

            if response.status_code != 200:
                _logger.error(
                    "WhatsApp API failed [%s] phone=%s error=%s",
                    response.status_code, phone_number, response.text
                )
                return False

            _logger.info("WhatsApp message sent successfully to %s", phone_number)
            return True

        except Exception as e:
            _logger.error("WhatsApp send failed for %s: %s", phone_number, str(e))
            return False
