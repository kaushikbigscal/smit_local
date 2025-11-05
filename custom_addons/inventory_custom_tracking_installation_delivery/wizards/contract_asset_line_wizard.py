from odoo import models, fields, api

class AmcContractAssetLineWizard(models.TransientModel):
    _name = 'amc.contract.asset.line.wizard'
    _description = 'AMC Contract Asset Line Wizard'

    contract_id = fields.Many2one('amc.contract', string="Contract", required=True,
                                  default=lambda self: self._default_contract_id)
    customer_id = fields.Many2one(
        'res.partner', string='Customer Name', tracking=True, ondelete='cascade'
    )
    available_product_ids = fields.Many2many(
        'product.product', compute="_compute_available_products", store=True
    )
    product_id = fields.Many2one('product.product', string="Product", required=True,domain="[('id', 'in', available_product_ids)]", ondelete='cascade',)
    # part_product_id = fields.Many2one('product.product', string='Part Product', required=True ,domain=[('is_part', '=', True)])
    product_category = fields.Many2one(
        'product.category', string='Product Category', tracking=True)


    user_ids = fields.Many2one(comodel_name='res.users', string="Assignee")
    quantity = fields.Float(string="Quantity", default=1.0)
    cost = fields.Monetary(string="Charge")
    tax_ids = fields.Many2many('account.tax', string="Taxes", domain=[('type_tax_use', '=', 'sale')],)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id)

    track_by_serial_number = fields.Boolean(string="Track By Serial Number", store=True)
    visit = fields.Integer(string="Visits")

    @api.depends('customer_id', 'product_category')
    def _compute_available_products(self):
        """ Fetch available products based on the selected customer and source type """
        for record in self:
            if record.product_category:
                record.available_product_ids = self.env['product.product'].search([
                    ('categ_id', '=', record.product_category.id),
                    ('detailed_type', '=', 'product')
                ])
            elif not record.product_category:
                record.available_product_ids = self.env['product.product'].search([
                    ('detailed_type', '=', 'product')
                ])

            else:
                record.available_product_ids = self.env['product.product'].browse([])

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.cost = line.product_id.service_charge
                line.tax_ids=line.product_id.taxes_id

    def action_add_line(self):
        amc_contract_line_obj = self.env['amc.contract.asset.line']

        if self.track_by_serial_number:
            for _ in range(int(self.quantity)):
                amc_contract_line_obj.create({
                    'contract_id': self.contract_id.id,
                    'product_id': self.product_id.id,
                    'user_ids': self.user_ids.id,
                    'quantity': 1,
                    'cost': self.cost,
                    'tax_ids': [(6, 0, self.tax_ids.ids)],
                    'currency_id': self.currency_id.id,
                    'track_by_serial_number': True,
                    'visit': self.visit,
                })
        else:
            amc_contract_line_obj.create({
                'contract_id': self.contract_id.id,
                'product_id': self.product_id.id,
                'user_ids': self.user_ids.id,
                'quantity': self.quantity,
                'cost': self.cost,
                'tax_ids': [(6, 0, self.tax_ids.ids)],
                'currency_id': self.currency_id.id,
                'track_by_serial_number': False,
                'visit': self.visit,
            })

        return {'type': 'ir.actions.act_window_close'}
