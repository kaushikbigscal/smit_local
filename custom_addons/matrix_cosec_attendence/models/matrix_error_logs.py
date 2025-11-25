from odoo import models, fields, api
from odoo.exceptions import UserError


class MatrixAttendanceLog(models.Model):
    _name = 'matrix.attendance.log'
    _description = 'Matrix Attendance Log'
    _order = 'log_date desc'
    _rec_name = 'biometric_id'
    _inherit = ['mail.thread']

    employee_id = fields.Many2one('hr.employee', string='Employee', tracking=True)
    biometric_id = fields.Char(string='Biometric ID', tracking=True)
    event_datetime = fields.Datetime(string='DateTime', tracking=True)
    entry_exit_type = fields.Selection([
        ('0', 'Check-In'),
        ('1', 'Check-Out')
    ], string='Entry/Exit Type')
    reason = fields.Text(string='Reason for Skipping', tracking=True)
    log_date = fields.Datetime(string='Log DateTime', default=fields.Datetime.now, tracking=True)
    username = fields.Char(string="Biometric Name", tracking=True)

    def action_create_attendance(self, *args):
        for record in self:
            # Create the context with default values for the attendance form
            context = {
                'default_employee_id': record.employee_id.id,
                'default_check_in': record.event_datetime if record.entry_exit_type == '0' else False,
                'default_check_out': record.event_datetime if record.entry_exit_type == '1' else False,
            }
            # Open the hr.attendance form with pre-filled data
            return {
                'type': 'ir.actions.act_window',
                'name': 'Create Attendance',
                'res_model': 'hr.attendance',
                'view_mode': 'form',
                'target': 'new',
                'context': context
            }
