from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    company_type = fields.Selection(
        selection=[
            ('person', 'Individual'),
            ('company', 'Company'),
            ('distribution', 'Distributor'),
        ],
        string='Company Type',
        store=True,
    )

    warehouse_id = fields.Many2one('stock.warehouse', string='Distributor Warehouse')

    @api.depends('is_company')
    def _compute_company_type(self):
        """Keep the current value if it's 'distribution', else use standard logic."""
        for partner in self:
            if partner.company_type == 'distribution':
                partner.company_type = 'distribution'
            else:
                # fallback to Odoo logic
                partner.company_type = 'company' if partner.is_company else 'person'

    def _write_company_type(self):
        """Write correct flags when 'distribution' selected."""
        for partner in self:
            if partner.company_type == 'distribution':
                # decide how you want is_company to behave
                partner.is_company = True
            else:
                partner.is_company = (partner.company_type == 'company')

    @api.constrains('supplier_rank', 'company_type')
    def _check_distribution_not_vendor(self):
        for partner in self:
            if partner.company_type == 'distribution' and partner.supplier_rank > 0:
                raise ValidationError(
                    "A partner with Company Type 'Distribution' cannot be a Vendor."
                )

    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields=allfields, attributes=attributes)
        if 'company_type' in res and 'selection' in res['company_type']:
            enable_distribution = self.env['ir.config_parameter'].sudo().get_param(
                'product_installation.enable_distributor', default='False'
            )
            enabled = str(enable_distribution).lower() in ('true', '1', 'yes')
            if not enabled:
                res['company_type']['selection'] = [
                    s for s in res['company_type']['selection'] if s[0] != 'distribution'
                ]
        return res

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner in partners:
            if partner.company_type == 'distribution' and not partner.warehouse_id:
                partner._create_distributor_warehouse()
        return partners

    def write(self, vals):
        res = super().write(vals)
        for partner in self:
            if partner.company_type == 'distribution' and not partner.warehouse_id:
                partner._create_distributor_warehouse()
        return res

    def _create_distributor_warehouse(self):
        """Create warehouse for distributor with name as partner name"""
        StockWarehouse = self.env['stock.warehouse']
        StockLocation = self.env['stock.location']

        for partner in self:
            if partner.warehouse_id:
                continue  # Skip if already has warehouse

            # Check if a warehouse with the same name already exists
            existing_warehouse = StockWarehouse.search([('name', '=', partner.name)], limit=1)
            if existing_warehouse:
                partner.warehouse_id = existing_warehouse.id
                continue

            # Create internal stock location
            main_loc = StockLocation.create({
                'name': f'{partner.name} Stock',
                'usage': 'internal',
            })

            # Create delivery location
            delivery_loc = StockLocation.create({
                'name': f'{partner.name} Delivery',
                'usage': 'customer',
            })

            # Create warehouse
            warehouse = StockWarehouse.create({
                'name': partner.name,
                'code': partner.name[:5].upper(),
                'lot_stock_id': main_loc.id,
                'view_location_id': main_loc.id,
                'wh_input_stock_loc_id': main_loc.id,
                'wh_output_stock_loc_id': delivery_loc.id,
                'company_id':partner.company_id.id,
                'is_distributor_warehouse': True,
            })

            # Link warehouse to distributor
            partner.warehouse_id = warehouse.id
