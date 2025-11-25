from odoo import http
from odoo.http import request


class AutoRefreshController(http.Controller):

    @http.route('/web_auto_refresh/config', type='json', auth='public')
    def get_auto_refresh_config(self):
        """Safe endpoint to return refresh settings (sudo access)."""
        try:
            params = request.env['ir.config_parameter'].sudo()
            enabled = params.get_param('web_auto_refresh.enable_auto_refresh', 'False')
            interval = params.get_param('web_auto_refresh.auto_refresh_interval', '0')
            return {
                'enabled': enabled == 'True',
                'interval': int(interval or 0),
            }
        except Exception as e:
            return {'error': str(e)}
