# models/notification_service.py
import logging
import firebase_admin
from firebase_admin import credentials, messaging
from odoo import models, api, fields, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NotificationService(models.AbstractModel):
    _name = 'mobile.notification.service'
    _description = 'Mobile Notification Service'

    @api.model
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Existing initialization code remains the same
            firebase_cred_path = self.env['ir.config_parameter'].sudo().get_param('firebase.credentials_path')

            if not firebase_cred_path:
                _logger.error("Firebase credentials path not configured")
                return False

            # Try to initialize Firebase if not already initialized
            try:
                firebase_admin.get_app()
            except ValueError:
                cred = credentials.Certificate(firebase_cred_path)
                firebase_admin.initialize_app(cred)

            return True
        except Exception as e:
            _logger.error(f"Firebase initialization error: {e}")
            return False

    @api.model
    def send_fcm_notification(self, user_ids, title, body, payload):
        """
        Send FCM notification to specified users

        :param user_ids: List of user IDs to send notification
        :param title: Notification title
        :param body: Notification body
        :param payload: Additional data for notification
        """
        # Ensure Firebase is initialized
        if not self._initialize_firebase():
            raise UserError("Firebase is not properly initialized")

        try:
            # Convert single user ID to list
            if not isinstance(user_ids, list):
                user_ids = [user_ids]
                print(user_ids)
            # Fetch device tokens for users
            device_tokens = self.env['res.users'].search([
                ('id', 'in', user_ids),
                ('active', '=', True)
            ]).mapped('device_token')

            # Ensure all tokens are strings
            _logger.info(f"Retrieved device tokens: {device_tokens}")

            if not device_tokens:
                _logger.info("No active device tokens found")
                return False

            # Prepare MulticastMessage
            messages = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),

                android=messaging.AndroidConfig(
                    priority='high'
                ),

                tokens=device_tokens,
                data=payload or {}
            )

            # Send notifications
            response = messaging.send_each_for_multicast(messages)

            # Log notification results
            if payload.get("type") == "normal":
                model_name = payload.get("model", "Unknown Model")
                self.env['notification.log'].create_log(
                    'fcm_notification',
                    f'{title}',
                    f'{body}',
                    user_ids,
                    model_name,
                    f'\n'.join([f'- {key}: {value}' for key, value in payload.items()]) + '\n',
                    f'Sent to {len(device_tokens)} devices.\n'
                    f'Success: {response.success_count}, Failure: {response.failure_count}'
                )

            # Handle failed tokens
            if response.failure_count > 0:
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        _logger.error(f"Failed to send to token {device_tokens[idx]}: {resp.exception}")

            return response.success_count > 0

        except Exception as e:
            _logger.error(f"FCM Notification Error: {e}")


class MailThreadFCM(models.AbstractModel):
    _inherit = 'mail.thread'

    def _notify_thread(self, message, msg_vals=False, **kwargs):


        # Call super to retain existing functionality
        recipients_data = super()._notify_thread(message, msg_vals=msg_vals, **kwargs)

        # Avoid extra processing if no recipients or message is not set
        if not message or not recipients_data:
            return recipients_data

        try:
            author_name = message.author_id.name
            _logger.info(f"msg_vals: {msg_vals}")
            _logger.info(f"message.body: {message.body}")

            # Prepare FCM payload
            fcm_payload = {
                'title': str(msg_vals.get('record_name') or f'New Message from {author_name}'),
                'body': str(tools.html2plaintext(message.body) or "Message"),
                'data': {
                    'message_id': str(message.id),
                    'model': str(message.model or ''),
                    'res_id': str(message.res_id or ''),
                    'record_name': str(message.record_name or ''),
                    'author_name': str(author_name),
                    'type': "normal"
                }
            }

            # Collect user IDs to notify
            user_ids = []
            for recipient in recipients_data:
                if recipient['active']:
                    partner = self.env['res.partner'].browse(recipient['id'])
                    if partner.user_ids:
                        user_ids.extend(partner.user_ids.ids)

            # Exclude the author from notification list
            user_ids = [uid for uid in user_ids if uid != message.author_id.id]

            if user_ids:
                users_with_tokens = self.env['res.users'].search([
                    ('id', 'in', user_ids),
                    ('active', '=', True),
                    ('device_token', '!=', False)
                ])

                device_tokens = [
                    str(token).strip()
                    for token in users_with_tokens.mapped('device_token')
                    if token and isinstance(token, (str, int))
                ]

                if device_tokens:
                    self.env['mobile.notification.service'].send_fcm_notification(
                        user_ids=users_with_tokens.ids,
                        title=fcm_payload['title'],
                        body=fcm_payload['body'],
                        payload=fcm_payload['data']
                    )
                else:
                    _logger.info("No valid device tokens found")

        except Exception as e:
            _logger.error(f"Error sending FCM notification in mail_thread: {e}")

        return recipients_data
