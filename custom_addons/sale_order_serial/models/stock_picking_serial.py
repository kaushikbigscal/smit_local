from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    serial_line_ids = fields.One2many('sale.order.serial', 'picking_id', string='Serial Numbers')
    product_ids = fields.Many2many(
        'product.product',
        compute='_compute_product_ids',
        string='Products in Picking',
        store=False
    )

    @api.depends('move_line_ids.product_id')
    def _compute_product_ids(self):
        for picking in self:
            picking.product_ids = [(6, 0, picking.move_line_ids.mapped('product_id').ids)]

    def write(self, vals):
        res = super(StockPicking, self).write(vals)
        if 'serial_line_ids' in vals:
            for record in self:
                if record.sale_id:
                    # Update serial numbers in sale order
                    for serial in record.serial_line_ids:
                        if not serial.order_id:
                            serial.order_id = record.sale_id.id
        return res
