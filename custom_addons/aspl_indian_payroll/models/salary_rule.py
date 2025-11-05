# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    taxable = fields.Boolean(string="Taxable")
    appear_on_contract = fields.Boolean(string="Appear on Contract")
    is_tax = fields.Boolean(string="Is a Tax")
    is_deduction = fields.Boolean(string="Is a Deduction")
