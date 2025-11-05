from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    Minimum_Duration_end_work = fields.Float(
        string="Minimum Duration for stop work",
        config_parameter="tour_plan.Minimum_Duration_end_work",
        help="Set the minimum Duration for for the stop work in Tour Plan."
    )
