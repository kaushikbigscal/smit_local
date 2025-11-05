from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    day_in_reminder_enabled = fields.Boolean(string="Enable Day In Reminder")
    day_out_reminder_enabled = fields.Boolean(string="Enable Day Out Reminder")
    auto_day_out = fields.Boolean(string="Auto Day Out")
