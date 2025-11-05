
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Inherit the res_config_settings model to add a selection field
    and a boolean field for enabling WhatsApp functionality."""
    _inherit = 'res.config.settings'

    pos_whatsapp_enabled = fields.Boolean(
        related="pos_config_id.pos_whatsapp_enabled", readonly=False,
        help='Checks WhatsApp Enabled button '
             'active or not')
    apply_send_receipt_or_invoice = fields.Selection([
        ('send_receipt', 'Send Receipt'),
        ('send_invoice', 'Send Invoice')
    ], string="Apply Send Receipt or Invoice",
        related="pos_config_id.apply_send_receipt_or_invoice",
        readonly=False,
        help='Select either Receipt or Invoice for sending to WhatsApp.')
