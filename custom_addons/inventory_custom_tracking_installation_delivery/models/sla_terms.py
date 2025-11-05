from odoo import models, fields

class ContractType(models.Model):
    _name = 'sla.term'
    _description = 'SLA Terms'

    name = fields.Char(string='Name', required=True)
    note = fields.Html(sting="Note")
