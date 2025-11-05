from odoo import models, fields


class PendingReason(models.Model):
    _name = 'pending.reason'
    _description = 'Pending Reason'

    name = fields.Char(string='Pending Reason', required=True)


class ActualReason(models.Model):
    _name = 'actual.problem'
    _description = 'Actual Problem'

    name = fields.Char(string='Actual Problem', required=True)