from odoo import models, fields


class CRMLead(models.Model):
    _inherit = 'crm.lead'

    project_template_name = fields.Many2one('project.project', string="Project Template Name",
                                            domain=[('is_project_template', '=', True)])  # Link to Project
