from odoo import models, fields, api
from odoo.exceptions import UserError


class UserDeviceLock(models.Model):
    _name = 'user.device.lock'
    _description = 'User Device Lock'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade', index=True)
    device_uuid = fields.Char(string='Device UUID', help='Unique identifier for the registered device')
    last_used = fields.Datetime(string='Last Used', default=fields.Datetime.now, index=True)
    login_type = fields.Selection([
        ('web', 'Web'),
        ('mobile', 'Mobile'),
    ], string='Login Type', help='Type of login when device was last used')
    is_active = fields.Boolean(string='Active', default=True, help='Whether this device lock is active')

    _sql_constraints = [
        ('unique_user_device', 'unique(user_id)', 'Each user can have only one device lock record!')
    ]

    def reset_device_lock(self):
        """
        Reset device UUID to allow re-registration on next login.
        This is used by administrators to reset user devices.
        """
        for rec in self:
            rec.write({
                'device_uuid': False,
                'last_used': fields.Datetime.now(),
                'is_active': True
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Device Reset',
                'message': f'Device lock has been reset for {len(self)} user(s). They can register a new device on next login.',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def create(self, vals):
        """Override create to ensure only one record per user"""
        existing = self.search([('user_id', '=', vals.get('user_id'))])
        if existing:
            existing.write(vals)
            return existing
        return super().create(vals)

    def name_get(self):
        """Custom display name for better UX"""
        result = []
        for record in self:
            user_name = record.user_id.name
            device_type = record.login_type or 'Unknown'
            last_used = record.last_used.strftime('%Y-%m-%d %H:%M') if record.last_used else 'Never'
            name = f"{user_name} ({device_type}) - Last: {last_used}"
            result.append((record.id, name))
        return result

    def copy_device_uuid_and_update_debug(self):
        """Copy device UUID to clipboard AND update debug token field"""
        self.ensure_one()

        if not self.device_uuid:
            raise UserError("No device UUID available to copy.")

        # Update the debug token field
        self.user_id.write({'debug_access_token': self.device_uuid})

        # Return custom client action to copy UUID
        return {
            'type': 'ir.actions.client',
            'tag': 'copy_uuid_to_clipboard',
            'params': {
                'uuid': self.device_uuid,
                'message': f'Debug token updated with UUID: {self.device_uuid}'
            }
        }


class UserDeviceInfo(models.Model):
    _name = 'user.device.info'
    _description = 'User Device Info'
    _rec_name = 'user_id'

    _sql_constraints = [
        ('unique_user_info', 'unique(user_id)', 'Device info will be single record per user!')
    ]

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade', index=True)
    device_os = fields.Char("Device OS", size=255)
    device_browser = fields.Char("Browser", size=255)
    device_user_agent = fields.Text("User Agent")
    device_platform = fields.Char("Platform", size=255)
    device_vendor = fields.Char("Vendor", size=255)
    device_model = fields.Char("Device Model", size=255)
    device_type = fields.Selection([
        ('web', 'Web/Desktop'),
        ('mobile', 'Mobile/Tablet'),
    ], string="Device Type")
    screen_resolution = fields.Char("Screen Resolution", size=50)
    timezone = fields.Char("Timezone", size=100)
    language = fields.Char("Language", size=10)
    last_updated = fields.Datetime("Last Updated", default=fields.Datetime.now, index=True)
    client_ip = fields.Char("IP Address", size=255)

    @api.model
    def create(self, vals):
        """Override create to ensure only one record per user"""
        existing = self.search([('user_id', '=', vals.get('user_id'))])
        if existing:
            existing.write(vals)
            return existing
        return super().create(vals)

    def name_get(self):
        """Custom display name for better UX"""
        result = []
        for record in self:
            user_name = record.user_id.name
            device_info = f"{record.device_os or 'Unknown OS'} - {record.device_browser or 'Unknown Browser'}"
            if record.device_model and record.device_model != 'Unknown':
                device_info = f"{record.device_model} - {device_info}"
            name = f"{user_name}: {device_info}"
            result.append((record.id, name))
        return result
