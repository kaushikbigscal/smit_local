from odoo import models, fields, api
from dateutil.relativedelta import relativedelta

# all code in this file is custom code--------------------------------

class AccountMove(models.Model):
    _inherit = 'account.move'

    warranty_start_date = fields.Date(
        string='Warranty Start Date',
        copy=True
    )

    warranty_end_date = fields.Date(
        string='Warranty End Date',
        compute='_compute_warranty_end_date',
        store=True
    )

    @api.depends('warranty_start_date', 'invoice_line_ids.warranty_period')
    def _compute_warranty_end_date(self):
        for move in self:
            max_warranty_months = max(move.invoice_line_ids.mapped('warranty_period') or [0])
            if move.warranty_start_date and max_warranty_months:
                move.warranty_end_date = move.warranty_start_date + relativedelta(months=max_warranty_months)
            else:
                move.warranty_end_date = False

    @api.model
    def create(self, vals):
        # Create the move
        move = super().create(vals)

        # If this is an invoice created from a sale order, copy warranty information
        if move.move_type in ('out_invoice', 'out_refund') and move.invoice_origin:
            sale_orders = self.env['sale.order'].search([('name', '=', move.invoice_origin)])
            if sale_orders:
                move.warranty_start_date = sale_orders[0].warranty_start_date

        return move


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    warranty_period = fields.Integer(
        string='Warranty Period',
        copy=True
    )

    line_warranty_end_date = fields.Date(
        string='Warranty End Date',
        compute='_compute_line_warranty_end_date',
        store=True
    )

    @api.depends('move_id.warranty_start_date', 'warranty_period')
    def _compute_line_warranty_end_date(self):
        for line in self:
            if line.move_id.warranty_start_date and line.warranty_period:
                line.line_warranty_end_date = line.move_id.warranty_start_date + relativedelta(
                    months=line.warranty_period)
            else:
                line.line_warranty_end_date = False

    def _prepare_invoice_line(self, **optional_values):
        """Inherit to add warranty information to invoice lines"""
        vals = super()._prepare_invoice_line(**optional_values)

        # If the line comes from a sale order line, copy the warranty period
        if self.sale_line_ids:
            sale_line = self.sale_line_ids[0]
            vals['warranty_period'] = sale_line.warranty_period

        return vals

