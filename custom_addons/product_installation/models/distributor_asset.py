from odoo import fields,models
from odoo.exceptions import UserError

class DistributorAsset(models.Model):

    _name = 'distributor.asset'
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.template',string="Product")
    status = fields.Selection([('allocated','Sold'),('unallocated','Unsold')],string="Status")
    distributor_id = fields.Many2one(
        'res.partner', string='Distributor Name', required=True, tracking=True, ondelete='cascade',
        domain="[('parent_id', '=', False),('company_type', '=','distribution')]")

    is_distributor = fields.Boolean("Distributor")
    lot_id = fields.Many2one('stock.lot', string='Serial / Lot Number')

    def action_open_bulk_distributor_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'distributor.asset.change.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': self.ids,
                'active_model': self._name,
            },
        }


from odoo import models, fields, api

class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    is_distributor_warehouse = fields.Boolean(
        string="Distributor Warehouse",
        default=False,
        help="Tick this if the warehouse belongs to a distributor."
    )

    @api.model
    def get_current_warehouses(self, domain=None):
        """Override to ensure is_distributor_warehouse field is included"""
        if domain is None:
            domain = []

        warehouses = self.search(domain)
        # Return warehouse data with the distributor field
        result = []
        for warehouse in warehouses:
            wh_data = {
                'id': warehouse.id,
                'name': warehouse.name,
                'code': warehouse.code,
                'is_distributor_warehouse': warehouse.is_distributor_warehouse,
            }
            result.append(wh_data)
        return result


class DistributorAssetChangeWizard(models.TransientModel):
    _name = 'distributor.asset.change.wizard'
    _description = 'Change Distributor for Assets'



    new_distributor_id = fields.Many2one(
        'res.partner', string='New Distributor',
        domain="[('parent_id','=',False),('company_type','=','distribution')]",
        required=True,
    )

    def action_change_distributor(self):
        """Transfer selected distributor assets and their stock to a new distributor."""
        asset_ids = self.env.context.get('active_ids', [])
        assets = self.env['distributor.asset'].browse(asset_ids)

        if not assets:
            raise UserError("No assets selected.")

        old_distributor = assets[0].distributor_id
        old_warehouse = old_distributor.warehouse_id
        new_warehouse = self.new_distributor_id.warehouse_id

        if not old_warehouse or not new_warehouse:
            raise UserError("Both distributors must have a warehouse.")


        StockMove = self.env['stock.move']

        # Create a single internal picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.env.ref('stock.picking_type_internal').id,
            'location_id': old_warehouse.lot_stock_id.id,
            'location_dest_id': new_warehouse.lot_stock_id.id,
            'origin': 'Distributor Asset Transfer',
        })

        for asset in assets:
            if asset.status == 'allocated':
                raise UserError(f"Asset {asset.product_id.display_name} is Sold; cannot transfer.")

            product = asset.product_id.product_variant_id

            # Prepare stock move line values
            move_line_vals = {
                'product_id': product.id,
                'quantity': 1,  # actual quantity being moved
                'product_uom_id': product.uom_id.id,
                'location_id': old_warehouse.lot_stock_id.id,
                'location_dest_id': new_warehouse.lot_stock_id.id,
            }

            # Include lot_id if product is tracked
            if asset.lot_id:
                move_line_vals['lot_id'] = asset.lot_id.id

            # Create stock move with move_line
            StockMove.create({
                'name': f'Transfer {product.display_name}',
                'product_id': product.id,
                'product_uom_qty': 1,  # planned quantity
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': old_warehouse.lot_stock_id.id,
                'location_dest_id': new_warehouse.lot_stock_id.id,
                'move_line_ids': [(0, 0, move_line_vals)],
            })

            # Update distributor on the asset
            asset.distributor_id = self.new_distributor_id.id

        # Confirm and validate picking to move stock
        picking.action_confirm()
        picking.action_assign()
        picking.button_validate()

        return {'type': 'ir.actions.act_window_close'}
