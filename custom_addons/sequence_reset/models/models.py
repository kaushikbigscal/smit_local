from odoo import models, fields, api
from datetime import datetime, date, timedelta


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    reset_sequence = fields.Selection([
        ('none', 'None'),
        ('Month', 'Monthly'),
        ('Year', 'Yearly'),
    ], string="Sequence Reset", default='none')

    def reset_sequence_number(self):
        today = datetime.now()
        tomorrow = today + timedelta(days=1)

        sequences = self.search([])
        for seq in sequences:
            if seq.reset_sequence == 'Month' and tomorrow.month != today.month:
                seq.sudo().write({'number_next_actual': 1})
            elif seq.reset_sequence == 'Year' and tomorrow.year != today.year:
                seq.sudo().write({'number_next_actual': 1})
            elif seq.reset_sequence == 'none':
                continue
