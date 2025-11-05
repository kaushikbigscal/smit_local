from odoo import models, fields


class PaidLeaveConfig(models.Model):
    _name = 'paid.leave.config'
    _description = 'Paid Leave Configuration'

    name = fields.Char(string='Description', required=True)
    leave_type_id = fields.Many2one('hr.leave.type', string='Leave Type', required=True)
    start_calculation_date = fields.Selection([
        ('join_date', 'Joining Date'),
        # ('contract_start_date', 'Contract Start Date')
    ], string="Start Calculation From", default='join_date', required=True)

    active = fields.Boolean(string="Active", default=True)

    # Create a One2many field to dynamically add leave credit levels
    leave_credit_lines = fields.One2many(
        'paid.leave.config.line', 'config_id', string="Leave Credit Levels"
    )



class PaidLeaveConfigLine(models.Model):
    _name = 'paid.leave.config.line'
    _description = 'Leave Credit Level Configuration Line'

    config_id = fields.Many2one('paid.leave.config', string="Configuration", required=True)
    min_years = fields.Float(string="Min Years", required=True)
    max_years = fields.Float(string="Max Years", required=True)
    leave_credit = fields.Float(string="Leave Credit", required=True)
