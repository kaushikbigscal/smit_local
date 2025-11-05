
from odoo import models


class PosSession(models.Model):
    """Inherit the pos_session model to load the WhatsApp number field into
    the POS session."""
    _inherit = 'pos.session'

    def _loader_params_res_partner(self):
        """Extends the loader parameters for the res_partner model to include
        the 'whatsapp_number' field."""
        result = super()._loader_params_res_partner()
        result['search_params']['fields'].extend(['whatsapp_number'])
        return result

    def _loader_params_res_users(self):
        """Extends the loader parameters for the res_users model to include
        the 'whatsapp_groups_checks' field."""
        result = super()._loader_params_res_users()
        result['search_params']['fields'].extend(['whatsapp_groups_checks'])
        return result
