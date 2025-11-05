from odoo import models, fields, api

class SundayAttendance(models.Model):
    _name = 'hr.sunday.attendance'
    _description = 'Sunday Attendance Records'
    _inherit = ['mail.thread']

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    check_in = fields.Datetime(string='Check In')
    check_out = fields.Datetime(string='Check Out')
    state = fields.Selection([
        ('validate', 'Validate'),
        ('draft', 'Draft'),
        ('refused', 'Refused')
    ], string='Status', default='draft', tracking=True, required=True)

    work_hours = fields.Float(string='Work Hours', store=True)
    counter = fields.Float(string='counter', store=True)

    def action_validate(self):
        for attendance in self:
            attendance.write({'state': 'validate'})
            if attendance.employee_id:
                attendance.employee_id.worked_sundays_count += attendance.counter

    def action_refuse(self):
        for attendance in self:
            attendance.write({'state': 'refused'})
