from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    device_lock_enabled = fields.Boolean(
        string='Enable Device Lock',
        default=False,
        help='Enable device lock for all users in this company. When enabled, users will be restricted to login from registered devices only.'
    )

    def write(self, vals):
        result = super().write(vals)
        if 'device_lock_enabled' in vals:
            self._update_device_lock_menu()
        return result

    def _update_device_lock_menu(self):
        """Update menu visibility based on device lock settings"""
        menu = self.env.ref('device_security.menu_user_device_lock', raise_if_not_found=False)
        if menu:
            # Check if any company has device lock enabled
            any_enabled = self.search([('device_lock_enabled', '=', True)], limit=1)
            menu.active = bool(any_enabled)
