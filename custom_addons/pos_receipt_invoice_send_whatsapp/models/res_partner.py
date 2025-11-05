
from odoo import fields, models


class ResPartner(models.Model):
    """Inherit the res_partner model to add a field for the WhatsApp number."""
    _inherit = 'res.partner'

    whatsapp_number = fields.Char(string='WhatsApp Number',
                                  help='A field is needed to add the '
                                       'WhatsApp number of the partner.')
