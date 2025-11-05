import base64
import requests
from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):

    _inherit = 'pos.order'

    def action_send_invoice(self, **kwargs):

        instant = self.env['configuration.manager'].search(
            [('state', '=', 'verified'),
             ('config_id', '=', kwargs.get('config_id'))], limit=1)
        _logger.info(f"Session ID {instant.token}")

        order = self.search([('id', '=', kwargs.get('order_id'))])

        
        if not order.account_move:
            order.action_pos_order_invoice()
        attachment_id = self.env['ir.attachment'].search([
            ('res_model', '=', 'mail.message'),
            ('res_id', 'in', order.account_move.message_ids.ids)])
        if not attachment_id:
            report = self.env['ir.actions.report']._render_qweb_pdf(
                "account.account_invoices", order.account_move.ids[0])
            values = {
                'name': "Invoice" + order.name,
                'type': 'binary',
                'datas': base64.b64encode(report[0]),
                'store_fname': base64.b64encode(report[0]),
                'mimetype': 'application/pdf',
            }
            attachment_id = self.env['ir.attachment'].create(values)
        if instant:
            if order.partner_id.mobile:

                url = f"http://{instant.ip_address}:{instant.port}/api/{instant.instance}/send-file"

                _logger.info(f"Session ID {instant.instance} url {instant.ip_address} port {url}")

                payload = {
                    "phone": order.partner_id.mobile,
                    "isGroup": False,
                    "isNewsletter": False,
                    "filename": attachment_id.name,
                    "caption": "Your Invoice is here! Thank You Visit Again <br/> Follow Us On Instgram: https://www.instagram.com/jalaram_fashion.1",
                    "base64": f"data:application/pdf;base64,{attachment_id.datas.decode('utf-8')}"
                }
                
                headers = {
                    'Authorization': f'Bearer {instant.fetched_token}',  # Pass the token in the headers
                    'Content-Type': 'application/json',  # Assuming the API expects JSON content
                    'Accept': 'application/json'
                }

                		
                try:
                    response = requests.post(url, json=payload, headers=headers)
                    _logger.info(f"status {response.status_code} headerssss{headers}")
                    response.raise_for_status()
                    if response.status_code == 200:
                        self.env['whatsapp.message'].create({
                            'status': 'sent',
                            'from_user_id': self.env.user.id,
                            'to_user': order.partner_id.whatsapp_number,
                            'user_name': order.partner_id.name,
                            'body': 'Your Invoice is here',
                            'attachment_id': attachment_id.id,
                            'date_and_time_sent': fields.datetime.now()
                        })
                except requests.RequestException as e:
                    return {'status': 'error', 'message': str(e)}
            else:
                return {'status': 'error',
                        'message': 'Partner have not a Whatsapp Number'}
        else:
            return {'status': 'error',
                    'message': 'You are not connected with API'}

    # def action_send_receipt(self, name, partner, ticket):
    #     """ Sends a receipt on WhatsApp if WhatsApp is enabled and
    #     the partner has a WhatsApp number is provided."""
    #     self.ensure_one()
    #     filename = 'Receipt-' + name + '.jpg'
    #     receipt = self.env['ir.attachment'].create({
    #         'name': filename,
    #         'type': 'binary',
    #         'datas': ticket,
    #         'res_model': 'pos.order',
    #         'res_id': self.ids[0],
    #         'mimetype': 'image/jpeg',
    #     })
    #     instant = self.env['configuration.manager'].search(
    #         [('state', '=', 'verified'),
    #          ('config_id', '=', partner['config_id'])], limit=1)
    #     if instant:
    #         if partner['whatsapp']:
    #             url = f"http://139.59.83.216:8076/api/{instant.instance}/send-file"
    #             payload = {
    #                 "token": instant.token,
    #                 "to": partner['whatsapp'],
    #                 "filename": receipt.name,
    #                 "document": receipt.datas.decode('utf-8'),
    #                 "caption": "Your Receipt is here",
    #             }
    #             headers = {'content-type': 'application/x-www-form-urlencoded'}
    #             try:
    #                 response = requests.post(url, data=payload, headers=headers)
    #                 response.raise_for_status()
    #                 if response.status_code == 200:
    #                     self.env['whatsapp.message'].create({
    #                         'status': 'sent',
    #                         'from_user_id': self.env.user.id,
    #                         'to_user': partner['whatsapp'],
    #                         'user_name': partner['name'],
    #                         'body': 'Your Receipt is here',
    #                         'attachment_id': receipt.id,
    #                         'date_and_time_sent': fields.datetime.now()
    #                     })
    #             except requests.RequestException as e:
    #                 return {'status': 'error', 'message': str(e)}
    #         else:
    #             return {'status': 'error',
    #                     'message': 'Partner have not a Whatsapp Number'}
    #     else:
    #         return {'status': 'error',
    #                 'message': 'You are not connected with API'}

    # def get_instance(self, **kwargs):
    #     """Retrieves the verified configuration instance."""
    #     instant = self.env['configuration.manager'].search(
    #         [('state', '=', 'verified'),
    #          ('config_id', '=', kwargs.get('config_id'))], limit=1)
    #     return {
    #         'instant_id': instant.id
    #     }
