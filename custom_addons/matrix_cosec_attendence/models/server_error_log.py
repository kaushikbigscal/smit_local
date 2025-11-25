from odoo import models, fields

class MatrixApiErrorLog(models.Model):
    _name = 'matrix.server.error.log'
    _description = 'Matrix Server Error Log'
    _order = 'event_datetime desc'
    _inherit = ['mail.thread']

    reason = fields.Text(string='Reason for Skipping', tracking=True)
    event_datetime = fields.Datetime(string='Datetime', tracking=True)
    api_status_code = fields.Integer(string="API Status Code", tracking=True)
