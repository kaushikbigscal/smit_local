import base64
import requests
from odoo import fields, models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class MailMail(models.Model):
    _inherit = 'mail.mail'

    def send(self, auto_commit=False, raise_exception=False):
        # Search for a single 'wppconnect.api' record
        crm_obj = self.env['wppconnect.api'].search([], limit=1)  # limit=1 to return only one record
        if not crm_obj:
            raise UserError(_("No configuration found for WPPConnect API."))

        _logger.info('crm_obj: %s', crm_obj)
        session = crm_obj.session
        _logger.info('session: %s', session)
        print('session.................', session)

        secret_key = crm_obj.secret_key
        _logger.info('secret_key: %s', secret_key)
        print('secret_key.........', secret_key)

        get_token = crm_obj.get_token  # Get the token from the WPPConnect API config
        _logger.info('get_token: %s', get_token)
        print('get_token.......................', get_token)

        # Now search for the related crm.lead record
        crm_lead = self.env['crm.lead'].search([('website_message_ids', 'in', self.mail_message_id.id)], limit=1)
        if not crm_lead:
            raise UserError(_("No related CRM lead found for this message."))

        _logger.info('crm_lead: %s', crm_lead)
        phone_number = crm_lead.phone
        _logger.info('phone_number: %s', phone_number)

        if not phone_number:
            raise UserError(_("No phone number found for the related CRM lead."))

        mail_compose_data = self.env['mail.compose.message'].search([], limit=1)
        # whatsapp_from = '7321944358'
        # message = "Hello, this is a test message!"
        message =  mail_compose_data.body
        print('message1////........',message)

        # Twilio API URL (Check if this is the correct URL format)
        url = f"http://45.118.162.148:21465/api/{session}/send-message"
        print(f"Constructed URL: {url}")  # Debugging the URL

        payload = {
            'phone': phone_number,  # Ensure phone number is formatted correctly
            'message': message,  # The message body
        }
        print('payload......', payload)
        headers = {
            'Authorization': f'Bearer {get_token}',
            'Content-Type': 'application/json'  # Optional: specify content type
        }
        print('headers......', headers)
        # Send the WhatsApp message
        response = requests.post(url, json=payload, headers=headers)
        print("response.......", response)

        _logger.info(f"Response Status Code: {response.status_code}")
        _logger.info(f"Response Content: {response.text}")

        if response.status_code == 201 or response.status_code == 200:
            _logger.info("Message sent successfully.")
        else:
            _logger.error(f"Failed to send message: {response.text}")
            raise Exception(f"Error sending message: {response.text}")


        @api.model
        def create(self, vals):
            lead = super(MailMail, self).create(vals)

            # Send WhatsApp message after lead creation
            if lead.phone:
                # message = f"Hello {lead.name}, thank you for reaching out to us. Our team will contact you shortly!"
                try:
                    self.send_whatsapp_message(lead.phone, message)
                except Exception as e:
                    _logger.error(f"Failed to send WhatsApp message: {str(e)}")

            return lead
