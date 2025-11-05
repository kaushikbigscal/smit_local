from odoo import models, fields,api
import io
import base64
from datetime import datetime
import xlsxwriter

from odoo.exceptions import UserError


class CallReport(models.Model):
    _name = 'call.report'
    _rec_name = 'custom_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    dates = fields.Date(string="Month", default=fields.Date.context_today)

    custom_name = fields.Char(string="Month-Year", compute="_compute_custom_name", store=True)

    @api.depends('dates')
    def _compute_custom_name(self):
        for rec in self:
            if rec.dates:
                rec.custom_name = rec.dates.strftime('%m/%Y')
            else:
                rec.custom_name = " "
                
    def generate_excel_report(self):
        if not self.dates:
            raise UserError("Please select a month before generating the report.")
      
        selected_month = self.dates.strftime('%m/%Y')
        return {
            'type': 'ir.actions.act_url',
            'url': '/download/excel_report?month=%s' % selected_month,
            'target': 'self',
        }
