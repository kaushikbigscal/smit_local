from odoo import models, fields, api


class CityZip(models.Model):
    _name = 'city.zip'
    _description = 'cities and Zip'

    name = fields.Char(string='Zip Code', required=True)
    city_id = fields.Many2one('state.city', string='City',required=True,)