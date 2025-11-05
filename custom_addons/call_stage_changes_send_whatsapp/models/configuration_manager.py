import base64
import io
import json

import qrcode
import requests
from PIL import Image
from io import BytesIO
from odoo import fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class ConfigurationManager(models.Model):
    """A new model is to be created for configuring the API settings
    required to connect to WhatsApp."""
    _name = "configuration.manager"
    _description = "Configuration Manager"
    _rec_name = 'instance'

    ip_address = fields.Char(string="IP Address", required=True)
    port = fields.Char(string="Port", required=True)
    instance = fields.Char(string="Session", required=True,
                           help="Give instance for whatsapp api")
    token = fields.Char(string="Security Key", required=True,
                        help="Give token for whatsapp api")
    fetched_token = fields.Char(string="token",help="Give token for whatsapp api")
    config_id = fields.Many2one("pos.config", string="Point of Sale",
                                required=True,
                                help="Give Point of Sale for whatsapp api")
    state = fields.Selection(
        selection=[('draft', 'Draft'),
                   ('verified', 'Verified')],
        default='draft', string="state",
        help="State for connection")


    def action_authenticate(self):
        """ Opens a wizard for scanning QR code,
        After scanning number get active status. /api/{session}/{secretkey}/generate-token"""

        url = f"http://{self.ip_address}:{self.port}/api/{self.instance}/{self.token}/generate-token"
        _logger.info(f"URL: {url}")

        try:
            # Make the POST request to the API
            req = requests.post(url)
            _logger.info(f"REQ: {req.status_code} - {req.text}")

            # Check for status code, expect 201 Created
            if req.status_code != 201:
                raise ValidationError(_(f"Please provide a valid token. Status code: {req.status_code}"))

            # Check if the response is JSON
            if 'application/json' in req.headers.get('Content-Type', ''):
                response_data = req.json()
            else:
                _logger.error(f"Unexpected response format: {req.text}")
                raise ValidationError(_(f"Invalid response format: {req.text}"))

            # Handle the new response structure
            if response_data.get('status') == 'success':
                self.state = "verified"
                token = response_data.get('token')
                self.fetched_token = token
                # You can now use session and token data from the response
                qr_code_data = self.get_qr_code()
                if qr_code_data:
                    return self.open_authenticate_wizard(qr_code_data)
                else:
                    raise ValidationError("Try Again")

            else:
                raise ValidationError(_('Authentication failed. Invalid response from the server.'))

        except requests.RequestException as e:
            raise ValidationError(_(f"Error during API request: {str(e)}"))

    def get_qr_code(self):
        """Retrieve the QR code from the Ultramsg API./api/{session}/qrcode-session"""
        # url = f"https://api.ultramsg.com/{self.instance}/instance/qrCode"
        url = f"http://{self.ip_address}:{self.port}/api/{self.instance}/start-session"
        _logger.info(f"URL: {url}")
        headers = {
            'Authorization': f'Bearer {self.fetched_token}',  # Pass the token in the headers
            'Content-Type': 'application/json',  # Assuming the API expects JSON content
            'Accept': 'application/json'
        }

        response = requests.post(url, headers=headers)
        response_data = response.json()
        _logger.info(f"response: {response_data}")
        if response.status_code == 200:
            self.state = "verified"
            qr_image_data = response_data.get('qrcode')
            if qr_image_data is not None:
                qr_code_data = qr_image_data.split(",")[1]
                _logger.info(f"response: {qr_code_data}")
                return qr_code_data
            else:
                raise ValidationError("Try Again")
        else:
            raise ValidationError("Try Again")

    def display_notification(self, message_type, message):
        """ Got connected message"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': message_type,
                'sticky': False,
            }
        }
    def open_authenticate_wizard(self, qr_code_data):
        try:
            image_bytes = base64.b64decode(qr_code_data)
            _logger.info(f"URL: {image_bytes}")
            image_buffer = BytesIO(image_bytes)
            # image_result.save(image_result, format='PNG')
            image_result = base64.b64encode(image_buffer.getvalue())

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'whatsapp.authenticate',
                'name': 'WhatsApp Connect',
                'views': [(False, 'form')],
                'target': 'new',
                'context': {
                    'default_qrcode': image_result,
                    'default_configuration_manager_id': self.id,
                }
            }
        except qrcode.exceptions.DataOverflowError:
            raise ValidationError(_("The QR code data is too large. Please try again with a smaller data set."))
        except Exception as e:
            _logger.error(f"Error generating QR code: {str(e)}")
            raise ValidationError(_("An error occurred while generating the QR code. Please try again."))
