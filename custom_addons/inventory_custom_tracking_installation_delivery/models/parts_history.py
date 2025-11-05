from odoo import models, fields, api
from odoo.api import ondelete


class PartHistory(models.Model):
    _name = 'part.history'
    _description = 'Part History Log'

    part_name = fields.Char("Part Name")
    customer_id = fields.Many2one('res.partner', string='Customer')
    product_id = fields.Many2one('product.template', string='Part')  # optional
    mapping_id = fields.Many2one('customer.product.mapping', string='Customer Product Mapping')
    task_id = fields.Many2one('project.task', string='Related Calls')
    action = fields.Selection([
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ], string='Action', required=True)
    description = fields.Char()
    date_time = fields.Datetime(default=lambda self: fields.Datetime.now(), required=True)
    part_service_type = fields.Selection([('replace', 'Replace'), ('repair', 'Repair')], string="Part Service Type")

    original_product_id = fields.Many2one('product.product', string="part's original product id",
                                          compute='_compute_original_part_product', search=True)
    serial_number_ids = fields.Many2one(
        'stock.lot',
        string='New Serial Number',
        domain="[('product_id', '=', original_product_id)]",
    )

    previous_serial_number_ids = fields.Many2one(comodel_name='stock.lot', string='Previous Serial Number', domain="[('product_id','=',original_product_id)]")


    @api.depends('product_id')
    def _compute_original_part_product(self):
        for record in self:
            if record.product_id:
                product = self.env['product.product'].search([('name', '=', record.product_id.name)], limit=1)
                record.original_product_id = product or False  # Always assign
            else:
                record.original_product_id = False







