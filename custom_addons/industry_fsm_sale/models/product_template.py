# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    project_id = fields.Many2one(
        domain="['|', ('company_id', '=', False), '&', ('company_id', '=?', company_id), ('company_id', '=', current_company_id), ('allow_billable', '=', True), '|', ('pricing_type', '=', 'task_rate'), ('is_fsm', '=', True), ('allow_timesheets', 'in', [service_policy == 'delivered_timesheet', True])]")

    # custom code for warranty -----------------------------------------------------------------

    minimum_warranty_period = fields.Integer(string="Warranty Period")
    is_warranty = fields.Boolean(string="Warranty", required=True)
    part_ids = fields.One2many('product.part_data', 'product_tmpl_data_id', string="Parts")
    service_charge = fields.Integer(string='Service Charge')
    external_service_charge = fields.Float(string='External Service Charge')

    is_part = fields.Boolean(string="Is Part", help="Indicates if the product has parts.", default=False)

    # num_of_field_service = fields.Integer(string="Number of Call")
    # filed_service_task = fields.Integer(string="Number of Months",
    #                                     help="Number of months after which a call should be created."
    #                                     )
    number_of_call = fields.Integer(string="Number of Calls")
    number_of_month = fields.Integer(string="Number of Months",
                                     help="Number of months after which a call should be created.")

    @api.onchange('is_warranty')
    def _onchange_minimum_warranty_period(self):
        for rec in self:
            if rec.is_warranty == False:
                rec.minimum_warranty_period = 0
            else:
                rec.minimum_warranty_period = self.minimum_warranty_period


# custom_product_part.py


class ProductPart(models.Model):
    _name = 'product.part_data'
    _description = 'Product Part'

    product_tmpl_data_id = fields.Many2one('product.template', string="Product Template", required=True,
                                           ondelete='cascade')

    display_name = fields.Many2one('product.template', string="Parts Name")
    minimum_warranty_period = fields.Integer(related='display_name.minimum_warranty_period', string="Warranty Period")
    description = fields.Text(string="Description")

    number_of_call = fields.Integer(related='display_name.number_of_call', string="Number of Calls")
    number_of_month = fields.Integer(related='display_name.number_of_month',
                                     string="Number of Months")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_display_name'):
            product = self.env['product.template'].browse(self.env.context['default_display_name'])
            if not product.is_part:
                raise UserError("This product is not marked as a part.")
        return res

    # tracking = fields.Selection([
    #     ('serial', 'By Unique Serial Number'),
    #     ('lot', 'By Lots'),
    #     ('none', 'No Tracking')
    # ], string="Tracking", required=True, default='none')
    #
    # # Make display_name product trackable by default
    # @api.onchange('display_name')
    # def _onchange_display_name(self):
    #     if self.display_name.product_id.tracking:
    #         return self.display_name.write({
    #             'tracking': self.display_name.product_id.tracking
    #         })
    #     else:
    #         return self.display_name.write({
    #             'tracking': 'none'
    #         })
