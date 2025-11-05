
from odoo import fields, models


class ResUsers(models.Model):
    """Inherit the res_user model to add a field for the WhatsApp Groups
     Enabled or not."""
    _inherit = 'res.users'

    whatsapp_groups_checks = fields.Boolean(
        string='WhatsApp Groups Enabled or not',
        compute="_compute_pos_receipt_invoice_send_whatsapp_group_user",
        help='A field that checks groups is added or not.')

    def _compute_pos_receipt_invoice_send_whatsapp_group_user(self):
        self.whatsapp_groups_checks = self.user_has_groups(
            'pos_receipt_invoice_send_whatsapp.pos_receipt_invoice_send_whatsapp_group_user')
