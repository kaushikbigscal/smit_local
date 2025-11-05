# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields


class AttendanceShortfall(models.TransientModel):
    _name = 'hr.attendance.shortfall'
    _description = 'Hr Attendance Shortfall'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee')
    working_hours = fields.Float("Working Hours")
    actual_hours = fields.Float("Actual Hours")
    shortfall = fields.Float("Short Fall")
    checkbox = fields.Boolean("Checkbox")
    shortfall_days = fields.Float("Short Fall Days")
    date_start = fields.Date()
    date_end = fields.Date()
