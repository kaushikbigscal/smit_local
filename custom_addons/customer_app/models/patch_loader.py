from odoo import models, api
from . import customer_product_patch

class PatchCustomerProductMapping(models.AbstractModel):
    _name = 'customer.product.mapping.hook'

    @api.model
    def _register_hook(self):
        customer_product_patch.patch_customer_notifications_on_model(self.env)
        return super()._register_hook()