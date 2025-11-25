from odoo import fields, models

class CustomerProductMapping(models.Model):
    _inherit = "customer.product.mapping"

    distributor_id = fields.Many2one('res.partner', domain=[('company_type', '=', 'distribution')])
    asset_status = fields.Selection([('allocated','Sold'),('unallocated','Unsold')],string="Status")
