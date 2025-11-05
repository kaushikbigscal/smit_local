from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    login_restriction = fields.Selection([
        ('web', 'Web Only'),
        ('mobile', 'Mobile Only'),
        ('none', 'No Restriction'),
    ], string='Login Restrictions', default='none',
        help='Restrict user login to specific platforms. This setting works with Device Lock feature.')

    device_lock_ids = fields.One2many(
        'user.device.lock',
        'user_id',
        string='Device Locks',
        help='Registered devices for this user'
    )

    debug_access_token = fields.Char(string="Debug Access Token")
    debug_token_last_used = fields.Datetime(string="Last Used",
                                            help="Last time debug token was used")

    show_device_lock_page = fields.Boolean(
        compute='_compute_show_device_lock_page', store=False
    )

    @api.depends('company_id.device_lock_enabled')
    def _compute_show_device_lock_page(self):
        for user in self:
            user.show_device_lock_page = not user.company_id.device_lock_enabled

    def write(self, vals):
        res = super().write(vals)
        if 'login_restriction' in vals:
            self.reset_user_device_lock()
        return res

    def reset_user_device_lock(self):
        """
        Reset device lock for this user - clears device UUID to allow re-registration
        """
        device_locks = self.env['user.device.lock'].search([('user_id', '=', self.id)])
        for lock in device_locks:
            lock.device_uuid = False
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Device Lock Reset',
                'message': f'Device lock has been reset for user {self.name}. They can now register a new device on next login.',
                'type': 'success',
                'sticky': False,
            }
        }

    def open_debug_login_page(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/session/logout?redirect=/web/login?device_lock_debug=1',
            'target': 'self',
        }

    def update_debug_token_usage(self):
        """
        Update last used timestamp when debug token is used
        and Clear debug token after Successfully login.

        """
        self.write({
            'debug_token_last_used': fields.Datetime.now(),
            'debug_access_token': False,
        })
