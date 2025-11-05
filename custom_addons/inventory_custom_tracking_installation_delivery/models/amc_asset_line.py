from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AmcContractAssetLine(models.Model):
    _name = 'amc.contract.asset.line'
    _description = 'AMC Contract Asset Line'

    contract_id = fields.Many2one('amc.contract', string="Contract", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    quantity = fields.Float(string="Quantity", default=5.0)
    cost = fields.Monetary(string="Charge")
    tax_ids = fields.Many2many('account.tax', string="Taxes", widget="Tags", domain=[('type_tax_use', '=', 'sale')],
)
    available_serial_numbers = fields.Many2many(
        'stock.lot', compute='_compute_available_serial_numbers', store=False
    )
    serial_number_ids = fields.Many2one(
        'stock.lot',
        string="Serial Number",
        domain="[('product_id', '=', product_id)]"
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company,
        readonly=True
    )
    # serial_number = fields.Char(string="Serial Number")

    remark = fields.Char(string="Remark")
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id)
    subtotal = fields.Monetary(string="Tax Included", compute='_compute_subtotal', store=True)
    user_ids = fields.Many2one(comodel_name='res.users', string="Assignee")
    track_by_serial_number = fields.Boolean(string="Track By Serial Number", store=True)
    visit = fields.Integer(string="PM frequency(Month)")
    tax_excluded = fields.Monetary(
        string="Tax Excluded",
        compute="_compute_tax_excluded",
        store=True,
        currency_field='currency_id'
    )

    @api.depends('quantity', 'cost')
    def _compute_tax_excluded(self):
        for line in self:
            line.tax_excluded = line.cost * line.quantity

    @api.depends('product_id')
    def _compute_available_serial_numbers(self):
        for line in self:
            if line.product_id:
                # Adjust logic here to filter stock lots for the product
                line.available_serial_numbers = self.env['stock.lot'].search([
                    ('product_id', '=', line.product_id.id)
                ])
            else:
                line.available_serial_numbers = self.env['stock.lot']

    @api.depends('quantity', 'cost', 'tax_ids')
    def _compute_subtotal(self):
        for line in self:
            price = line.cost
            quantity = line.quantity
            taxes = line.tax_ids

            if taxes:
                taxes_result = taxes.compute_all(
                    price, currency=line.currency_id, quantity=quantity, product=line.product_id, partner=None
                )
                line.subtotal = taxes_result['total_included']
            else:
                line.subtotal = price * quantity

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.cost = line.product_id.standard_price

    @api.model
    def create(self, vals):
        self._check_serial_number_conflict(vals)
        return super().create(vals)

    def write(self, vals):
        for rec in self:
            rec._check_serial_number_conflict(vals)
        return super().write(vals)

    def _check_serial_number_conflict(self, vals):
        serial_id = vals.get('serial_number_ids') or self.serial_number_ids.id
        contract_id = vals.get('contract_id') or self.contract_id.id
        product_id = vals.get('product_id') or self.product_id.id

        if not serial_id:
            return  # No serial, nothing to check

        # === 1. Check same contract, same product, same serial ===
        domain_1 = [
            ('id', '!=', self.id),  # avoid current record in update
            ('contract_id', '=', contract_id),
            ('product_id', '=', product_id),
            ('serial_number_ids', '=', serial_id),
        ]
        if self.env['amc.contract.asset.line'].search_count(domain_1):
            raise ValidationError("This serial number is already used in the same contract for the same product.")

        # === 2. Check active contract using same serial ===
        domain_2 = [
            ('id', '!=', self.id),
            ('serial_number_ids', '=', serial_id),
            ('contract_id.stage_id', '=', 'active'),
        ]
        if self.env['amc.contract.asset.line'].search_count(domain_2):
            raise ValidationError(
                "This serial number is already in use in another active contract. Please use a different one.")



class AmcAttachmentLine(models.Model):
    _name = 'amc.attachment.line'
    _description = 'Attachment Line'

    name = fields.Char('Description', store=True, required=True)
    upload_file = fields.Binary(string='Upload Document', store=True)
    contract_id = fields.Many2one('amc.contract', string='Contract', ondelete='cascade')

    upload_file_filename = fields.Char('File Name')

    ir_attachment_id = fields.Many2one('ir.attachment', string="Chatter Attachment", copy=False)

    @api.model
    def create(self, vals):
        record = super().create(vals)
        record._create_ir_attachment()
        return record

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._create_ir_attachment()
        return res

    def unlink(self):
        if self.env.context.get('skip_attachment_unlink'):
            return super().unlink()
        for rec in self:
            if rec.ir_attachment_id:
                rec.ir_attachment_id.with_context(skip_amc_unlink=True).unlink()
        return super().unlink()

    def _create_ir_attachment(self):
        for rec in self:
            if rec.upload_file and rec.contract_id:
                existing = self.env['ir.attachment'].search([
                    ('id', '=', rec.ir_attachment_id.id)
                ], limit=1)

                filename = rec.upload_file_filename or rec.name or "Attachment"
                datas = rec.upload_file

                if existing:
                    # Use sudo to avoid permission issues, and only write if needed
                    if rec.ir_attachment_id != existing:
                        rec.sudo().write({'ir_attachment_id': existing.id})
                else:
                    attachment = self.env['ir.attachment'].create({
                        'name': filename,
                        'type': 'binary',
                        'datas': datas,
                        'res_model': 'amc.contract',
                        'res_id': rec.contract_id.id,
                        'mimetype': 'application/octet-stream',
                    })
                    rec.ir_attachment_id = attachment.id


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def unlink(self):
        if self.env.context.get('skip_amc_unlink'):
            return super().unlink()
        for attachment in self:
            lines = self.env['amc.attachment.line'].search([('ir_attachment_id', '=', attachment.id)])
            lines.with_context(skip_attachment_unlink=True).unlink()
        return super().unlink()
