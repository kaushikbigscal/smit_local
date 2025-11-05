# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import api, models, fields, _
from odoo.tools import float_is_zero
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = ['sale.order']

    task_id = fields.Many2one('project.task', string="Task", help="Task from which this quotation have been created")

    @api.model_create_multi
    def create(self, vals):
        orders = super().create(vals)
        for sale_order in orders:
            if sale_order.task_id:
                message = _("Extra Quotation Created: %s", sale_order._get_html_link())
                sale_order.task_id.message_post(body=message)
        return orders

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        if self.env.context.get('fsm_no_message_post'):
            return False
        return super().message_post(**kwargs)

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        self.action_auto_call_creation()
        for sale_order in self:
            if sale_order.task_id:
                message = _("This Sales Order has been created from Task: %s", sale_order.task_id._get_html_link())
                sale_order.message_post(body=message)

        return res

    def _get_product_catalog_record_lines(self, product_ids):
        """
            Accessing the catalog from the smart button of a "field service" should compute
            the content of the catalog related to that field service rather than the content
            of the catalog related to the sale order containing that "field service".
        """
        task_id = self.env.context.get('fsm_task_id')
        if task_id:
            grouped_lines = defaultdict(lambda: self.env['sale.order.line'])
            for line in self.order_line:
                if line.task_id.id == task_id and line.product_id.id in product_ids:
                    grouped_lines[line.product_id] |= line
            return grouped_lines
        return super()._get_product_catalog_record_lines(product_ids)

    # warranty dates custom ---------------------------
    order_parts_ids = fields.One2many('sale.order.parts', 'sale_order_id', string='Parts List')

    warranty_start_date = fields.Date(
        string='Warranty Start Date',
        default=fields.Date.context_today,
        required=True
    )

    warranty_end_date = fields.Date(
        string='Warranty End Date',
        compute='_compute_warranty_end_date',
        store=True
    )

    @api.depends('warranty_start_date', 'order_line.warranty_period')
    def _compute_warranty_end_date(self):
        for order in self:
            max_warranty_months = max(order.order_line.mapped('warranty_period') or [0])
            if order.warranty_start_date and max_warranty_months:
                order.warranty_end_date = order.warranty_start_date + relativedelta(months=max_warranty_months)
            else:
                order.warranty_end_date = False

    def _prepare_invoice(self):
        """Inherit to add warranty information when creating invoice"""
        invoice_vals = super()._prepare_invoice()
        invoice_vals.update({
            'warranty_start_date': self.warranty_start_date,
        })
        return invoice_vals

    def action_auto_call_creation(self):
        for order in self:
            print(f"Order state: {order.state}")
            if order.state == 'sale':
                for line in order.order_line:
                    if line.number_of_month and line.number_of_call:
                        if line.number_of_month > 0:
                            next_task_date = order.warranty_start_date + relativedelta(
                                months=line.number_of_month)
                        else:
                            next_task_date = False
                        line.next_call_date = next_task_date
                        line.call_counter = line.number_of_call
                        print(f"Setting next task date to {next_task_date} for line {line.id}")

    # warranty dates custom ---------------------------


class SaleOrderLine(models.Model):
    _inherit = ['sale.order.line']

    delivered_price_subtotal = fields.Monetary(compute='_compute_delivered_amount', string='Delivered Subtotal')
    delivered_price_tax = fields.Float(compute='_compute_delivered_amount', string='Delivered Total Tax')
    delivered_price_total = fields.Monetary(compute='_compute_delivered_amount', string='Delivered Total')

    @api.depends('qty_delivered', 'discount', 'price_unit', 'tax_id')
    def _compute_delivered_amount(self):
        """
        Compute the amounts of the SO line for delivered quantity.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.qty_delivered,
                                            product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.delivered_price_tax = sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
            line.delivered_price_total = taxes['total_included']
            line.delivered_price_subtotal = taxes['total_excluded']

    def _timesheet_create_task_prepare_values(self, project):
        res = super(SaleOrderLine, self)._timesheet_create_task_prepare_values(project)
        if project.is_fsm:
            res.update({'partner_id': self.order_id.partner_shipping_id.id})
        return res

    def _timesheet_create_project_prepare_values(self):
        """Generate project values"""
        values = super(SaleOrderLine, self)._timesheet_create_project_prepare_values()
        if self.product_id.project_template_id.is_fsm:
            values.pop('sale_line_id', False)
        return values

    def _compute_invoice_status(self):
        sol_from_task_without_amount = self.filtered(
            lambda sol: sol.task_id.is_fsm and float_is_zero(sol.price_unit, precision_digits=sol.currency_id.rounding))
        sol_from_task_without_amount.invoice_status = 'no'
        super(SaleOrderLine, self - sol_from_task_without_amount)._compute_invoice_status()

    @api.depends('price_unit')
    def _compute_qty_to_invoice(self):
        sol_from_task_without_amount = self.filtered(
            lambda sol: sol.task_id.is_fsm and float_is_zero(sol.price_unit, precision_digits=sol.currency_id.rounding))
        sol_from_task_without_amount.qty_to_invoice = 0.0
        super(SaleOrderLine, self - sol_from_task_without_amount)._compute_qty_to_invoice()

    def action_add_from_catalog(self):
        if len(self.task_id) == 1 and self.task_id.allow_material:
            return self.task_id.action_fsm_view_material()
        return super().action_add_from_catalog()

    # custom code for warranty -----------------------------------------------------------------

    warranty_period = fields.Integer(
        string="Warranty Period",
        help="Warranty period in months for this product"
    )

    line_warranty_end_date = fields.Date(
        string='Warranty End Date',
        compute='_compute_line_warranty_end_date',
        store=True
    )

    @api.onchange('product_id')
    def _onchange_product_id_warranty(self):
        if self.product_id:
            # Access product template through product.product relation
            product_tmpl = self.product_id.product_tmpl_id
            if not self.warranty_period and product_tmpl:
                self.warranty_period = product_tmpl.minimum_warranty_period

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('product_id') and not vals.get('warranty_period'):
                product = self.env['product.product'].browse(vals['product_id'])
                if product and product.product_tmpl_id:
                    vals['warranty_period'] = product.product_tmpl_id.minimum_warranty_period
        return super().create(vals_list)

    @api.depends('order_id.warranty_start_date', 'warranty_period')
    def _compute_line_warranty_end_date(self):
        for line in self:
            if line.order_id.warranty_start_date and line.warranty_period:
                line.line_warranty_end_date = line.order_id.warranty_start_date + relativedelta(
                    months=line.warranty_period)
            else:
                line.line_warranty_end_date = False

    def _prepare_invoice_line(self, **optional_values):
        """Inherit to add warranty information when creating invoice lines"""
        res = super()._prepare_invoice_line(**optional_values)
        res.update({
            'warranty_period': self.warranty_period,
        })
        return res

        # custom code for warranty -----------------------------------------------------------------

    # Computed field to fetch the part list
    def _prepare_parts_data(self):
        self.ensure_one()
        parts_commands = []
        product_tmpl = self.product_id.product_tmpl_id

        if product_tmpl.part_ids:
            for part in product_tmpl.part_ids:
                parts_commands.append((0, 0, {
                    'sale_order_id': self.order_id.id,
                    'product_id': product_tmpl.id,
                    'part_data_id': part.id,
                    'quantity': int(self.product_uom_qty or 1)
                }))
        return parts_commands

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.product_id and line.product_id.part_ids:
                parts_commands = line._prepare_parts_data()
                if parts_commands:
                    line.order_id.write({'order_parts_ids': parts_commands})
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'product_id' in vals or 'product_uom_qty' in vals:
            for line in self:
                # Delete existing parts for this product
                existing_parts = self.env['sale.order.parts'].search([
                    ('sale_order_id', '=', line.order_id.id),
                    ('product_id', '=', line.product_id.product_tmpl_id.id)
                ])
                if existing_parts:
                    existing_parts.unlink()

                # Create new parts
                if line.product_id and line.product_id.part_ids:
                    parts_commands = line._prepare_parts_data()
                    if parts_commands:
                        line.order_id.write({'order_parts_ids': parts_commands})
        return res

    # custom code for unit status and service count----------------------

    # unit_status = fields.Selection([
    #     ('warranty', 'Warranty'),
    #     ('amc', 'AMC'),
    #     ('chargeable', 'Chargeable'),
    #     ('free', 'Free'),
    #     ('project', 'Project')], string="Unit Status", store=True, required=True)
    unit_status = fields.Selection(selection=lambda self: self.env['call.type'].get_unit_status_selection(),
                                   string="Unit Status", store=True, required=True)

    number_of_call = fields.Integer(
        string="Number of Calls"
    )
    number_of_month = fields.Integer(string="Number of Months",
                                     help="Number of months after which a call should be created.")

    @api.onchange('product_id', 'unit_status')
    def _onchange_product_id_service_record(self):
        if self.product_id:
            product_tmpl = self.product_id.product_tmpl_id
            if product_tmpl:
                if self.unit_status in ['warranty', 'amc']:
                    # Keep the values from the product template
                    self.number_of_call = product_tmpl.number_of_call
                    self.number_of_month = product_tmpl.number_of_month
                else:
                    # Reset the fields to zero for other statuses
                    self.number_of_call = 0
                    self.number_of_month = 0

    # @api.onchange('product_id')
    # def _onchange_product_id_service_record(self):
    #     if self.product_id:
    #         # Access product template through product.product relation
    #         product_tmpl = self.product_id.product_tmpl_id
    #         if not self.number_of_call and product_tmpl:
    #             self.number_of_call = product_tmpl.number_of_call

    next_call_date = fields.Date(string="Next Date")
    call_counter = fields.Integer(string="Task Count")

    # @api.model
    # def _create_field_service_tasks(self):
    #     today = fields.Date.context_today(self)
    #     sale_order_lines = self.search([
    #         ('order_id.state', '=', 'sale'),
    #         ('call_counter', '>', 0),
    #         ('next_call_date', '=', today),
    #     ])
    #     print(sale_order_lines)
    #     for line in sale_order_lines:
    #         task_vals = {
    #             'name': f"Service call for {line.order_id.name} - {line.product_id.display_name}",
    #             'project_id': 33,
    #             'partner_id': line.order_id.partner_id.id
    #         }
    #         self.env['project.task'].create(task_vals)
    #         print("task done")
    #         line.call_counter = line.call_counter - 1
    #
    #         print(line.call_counter)
    #         if line.number_of_month:
    #             line.next_call_date = today + relativedelta(months=line.number_of_month)
    #             print(line.next_call_date)
    #
    #     return True
    @api.model
    def _create_field_service_tasks(self):
        today = fields.Date.context_today(self)

        # Search sale order lines that meet the condition
        sale_order_lines = self.search([
            ('order_id.state', '=', 'sale'),
            ('call_counter', '>', 0),
            ('next_call_date', '=', today),
        ])

        print(sale_order_lines)

        for line in sale_order_lines:
            # Dynamically find the project based on the current company and is_fsm=True
            project = self.env['project.project'].search([
                ('company_id', '=', self.env.company.id),
                ('is_fsm', '=', True)
            ], limit=1)  # Assuming only one project with is_fsm=True per company

            if not project:
                print("No FSM project found for the current company")
                continue  # Skip this iteration if no project is found

            task_vals = {
                'name': f"Service call for {line.order_id.name} - {line.product_id.display_name}",
                'project_id': project.id,
                'partner_id': line.order_id.partner_id.id
            }
            # Create a new task for each sale order line
            self.env['project.task'].create(task_vals)
            print("task done")

            # Decrease the call counter
            line.call_counter = line.call_counter - 1
            print(line.call_counter)

            # Update the next call date if applicable
            if line.number_of_month:
                line.next_call_date = today + relativedelta(months=line.number_of_month)
                print(line.next_call_date)

        return True


class SaleOrderParts(models.Model):
    _name = 'sale.order.parts'
    _description = 'Sale Order Parts'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.template', string='Main Product', required=True)
    part_data_id = fields.Many2one('product.part_data', string='Part', required=True)
    part_name = fields.Char(related='part_data_id.display_name.name', string='Part Name', store=True, readonly=True)
    quantity = fields.Integer(string='Quantity', default=1)
    minimum_warranty_period = fields.Integer(related='part_data_id.minimum_warranty_period', readonly=True)
    description = fields.Text(related='part_data_id.description')
