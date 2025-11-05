# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Student(models.Model):
    _name = 'wb.student'
    _description = 'this is student profile.'


    name = fields.Char("Name")
    roll_no = fields.Integer()
    address = fields.Char("Address")

    country_id = fields.Many2one('res.country', string='Country', required=True)
    state_id = fields.Many2one('res.country.state', string='State', domain="[('country_id', '=', country_id)]")

    def write(self, vals):
        print(vals)
        return super(Student,self).write(vals)

    @api.onchange('country_id')
    def _onchange_country_id(self):
        if self.country_id:
            return {'domain': {'state_id': [('country_id', '=', self.country_id.id)]}}
        else:
            return {'domain': {'state_id': []}}

class school(models.Model):
    _name = 'wb.school'

    name = fields.Char("school Name")


    # name2 = fields.Char("Name2")
    # name3 = fields.Char("Name3")
    # name4 = fields.Char("Custom Field")
    # roll_no = fields.Integer()
    # std_fees = fields.Float(string="student_fees", digits=(4,1))
    # is_paid = fields.Boolean(string="Paid?", help="this is for student who not pay fees")
    # address_html = fields.Html("address_html")
    # gender = fields.Selection(required=1,selection=[('male', 'Male'), ('female', 'Female')])
    # advance_gender = fields.Selection("get_advance_gender")
    # school_data = fields.Json()
    # join_date = fields.Date()
    #
    # def create(self, vals_list):
    #     print(vals_list)
    #     ret = super(Student,self).create(vals_list)
    #     print(ret)
    #     return ret
    #
    # def get_advance_gender(self):
    #     return ([('male', 'Male'),
    #             ('female', 'Female')])
    #
    # def json_school_data(self):
    #     self.school_data = {"name": self.name, "id": self.ids, "fees": self.std_fees}