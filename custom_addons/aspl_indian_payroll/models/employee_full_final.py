# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from num2words import num2words

from odoo import models, fields, api


class EmployeeFullFinal(models.Model):
    _name = 'employee.full.final'
    _description = 'Employee Full Final'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee')
    separation_mode = fields.Selection(related='employee_id.separation_mode', string="Separation Mode")
    resign_date = fields.Date(related='employee_id.resignation_date', string="Resign Date")
    last_date = fields.Date(related='employee_id.tentative_leaving_date', string="Last Date")
    company_id = fields.Many2one(related='employee_id.company_id', string="Company")
    notice_period = fields.Integer(related='employee_id.resigned_notice_period', string="Notice Period")
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], 'Status', readonly=True, default='draft')
    payslip_line_ids = fields.One2many('hr.payslip', 'full_final_emp_payslip_id', string='Payslip Lines')

    @api.model
    def create(self, vals):
        full_final_emp_obj = super(EmployeeFullFinal, self).create(vals)

        # Creating Payslips In Full & Final Employee
        full_final_emp_payslips = self.env['hr.payslip'].sudo().search(
            [('employee_id', '=', vals['employee_id']), ('date_from', '>=', full_final_emp_obj.resign_date)])
        full_final_emp_obj.payslip_line_ids = [(6, 0, full_final_emp_payslips.ids)]

        return full_final_emp_obj

    def _number_to_words(self, number):
        words = num2words(round(number))
        words = words[0].capitalize() + words[1:]

        return f'(Rupees {words} Only)'

    def _payslip_obj(self):
        last_drawn_salary_slip = self.env['hr.payslip'].sudo().search(
            [('employee_id', '=', self.employee_id.id), ('date_from', '>=', self.resign_date)], limit=1,
            order='id desc')

        return last_drawn_salary_slip

    def action_done(self):
        self.state = 'done'

    def action_draft(self):
        self.state = 'draft'
