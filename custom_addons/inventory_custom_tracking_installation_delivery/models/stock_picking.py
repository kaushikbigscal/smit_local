from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    inventory_delivery_responsible = fields.Boolean(
        string="Inventory Delivery Responsible",
        help="If checked, the user will be available for selection as Delivery Responsible",
    )


# stock_picking.py
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_delivery_responsible_domain(self):
        try:
            group = self.env.ref("inventory_custom_tracking_installation_delivery.group_technical_user",
                                 raise_if_not_found=False)
            if not group:
                raise UserError(
                    "The group 'group_technical_user' does not exist in the module 'inventory_custom_tracking_installation_delivery'.")
            return [("groups_id", "=", group.id)]
        except Exception as e:
            raise UserError(f"An error occurred while fetching the Delivery Responsible domain: {str(e)}")

    delivery_responsible = fields.Many2one(
        'res.users',
        string="Delivery Responsible",
        domain=lambda self: self._get_delivery_responsible_domain(),
        tracking=True,
    )
    installation_date = fields.Datetime(string="Installation Date")
    picking_parts_ids = fields.One2many('stock.picking.parts', 'picking_id', string='Parts List')

    def button_create_task(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Task',
            'res_model': 'validate.task.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id
            },
        }

    def button_validate(self):
        # Validate serial numbers for parts
        for part in self.picking_parts_ids:
            if part.tracking == 'serial':
                if len(part.lot_ids) != part.quantity:
                    raise UserError(
                        _('You need to provide a serial number for each part quantity for %s') % part.part_name)

        # Create/update stock moves for parts
        self.picking_parts_ids._create_stock_moves()

        return super(StockPicking, self).button_validate()

    @api.model
    def create(self, vals):
        picking = super(StockPicking, self).create(vals)

        # Check if the picking is related to a sale order
        if picking.origin and not picking.picking_parts_ids:
            sale_order = self.env['sale.order'].search([('name', '=', picking.origin)], limit=1)
            if sale_order:
                _logger.info("Transferring parts from Sale Order: %s to Picking: %s", sale_order.name, picking.name)
                picking._transfer_parts_from_sale_order(sale_order)
            else:
                _logger.warning("No Sale Order found for Picking: %s", picking.name)

        return picking

    def _transfer_parts_from_sale_order(self, sale_order):
        for picking in self:
            if sale_order.order_parts_ids:
                _logger.info("Found parts in Sale Order: %s", sale_order.name)
                # Clear existing parts if any
                picking.picking_parts_ids.unlink()
                for part in sale_order.order_parts_ids:
                    part_record = self.env['stock.picking.parts'].create({
                        'picking_id': picking.id,
                        'sale_order_part_id': part.id,
                        'quantity': part.quantity,
                    })
                    _logger.info("Created part record in Picking: %s", part_record)
            else:
                _logger.warning("No parts found in Sale Order: %s", sale_order.name)


class StockPickingParts(models.Model):
    _name = 'stock.picking.parts'
    _description = 'Stock Picking Parts'

    picking_id = fields.Many2one('stock.picking', string='Picking', required=True, ondelete='cascade')
    sale_order_part_id = fields.Many2one('sale.order.parts', string='Sale Order Part')
    product_id = fields.Many2one('product.template', related='sale_order_part_id.product_id', string='Main Product',
                                 store=True)
    part_data_id = fields.Many2one('product.part_data', related='sale_order_part_id.part_data_id', string='Part',
                                   store=True)
    part_name = fields.Char(string='Part Name', compute='_compute_names', store=True)
    main_product_name = fields.Char(string='Product Name', compute='_compute_names', store=True)
    quantity = fields.Integer(string='Quantity', store=True)
    original_product_id = fields.Many2one('product.product', string="part's original product id",
                                          compute='_compute_original_part_product', search=True)
    lot_ids = fields.Many2many(
        'stock.lot',
        string='Serial Numbers',
        domain="[('product_id', '=', original_product_id)]",
    )

    # tracking = fields.Selection(related='original_product_id.tracking', string='Tracking', store=True)
    tracking = fields.Char(compute='_compute_tracking', string='Tracking', store=True)

    move_id = fields.Many2one('stock.move', string='Stock Move')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='picking_id.company_id',
        store=True
    )

    @api.depends('product_id', 'part_data_id')
    def _compute_names(self):
        for record in self:
            record.main_product_name = record.product_id.name if record.product_id else ''
            record.part_name = record.part_data_id.display_name.name if record.part_data_id else ''

    @api.depends('part_data_id')
    def _compute_original_part_product(self):
        for record in self:
            if record.part_data_id:
                product = self.env['product.product'].search([('name', '=', record.part_name)], limit=1)
                if product:
                    record.original_product_id = product
                else:
                    record.original_product_id = False

    @api.depends('original_product_id')
    def _compute_tracking(self):
        for record in self:
            if record.original_product_id:
                record.tracking = record.original_product_id.tracking
            else:
                record.tracking = False
            print(record.tracking)

    def _create_stock_moves(self):
        StockMove = self.env['stock.move']
        StockMoveLine = self.env['stock.move.line']
        for part in self:

            if not part.move_id:
                move_vals = {
                    'name': f'Part: {part.part_name}',
                    'product_id': part.original_product_id.id,
                    'product_uom_qty': part.quantity,
                    'product_uom': part.original_product_id.uom_id.id,
                    'picking_id': part.picking_id.id,
                    'location_id': part.picking_id.location_id.id,
                    'location_dest_id': part.picking_id.location_dest_id.id,
                    'state': 'draft',

                }
                move = StockMove.create(move_vals)
                part.move_id = move.id

                # Check for serial number uniqueness and create move lines
                if part.tracking == 'serial' and part.lot_ids:
                    move_lines = []
                    for lot in part.lot_ids:
                        # Create move lines if validation passes
                        move_line_vals = {
                            'move_id': move.id,
                            'product_id': move.product_id.id,
                            'product_uom_id': move.product_uom.id,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'lot_id': lot.id,
                            'quantity': 1,
                            # Use 'quantity_done' for stock.move.line to track the quantity moved
                        }
                        StockMoveLine.create(move_line_vals)
