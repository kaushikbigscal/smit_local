from odoo import http
from odoo.http import request


class MapController(http.Controller):

    @http.route('/effezient_web_map/partners', auth='user', type='json')
    def partner_locations(self, partner_ids=None):
        domain = [('partner_latitude', '!=', False), ('partner_longitude', '!=', False)]
        if partner_ids:
            domain.append(('id', 'in', partner_ids))
        partners = request.env['res.partner'].search(domain)
        return [
            {
                'id': p.id,
                'name': p.name,
                'partner_latitude': p.partner_latitude,
                'partner_longitude': p.partner_longitude
            } for p in partners
        ]

