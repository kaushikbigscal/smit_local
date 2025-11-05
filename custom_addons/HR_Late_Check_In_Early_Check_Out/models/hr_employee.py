
from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    late_check_in_count = fields.Integer(
        string='Late Day-ins',
        store=True,
        help='Number of late day-ins in current month'
    )
    early_check_out_count = fields.Integer(
        string='Early Day-outs',
        store=True,
        help='Number of early day-outs in current month'
    )