from odoo import models, fields, api


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    product_category_id = fields.Many2many('product.category', string='Product Category')
    product_id = fields.Many2many('product.product', string='Product')
    computed_product_domain_ids = fields.Many2many(
        'product.product',
        compute='_compute_product_domain_ids',
        string='Available Products',
        store=False
    )

    @api.depends('product_category_id')
    def _compute_product_domain_ids(self):
        for record in self:
            if record.product_category_id:
                categories = record.product_category_id
                all_cats = categories | categories.mapped('child_id')
                while True:
                    new_cats = all_cats.mapped('child_id') - all_cats
                    if not new_cats:
                        break
                    all_cats |= new_cats
                record.computed_product_domain_ids = self.env['product.product'].search([
                    ('categ_id', 'in', all_cats.ids)
                ])
            else:
                # If no category selected, show all products
                record.computed_product_domain_ids = self.env['product.product'].search([])
