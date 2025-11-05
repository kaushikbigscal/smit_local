from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    serial_line_ids = fields.One2many('sale.order.serial', 'order_id', string='Serial Numbers')
    product_ids = fields.Many2many(
        'product.product',
        compute='_compute_product_ids',
        string='Products in Order',
        store=True
    )

    @api.depends('order_line.product_id')
    def _compute_product_ids(self):
        for order in self:
            order.product_ids = [(6, 0, order.order_line.mapped('product_id').ids)]

    def write(self, vals):
        res = super(SaleOrder, self).write(vals)
        if 'serial_line_ids' in vals:
            for record in self:
                # Get the related picking(s)
                pickings = self.env['stock.picking'].search([
                    ('sale_id', '=', record.id),
                    ('state', 'not in', ['done', 'cancel'])
                ])
                if pickings:
                    # Update serial numbers in the picking
                    for serial in record.serial_line_ids:
                        if not serial.picking_id:
                            serial.picking_id = pickings[0].id  # Link to the first available picking
        return res

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        # When confirming the sale order, link all serial numbers to the created picking
        for order in self:
            picking = self.env['stock.picking'].search([
                ('sale_id', '=', order.id),
                ('state', 'not in', ['done', 'cancel'])
            ], limit=1)
            if picking:
                order.serial_line_ids.write({'picking_id': picking.id})
        return res


class SaleOrderSerial(models.Model):
    _name = 'sale.order.serial'
    _description = 'Sale Order Serial Numbers'
    _rec_name = 'serial_number'

    order_id = fields.Many2one('sale.order', string='Sale Order', ondelete='cascade')
    picking_id = fields.Many2one('stock.picking', string='Stock Picking', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    serial_number = fields.Char(string='Serial Number', required=True, copy=False)

    @api.model
    def create(self, vals):
        record = super(SaleOrderSerial, self).create(vals)
        # If created from sale order, try to find and link to picking
        if record.order_id and not record.picking_id:
            picking = self.env['stock.picking'].search([
                ('sale_id', '=', record.order_id.id),
                ('state', 'not in', ['done', 'cancel'])
            ], limit=1)
            if picking:
                record.picking_id = picking.id
        # If created from picking, try to find and link to sale order
        elif record.picking_id and not record.order_id:
            if record.picking_id.sale_id:
                record.order_id = record.picking_id.sale_id.id
        return record

    def write(self, vals):
        res = super(SaleOrderSerial, self).write(vals)
        # When updating serial number from sale order
        if 'order_id' in vals and vals['order_id']:
            for record in self:
                if not record.picking_id:
                    picking = self.env['stock.picking'].search([
                        ('sale_id', '=', vals['order_id']),
                        ('state', 'not in', ['done', 'cancel'])
                    ], limit=1)
                    if picking:
                        record.picking_id = picking.id
        return res

    @api.constrains('product_id', 'order_id')
    def _check_product_quantity(self):
        for record in self:
            if record.order_id:  # Only check if order_id exists
                order_line = record.order_id.order_line.filtered(
                    lambda l: l.product_id == record.product_id
                )
                if not order_line:
                    raise ValidationError(_(
                        'Product %s is not in the order lines!'
                    ) % record.product_id.name)

                product_qty = order_line.product_uom_qty
                serial_count = self.search_count([
                    ('order_id', '=', record.order_id.id),
                    ('product_id', '=', record.product_id.id)
                ])
                if serial_count > product_qty:
                    raise ValidationError(_(
                        'You cannot add more serial numbers than the quantity ordered for product %s (Ordered: %s, Serial Numbers: %s)'
                    ) % (record.product_id.name, int(product_qty), serial_count))

    @api.constrains('serial_number')
    def _check_unique_serial(self):
        for record in self:
            if record.serial_number:
                domain = [('serial_number', '=', record.serial_number)]
                if record.id:
                    domain.append(('id', '!=', record.id))
                if self.search_count(domain):
                    raise ValidationError(_('Serial number %s already exists!') % record.serial_number)
