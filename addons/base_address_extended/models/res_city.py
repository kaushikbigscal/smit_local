# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.osv import expression


class City(models.Model):
    _name = 'res.city'
    _description = 'City'
    _order = 'name'
    _rec_names_search = ['name']

    name = fields.Char("Name", required=True, translate=True)
    # zipcode = fields.Char("Zip")
    country_id = fields.Many2one(comodel_name='res.country', string='Country', required=True)
    state_id = fields.Many2one(comodel_name='res.country.state', string='State',
                               domain="[('country_id', '=', country_id)]")

    @api.depends('name')
    def _compute_display_name(self):
        for city in self:
            name = city.name
            city.display_name = name
