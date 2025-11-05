from odoo import models, fields, api
from odoo.exceptions import UserError


class FCMTestNotificationWizard(models.TransientModel):
    _name = 'fcm.test.notification.wizard'
    _description = 'FCM Test Notification Wizard'

    user_id = fields.Many2one(
        'res.users',
        string='Recipient',
        required=True,
        default=lambda self: self.env.user
    )
    title = fields.Char(
        string='Notification Title',
        default='Odoo FCM Test Notification',
        required=True
    )
    message = fields.Text(
        string='Notification Message',
        default='This is a test notification to verify FCM integration.',
        required=True
    )

    @api.model
    def check_device_tokens(self, user_id):
        """
        Check if the user has registered device tokens
        """
        tokens = self.env['res.users'].search([
            ('id', '=', user_id),
            ('active', '=', True)
        ])
        return tokens

    def send_test_notification(self):
        """
        Send a test notification to the selected user
        """
        # Check for device tokens
        tokens = self.check_device_tokens(self.user_id.id)
        if not tokens:
            raise UserError(
                f"No active device tokens found for user {self.user_id.name}. "
                "Please ensure the mobile app is installed and token is registered."
            )

        # Prepare payload
        payload = {
            'timestamp': fields.Datetime.now().isoformat(),
        }

        # Send notification
        result = self.env['mobile.notification.service'].send_fcm_notification(
            user_ids=self.user_id.id,
            title=self.title,
            body=self.message,
            payload=payload
        )
        # Provide feedback
        if result:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Notification Test',
                    'message': f'Test notification sent to {self.user_id.name}',
                    'type': 'success',
                }
            }
        else:
            raise UserError("Failed to send test notification. Check server logs for details.")
