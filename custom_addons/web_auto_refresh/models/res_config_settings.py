from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_auto_refresh = fields.Boolean(
        string="Enable Auto Refresh",
        config_parameter='web_auto_refresh.enable_auto_refresh',
        help="Enable periodic auto refresh for all web pages."
    )
    auto_refresh_interval = fields.Integer(
        string="Auto Refresh Interval (seconds)",
        config_parameter='web_auto_refresh.auto_refresh_interval',
        help="Set the time interval (in seconds) for page auto refresh.",
        default=60
    )

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'web_auto_refresh.enable_auto_refresh', self.enable_auto_refresh
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'web_auto_refresh.auto_refresh_interval', self.auto_refresh_interval
        )

    @api.model
    def get_values(self):
        res = super().get_values()
        res.update(
            enable_auto_refresh=self.env['ir.config_parameter'].sudo().get_param(
                'web_auto_refresh.enable_auto_refresh', 'False'
            ) == 'True',
            auto_refresh_interval=int(self.env['ir.config_parameter'].sudo().get_param(
                'web_auto_refresh.auto_refresh_interval', '0'
            )),
        )
        return res

    @api.onchange('enable_auto_refresh')
    def _onchange_enable_auto_refresh(self):
        """Automatically clear interval when disabled."""
        if not self.enable_auto_refresh:
            self.auto_refresh_interval = 0
