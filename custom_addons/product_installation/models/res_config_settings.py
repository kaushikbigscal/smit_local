from odoo import fields, models,api,_
from odoo.exceptions import ValidationError

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_distributor = fields.Boolean(
        string="Distributor Feature",
        config_parameter='product_installation.enable_distributor'
    )

    @api.model
    def _register_hook(self):
        """Set initial menu visibility when module is installed/updated"""
        res = super()._register_hook()
        self._update_menu_visibility()
        return res

    @api.model
    def _update_menu_visibility(self):
        param_value = self.env['ir.config_parameter'].sudo().get_param(
            'product_installation.enable_distributor', 'False'
        )
        enabled = (param_value == 'True')
        menu_xml_ids = [
            'product_installation.menu_product_stock_distributor',
            'product_installation.menu_distribution_management',
        ]

        for xml_id in menu_xml_ids:
            menu = self.env.ref(xml_id, raise_if_not_found=False)
            if menu:
                menu.sudo().active = enabled

    def set_values(self):
        param = self.env['ir.config_parameter'].sudo()
        # Get old value BEFORE saving new one
        old_value = param.get_param('product_installation.enable_distributor', 'False')

        # Save the new value
        res = super().set_values()
        self._update_menu_visibility()

        new_value = 'True' if self.enable_distributor else 'False'

        # Only run validation if disabling the distributor feature
        if old_value == 'True' and new_value == 'False':
            distributor_whs = self.env['stock.warehouse'].search([
                ('is_distributor_warehouse', '=', True),
                ('active', '=', True)
            ])
            for wh in distributor_whs:
                # Check actual stock using stock.quant
                quants = self.env['stock.quant'].search([
                    ('location_id.usage', '=', 'internal'),
                    ('location_id.warehouse_id', '=', wh.id),
                    ('quantity', '!=', 0)
                ])
                product_names = ', '.join(quants.mapped('product_id.display_name'))
                if quants:
                    raise ValidationError(_(
                        "You cannot disable Distributor Feature because warehouse '%s' still has stock: %s. First settle stock."
                    ) % (wh.display_name, product_names))
            # If no stock, deactivate distributor warehouses
            distributor_whs.write({'active': False})

        return res
