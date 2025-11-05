from odoo import models, fields, api


class StateCity(models.Model):
    _name = 'state.city'
    _description = 'States and Cities'

    name = fields.Char(string='City Name', required=True)
    state_id = fields.Many2one('res.country.state', string='State', required=True,
                               domain=[('country_id.code', '=', 'IN')])
