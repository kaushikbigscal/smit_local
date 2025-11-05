from odoo import models, fields

class DataRecycleErrorWizard(models.TransientModel):
    _name = 'data.recycle.error.wizard'
    _description = 'Data Recycle Error Log Wizard'

    error_log = fields.Text('Error Log')
    title = fields.Char('Title', default='Error Log')