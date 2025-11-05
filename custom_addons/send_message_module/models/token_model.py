
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import base64
import logging

_logger = logging.getLogger(__name__)

class WPPConnect(models.Model):
    _name = 'wppconnect.api'
    _description = 'WPPConnect API Integration'
    _inherit = 'mail.thread'


    session = fields.Char(string='Session', required=True)
    secret_key = fields.Char(string='Secret Key', required=True, default='Wpp@byHe@lthRayMangeWi$$i968', readonly=True)
    qrcode_image = fields.Binary(string='QR Code', readonly=True)
    qrcode_filename = fields.Char(string='QR Code Filename', readonly=True)
    get_token = fields.Char()

    def generate_qr_code(self):
        # hardcoded_secret_key = 'Wpp@byHe@lthRayMangeWi$$i968'  # Temporary for testing

        # _logger.info("Requesting token with session: %s and secret key: %s", self.session, hardcoded_secret_key)

        # Generate token
        token_response = requests.post(
            f"http://45.118.162.148:21465/api/{self.session}/{self.secret_key}/generate-token"
        )
        if token_response.status_code != 201:
            raise UserError(_('Error generating token: %s') % token_response.text)

        token_data = token_response.json()
        if not token_data.get('token'):
            raise UserError(_('Failed to generate token: %s') % token_data.get('message'))

        # Start session
        token = token_data['token']
        self.get_token = token
        session_response = requests.post(
            f"http://45.118.162.148:21465/api/{self.session}/start-session",
            headers={'Authorization': f'Bearer {token}'}
        )
        if session_response.status_code != 200:
            raise UserError(_('Error starting session: %s') % session_response.text)

        session_data = session_response.json()
        _logger.info("Session data: %s", session_data)

        # Decode base64 QR code image
        qrcode_base64 = session_data.get('qrcode')
        print(qrcode_base64)
        if not qrcode_base64:
            raise UserError(_('No QR code received.'))

        if qrcode_base64.startswith('data:image/png;base64,'):
            qrcode_base64 = qrcode_base64.split(',')[1]

        qrcode_image = base64.b64decode(qrcode_base64)
        self.qrcode_image = base64.b64encode(qrcode_image).decode('utf-8')  # Ensure it's a string
        self.qrcode_filename = f"{self.session}_qrcode.png"

