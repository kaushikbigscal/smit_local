from odoo import models, fields, api


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """
        Override the search_read method to dynamically resolve actions.
        """
        # Call the original method to get the menus
        menus = super(IrUiMenu, self).search_read(domain, fields, offset, limit, order)

        # Check for actions in menus and resolve them if needed
        for menu in menus:
            action = menu.get('action')
            if action and action.startswith('ir.actions.server'):
                action_id = int(action.split(',')[1])
                server_action = self.env['ir.actions.server'].browse(action_id)
                if server_action.exists():
                    # Execute the server action and resolve its resulting action
                    result = server_action.run()
                    if isinstance(result, dict) and result.get('type') == 'ir.actions.act_window':
                        menu['action'] = f"ir.actions.act_window,{result.get('id')}"

        return menus
